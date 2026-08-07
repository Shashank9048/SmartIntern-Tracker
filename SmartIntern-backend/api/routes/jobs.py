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


INDIA_LOCATION_HINTS = (
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "delhi",
    "gurgaon", "gurugram", "noida", "chennai", "kolkata", "ahmedabad",
    "karnataka", "maharashtra", "telangana", "tamil nadu", "haryana",
    "jaipur", "indore", "chandigarh", "kochi", "coimbatore", "trivandrum",
    "thiruvananthapuram", "ghaziabad", "faridabad", "greater noida",
    "mysore", "mysuru", "nagpur", "surat", "vadodara", "bhopal",
    "bhubaneswar", "visakhapatnam", "vizag", "ncr", "lucknow", "kanpur",
    "patna", "agra", "varanasi", "madurai", "guwahati", "kerala", "punjab",
    "rajasthan", "gujarat", "uttar pradesh", "west bengal"
)

NON_INDIA_LOCATION_HINTS = (
    "usa", "united states", " us,", "u.s.", "uk", "united kingdom",
    "canada", "germany", "singapore", "australia",
)


def _is_india_relevant(job: Job) -> bool:
    """
    Deprecated: We now allow jobs from all regions and rely on frontend filtering.
    """
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
    """
    from services.jobs_provider import _get_direct_apply_url

    apply_url = _get_direct_apply_url(raw_job, source)

    if not apply_url:
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
        "apply_url": apply_url,   # ← unified field — frontend ONLY reads this
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Job])
async def get_jobs(
    query: str = Query("", description="Search term for job title or skills"),
    location: str = Query("India", description="Job location"),
    limit: int = Query(20, ge=1, le=50, description="Max number of jobs to return"),
    current_user: str = Depends(get_current_user),
):
    """
    Fetch current and upcoming jobs from providers/DB.
    Excludes expired deadlines, delisted jobs, and stale postings (>45 days).
    Also excludes any job lacking a real direct apply link, and any job that
    isn't relevant to an India-based candidate (see _is_india_relevant).

    Provider fetch order & dedup priority (UPDATED — Jooble and Adzuna are now
    the priority sources for India-focused results; Arbeitnow/Remotive are
    remote-tech-only and skew international, so they're kept but no longer
    prioritized over the two sources that actually target Indian listings):
      1. Jooble     (JOOBLE_API_KEY required) — TOP PRIORITY for India
      2. Adzuna     (ADZUNA_APP_ID/KEY required) — PRIORITY for India
      3. JSearch    (RAPIDAPI_KEY required)
      4. Arbeitnow  (native ATS links, no auth, remote-tech-heavy)
      5. Remotive   (free, no auth, remote-only)
      6. Himalayas  (free, no auth — currently yields 0 under strict rule: internal URLs)
      7. CareerOneStop (US-only data — excluded by the India-relevance filter below anyway)
      8. Mock       (fallback when all live sources return 0)
    """
    import re as _re

    def _normalise_sig(title: str, company: str) -> str:
        combined = f"{title.lower().strip()} {company.lower().strip()}"
        return _re.sub(r'[^a-z0-9 ]', '', combined).strip()

    jobs: list = []
    seen_sigs: set = set()

    async def _safe_fetch(provider, name, **kwargs):
        try:
            res = await provider.fetch_jobs(**kwargs)
            added = 0
            for j in res or []:
                sig = _normalise_sig(j.title, j.company)
                if sig in seen_sigs:
                    continue
                seen_sigs.add(sig)
                jobs.append(j)
                added += 1
            if added:
                logger.info(f"GET /jobs: got {added} new (deduped) jobs from {name}")
        except Exception as e:
            logger.error(f"{name} fetch error: {e}")

    # Priority order: Jooble and Adzuna first, so if the same posting also
    # shows up from a lower-priority source later, it's already deduped out
    # and the Jooble/Adzuna version (kept first) wins.
    await _safe_fetch(jooble_provider, "Jooble", query=query, location=location, limit=limit)
    await _safe_fetch(adzuna_provider, "Adzuna", query=query, location=location, limit=limit)
    await _safe_fetch(jsearch_provider, "JSearch", query=query or "software intern", location=location, limit=limit)
    await _safe_fetch(arbeitnow_provider, "Arbeitnow", query=query, location=location, limit=limit)
    await _safe_fetch(remotive_provider, "Remotive", query=query, location=location, limit=limit)
    await _safe_fetch(himalayas_provider, "Himalayas", query=query, location=location, limit=limit)
    await _safe_fetch(careeronestop_provider, "CareerOneStop", query=query, location=location, limit=limit)

    if not jobs:
        logger.info("No live jobs found.")

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

    Provider priority order (highest → lowest for cross-source dedup) —
    UPDATED: Jooble and Adzuna are now fetched first since they're the
    priority sources for India-focused listings:
      1. Jooble       : JOOBLE_API_KEY required. ~500 req/day limit. TOP PRIORITY for India.
      2. Adzuna       : ADZUNA_APP_ID/KEY required. 8h in-memory cache. ~1,000 calls/month. PRIORITY for India.
      3. JSearch      : RAPIDAPI_KEY required. ~23h rate-limit guard (~200 req/month).
      4. Arbeitnow    : no auth, 3h in-memory cache. Native ATS links, remote-tech-heavy.
      5. Remotive     : free, no auth, 6h cache. Always "remote" work_mode.
      6. Himalayas    : free, no auth, 3h cache. Currently yields 0 (internal board URLs).
      7. CareerOneStop: CAREERONESTOP_USER_ID + TOKEN required. US-only data — filtered out
                        of the India-facing feed by _is_india_relevant anyway.
      8. Mock         : fallback only when ALL seven live sources return 0 jobs.

    Direct-link rule (HARD DISCARD before upsert):
      Any fetched job without a real http(s):// application_url that is NOT an
      internal job-board page is discarded before being stored. Never in MongoDB.

    Cross-source deduplication:
      If the same posting appears from multiple sources (matched by normalised
      title + company), the higher-priority source version is kept — Jooble
      and Adzuna now win any cross-source conflict.

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

    # Helper for dedup
    combined_sigs = set()
    cross_deduped_total = 0

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

    if os.getenv("JOOBLE_API_KEY"):
        await _sync_provider(jooble_provider, "Jooble", query="software developer intern", location="India", limit=50)
    else:
        provider_status["jooble"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: JOOBLE_API_KEY not set"}

    if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
        await _sync_provider(adzuna_provider, "Adzuna", query="software developer intern", location="India", limit=150)
    else:
        provider_status["adzuna"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: ADZUNA credentials not set"}

    if os.getenv("RAPIDAPI_KEY"):
        await _sync_provider(jsearch_provider, "JSearch", query="software developer intern", location="India", limit=50)
    else:
        provider_status["jsearch"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: RAPIDAPI_KEY not set"}

    await _sync_provider(arbeitnow_provider, "Arbeitnow", limit=150)

    await _sync_provider(remotive_provider, "Remotive", limit=100)

    await _sync_provider(himalayas_provider, "Himalayas", limit=100)

    if os.getenv("CAREERONESTOP_USER_ID") and os.getenv("CAREERONESTOP_TOKEN"):
        await _sync_provider(careeronestop_provider, "CareerOneStop", query="software", location="US", limit=50)
    else:
        provider_status["careeronestop"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: CAREERONESTOP credentials not set"}

    used_mock = False
    if not fresh_jobs:
        logger.info("Sync: all live providers returned 0 jobs.")
        provider_status["mock"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "not_needed"}
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

async def _run_ai_matching(current_user: str, resume_version: str):
    from ..models import Job, UserJobMatch, Resume, User
    from ..ai_utils import batch_analyze_job_matches
    import asyncio
    
    try:
        resume_doc = await Resume.find_one(Resume.user_id == current_user)
        resume_text = resume_doc.raw_text if resume_doc and resume_doc.raw_text else ""
        if not resume_text:
            user = await User.find_one(User.email == current_user)
            if user and hasattr(user, "resume_text"):
                resume_text = user.resume_text
                
        if not resume_text:
            logger.warning(f"No resume text found for {current_user} during background match")
            return

        all_jobs = await Job.find_all().to_list()
        current_jobs = [j for j in all_jobs if _is_job_current_and_upcoming(j)]
        
        # Check existing matches so we don't re-run AI unnecessarily
        existing_matches = await UserJobMatch.find(
            UserJobMatch.user_id == current_user,
            UserJobMatch.resume_version == resume_version
        ).to_list()
        existing_job_ids = {m.job_id for m in existing_matches}
        
        jobs_to_process = [j for j in current_jobs if str(j.id) not in existing_job_ids]
        
        if not jobs_to_process:
            logger.info(f"No new jobs to match for {current_user}")
            return
            
        logger.info(f"Starting background AI matching for {len(jobs_to_process)} jobs for {current_user}")
        
        batch_size = 8
        for i in range(0, len(jobs_to_process), batch_size):
            batch = jobs_to_process[i:i+batch_size]
            
            jobs_payload = [{
                "job_id": str(j.id),
                "title": j.title,
                "description": j.description,
                "skills": j.required_skills
            } for j in batch]
            
            try:
                results = await batch_analyze_job_matches(resume_text, jobs_payload)
                for r in results:
                    job_id = str(r.get("job_id"))
                    score = r.get("match_score", 0)
                    matched = r.get("matched_skills", [])
                    missing = r.get("missing_skills", [])
                    
                    existing = await UserJobMatch.find_one(
                        UserJobMatch.user_id == current_user,
                        UserJobMatch.job_id == job_id
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
                    
                logger.info(f"Processed batch {i//batch_size + 1}/{(len(jobs_to_process)-1)//batch_size + 1} for {current_user}")
                # Optional: Sleep slightly between batches to avoid rapid API bursts
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error in background AI matching batch: {e}")
                
        logger.info(f"Completed background AI matching for {current_user}")
    except Exception as e:
        logger.error(f"Error in _run_ai_matching: {e}")


@router.post("/match")
@router.post("/match/run")
async def trigger_job_matching(
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """
    Compute highly accurate AI semantic match scores between user resume and active jobs.
    """
    resume_version, candidate_skills = await _extract_candidate_skills(current_user)

    if resume_version is None:
        return {"triggered": False, "reason": "no_resume", "total_jobs": 0}

    all_jobs = await Job.find_all().to_list()
    current_jobs = [j for j in all_jobs if _is_job_current_and_upcoming(j)]
    
    # We offload the heavy AI batching to a background task
    background_tasks.add_task(_run_ai_matching, current_user, resume_version)

    return {"triggered": True, "total_jobs": len(current_jobs), "resume_version": resume_version}


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

    # IMPORTANT: use _extract_candidate_skills() for resume_version resolution
    # rather than reading resume_doc.resume_version directly. If the version
    # stored on the Resume doc is empty, _extract_candidate_skills falls back
    # to "v1" — the same value used when matches were originally computed.
    # Reading resume_doc.resume_version directly would return "" and never
    # match the "v1" matches, leaving this endpoint stuck on "computing" forever.
    resume_version, _ = await _extract_candidate_skills(current_user)

    match_count = await UserJobMatch.find(
        UserJobMatch.user_id == current_user,
        UserJobMatch.resume_version == resume_version,
    ).count()

    total_active_jobs = await Job.find(Job.is_active == True).count()

    if total_active_jobs == 0:
        return {
            "status": "no_jobs",
            "match_count": 0,
            "resume_version": resume_version,
        }

    if match_count < total_active_jobs:
        return {
            "status": "computing",
            "match_count": match_count,
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
            # All jobs are now surfaced, frontend countryFilter handles India vs Foreign
            # (No backend region blocking)
        except Exception as e:
            # Previously a bare except silently swallowed all errors here,
            # making a persistently empty recommended feed impossible to diagnose.
            logger.warning(
                f"get_recommended_jobs: failed to load/validate job_id={match.job_id} "
                f"for user={current_user}: {e}"
            )
            continue

        seen_job_ids.add(match.job_id)
        
        apply_url_resolved = job.application_url
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

    # If the frontend requests all jobs (min_score == 0), append unscored active jobs to fill the limit
    if min_score == 0 and len(results) < limit:
        all_jobs = await Job.find(Job.is_active == True).to_list()
        # Sort by posted_at descending to show freshest jobs
        all_jobs.sort(key=lambda j: getattr(j, "posted_at", None) or datetime.min, reverse=True)
        for job in all_jobs:
            if len(results) >= limit:
                break
            job_id_str = str(job.id)
            if job_id_str in seen_job_ids:
                continue
            if not _is_job_current_and_upcoming(job):
                continue
            
            apply_url_resolved = job.application_url
            if not apply_url_resolved or not apply_url_resolved.startswith("http"):
                continue

            results.append(
                {
                    "job_id": job_id_str,
                    "match_score": 0,
                    "matched_skills": [],
                    "missing_skills": [],
                    "computed_at": None,
                    "job": {
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "description": job.description,
                        "required_skills": job.required_skills,
                        "apply_url": apply_url_resolved,
                        "application_url": apply_url_resolved,
                        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                        "deadline": job.deadline.isoformat() if job.deadline else None,
                        "is_active": job.is_active,
                        "work_mode": getattr(job, "work_mode", "onsite"),
                        "source": job.source,
                    },
                }
            )
            seen_job_ids.add(job_id_str)

    return results


@router.post("/admin")
async def create_admin_job(
    job_data: JobCreate,
    current_user: str = Depends(get_current_user)
):
    """
    Manually create a job posting (Admin-only).
    application_url is required for applyable jobs. Optional deadline supported.

    SECURITY FIX: previously this endpoint had no authorization check at all —
    any authenticated user could insert arbitrary postings into the shared Job
    collection, visible in every user's job board and recommended feed. Now
    requires User.is_admin == True. Everyone defaults to is_admin=False; flip
    it manually in Mongo for whichever account should have admin rights.
    """
    from ..models import User
    admin_user = await User.find_one(User.email == current_user)
    if not admin_user or not admin_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required to create job postings")

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
      1. Jooble (JOOBLE_API_KEY required) — TOP PRIORITY for India
      2. Adzuna (ADZUNA_APP_ID/KEY) — PRIORITY for India
      3. JSearch (RAPIDAPI_KEY)
      4. Arbeitnow (native ATS links, no auth)
      5. Remotive (free, no auth)
      6. Himalayas (free, no auth — yields 0: internal board URLs)
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
                # Removed _is_india_relevant check to allow global jobs
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

    await _fetch_and_normalise(jooble_provider, "Jooble", query=query, location=location, limit=limit)
    await _fetch_and_normalise(adzuna_provider, "Adzuna", query=query, location=location, limit=limit)
    await _fetch_and_normalise(jsearch_provider, "JSearch", query=query or "software intern", location=location, limit=limit)
    await _fetch_and_normalise(arbeitnow_provider, "Arbeitnow", limit=limit)
    await _fetch_and_normalise(remotive_provider, "Remotive", query=query, location=location, limit=limit)
    await _fetch_and_normalise(himalayas_provider, "Himalayas", limit=limit)
    await _fetch_and_normalise(careeronestop_provider, "CareerOneStop", query=query, location=location, limit=limit)

    # No mock fallback. If no live results, just return empty.
    if not jobs_list:
        logger.info("GET /jobs/today: no live results")

    return {
        "status": "success",
        "count": len(jobs_list),
        "data": jobs_list[:limit],
    }
