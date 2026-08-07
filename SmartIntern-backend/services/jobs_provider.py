"""jobs_provider.py — Live job feed providers (7-source engine).

Provider priority order (highest → lowest for dedup tie-breaking):
  1. ArbeitnowProvider   — https://www.arbeitnow.com/api/job-board-api (no auth, 3h cache).
                           Native ATS links (Greenhouse/Lever/SmartRecruiters). TOP PRIORITY.
  2. AdzunaProvider      — ADZUNA_APP_ID/ADZUNA_APP_KEY, maps redirect_url → application_url.
                           ~1,000 calls/month free tier; 8h cache.
  3. RemotiveProvider    — https://remotive.com/api/remote-jobs (no auth, 6h cache).
                           Always "remote" work_mode. Remotive attribution required on cards.
  4. JSearchProvider     — RapidAPI JSearch (RAPIDAPI_KEY, ~23h rate-limit guard, ~200 req/month).
  5. HimalayasProvider   — https://himalayas.app/jobs/api (no auth, 3h cache).
                           ⚠️  Free API only exposes himalayas.app internal URLs in
                           applicationLink — these are NOT direct ATS links and are
                           discarded by _get_direct_apply_url. Yields 0 until API exposes
                           direct employer links.
  6. JoobleProvider      — POST https://jooble.org/api/{JOOBLE_API_KEY}.
                           ~500 req/day rate limit.
  7. CareerOneStopProvider — https://api.careeronestop.org (CAREERONESTOP_USER_ID + TOKEN).
                             US-only data; low yield for India searches.
  8. MockJobsProvider    — local fixtures, fallback only when ALL live sources return 0 jobs.

Source tags written to Job.source:
  "arbeitnow" | "adzuna" | "remotive" | "jsearch" | "himalayas" | "jooble"
  | "careeronestop" | "mock" | "manual"

Work mode:
  Arbeitnow → "remote" if boolean remote==True, else inferred from text
  Adzuna    → "remote" if title/description contains "remote", else "onsite"
  Remotive  → always "remote"
  JSearch   → "remote" if job_is_remote else "onsite"
  Himalayas → always "remote" (remote-only board)
  Jooble    → inferred from title/description/location text
  Mock      → inferred from location string

Direct-link rule (HARD DISCARD):
  Every job MUST have a real application URL starting with http:// or https://
  that does NOT point to an internal job-board page (e.g. himalayas.app own pages).
  Jobs failing this check are discarded at fetch time — they are never stored in
  MongoDB and never shown in the app. No Google-search fallback is generated.
"""
import os
import re
import httpx
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
while current_dir != os.path.dirname(current_dir):
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break
    current_dir = os.path.dirname(current_dir)

# Assuming models are in api.models (adjust import if needed)
from api.models import Job

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# URL validation helpers
# ─────────────────────────────────────────────────────────────────────────────

_URL_RE = re.compile(r'^https?://', re.IGNORECASE)

def _is_real_url(url: Optional[str]) -> bool:
    """Return True only if url is a non-empty string starting with http:// or https://."""
    if not url or not isinstance(url, str):
        return False
    stripped = url.strip()
    return bool(_URL_RE.match(stripped)) and len(stripped) > 10


# Internal job-board URL prefixes that are NOT direct employer ATS links.
# Jobs with application URLs matching any of these are discarded.
_INTERNAL_BOARD_URL_PREFIXES = (
    "https://himalayas.app",
    "http://himalayas.app",
)


def _is_direct_employer_url(url: str) -> bool:
    """Return True only if the URL is a real URL AND is not an internal job-board page."""
    if not _is_real_url(url):
        return False
    for prefix in _INTERNAL_BOARD_URL_PREFIXES:
        if url.lower().startswith(prefix.lower()):
            return False
    return True


def _get_direct_apply_url(raw: dict, source: str) -> Optional[str]:
    """
    Extract a REAL direct application URL from a raw job dict.

    Source-specific field mapping (confirmed via live API testing 2026-07-31):
      Arbeitnow    → url          (direct ATS link — Greenhouse/Lever/etc.) ✅
      Adzuna       → redirect_url (direct employer redirect) ✅
      Remotive     → url          (direct employer link) ✅
      JSearch      → job_apply_link, falling back to apply_options[0].apply_link
      Himalayas    → applicationLink ⚠️ returns himalayas.app internal pages;
                     filtered by _is_direct_employer_url → yields None → job discarded
      Jooble       → link         (direct job link, confirmed from Jooble API docs)
      CareerOneStop → JobURL      (from CareerOneStop API v1 response schema)

    Returns the URL string if valid and direct, else None.
    Jobs returning None MUST be discarded — do not store them in MongoDB.

    NOTE: No Google-search fallback is generated here. A missing link means
    the job is silently dropped, never stored, never shown.
    """
    candidate = ""
    if source == "adzuna":
        candidate = raw.get("redirect_url") or ""
    elif source == "remotive":
        candidate = raw.get("url") or ""
    elif source == "jsearch":
        candidate = raw.get("job_apply_link") or ""
        if not candidate:
            options = raw.get("apply_options") or []
            if options and isinstance(options, list):
                first = options[0]
                candidate = first.get("apply_link") or ""
    elif source == "arbeitnow":
        candidate = raw.get("url") or ""
    elif source == "himalayas":
        candidate = raw.get("applicationLink") or ""
    elif source == "jooble":
        candidate = raw.get("link") or ""
    elif source == "careeronestop":
        candidate = raw.get("JobURL") or ""

    stripped = candidate.strip() if candidate else ""
    # Use _is_direct_employer_url which checks both valid URL format AND
    # that it does not point to an internal job-board page (e.g. himalayas.app)
    return stripped if _is_direct_employer_url(stripped) else None


def _infer_work_mode_from_text(*texts: str) -> str:
    """Infer work_mode from title/description strings. Defaults to 'onsite'."""
    combined = " ".join(t.lower() for t in texts if t)
    if "remote" in combined:
        return "remote"
    if "hybrid" in combined:
        return "hybrid"
    return "onsite"


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────────────────────

class JobsProvider(ABC):
    """Interface for job data providers."""
    @abstractmethod
    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# AdzunaProvider — PRIMARY source
# ─────────────────────────────────────────────────────────────────────────────

class AdzunaProvider(JobsProvider):
    """
    Calls the Adzuna Jobs API.
    Auth: ADZUNA_APP_ID + ADZUNA_APP_KEY (required).
    Country: 'in' (India) — covers local/onsite + remote Indian tech roles.
    Cache TTL: 8 hours (~3 fetches/day = ~90 API calls/month, well within 1k free tier).

    Only jobs with a real redirect_url are stored. Jobs with missing/empty
    redirect_url are discarded before returning from fetch_jobs.

    source = "adzuna"
    work_mode: "remote" if title/description contains 'remote', else "onsite"
    """
    TTL_SECONDS = 8 * 3600          # 8 hours
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"
    COUNTRY = "in"                   # India
    DEFAULT_QUERIES = [
        "software intern",
        "developer intern",
        "engineer intern",
    ]

    def __init__(self):
        self._cache: List[Job] = []
        self._cache_ts: float = 0.0

    @property
    def app_id(self) -> str:
        return os.getenv("ADZUNA_APP_ID", "").strip()

    @property
    def app_key(self) -> str:
        return os.getenv("ADZUNA_APP_KEY", "").strip()

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        import time
        if not self.app_id or not self.app_key:
            logger.warning("AdzunaProvider: ADZUNA_APP_ID or ADZUNA_APP_KEY not set — skipping.")
            return []

        now_ts = time.time()
        if self._cache and (now_ts - self._cache_ts) < self.TTL_SECONDS:
            logger.info(f"AdzunaProvider: serving {len(self._cache)} jobs from cache (TTL ok)")
            jobs = self._cache
        else:
            jobs = await self._fetch_fresh()
            self._cache = jobs
            self._cache_ts = now_ts

        # Filter by query/location if provided
        if query:
            q = query.lower()
            jobs = [
                j for j in jobs
                if q in j.title.lower()
                or q in j.company.lower()
                or any(q in s.lower() for s in j.required_skills)
            ]
        if location:
            loc_lower = location.lower()
            if loc_lower not in ("india", "in"):
                jobs = [j for j in jobs if loc_lower in j.location.lower()]

        return jobs[:limit]

    async def _fetch_fresh(self) -> List[Job]:
        jobs: List[Job] = []
        seen_ids: set = set()
        fetched = 0
        discarded = 0

        for q in self.DEFAULT_QUERIES:
            page_jobs, page_fetched, page_discarded = await self._fetch_query(q)
            for job in page_jobs:
                if job.external_id not in seen_ids:
                    seen_ids.add(job.external_id)
                    jobs.append(job)
            fetched += page_fetched
            discarded += page_discarded

        logger.info(
            f"AdzunaProvider: fetched {fetched} raw, "
            f"kept {len(jobs)} unique (discarded {discarded} no-link)"
        )
        return jobs

    async def _fetch_query(self, query: str) -> tuple:
        """Fetch one Adzuna search query. Returns (jobs, fetched_count, discarded_count)."""
        url = f"{self.BASE_URL}/{self.COUNTRY}/search/1"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": 50,
            "sort_by": "date",
            "content-type": "application/json",
        }
        jobs: List[Job] = []
        fetched = 0
        discarded = 0

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            now = datetime.now()
            for item in data.get("results", []):
                fetched += 1
                apply_url = _get_direct_apply_url(item, "adzuna")
                if not apply_url:
                    discarded += 1
                    logger.debug(
                        f"AdzunaProvider: discarding '{item.get('title', '?')}' @ "
                        f"'{item.get('company', {}).get('display_name', '?')}' — no redirect_url"
                    )
                    continue

                company_name = (
                    item.get("company", {}).get("display_name", "")
                    or item.get("company_name", "")
                    or ""
                ).strip()
                title = (item.get("title") or "").strip()
                description = (item.get("description") or "")[:2000]
                location_name = (
                    item.get("location", {}).get("display_name", "")
                    or item.get("location_name", "")
                    or "India"
                ).strip()

                # Parse date
                created_str = item.get("created", "")
                try:
                    posted_at = datetime.fromisoformat(created_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    posted_at = now

                work_mode = _infer_work_mode_from_text(title, description, location_name)

                # Extract skills from category label
                category = item.get("category", {}).get("label", "")
                skills: List[str] = [category] if category else []

                external_id = f"adzuna-{item.get('id', '')}"

                job = Job(
                    title=title,
                    company=company_name,
                    description=description,
                    required_skills=skills,
                    location=location_name,
                    source="adzuna",
                    external_id=external_id,
                    application_url=apply_url,
                    posted_at=posted_at,
                    deadline=None,
                    is_active=True,
                    work_mode=work_mode,
                )
                jobs.append(job)

        except Exception as e:
            logger.error(f"AdzunaProvider._fetch_query('{query}') error: {e}")

        return jobs, fetched, discarded


# ─────────────────────────────────────────────────────────────────────────────
# RemotiveProvider
# ─────────────────────────────────────────────────────────────────────────────

class RemotiveProvider(JobsProvider):
    """
    Calls the Remotive public API — no auth required.
    GET https://remotive.com/api/remote-jobs?category=software-dev
    Returns remote tech/software roles with a direct 'url' (real employer link).

    Only jobs with a real 'url' field are kept — jobs missing it are discarded.
    Results are cached in-memory for TTL_SECONDS (6 hours).

    Attribution: Remotive requires a "via Remotive" link on job cards — rendered
    on the frontend for source == "remotive".

    Remotive rate limits (from their ToS):
      - No more than ~4 syncs/day (enforced by 6h TTL)
      - Never more than twice per minute (enforced by the TTL cache)
    """
    TTL_SECONDS = 6 * 3600  # 6 hours

    def __init__(self):
        self._cache: List[Job] = []
        self._cache_ts: float = 0.0

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        import time
        now_ts = time.time()

        if self._cache and (now_ts - self._cache_ts) < self.TTL_SECONDS:
            logger.info(f"RemotiveProvider: serving {len(self._cache)} jobs from cache (TTL ok)")
            jobs = self._cache
        else:
            jobs = await self._fetch_fresh()
            self._cache = jobs
            self._cache_ts = now_ts

        if query:
            q = query.lower()
            jobs = [
                j for j in jobs
                if q in j.title.lower()
                or q in j.company.lower()
                or any(q in s.lower() for s in j.required_skills)
            ]
        return jobs[:limit]

    async def _fetch_fresh(self) -> List[Job]:
        url = "https://remotive.com/api/remote-jobs"
        params = {"category": "software-dev", "limit": 100}
        jobs: List[Job] = []
        fetched = 0
        discarded = 0

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            now = datetime.now()
            for item in data.get("jobs", []):
                fetched += 1

                # Hard-discard check: Remotive's direct employer link is 'url'
                apply_url = _get_direct_apply_url(item, "remotive")
                if not apply_url:
                    discarded += 1
                    logger.debug(
                        f"RemotiveProvider: discarding '{item.get('title', '?')}' — no url field"
                    )
                    continue

                tags = item.get("tags", [])
                skills = [t for t in tags if isinstance(t, str)][:15]

                pub_date_str = item.get("publication_date", "")
                try:
                    posted_at = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    posted_at = now

                job = Job(
                    title=item.get("title", "").strip(),
                    company=item.get("company_name", "").strip(),
                    description=(item.get("description", "") or "")[:2000],
                    required_skills=skills,
                    location=item.get("candidate_required_location", "Remote"),
                    source="remotive",
                    external_id=f"remotive-{item.get('id', '')}",
                    application_url=apply_url,
                    posted_at=posted_at,
                    deadline=None,
                    is_active=True,
                    work_mode="remote",  # Remotive is a remote-only job board
                )
                jobs.append(job)

            logger.info(
                f"RemotiveProvider: fetched {fetched} raw, "
                f"kept {len(jobs)} (discarded {discarded} no-link)"
            )
        except Exception as e:
            logger.error(f"RemotiveProvider fetch error: {e}")

        return jobs


# ─────────────────────────────────────────────────────────────────────────────
# JSearchProvider
# ─────────────────────────────────────────────────────────────────────────────

class JSearchProvider(JobsProvider):
    """
    Calls JSearch on RapidAPI.
    Uses RAPIDAPI_KEY. Rate-limited to once per ~23 hours (~200 req/month free tier).

    Only jobs with a real job_apply_link (or apply_options fallback) are kept.
    JSearch fills in local/on-site India roles that Adzuna or Remotive don't surface.
    """
    DAILY_LIMIT_SECONDS = 23 * 3600  # 23 hours between fetches

    def __init__(self):
        self.base_url = "https://jsearch.p.rapidapi.com/search"
        self._last_fetch_ts: float = 0.0
        self._cache: List[Job] = []

    @property
    def api_key(self) -> str:
        return os.getenv("RAPIDAPI_KEY", "").strip()

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        import time
        if not self.api_key:
            logger.warning("RAPIDAPI_KEY is missing. Returning empty jobs from JSearchProvider.")
            return []

        now_ts = time.time()
        if self._cache and (now_ts - self._last_fetch_ts) < self.DAILY_LIMIT_SECONDS:
            logger.info(f"JSearchProvider: rate-limit guard active. Serving {len(self._cache)} cached jobs.")
            return self._cache[:limit]

        search_query = query
        if location:
            search_query += f" in {location}"

        querystring = {"query": search_query, "num_pages": "1"}
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }

        jobs: List[Job] = []
        fetched = 0
        discarded = 0

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(self.base_url, headers=headers, params=querystring)
                response.raise_for_status()
                data = response.json()

                for result in data.get("data", [])[:limit]:
                    fetched += 1

                    # Hard-discard check: JSearch's primary apply field is 'job_apply_link'
                    apply_url = _get_direct_apply_url(result, "jsearch")
                    if not apply_url:
                        discarded += 1
                        logger.debug(
                            f"JSearchProvider: discarding '{result.get('job_title', '?')}' — no job_apply_link"
                        )
                        continue

                    skills = []
                    reqs = result.get("job_required_skills")
                    if isinstance(reqs, list):
                        skills = reqs

                    exp_str = result.get("job_offer_expiration_datetime_utc")
                    deadline = None
                    if exp_str:
                        try:
                            deadline = datetime.fromisoformat(exp_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        except Exception:
                            deadline = None

                    posted_at_str = result.get("job_posted_at_datetime_utc")
                    try:
                        posted_at = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        posted_at = datetime.now()

                    work_mode = "remote" if result.get("job_is_remote") else "onsite"

                    job = Job(
                        title=result.get("job_title", ""),
                        company=result.get("employer_name", ""),
                        description=result.get("job_description", ""),
                        required_skills=skills,
                        location=f'{result.get("job_city", "")}, {result.get("job_country", "")}'.strip(", "),
                        source="jsearch",
                        external_id=result.get("job_id", ""),
                        application_url=apply_url,
                        posted_at=posted_at,
                        deadline=deadline,
                        is_active=True,
                        work_mode=work_mode,
                    )
                    jobs.append(job)

            import time as _time
            self._last_fetch_ts = _time.time()
            self._cache = jobs
            logger.info(
                f"JSearchProvider: fetched {fetched} raw, "
                f"kept {len(jobs)} (discarded {discarded} no-link)"
            )
        except Exception as e:
            logger.error(f"Error fetching jobs from JSearch: {e}")

        return jobs


# ─────────────────────────────────────────────────────────────────────────────
# MockJobsProvider — fallback only
# ─────────────────────────────────────────────────────────────────────────────

class MockJobsProvider(JobsProvider):
    """
    Returns realistic fixture postings for Indian tech internships/entry-level roles.
    Used ONLY as a fallback when ALL live providers (Adzuna + Remotive + JSearch)
    return zero jobs. All fixtures use real career page URLs.
    """
    def __init__(self):
        self.fixtures_data = self._generate_fixtures()

    def _generate_fixtures(self) -> list:
        return [
            {
                "title": "Software Engineering Intern",
                "company": "Google",
                "location": "Bangalore, India",
                "description": "Join Google's engineering team as an intern. Work on core infrastructure, Search, or Cloud products.",
                "required_skills": ["Python", "C++", "Java", "Data Structures", "Algorithms"],
                "source": "mock",
                "application_url": "https://careers.google.com/jobs/results/"
            },
            {
                "title": "Frontend Developer Intern",
                "company": "Swiggy",
                "location": "Bangalore, India",
                "description": "Help build seamless user experiences for millions of Swiggy users. Work with React and Redux.",
                "required_skills": ["React", "JavaScript", "HTML", "CSS", "Redux"],
                "source": "mock",
                "application_url": "https://careers.swiggy.com/"
            },
            {
                "title": "Backend Engineering Intern",
                "company": "Zomato",
                "location": "Gurgaon, India",
                "description": "Scale Zomato's backend systems. Experience with microservices and caching is a plus.",
                "required_skills": ["Node.js", "Python", "MongoDB", "Redis", "AWS"],
                "source": "mock",
                "application_url": "https://www.zomato.com/careers"
            },
            {
                "title": "Data Science Intern",
                "company": "Flipkart",
                "location": "Bangalore, India",
                "description": "Analyze large datasets to improve e-commerce recommendation systems and supply chain logistics.",
                "required_skills": ["Python", "Pandas", "Machine Learning", "SQL", "Scikit-Learn"],
                "source": "mock",
                "application_url": "https://www.flipkartcareers.com/"
            },
            {
                "title": "Full Stack Intern",
                "company": "Razorpay",
                "location": "Remote",
                "description": "Work on building robust payment gateways and modern dashboards for merchants.",
                "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL"],
                "source": "mock",
                "application_url": "https://razorpay.com/jobs/"
            },
            {
                "title": "SDE Intern (Entry Level)",
                "company": "Amazon",
                "location": "Hyderabad, India",
                "description": "Design and build scalable services for AWS. Strong problem-solving skills required.",
                "required_skills": ["Java", "C++", "System Design", "AWS"],
                "source": "mock",
                "application_url": "https://www.amazon.jobs/en/teams/internships-for-students"
            },
            {
                "title": "React Native Intern",
                "company": "Cred",
                "location": "Bangalore, India",
                "description": "Contribute to building the most premium credit card payment app in India.",
                "required_skills": ["React Native", "TypeScript", "Mobile Development"],
                "source": "mock",
                "application_url": "https://careers.cred.club/"
            },
            {
                "title": "Machine Learning Intern",
                "company": "Ola",
                "location": "Bangalore, India",
                "description": "Optimize routing algorithms and pricing models using advanced machine learning techniques.",
                "required_skills": ["Python", "TensorFlow", "PyTorch", "Algorithms"],
                "source": "mock",
                "application_url": "https://www.olacabs.com/careers"
            },
            {
                "title": "DevOps Intern",
                "company": "PhonePe",
                "location": "Bangalore, India",
                "description": "Help manage highly available infrastructure and deployment pipelines.",
                "required_skills": ["Linux", "Docker", "Kubernetes", "CI/CD", "AWS"],
                "source": "mock",
                "application_url": "https://www.phonepe.com/careers/"
            },
            {
                "title": "Product Analyst Intern",
                "company": "Paytm",
                "location": "Noida, India",
                "description": "Analyze user behavior and provide actionable insights for product development.",
                "required_skills": ["SQL", "Excel", "Data Analysis", "Python"],
                "source": "mock",
                "application_url": "https://paytm.com/about-us/careers/"
            },
            {
                "title": "UI/UX Design Intern",
                "company": "MakeMyTrip",
                "location": "Gurgaon, India",
                "description": "Design intuitive travel booking experiences for millions of users.",
                "required_skills": ["Figma", "UI/UX", "Prototyping", "User Research"],
                "source": "mock",
                "application_url": "https://careers.makemytrip.com/"
            },
            {
                "title": "Cloud Engineering Intern",
                "company": "Freshworks",
                "location": "Chennai, India",
                "description": "Learn to manage and scale cloud resources efficiently.",
                "required_skills": ["AWS", "Azure", "Linux", "Networking"],
                "source": "mock",
                "application_url": "https://www.freshworks.com/company/careers/"
            },
            {
                "title": "Cybersecurity Intern",
                "company": "Zerodha",
                "location": "Remote",
                "description": "Assist in vulnerability assessments and ensuring platform security.",
                "required_skills": ["Network Security", "Ethical Hacking", "Python"],
                "source": "mock",
                "application_url": "https://zerodha.com/jobs/"
            },
            {
                "title": "Go Developer Intern",
                "company": "Gojek",
                "location": "Bangalore, India",
                "description": "Build high-throughput microservices using Golang.",
                "required_skills": ["Golang", "Microservices", "gRPC", "Docker"],
                "source": "mock",
                "application_url": "https://www.gojek.com/careers/"
            },
            {
                "title": "Android Developer Intern",
                "company": "ShareChat",
                "location": "Bangalore, India",
                "description": "Build features for India's largest vernacular social network.",
                "required_skills": ["Android", "Kotlin", "Java", "MVVM"],
                "source": "mock",
                "application_url": "https://sharechat.com/careers"
            },
            {
                "title": "iOS Developer Intern",
                "company": "Dream11",
                "location": "Mumbai, India",
                "description": "Create engaging experiences for fantasy sports enthusiasts on iOS.",
                "required_skills": ["Swift", "iOS", "Xcode", "UIKit"],
                "source": "mock",
                "application_url": "https://www.dream11.com/careers"
            },
            {
                "title": "SDE-1 (Fresher)",
                "company": "Microsoft",
                "location": "Hyderabad, India",
                "description": "Join as an entry-level SDE working on Azure, Office, or Windows ecosystems.",
                "required_skills": ["C#", "C++", "System Design", "Algorithms"],
                "source": "mock",
                "application_url": "https://careers.microsoft.com/students/us/en/india-university"
            },
            {
                "title": "Junior Python Developer",
                "company": "Groww",
                "location": "Bangalore, India",
                "description": "Build scalable financial and investing tools. Fast-paced startup environment.",
                "required_skills": ["Python", "Django", "PostgreSQL", "REST APIs"],
                "source": "mock",
                "application_url": "https://groww.in/p/careers"
            },
            {
                "title": "Web Development Intern",
                "company": "Postman",
                "location": "Bangalore, India",
                "description": "Contribute to the world's leading API platform.",
                "required_skills": ["JavaScript", "React", "Node.js", "API Design"],
                "source": "mock",
                "application_url": "https://www.postman.com/company/careers/"
            },
            {
                "title": "Game Developer Intern",
                "company": "MPL (Mobile Premier League)",
                "location": "Remote",
                "description": "Develop and optimize mobile games for the MPL platform.",
                "required_skills": ["Unity", "C#", "Game Design", "C++"],
                "source": "mock",
                "application_url": "https://www.mpl.live/careers"
            }
        ]

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        now = datetime.now()
        jobs = []
        for i, item in enumerate(self.fixtures_data):
            posted_time = now - timedelta(days=i % 14, hours=i * 2)
            deadline_time = (now + timedelta(days=15 + (i % 15))) if (i % 3 == 0) else None
            loc = item.get("location", "")
            work_mode = "remote" if "remote" in loc.lower() else "onsite"
            job = Job(
                title=item["title"],
                company=item["company"],
                description=item["description"],
                required_skills=item["required_skills"],
                location=loc,
                source=item["source"],
                external_id=f"mock-{i}",
                application_url=None,
                posted_at=posted_time,
                deadline=deadline_time,
                is_active=True,
                work_mode=work_mode,
            )
            jobs.append(job)

        filtered = jobs
        if query:
            q_lower = query.lower()
            filtered = [
                j for j in filtered
                if q_lower in j.title.lower()
                or q_lower in j.company.lower()
                or any(q_lower in s.lower() for s in j.required_skills)
            ]
        if location:
            l_lower = location.lower()
            filtered = [j for j in filtered if l_lower in j.location.lower()]

        return filtered[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# ArbeitnowProvider
# ─────────────────────────────────────────────────────────────────────────────

class ArbeitnowProvider(JobsProvider):
    TTL_SECONDS = 3 * 3600
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self):
        self._cache = []
        self._cache_ts = 0.0

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        import time
        now_ts = time.time()
        if self._cache and (now_ts - self._cache_ts) < self.TTL_SECONDS:
            jobs = self._cache
        else:
            jobs = await self._fetch_fresh(limit=limit)
            self._cache = jobs
            self._cache_ts = now_ts
        return jobs[:limit]

    async def _fetch_fresh(self, limit: int) -> List[Job]:
        jobs = []
        fetched = 0
        discarded = 0
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(self.BASE_URL)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Arbeitnow API request error: {str(e)}")
            return []

        now = datetime.now()
        for item in data.get("data", []):
            fetched += 1
            apply_url = _get_direct_apply_url(item, "arbeitnow")
            if not apply_url:
                discarded += 1
                continue

            title = item.get("title", "Untitled Role")
            company = item.get("company_name", "Unknown Company")
            loc = item.get("location", "Remote")
            desc = item.get("description", "")
            work_mode = "remote" if item.get("remote") else _infer_work_mode_from_text(title, desc)
            
            posted_at = now
            created_str = item.get("created_at")
            if created_str:
                try:
                    posted_at = datetime.fromtimestamp(created_str)
                except:
                    pass
            
            jobs.append(Job(
                title=title,
                company=company,
                location=loc,
                description=desc,
                application_url=apply_url,
                source="arbeitnow",
                external_id=f"arbeitnow-{item.get('slug')}",
                work_mode=work_mode,
                required_skills=[],
                posted_at=posted_at,
                is_active=True
            ))

        logger.info(
            f"ArbeitnowProvider: fetched {fetched} raw, "
            f"kept {len(jobs)} (discarded {discarded} no-link)"
        )
        return jobs

# ─────────────────────────────────────────────────────────────────────────────
# HimalayasProvider
# ─────────────────────────────────────────────────────────────────────────────

class HimalayasProvider(JobsProvider):
    """
    Calls the Himalayas public API — no auth required.
    GET https://himalayas.app/jobs/api?limit=100

    ⚠️ KNOWN LIMITATION (verified 2026-07-31):
    The free API only exposes applicationLink which returns Himalayas' own
    internal listing pages (himalayas.app/companies/...), NOT direct employer
    ATS links. All jobs are discarded by _get_direct_apply_url under the strict
    direct-link rule. Yield = 0 until Himalayas exposes direct employer URLs.

    Fields confirmed via live API test:
      title, companyName, description, applicationLink (internal),
      guid, pubDate (Unix epoch), expiryDate (Unix epoch),
      locationRestrictions, employmentType, seniority, categories
    """
    TTL_SECONDS = 3 * 3600
    BASE_URL = "https://himalayas.app/jobs/api"

    def __init__(self):
        self._cache = []
        self._cache_ts = 0.0

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        import time
        now_ts = time.time()
        if self._cache and (now_ts - self._cache_ts) < self.TTL_SECONDS:
            jobs = self._cache
        else:
            jobs = await self._fetch_fresh(limit=limit)
            self._cache = jobs
            self._cache_ts = now_ts
        return jobs[:limit]

    async def _fetch_fresh(self, limit: int) -> List[Job]:
        jobs = []
        fetched = 0
        discarded = 0
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(self.BASE_URL, params={"limit": 100})
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"HimalayasProvider API request error: {str(e)}")
            return []

        now = datetime.now()
        for item in data.get("jobs", []):
            fetched += 1
            # _get_direct_apply_url will reject himalayas.app internal URLs
            apply_url = _get_direct_apply_url(item, "himalayas")
            if not apply_url:
                discarded += 1
                logger.debug(
                    f"HimalayasProvider: discarding '{item.get('title', '?')}' "
                    f"@ '{item.get('companyName', '?')}' — applicationLink is "
                    f"internal board URL: {str(item.get('applicationLink', ''))[:60]}"
                )
                continue

            title = item.get("title", "Untitled Role")
            company = item.get("companyName", "Unknown Company")
            # Himalayas is remote-only; locationRestrictions lists allowed regions
            restrictions = item.get("locationRestrictions") or []
            loc = ", ".join(restrictions) if restrictions else "Remote"
            desc = item.get("description") or item.get("excerpt", "")
            work_mode = "remote"  # Himalayas is an exclusively remote job board

            # pubDate and expiryDate are Unix epoch integers
            posted_at = now
            pub_epoch = item.get("pubDate")
            if pub_epoch:
                try:
                    posted_at = datetime.fromtimestamp(int(pub_epoch))
                except Exception:
                    pass

            deadline = None
            expiry_epoch = item.get("expiryDate")
            if expiry_epoch:
                try:
                    deadline = datetime.fromtimestamp(int(expiry_epoch))
                except Exception:
                    pass

            # Extract skills from categories list
            categories = item.get("categories") or []
            skills = [c.replace("-", " ").title() for c in categories[:10]] if categories else []

            jobs.append(Job(
                title=title,
                company=company,
                location=loc,
                description=desc[:2000] if desc else "",
                application_url=apply_url,
                source="himalayas",
                external_id=f"himalayas-{item.get('guid', str(item.get('title', ''))[:40])}",
                work_mode=work_mode,
                required_skills=skills,
                posted_at=posted_at,
                deadline=deadline,
                is_active=True
            ))

        logger.info(
            f"HimalayasProvider: fetched {fetched} raw, "
            f"kept {len(jobs)} (discarded {discarded} — internal board URLs rejected)"
        )
        return jobs

# ─────────────────────────────────────────────────────────────────────────────
# JoobleProvider
# ─────────────────────────────────────────────────────────────────────────────

class JoobleProvider(JobsProvider):
    BASE_URL = "https://jooble.org/api/"

    def __init__(self):
        pass

    @property
    def api_key(self) -> str:
        return os.getenv("JOOBLE_API_KEY", "").strip()

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        if not self.api_key:
            logger.warning("JoobleProvider: Credentials missing. Skipping.")
            return []
        
        url = f"{self.BASE_URL}{self.api_key}"
        payload = {"keywords": query or "software", "location": location or "India"}

        jobs = []
        fetched = 0
        discarded = 0
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Jooble API request error: {str(e)}")
            return []

        now = datetime.now()
        for item in data.get("jobs", []):
            fetched += 1
            apply_url = _get_direct_apply_url(item, "jooble")
            if not apply_url:
                discarded += 1
                continue

            title = item.get("title", "Untitled Role")
            company = item.get("company", "Unknown Company")
            loc = item.get("location", "Remote")
            desc = item.get("snippet", "")
            work_mode = _infer_work_mode_from_text(title, desc, loc)
            
            jobs.append(Job(
                title=title,
                company=company,
                location=loc,
                description=desc,
                application_url=apply_url,
                source="jooble",
                external_id=f"jooble-{item.get('id', title+company)}",
                work_mode=work_mode,
                required_skills=[],
                posted_at=now,
                is_active=True
            ))
            
        logger.info(
            f"JoobleProvider: fetched {fetched} raw, "
            f"kept {len(jobs)} (discarded {discarded} no-link)"
        )
        return jobs[:limit]

# ─────────────────────────────────────────────────────────────────────────────
# CareerOneStopProvider
# ─────────────────────────────────────────────────────────────────────────────

class CareerOneStopProvider(JobsProvider):
    BASE_URL = "https://api.careeronestop.org/v1/jobsearch"

    def __init__(self):
        pass

    @property
    def user_id(self) -> str:
        return os.getenv("CAREERONESTOP_USER_ID", "").strip()

    @property
    def token(self) -> str:
        return os.getenv("CAREERONESTOP_TOKEN", "").strip()

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        if not self.user_id or not self.token:
            logger.warning("CareerOneStopProvider: Credentials missing. Skipping.")
            return []
            
        kw = query or "software"
        loc = location or "US"
        url = f"{self.BASE_URL}/{self.user_id}/{kw}/{loc}/25/30/Date/1/{limit}/0"
        headers = {"Authorization": f"Bearer {self.token}"}

        jobs = []
        fetched = 0
        discarded = 0
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"CareerOneStop API request error: {str(e)}")
            return []

        now = datetime.now()
        for item in data.get("Jobs", []):
            fetched += 1
            apply_url = _get_direct_apply_url(item, "careeronestop")
            if not apply_url:
                discarded += 1
                continue

            title = item.get("JobTitle", "Untitled Role")
            company = item.get("Company", "Unknown Company")
            job_loc = item.get("Location", "US")
            desc = ""
            work_mode = _infer_work_mode_from_text(title, job_loc)
            
            jobs.append(Job(
                title=title,
                company=company,
                location=job_loc,
                description=desc,
                application_url=apply_url,
                source="careeronestop",
                external_id=f"careeronestop-{item.get('JvId', title+company)}",
                work_mode=work_mode,
                required_skills=[],
                posted_at=now,
                is_active=True
            ))

        logger.info(
            f"CareerOneStopProvider: fetched {fetched} raw, "
            f"kept {len(jobs)} (discarded {discarded} no-link)"
        )
        return jobs[:limit]
