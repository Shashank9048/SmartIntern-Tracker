import os
import hashlib
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from ..models import Job, Resume, UserJobMatch
from ..auth import get_current_user
from services.jobs_provider import MockJobsProvider, RemotiveProvider, JSearchProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

mock_provider = MockJobsProvider()
remotive_provider = RemotiveProvider()
jsearch_provider = JSearchProvider()

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
    Priority: Remotive (no auth) → JSearch (rate-limited, daily) → Mock.
    """
    jobs: list = []

    # 1. Remotive (free, no auth, cached 6h)
    try:
        jobs = await remotive_provider.fetch_jobs(query=query, location=location, limit=limit)
        if jobs:
            logger.info(f"GET /jobs: got {len(jobs)} jobs from Remotive")
    except Exception as e:
        logger.error(f"Remotive fetch error: {e}")
        jobs = []

    # 2. JSearch supplement (rate-limited to 1x/day)
    try:
        jsearch_jobs = await jsearch_provider.fetch_jobs(query=query or "software intern", location=location or "India", limit=limit)
        if jsearch_jobs:
            logger.info(f"GET /jobs: got {len(jsearch_jobs)} jobs from JSearch")
            jobs = jobs + jsearch_jobs
    except Exception as e:
        logger.error(f"JSearch fetch error: {e}")

    # 3. Mock fallback
    if not jobs:
        logger.info("No live jobs — falling back to MockJobsProvider")
        jobs = await mock_provider.fetch_jobs(query=query, location=location, limit=limit)

    current_jobs = [j for j in jobs if _is_job_current_and_upcoming(j)]
    return current_jobs[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/jobs/sync — sync fresh jobs & mark delisted jobs inactive
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_jobs(
    current_user: str = Depends(get_current_user),
):
    """
    Sync fresh job listings from Remotive + JSearch.
    Marks jobs as is_active=False if they no longer appear in the fresh pull (delisted).
    """
    fresh_jobs: list = []

    # Remotive (freely callable)
    try:
        remotive_jobs = await remotive_provider.fetch_jobs(limit=100)
        fresh_jobs.extend(remotive_jobs)
        logger.info(f"Sync: got {len(remotive_jobs)} from Remotive")
    except Exception as e:
        logger.error(f"Sync error from RemotiveProvider: {e}")

    # JSearch (rate-limited)
    try:
        jsearch_jobs = await jsearch_provider.fetch_jobs(query="software intern", location="India", limit=50)
        fresh_jobs.extend(jsearch_jobs)
        logger.info(f"Sync: got {len(jsearch_jobs)} from JSearch")
    except Exception as e:
        logger.error(f"Sync error from JSearchProvider: {e}")

    # Fall back to mock if both live sources fail
    if not fresh_jobs:
        fresh_jobs = await mock_provider.fetch_jobs(limit=50)
        logger.info("Sync: using mock data fallback")

    fresh_external_ids = {j.external_id for j in fresh_jobs if j.external_id}
    fresh_signatures = {(j.company.lower().strip(), j.title.lower().strip()) for j in fresh_jobs}

    existing_db_jobs = await Job.find_all().to_list()
    delisted_count = 0
    updated_count = 0

    for db_job in existing_db_jobs:
        is_still_present = (
            (db_job.external_id and db_job.external_id in fresh_external_ids) or
            ((db_job.company.lower().strip(), db_job.title.lower().strip()) in fresh_signatures)
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
                updated_count += 1

    inserted_count = 0
    for fj in fresh_jobs:
        existing = await Job.find_one(
            (Job.external_id == fj.external_id) if fj.external_id else (Job.title == fj.title, Job.company == fj.company)
        )
        if not existing:
            await fj.insert()
            inserted_count += 1

    return {
        "message": "Jobs synced successfully",
        "total_fresh": len(fresh_jobs),
        "inserted": inserted_count,
        "delisted": delisted_count,
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
                    "application_url": job.application_url,
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                    "deadline": job.deadline.isoformat() if job.deadline else None,
                    "is_active": job.is_active,
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
