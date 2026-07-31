import os
import hashlib
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from ..models import Job, Resume, UserJobMatch
from ..auth import get_current_user
from services.jobs_provider import (
    AdzunaProvider, MockJobsProvider, RemotiveProvider, JSearchProvider,
    ArbeitnowProvider, HimalayasProvider, CareerOneStopProvider, JoobleProvider
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

adzuna_provider = AdzunaProvider()
remotive_provider = RemotiveProvider()
jsearch_provider = JSearchProvider()
arbeitnow_provider = ArbeitnowProvider()
himalayas_provider = HimalayasProvider()
careeronestop_provider = CareerOneStopProvider()
jooble_provider = JoobleProvider()
mock_provider = MockJobsProvider()

class JobCreate(BaseModel):
    title: str
    company: str
    description: str
    required_skills: List[str]
    location: str
    application_url: str
    deadline: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(skill: str) -> str:
    """Lower-case, strip whitespace for case-insensitive comparison."""
    return skill.strip().lower()


def _is_job_current_and_upcoming(job: Job) -> bool:
    """
    Check if a job posting is current and upcoming:
    - is_active must be True (not delisted)
    - If deadline is set: deadline must be >= now
    - If deadline is None: posted_at must be within 45 days of now
    """
    if not job.is_active:
        return False

    now = datetime.now()

    if job.deadline is not None:
        return job.deadline >= now

    if job.posted_at is not None:
        stale_cutoff = now - timedelta(days=45)
        return job.posted_at >= stale_cutoff

    return True


def _score_resume_against_job(
    candidate_skills: List[str],
    required_skills: List[str],
) -> tuple[int, List[str], List[str]]:
    """
    Keyword-overlap scoring.
    Returns (score 0-100, matched_skills, missing_skills).
    """
    if not required_skills:
        return 0, [], []

    candidate_norm = {_normalise(s) for s in candidate_skills}
    matched, missing = [], []

    for skill in required_skills:
        if _normalise(skill) in candidate_norm:
            matched.append(skill)
        else:
            missing.append(skill)

    score = int(round(len(matched) / len(required_skills) * 100))
    return score, matched, missing


async def _extract_candidate_skills(user_email: str) -> tuple[Optional[str], List[str]]:
    """
    Load the user's Resume doc (or fallback to User profile skills)
    and extract their skills list + resume_version.
    Returns (resume_version, skills_list) or (None, []) if no resume/skills found.
    """
    from ..models import User
    resume_doc = await Resume.find_one(Resume.user_id == user_email)
    if resume_doc:
        parsed = resume_doc.parsed_json or {}
        skills: List[str] = parsed.get("skills", [])
        if not skills and resume_doc.raw_text:
            tokens = []
            for tok in resume_doc.raw_text.replace(",", "\n").split("\n"):
                t = tok.strip()
                if 2 <= len(t) <= 25:
                    tokens.append(t)
            skills = tokens[:80]
        return resume_doc.resume_version or "v1", skills

    user = await User.find_one(User.email == user_email)
    if user and user.skills:
        version_hash = hashlib.sha256(",".join(user.skills).encode()).hexdigest()[:12]
        return version_hash, user.skills

    if user and user.resume_text:
        version_hash = hashlib.sha256(user.resume_text.encode()).hexdigest()[:12]
        tokens = [t.strip() for t in user.resume_text.replace(",", "\n").split("\n") if 2 <= len(t.strip()) <= 25]
        return version_hash, tokens

    return None, []


# ─────────────────────────────────────────────────────────────────────────────
# normalize_job_item — unify apply links from all providers into apply_url
# ─────────────────────────────────────────────────────────────────────────────

def normalize_job_item(raw_job: dict, source: str) -> Optional[dict]:
    """
    Inspect a raw job dict from any provider and standardise it into a
    flat payload with a verified direct apply_url.

    Priority order for the apply link:
      1. job_apply_link   — JSearch primary field
      2. url              — Remotive/Arbeitnow direct employer link
      3. apply_options[0]["apply_link"] — JSearch ATS deeplink (often cleaner)
      4. redirect_url     — Adzuna direct link
      5. apply_url        — custom scraped sources
      6. applicationLink  — Himalayas (rejected if himalayas.app internal URL)
      7. link             — Jooble direct link
      8. JobURL           — CareerOneStop

    Returns None if no valid direct apply URL is found (strict direct-link rule).
    Callers MUST check for None and skip/discard that job.
    No Google Search fallback is ever generated.
    """
    from services.jobs_provider import _get_direct_apply_url, _is_real_url

    # Build a normalised raw dict that _get_direct_apply_url can process
    # by checking all known field names across providers
    apply_url: str = (
        raw_job.get("job_apply_link") or
        raw_job.get("url") or
        raw_job.get("redirect_url") or
        raw_job.get("apply_url") or
        ""
    )

    # JSearch secondary: check apply_options array for a cleaner ATS deeplink
    if not apply_url:
        options = raw_job.get("apply_options") or []
        if options and isinstance(options, list):
            first = options[0]
            apply_url = (
                first.get("apply_link") or
                first.get("link") or
                first.get("url") or
                ""
            )

    # Himalayas / Jooble / CareerOneStop fallback fields
    if not apply_url:
        apply_url = (
            raw_job.get("applicationLink") or
            raw_job.get("link") or
            raw_job.get("JobURL") or
            ""
        )

    # Strict direct-link rule: discard if no real URL or if it's an internal board page
    from services.jobs_provider import _is_direct_employer_url
    if not apply_url or not _is_direct_employer_url(apply_url.strip()):
        logger.debug(
            f"normalize_job_item [{source}]: no valid direct apply URL for "
            f"'{raw_job.get('job_title') or raw_job.get('title', '?')}' — discarding"
        )
        return None

    return {
        "job_title": raw_job.get("job_title") or raw_job.get("title", "Untitled Role"),
        "company_name": raw_job.get("employer_name") or raw_job.get("company_name", "Unknown Company"),
        "location": (
            raw_job.get("job_country") or
            raw_job.get("candidate_required_location") or
            raw_job.get("location", "India / Remote")
        ),
        "source": source,
        "apply_url": apply_url.strip(),   # ← unified field — frontend ONLY reads this
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Job])
async def get_jobs(
    query: str = Query("", description="Search term for job title or skills"),
    location: str = Query("", description="Job location"),
    limit: int = Query(20, ge=1, le=50, description="Max number of jobs to return"),
    current_user: str = Depends(get_current_user),
):
    """
    Fetch current and upcoming jobs from providers/DB.
    Excludes expired deadlines, delisted jobs, and stale postings (>45 days).
    Also excludes any job lacking a real direct apply link.

    Provider fetch order & dedup priority:
      1. Arbeitnow  (TOP PRIORITY — native ATS links, no auth)
      2. Adzuna     (ADZUNA_APP_ID/KEY required)
      3. Remotive   (free, no auth, remote-only)
      4. JSearch    (RAPIDAPI_KEY required)
      5. Himalayas  (free, no auth — yields 0 under strict rule: free API returns internal URLs)
      6. Jooble     (JOOBLE_API_KEY required)
      7. CareerOneStop (CAREERONESTOP credentials required, US-only data)
      8. Mock       (fallback when all live sources return 0)
    """
    jobs: list = []

    async def _safe_fetch(provider, name, **kwargs):
        try:
            res = await provider.fetch_jobs(**kwargs)
            if res:
                logger.info(f"GET /jobs: got {len(res)} jobs from {name}")
                jobs.extend(res)
        except Exception as e:
            logger.error(f"{name} fetch error: {e}")

    # Fetch sequentially (cached sources return quickly)
    await _safe_fetch(arbeitnow_provider, "Arbeitnow", query=query, location=location, limit=limit)
    await _safe_fetch(adzuna_provider, "Adzuna", query=query, location=location, limit=limit)
    await _safe_fetch(remotive_provider, "Remotive", query=query, location=location, limit=limit)
    await _safe_fetch(jsearch_provider, "JSearch", query=query or "software intern", location=location or "India", limit=limit)
    await _safe_fetch(himalayas_provider, "Himalayas", query=query, location=location, limit=limit)
    await _safe_fetch(jooble_provider, "Jooble", query=query, location=location, limit=limit)
    await _safe_fetch(careeronestop_provider, "CareerOneStop", query=query, location=location, limit=limit)

    if not jobs:
        logger.info("No live jobs — falling back to MockJobsProvider")
        jobs = await mock_provider.fetch_jobs(query=query, location=location, limit=limit)

    # Filter: current/upcoming AND has a real direct apply link
    current_jobs = [
        j for j in jobs
        if _is_job_current_and_upcoming(j)
        and j.application_url
        and j.application_url.startswith("http")
    ]
    return current_jobs[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/jobs/sync — sync fresh jobs & mark delisted jobs inactive
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_jobs(
    current_user: str = Depends(get_current_user),
):
    """
    Sync fresh job listings from all 7 live sources into MongoDB.

    Provider priority order (highest → lowest for cross-source dedup):
      1. Arbeitnow    : no auth, 3h in-memory cache. Native ATS links (TOP PRIORITY).
      2. Adzuna       : ADZUNA_APP_ID/KEY required. 8h in-memory cache. ~1,000 calls/month.
      3. Remotive     : free, no auth, 6h cache. Always "remote" work_mode.
      4. JSearch      : RAPIDAPI_KEY required. ~23h rate-limit guard (~200 req/month).
      5. Himalayas    : free, no auth, 3h cache. Currently yields 0 (internal board URLs).
      6. Jooble       : JOOBLE_API_KEY required. ~500 req/day limit.
      7. CareerOneStop: CAREERONESTOP_USER_ID + TOKEN required. US-only data.
      8. Mock         : fallback only when ALL seven live sources return 0 jobs.

    Direct-link rule (HARD DISCARD before upsert):
      Any fetched job without a real http(s):// application_url that is NOT an
      internal job-board page is discarded before being stored. Never in MongoDB.

    Cross-source deduplication:
      If the same posting appears from multiple sources (matched by normalised
      title + company), the higher-priority source version is kept.

    After upserting fresh jobs:
      - Jobs no longer returned by any provider are marked is_active=False.
      - Existing docs with changed work_mode are updated in place.
    """
    from services.jobs_provider import _is_real_url
    import re as _re

    def _normalise_sig(title: str, company: str) -> str:
        """Normalise title+company into a dedup signature (lower, strip punctuation)."""
        combined = f"{title.lower().strip()} {company.lower().strip()}"
        return _re.sub(r'[^a-z0-9 ]', '', combined).strip()



    provider_status: dict = {}
    fresh_jobs: list = []        # all valid (has real link) jobs from all sources
    discarded_total = 0

    # Priority: Arbeitnow > Adzuna > Remotive > JSearch > Himalayas > Jooble > CareerOneStop

    # Helper for dedup
    combined_sigs = set()

    async def _sync_provider(provider, name, **kwargs):
        nonlocal cross_deduped_total
        try:
            raw_jobs = await provider.fetch_jobs(**kwargs)
            valid_jobs = [j for j in raw_jobs if _is_real_url(j.application_url)]
            
            deduped = []
            cross_deduped = 0
            for j in valid_jobs:
                sig = _normalise_sig(j.title, j.company)
                if sig in combined_sigs:
                    cross_deduped += 1
                else:
                    deduped.append(j)
                    combined_sigs.add(sig)
                    
            fresh_jobs.extend(deduped)
            provider_status[name.lower()] = {
                "fetched": len(raw_jobs),
                "kept": len(deduped),
                "discarded_no_link": len(raw_jobs) - len(valid_jobs),
                "deduped_cross_source": cross_deduped,
                "status": "ok",
            }
            logger.info(f"Sync: kept {len(deduped)} from {name} (cross-deduped {cross_deduped})")
        except Exception as e:
            provider_status[name.lower()] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": f"error: {e}"}
            logger.error(f"Sync error from {name}Provider: {e}")

    cross_deduped_total = 0

    await _sync_provider(arbeitnow_provider, "Arbeitnow", limit=150)
    
    if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
        await _sync_provider(adzuna_provider, "Adzuna", query="software developer intern", location="India", limit=150)
    else:
        provider_status["adzuna"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: ADZUNA credentials not set"}

    await _sync_provider(remotive_provider, "Remotive", limit=100)
    
    if os.getenv("RAPIDAPI_KEY"):
        await _sync_provider(jsearch_provider, "JSearch", query="software developer intern", location="India", limit=50)
    else:
        provider_status["jsearch"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: RAPIDAPI_KEY not set"}

    await _sync_provider(himalayas_provider, "Himalayas", limit=100)
    
    if os.getenv("JOOBLE_API_KEY"):
        await _sync_provider(jooble_provider, "Jooble", query="software", location="India", limit=50)
    else:
        provider_status["jooble"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: JOOBLE_API_KEY not set"}

    if os.getenv("CAREERONESTOP_USER_ID") and os.getenv("CAREERONESTOP_TOKEN"):
        await _sync_provider(careeronestop_provider, "CareerOneStop", query="software", location="US", limit=50)
    else:
        provider_status["careeronestop"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: CAREERONESTOP credentials not set"}

    used_mock = False
    if not fresh_jobs:
        mock_jobs = await mock_provider.fetch_jobs(limit=50)
        fresh_jobs.extend(mock_jobs)
        used_mock = True
        provider_status["mock"] = {"fetched": len(mock_jobs), "kept": len(mock_jobs), "discarded_no_link": 0, "deduped_cross_source": 0, "status": "fallback"}
        logger.info("Sync: all live providers returned 0 jobs — using mock fallback")
    else:
        provider_status["mock"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "not_needed"}

    # ── 5. Delist jobs no longer returned by any provider ─────────────────────
    fresh_external_ids = {j.external_id for j in fresh_jobs if j.external_id}
    fresh_signatures = {
        (j.company.lower().strip(), j.title.lower().strip()) for j in fresh_jobs
    }

    existing_db_jobs = await Job.find_all().to_list()
    delisted_count = 0
    relisted_count = 0

    for db_job in existing_db_jobs:
        is_still_present = (
            (db_job.external_id and db_job.external_id in fresh_external_ids)
            or (db_job.company.lower().strip(), db_job.title.lower().strip()) in fresh_signatures
        )
        if not is_still_present:
            if db_job.is_active:
                db_job.is_active = False
                await db_job.save()
                delisted_count += 1
        else:
            if not db_job.is_active:
                db_job.is_active = True
                await db_job.save()
                relisted_count += 1
            fj_match = next(
                (fj for fj in fresh_jobs if fj.external_id and fj.external_id == db_job.external_id),
                None,
            )
            if fj_match and getattr(fj_match, "work_mode", None) and fj_match.work_mode != getattr(db_job, "work_mode", None):
                db_job.work_mode = fj_match.work_mode
                await db_job.save()

    # ── 6. Upsert new jobs — external_id dedup within source ─────────────────
    inserted_count = 0
    for fj in fresh_jobs:
        # Final safety: never store a job without a real apply link
        if not _is_real_url(fj.application_url):
            logger.warning(f"Sync: skipping upsert for '{fj.title}' — application_url not a real URL")
            continue
        if fj.external_id:
            existing = await Job.find_one(Job.external_id == fj.external_id)
        else:
            existing = await Job.find_one(
                Job.title == fj.title,
                Job.company == fj.company,
            )
        if not existing:
            await fj.insert()
            inserted_count += 1

    logger.info(
        f"Sync complete. fresh={len(fresh_jobs)}, inserted={inserted_count}, "
        f"delisted={delisted_count}, relisted={relisted_count}"
    )
    return {
        "message": "Jobs synced successfully",
        "total_fresh": len(fresh_jobs),
        "inserted": inserted_count,
        "delisted": delisted_count,
        "relisted": relisted_count,
        "used_mock_fallback": used_mock,
        "providers": provider_status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/jobs/match — trigger batch matching for current user
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/match")
@router.post("/match/run")
async def trigger_job_matching(
    current_user: str = Depends(get_current_user),
):
    """
    Compute keyword-overlap match scores between user resume and active jobs.
    """
    resume_version, candidate_skills = await _extract_candidate_skills(current_user)

    if resume_version is None:
        return {"triggered": False, "reason": "no_resume", "total_jobs": 0}

    all_jobs = await Job.find_all().to_list()

    if not all_jobs:
        seeded = await mock_provider.fetch_jobs(limit=50)
        for job in seeded:
            await job.insert()
        all_jobs = await Job.find_all().to_list()

    current_jobs = [j for j in all_jobs if _is_job_current_and_upcoming(j)]

    scored = 0
    for job in current_jobs:
        score, matched, missing = _score_resume_against_job(
            candidate_skills,
            job.required_skills,
        )

        job_id = str(job.id)

        existing = await UserJobMatch.find_one(
            UserJobMatch.user_id == current_user,
            UserJobMatch.job_id == job_id,
        )
        if existing:
            await existing.delete()

        match_doc = UserJobMatch(
            user_id=current_user,
            job_id=job_id,
            match_score=score,
            matched_skills=matched,
            missing_skills=missing,
            resume_version=resume_version,
            computed_at=datetime.now(),
        )
        await match_doc.insert()
        scored += 1

    logger.info(f"Batch match complete for {current_user}: {scored} active jobs scored")
    return {"triggered": True, "total_jobs": scored, "resume_version": resume_version}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/match/status — polling status for frontend
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/match/status")
async def get_match_status(
    current_user: str = Depends(get_current_user),
):
    resume_doc = await Resume.find_one(Resume.user_id == current_user)

    if not resume_doc:
        return {"status": "no_resume", "match_count": 0}

    resume_version = resume_doc.resume_version

    match_count = await UserJobMatch.find(
        UserJobMatch.user_id == current_user,
        UserJobMatch.resume_version == resume_version,
    ).count()

    if match_count == 0:
        return {
            "status": "computing",
            "match_count": 0,
            "resume_version": resume_version,
        }

    return {
        "status": "ready",
        "match_count": match_count,
        "resume_version": resume_version,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/recommended — enriched sorted results
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/recommended")
async def get_recommended_jobs(
    min_score: int = Query(0, ge=0, le=100, description="Minimum match score filter (0 = return all)"),
    limit: int = Query(50, ge=1, le=100),
    current_user: str = Depends(get_current_user),
):
    """
    Return enriched, score-sorted job matches for current user.
    Only returns current and upcoming active jobs.
    """
    resume_version, _ = await _extract_candidate_skills(current_user)
    if not resume_version:
        return []

    matches = await UserJobMatch.find(
        UserJobMatch.user_id == current_user,
        UserJobMatch.resume_version == resume_version,
        UserJobMatch.match_score >= min_score,
    ).to_list()

    matches.sort(key=lambda m: m.match_score, reverse=True)
    matches = matches[:limit]

    results = []
    seen_job_ids = set()
    for match in matches:
        if match.job_id in seen_job_ids:
            continue
        try:
            from beanie import PydanticObjectId
            job = await Job.get(PydanticObjectId(match.job_id))
            if not job or not _is_job_current_and_upcoming(job):
                continue
        except Exception:
            continue

        seen_job_ids.add(match.job_id)
        # normalize_job_item now returns None if no direct apply URL exists
        raw_for_norm = {
            "job_title": job.title,
            "employer_name": job.company,
            "location": job.location,
            "job_apply_link": job.application_url,
            "apply_url": job.application_url,
        }
        norm_result = normalize_job_item(raw_for_norm, source=job.source)
        if not norm_result:
            # No direct apply URL — discard under strict rule
            continue
        apply_url_resolved = norm_result.get("apply_url", "")

        # Extra safety guard (should already be filtered by normalize_job_item)
        if not apply_url_resolved or not apply_url_resolved.startswith("http"):
            continue

        results.append(
            {
                "job_id": match.job_id,
                "match_score": match.match_score,
                "matched_skills": match.matched_skills,
                "missing_skills": match.missing_skills,
                "computed_at": match.computed_at.isoformat() if match.computed_at else None,
                "job": {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "description": job.description,
                    "required_skills": job.required_skills,
                    # apply_url — unified field; frontend reads ONLY this
                    "apply_url": apply_url_resolved,
                    # application_url kept for backward compat (older cached clients)
                    "application_url": apply_url_resolved,
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                    "deadline": job.deadline.isoformat() if job.deadline else None,
                    "is_active": job.is_active,
                    "work_mode": getattr(job, "work_mode", "onsite"),
                    "source": job.source,
                },
            }
        )

    return results


@router.post("/admin")
async def create_admin_job(
    job_data: JobCreate,
    current_user: str = Depends(get_current_user)
):
    """
    Manually create a job posting (Admin).
    application_url is required for applyable jobs. Optional deadline supported.
    """
    new_job = Job(
        title=job_data.title,
        company=job_data.company,
        description=job_data.description,
        required_skills=job_data.required_skills,
        location=job_data.location,
        source="manual",
        application_url=job_data.application_url,
        deadline=job_data.deadline,
        is_active=True,
    )
    await new_job.insert()
    return {"message": "Job created successfully", "job_id": str(new_job.id)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/today — normalised live feed from all active providers
# Returns flat dicts with verified direct apply_url for every card.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today_jobs(
    query: str = Query("software intern", description="Search term for job title or skills"),
    location: str = Query("India", description="Target location"),
    limit: int = Query(30, ge=1, le=100, description="Max results"),
    current_user: str = Depends(get_current_user),
):
    """
    Fetch a fresh, normalised list of today's live job postings from all active providers.

    Provider order (same as /sync priority):
      1. Arbeitnow (native ATS links, no auth)
      2. Adzuna (ADZUNA_APP_ID/KEY)
      3. Remotive (free, no auth)
      4. JSearch (RAPIDAPI_KEY)
      5. Himalayas (free, no auth — yields 0: internal board URLs)
      6. Jooble (JOOBLE_API_KEY)
      7. CareerOneStop (CAREERONESTOP credentials)

    Strict direct-link rule: only jobs with a real direct apply URL are included.
    No Google Search fallback is ever generated. Jobs without a real URL are discarded.
    """
    jobs_list: list = []
    seen_sigs: set = set()

    async def _fetch_and_normalise(provider, name: str, **kwargs):
        """Fetch jobs from a provider and normalise into flat dicts for the today feed."""
        try:
            fetched = await provider.fetch_jobs(**kwargs)
            added = 0
            for job in fetched:
                sig = f"{job.title.lower().strip()}|{job.company.lower().strip()}"
                if sig in seen_sigs:
                    continue
                # Jobs from providers already have application_url validated;
                # re-run through normalize_job_item to get the flat dict shape
                raw = {
                    "job_title": job.title,
                    "employer_name": job.company,
                    "location": job.location,
                    "job_apply_link": job.application_url,
                    "apply_url": job.application_url,
                    "source": job.source,
                }
                norm = normalize_job_item(raw, source=name)
                if norm:  # None means no valid direct URL — discard
                    jobs_list.append(norm)
                    seen_sigs.add(sig)
                    added += 1
            logger.info(f"GET /jobs/today: {added} from {name}")
        except Exception as e:
            logger.error(f"GET /jobs/today {name} error: {e}")

    # Priority order: Arbeitnow first
    await _fetch_and_normalise(arbeitnow_provider, "Arbeitnow", limit=limit)
    await _fetch_and_normalise(adzuna_provider, "Adzuna", query=query, location=location, limit=limit)
    await _fetch_and_normalise(remotive_provider, "Remotive", query=query, limit=limit)
    await _fetch_and_normalise(jsearch_provider, "JSearch", query=query or "software intern", location=location or "India", limit=limit)
    await _fetch_and_normalise(himalayas_provider, "Himalayas", limit=limit)
    await _fetch_and_normalise(jooble_provider, "Jooble", query=query, location=location, limit=limit)
    await _fetch_and_normalise(careeronestop_provider, "CareerOneStop", query=query, location=location, limit=limit)

    # Mock fallback if all live sources returned nothing
    if not jobs_list:
        logger.info("GET /jobs/today: no live results — returning mock fallback")
        mock_jobs = await mock_provider.fetch_jobs(query=query, location=location, limit=limit)
        for mj in mock_jobs:
            if mj.application_url and mj.application_url.startswith("http"):
                jobs_list.append({
                    "job_title": mj.title,
                    "company_name": mj.company,
                    "location": mj.location,
                    "source": "Mock",
                    "apply_url": mj.application_url,
                })

    return {
        "status": "success",
        "count": len(jobs_list),
        "data": jobs_list[:limit],
    }
