"""jobs_provider.py — Live job feed providers.

Active providers (NO Adzuna):
  • RemotiveProvider  — https://remotive.com/api/remote-jobs  (no auth, 6h cache)
  • JSearchProvider   — RapidAPI JSearch (RAPIDAPI_KEY, ~23h rate-limit guard)
  • MockJobsProvider  — local fixtures, fallback when both live sources are empty

Source tags written to Job.source:
  "remotive" | "jsearch" | "mock" | "manual"

Work mode:
  Remotive → always "remote"
  JSearch  → "remote" if job_is_remote else "onsite"
  Mock     → inferred from location string
"""
import os
import httpx
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio

# Assuming models are in api.models (adjust import if needed)
from api.models import Job

logger = logging.getLogger(__name__)

class JobsProvider(ABC):
    """
    Interface for job data providers.
    """
    @abstractmethod
    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        pass

class MockJobsProvider(JobsProvider):
    """
    Returns realistic fixture postings for Indian tech internships/entry-level roles.
    """
    def __init__(self):
        self.fixtures = self._generate_fixtures()

    def _generate_fixtures(self) -> List[Job]:
        now = datetime.now()
        fixtures_data = [
            {
                "title": "Software Engineering Intern",
                "company": "Google",
                "location": "Bangalore, India",
                "description": "Join Google's engineering team as an intern. Work on core infrastructure, Search, or Cloud products.",
                "required_skills": ["Python", "C++", "Java", "Data Structures", "Algorithms"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Frontend Developer Intern",
                "company": "Swiggy",
                "location": "Bangalore, India",
                "description": "Help build seamless user experiences for millions of Swiggy users. Work with React and Redux.",
                "required_skills": ["React", "JavaScript", "HTML", "CSS", "Redux"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Backend Engineering Intern",
                "company": "Zomato",
                "location": "Gurgaon, India",
                "description": "Scale Zomato's backend systems. Experience with microservices and caching is a plus.",
                "required_skills": ["Node.js", "Python", "MongoDB", "Redis", "AWS"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Data Science Intern",
                "company": "Flipkart",
                "location": "Bangalore, India",
                "description": "Analyze large datasets to improve e-commerce recommendation systems and supply chain logistics.",
                "required_skills": ["Python", "Pandas", "Machine Learning", "SQL", "Scikit-Learn"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Full Stack Intern",
                "company": "Razorpay",
                "location": "Remote",
                "description": "Work on building robust payment gateways and modern dashboards for merchants.",
                "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "SDE Intern (Entry Level)",
                "company": "Amazon",
                "location": "Hyderabad, India",
                "description": "Design and build scalable services for AWS. Strong problem-solving skills required.",
                "required_skills": ["Java", "C++", "System Design", "AWS"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "React Native Intern",
                "company": "Cred",
                "location": "Bangalore, India",
                "description": "Contribute to building the most premium credit card payment app in India.",
                "required_skills": ["React Native", "TypeScript", "Mobile Development"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Machine Learning Intern",
                "company": "Ola",
                "location": "Bangalore, India",
                "description": "Optimize routing algorithms and pricing models using advanced machine learning techniques.",
                "required_skills": ["Python", "TensorFlow", "PyTorch", "Algorithms"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "DevOps Intern",
                "company": "PhonePe",
                "location": "Bangalore, India",
                "description": "Help manage highly available infrastructure and deployment pipelines.",
                "required_skills": ["Linux", "Docker", "Kubernetes", "CI/CD", "AWS"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Product Analyst Intern",
                "company": "Paytm",
                "location": "Noida, India",
                "description": "Analyze user behavior and provide actionable insights for product development.",
                "required_skills": ["SQL", "Excel", "Data Analysis", "Python"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "UI/UX Design Intern",
                "company": "MakeMyTrip",
                "location": "Gurgaon, India",
                "description": "Design intuitive travel booking experiences for millions of users.",
                "required_skills": ["Figma", "UI/UX", "Prototyping", "User Research"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Cloud Engineering Intern",
                "company": "Freshworks",
                "location": "Chennai, India",
                "description": "Learn to manage and scale cloud resources efficiently.",
                "required_skills": ["AWS", "Azure", "Linux", "Networking"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Cybersecurity Intern",
                "company": "Zerodha",
                "location": "Remote",
                "description": "Assist in vulnerability assessments and ensuring platform security.",
                "required_skills": ["Network Security", "Ethical Hacking", "Python"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Go Developer Intern",
                "company": "Gojek",
                "location": "Bangalore, India",
                "description": "Build high-throughput microservices using Golang.",
                "required_skills": ["Golang", "Microservices", "gRPC", "Docker"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Android Developer Intern",
                "company": "ShareChat",
                "location": "Bangalore, India",
                "description": "Build features for India's largest vernacular social network.",
                "required_skills": ["Android", "Kotlin", "Java", "MVVM"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "iOS Developer Intern",
                "company": "Dream11",
                "location": "Mumbai, India",
                "description": "Create engaging experiences for fantasy sports enthusiasts on iOS.",
                "required_skills": ["Swift", "iOS", "Xcode", "UIKit"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "SDE-1 (Fresher)",
                "company": "Microsoft",
                "location": "Hyderabad, India",
                "description": "Join as an entry-level SDE working on Azure, Office, or Windows ecosystems.",
                "required_skills": ["C#", "C++", "System Design", "Algorithms"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Junior Python Developer",
                "company": "Groww",
                "location": "Bangalore, India",
                "description": "Build scalable financial and investing tools. Fast-paced startup environment.",
                "required_skills": ["Python", "Django", "PostgreSQL", "REST APIs"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Web Development Intern",
                "company": "Postman",
                "location": "Bangalore, India",
                "description": "Contribute to the world's leading API platform.",
                "required_skills": ["JavaScript", "React", "Node.js", "API Design"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            },
            {
                "title": "Game Developer Intern",
                "company": "MPL (Mobile Premier League)",
                "location": "Remote",
                "description": "Develop and optimize mobile games for the MPL platform.",
                "required_skills": ["Unity", "C#", "Game Design", "C++"],
                "source": "mock",
                "application_url": "https://example.com/apply"
            }
        ]

        self.fixtures_data = fixtures_data

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 20) -> List[Job]:
        now = datetime.now()
        jobs = []
        for i, item in enumerate(self.fixtures_data):
            posted_time = now - timedelta(days=i % 14, hours=i * 2)
            # Give every third mock job a future deadline (e.g. 15-30 days out)
            deadline_time = (now + timedelta(days=15 + (i % 15))) if (i % 3 == 0) else None
            # Detect work mode from location string
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
                application_url=item["application_url"],
                posted_at=posted_time,
                deadline=deadline_time,
                is_active=True,
                work_mode=work_mode,
            )
            jobs.append(job)
            
        # Filter fixtures dynamically based on query
        filtered = jobs
        if query:
            q_lower = query.lower()
            filtered = [j for j in filtered if q_lower in j.title.lower() or q_lower in j.company.lower() or any(q_lower in s.lower() for s in j.required_skills)]
        if location:
            l_lower = location.lower()
            filtered = [j for j in filtered if l_lower in j.location.lower()]
            
        # Return limit
        return filtered[:limit]


class RemotiveProvider(JobsProvider):
    """
    Calls the Remotive public API — no auth required.
    GET https://remotive.com/api/remote-jobs?category=software-dev
    Returns remote tech/software roles with a direct 'url' (real employer link).
    Results are cached in-memory for TTL_SECONDS (6 hours) to avoid hammering.
    """
    TTL_SECONDS = 6 * 3600  # 6 hours

    def __init__(self):
        self._cache: List[Job] = []
        self._cache_ts: float = 0.0

    async def fetch_jobs(self, query: str = "", location: str = "", limit: int = 50) -> List[Job]:
        import time
        now_ts = time.time()

        # Serve from cache if fresh
        if self._cache and (now_ts - self._cache_ts) < self.TTL_SECONDS:
            logger.info(f"RemotiveProvider: serving {len(self._cache)} jobs from cache (TTL ok)")
            jobs = self._cache
        else:
            jobs = await self._fetch_fresh()
            self._cache = jobs
            self._cache_ts = now_ts

        # Filter by query if provided
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
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            now = datetime.now()
            for item in data.get("jobs", []):
                # Extract skills from tags list
                tags = item.get("tags", [])
                skills = [t for t in tags if isinstance(t, str)][:15]

                # Parse date
                pub_date_str = item.get("publication_date", "")
                try:
                    posted_at = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    posted_at = now

                job = Job(
                    # Use 'title' directly — 'job_type_label' is a category string (e.g. "Full-Time"),
                    # NOT the position title.
                    title=item.get("title", "").strip(),
                    company=item.get("company_name", "").strip(),
                    description=(item.get("description", "") or "")[:2000],
                    required_skills=skills,
                    location=item.get("candidate_required_location", "Remote"),
                    source="remotive",
                    external_id=f"remotive-{item.get('id', '')}",
                    # 'url' is the direct employer application page — not a redirect
                    application_url=item.get("url", ""),
                    posted_at=posted_at,
                    deadline=None,
                    is_active=True,
                    work_mode="remote",  # Remotive is a remote-only job board
                )
                jobs.append(job)

            logger.info(f"RemotiveProvider: fetched {len(jobs)} jobs from API")
        except Exception as e:
            logger.error(f"RemotiveProvider fetch error: {e}")

        return jobs


class JSearchProvider(JobsProvider):
    """
    Calls JSearch on RapidAPI.
    Uses RAPIDAPI_KEY.
    Rate-limited to once per 24 hours to respect the ~200 req/month cap.
    """
    DAILY_LIMIT_SECONDS = 23 * 3600  # 23 hours between fetches

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.base_url = "https://jsearch.p.rapidapi.com/search"
        self._last_fetch_ts: float = 0.0
        self._cache: List[Job] = []

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

        jobs = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(self.base_url, headers=headers, params=querystring)
                response.raise_for_status()
                data = response.json()

                for result in data.get("data", [])[:limit]:
                    skills = []
                    reqs = result.get("job_required_skills")
                    if isinstance(reqs, list):
                        skills = reqs

                    exp_str = result.get("job_offer_expiration_datetime_utc")
                    deadline = None
                    if exp_str:
                        try:
                            deadline = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                        except Exception:
                            deadline = None

                    job = Job(
                        title=result.get("job_title", ""),
                        company=result.get("employer_name", ""),
                        description=result.get("job_description", ""),
                        required_skills=skills,
                        location=f'{result.get("job_city", "")}, {result.get("job_country", "")}'.strip(", "),
                        source="jsearch",
                        external_id=result.get("job_id", ""),
                        application_url=result.get("job_apply_link", ""),
                        posted_at=datetime.fromisoformat(result["job_posted_at_datetime_utc"].replace("Z", "+00:00")) if result.get("job_posted_at_datetime_utc") else datetime.now(),
                        deadline=deadline,
                        is_active=True,
                        work_mode="remote" if result.get("job_is_remote") else "onsite",
                    )
                    jobs.append(job)

            import time
            self._last_fetch_ts = time.time()
            self._cache = jobs
            logger.info(f"JSearchProvider: fetched {len(jobs)} fresh jobs")
        except Exception as e:
            logger.error(f"Error fetching jobs from JSearch: {e}")

        return jobs
