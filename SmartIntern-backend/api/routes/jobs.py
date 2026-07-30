import os
import hashlib
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from ..models import Job, Resume, UserJobMatch
from ..auth import get_current_user
from services.jobs_provider import AdzunaProvider, MockJobsProvider, RemotiveProvider, JSearchProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

adzuna_provider = AdzunaProvider()
remotive_provider = RemotiveProvider()
jsearch_provider = JSearchProvider()
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

def normalize_job_item(raw_job: dict, source: str) -> dict:
    """
    Inspect a raw job dict from any provider and standardise it into a
    flat payload with a guaranteed non-empty apply_url.

    Priority order for the apply link:
      1. job_apply_link   — JSearch primary field
      2. url              — Remotive direct employer link
      3. apply_options[0]["apply_link"] — JSearch ATS deeplink (often cleaner)
      4. redirect_url     — reserved for future providers
      5. apply_url        — custom scraped sources
      6. Google-search fallback — button is *never* broken
    """
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

    # Final fallback: Google search — the Apply button is NEVER broken
    if not apply_url or apply_url.strip() in ("", "Not specified"):
        company = (
            raw_job.get("employer_name") or
            raw_job.get("company_name") or
            raw_job.get("company") or
            ""
        ).replace(" ", "+")
        title = (
            raw_job.get("job_title") or
            raw_job.get("title") or
            "Job"
        ).replace(" ", "+")
        apply_url = f"https://www.google.com/search?q={company}+{title}+careers+apply"

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
    location: str = Query("", description="Job location"),
    limit: int = Query(20, ge=1, le=50, description="Max number of jobs to return"),
    current_user: str = Depends(get_current_user),
):
    """
    Fetch current and upcoming jobs from providers/DB.
    Excludes expired deadlines, delisted jobs, and stale postings (>45 days).
    Also excludes any job lacking a real direct apply link.
    Priority: Adzuna (primary) → Remotive → JSearch → Mock fallback.
    """
    jobs: list = []

    # 1. Adzuna (primary — most generous free tier, India tech roles)
    try:
        adzuna_jobs = await adzuna_provider.fetch_jobs(query=query, location=location, limit=limit)
        if adzuna_jobs:
            logger.info(f"GET /jobs: got {len(adzuna_jobs)} jobs from Adzuna")
            jobs.extend(adzuna_jobs)
    except Exception as e:
        logger.error(f"Adzuna fetch error: {e}")

    # 2. Remotive (free, no auth, cached 6h — remote-only tech roles)
    try:
        remotive_jobs = await remotive_provider.fetch_jobs(query=query, location=location, limit=limit)
        if remotive_jobs:
            logger.info(f"GET /jobs: got {len(remotive_jobs)} jobs from Remotive")
            jobs.extend(remotive_jobs)
    except Exception as e:
        logger.error(f"Remotive fetch error: {e}")

    # 3. JSearch supplement (rate-limited to ~1x/day, India local/on-site roles)
    try:
        jsearch_jobs = await jsearch_provider.fetch_jobs(
            query=query or "software intern", location=location or "India", limit=limit
        )
        if jsearch_jobs:
            logger.info(f"GET /jobs: got {len(jsearch_jobs)} jobs from JSearch")
            jobs.extend(jsearch_jobs)
    except Exception as e:
        logger.error(f"JSearch fetch error: {e}")

    # 4. Mock fallback (only when ALL live providers returned nothing)
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
    Sync fresh job listings from Adzuna (primary) + Remotive + JSearch.

    Provider details:
      - Adzuna    : ADZUNA_APP_ID/ADZUNA_APP_KEY required. Primary source. 8h in-memory cache.
                    Maps redirect_url → application_url. ~1,000 calls/month free tier.
      - Remotive  : free, no auth, 6-hour in-memory cache. Always "remote" work_mode.
                    Attribution badge required on card (rendered by frontend).
      - JSearch   : RAPIDAPI_KEY required, ~23-hour rate-limit guard (~200 req/month free tier).
                    Local/on-site India roles Adzuna/Remotive don't surface.
      - Mock      : fallback only when ALL three live sources return 0 jobs.

    Direct-link rule (HARD DISCARD before upsert):
      Any fetched job without a real http(s):// application_url is discarded before
      being stored — it is never inserted into MongoDB.

    Cross-source deduplication:
      If the same posting appears from multiple sources (matched by normalised
      title + company), the Adzuna version is kept and the duplicate is counted
      but not inserted.

    After upserting fresh jobs:
      - Jobs no longer returned by any provider are marked is_active=False (delisted).
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

    # ── 1. Adzuna (PRIMARY — synced first, most generous rate limit) ──────────
    adzuna_key_set = bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))
    if not adzuna_key_set:
        provider_status["adzuna"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "status": "skipped: ADZUNA_APP_ID/KEY not set"}
        logger.warning("Sync: Adzuna credentials not set — Adzuna skipped")
    else:
        try:
            adzuna_jobs = await adzuna_provider.fetch_jobs(
                query="software developer intern",
                location="India",
                limit=150,
            )
            # AdzunaProvider already hard-discards no-link jobs; count what came through
            valid_adzuna = [j for j in adzuna_jobs if _is_real_url(j.application_url)]
            fresh_jobs.extend(valid_adzuna)
            provider_status["adzuna"] = {
                "fetched": len(adzuna_jobs),
                "kept": len(valid_adzuna),
                "discarded_no_link": len(adzuna_jobs) - len(valid_adzuna),
                "status": "ok",
            }
            logger.info(f"Sync: kept {len(valid_adzuna)} from Adzuna")
        except Exception as e:
            provider_status["adzuna"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "status": f"error: {e}"}
            logger.error(f"Sync error from AdzunaProvider: {e}")

    # Build Adzuna signature set for cross-source dedup (Adzuna wins)
    adzuna_sigs = {
        _normalise_sig(j.title, j.company)
        for j in fresh_jobs
        if j.source == "adzuna"
    }

    # ── 2. Remotive (freely callable, 6h server-side cache, remote-only) ──────
    try:
        remotive_raw = await remotive_provider.fetch_jobs(limit=100)
        valid_remotive = [j for j in remotive_raw if _is_real_url(j.application_url)]
        # Cross-source dedup: drop if already covered by Adzuna
        deduped_remotive = []
        cross_deduped_r = 0
        for j in valid_remotive:
            sig = _normalise_sig(j.title, j.company)
            if sig in adzuna_sigs:
                cross_deduped_r += 1
            else:
                deduped_remotive.append(j)
        fresh_jobs.extend(deduped_remotive)
        provider_status["remotive"] = {
            "fetched": len(remotive_raw),
            "kept": len(deduped_remotive),
            "discarded_no_link": len(remotive_raw) - len(valid_remotive),
            "deduped_cross_source": cross_deduped_r,
            "status": "ok",
        }
        logger.info(f"Sync: kept {len(deduped_remotive)} from Remotive (cross-deduped {cross_deduped_r})")
    except Exception as e:
        provider_status["remotive"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": f"error: {e}"}
        logger.error(f"Sync error from RemotiveProvider: {e}")

    # ── 3. JSearch (RAPIDAPI_KEY, rate-limited ~23h, India local/on-site) ─────
    jsearch_key = os.getenv("RAPIDAPI_KEY")
    if not jsearch_key:
        provider_status["jsearch"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": "skipped: RAPIDAPI_KEY not set"}
        logger.warning("Sync: RAPIDAPI_KEY not set — JSearch skipped")
    else:
        try:
            jsearch_raw = await jsearch_provider.fetch_jobs(
                query="software developer intern",
                location="India",
                limit=50,
            )
            valid_jsearch = [j for j in jsearch_raw if _is_real_url(j.application_url)]
            # Cross-source dedup: Adzuna takes priority
            combined_sigs = adzuna_sigs | {
                _normalise_sig(j.title, j.company)
                for j in fresh_jobs
                if j.source == "remotive"
            }
            deduped_jsearch = []
            cross_deduped_j = 0
            for j in valid_jsearch:
                sig = _normalise_sig(j.title, j.company)
                if sig in combined_sigs:
                    cross_deduped_j += 1
                else:
                    deduped_jsearch.append(j)
            fresh_jobs.extend(deduped_jsearch)
            provider_status["jsearch"] = {
                "fetched": len(jsearch_raw),
                "kept": len(deduped_jsearch),
                "discarded_no_link": len(jsearch_raw) - len(valid_jsearch),
                "deduped_cross_source": cross_deduped_j,
                "status": "ok",
            }
            logger.info(f"Sync: kept {len(deduped_jsearch)} from JSearch (cross-deduped {cross_deduped_j})")
        except Exception as e:
            provider_status["jsearch"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "deduped_cross_source": 0, "status": f"error: {e}"}
            logger.error(f"Sync error from JSearchProvider: {e}")

    # ── 4. Mock fallback (only when ALL three live sources returned nothing) ───
    used_mock = False
    if not fresh_jobs:
        mock_jobs = await mock_provider.fetch_jobs(limit=50)
        fresh_jobs.extend(mock_jobs)
        used_mock = True
        provider_status["mock"] = {"fetched": len(mock_jobs), "kept": len(mock_jobs), "discarded_no_link": 0, "status": "fallback"}
        logger.info("Sync: all live providers returned 0 jobs — using mock fallback")
    else:
        provider_status["mock"] = {"fetched": 0, "kept": 0, "discarded_no_link": 0, "status": "not_needed"}

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
        raw_for_norm = {
            "job_title": job.title,
            "employer_name": job.company,
            "location": job.location,
            "job_apply_link": job.application_url,
            "apply_url": job.application_url,
        }
        apply_url_resolved = normalize_job_item(raw_for_norm, source=job.source).get("apply_url", "")

        # Skip if job has no real apply URL (hard-discard rule for recommended feed)
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
# GET /api/jobs/today — normalised live feed (JSearch + Remotive, NO Adzuna)
# Returns flat dicts with guaranteed apply_url for every card.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/today")
async def get_today_jobs(
    query: str = Query("software intern", description="Search term for job title or skills"),
    location: str = Query("India", description="Target location"),
    limit: int = Query(30, ge=1, le=100, description="Max results"),
    current_user: str = Depends(get_current_user),
):
    """
    Fetch a fresh, normalised list of today's live job postings from:
      - Adzuna API (ADZUNA_APP_ID/KEY required, 8h cache, primary source)
      - Remotive API (free, no auth, 6h cache)
      - JSearch via RapidAPI (RAPIDAPI_KEY required, 23h rate-limit guard)

    Every item in the response is guaranteed to have a non-empty apply_url
    (falls back to Google search for display-only cards — NOT persisted).
    Jobs without a real direct link are never stored in MongoDB via /sync.
    """
    import httpx

    jobs_list: list = []

    # ── 1. Adzuna (primary source — India tech roles) ────────────────
    adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY")
    if not adzuna_app_id or not adzuna_app_key:
        logger.warning("GET /jobs/today: ADZUNA_APP_ID/KEY not set — Adzuna skipped")
    else:
        try:
            adzuna_url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
            adzuna_params = {
                "app_id": adzuna_app_id,
                "app_key": adzuna_app_key,
                "what": query,
                "results_per_page": limit,
                "sort_by": "date",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(adzuna_url, params=adzuna_params)
                resp.raise_for_status()
                data = resp.json()
            for item in data.get("results", []):
                # For /today display path, use normalize_job_item which handles redirect_url
                norm = normalize_job_item(
                    {**item, "redirect_url": item.get("redirect_url", ""),
                     "title": item.get("title", ""),
                     "company_name": item.get("company", {}).get("display_name", ""),
                     "location": item.get("location", {}).get("display_name", "")},
                    source="Adzuna"
                )
                jobs_list.append(norm)
            logger.info(f"GET /jobs/today: got {len(data.get('results', []))} from Adzuna")
        except Exception as e:
            logger.error(f"GET /jobs/today Adzuna error: {e}")

    # ── 2. Remotive (free, no-auth) ─────────────────────────────────
    try:
        remotive_url = "https://remotive.com/api/remote-jobs"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(remotive_url, params={"category": "software-dev", "limit": limit})
            resp.raise_for_status()
            data = resp.json()
        for item in data.get("jobs", []):
            jobs_list.append(normalize_job_item(item, source="Remotive"))
        logger.info(f"GET /jobs/today: got {len(data.get('jobs', []))} from Remotive")
    except Exception as e:
        logger.error(f"GET /jobs/today Remotive error: {e}")

    # ── 3. JSearch via RapidAPI (requires RAPIDAPI_KEY) ────────────
    jsearch_key = os.getenv("RAPIDAPI_KEY")
    if not jsearch_key:
        logger.warning("GET /jobs/today: RAPIDAPI_KEY not set — JSearch skipped")
    else:
        try:
            search_q = query
            if location:
                search_q += f" in {location}"
            jsearch_url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                "X-RapidAPI-Key": jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    jsearch_url,
                    headers=headers,
                    params={"query": search_q, "num_pages": "1"},
                )
                resp.raise_for_status()
                data = resp.json()
            for item in data.get("data", [])[:limit]:
                jobs_list.append(normalize_job_item(item, source="JSearch"))
            logger.info(f"GET /jobs/today: got {len(data.get('data', []))} from JSearch")
        except Exception as e:
            logger.error(f"GET /jobs/today JSearch error: {e}")

    # ── 4. Mock fallback if all live sources returned nothing ─────────
    if not jobs_list:
        logger.info("GET /jobs/today: no live results — returning mock fallback")
        mock_jobs = await mock_provider.fetch_jobs(query=query, location=location, limit=limit)
        for mj in mock_jobs:
            raw = {
                "title": mj.title,
                "company_name": mj.company,
                "location": mj.location,
                "apply_url": mj.application_url or "",
            }
            jobs_list.append(normalize_job_item(raw, source="Mock"))

    return {
        "status": "success",
        "count": len(jobs_list),
        "data": jobs_list[:limit],
    }
