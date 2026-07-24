import os
import hashlib
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from ..models import Job, Resume, UserJobMatch
from ..auth import get_current_user
from services.jobs_provider import MockJobsProvider, AdzunaProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

mock_provider = MockJobsProvider()
adzuna_provider = AdzunaProvider()

class JobCreate(BaseModel):
    title: str
    company: str
    description: str
    required_skills: List[str]
    location: str
    application_url: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(skill: str) -> str:
    """Lower-case, strip whitespace for case-insensitive comparison."""
    return skill.strip().lower()


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
    Load the user's Resume doc and extract their skills list + resume_version.
    Returns (resume_version, skills_list) or (None, []) if no resume.
    """
    resume_doc = await Resume.find_one(Resume.user_id == user_email)
    if not resume_doc:
        return None, []

    # Prefer parsed_json.skills (structured), fall back to raw_text keywords
    parsed = resume_doc.parsed_json or {}
    skills: List[str] = parsed.get("skills", [])

    # If parsed_json has no skills, try to extract tokens from raw_text
    if not skills and resume_doc.raw_text:
        # Simple heuristic: split on commas/newlines, take tokens 2-25 chars
        tokens = []
        for tok in resume_doc.raw_text.replace(",", "\n").split("\n"):
            t = tok.strip()
            if 2 <= len(t) <= 25:
                tokens.append(t)
        skills = tokens[:80]  # cap at 80 to avoid runaway lists

    return resume_doc.resume_version, skills


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs  (Phase 3 — unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Job])
async def get_jobs(
    query: str = Query("", description="Search term for job title or skills"),
    location: str = Query("", description="Job location"),
    limit: int = Query(20, ge=1, le=50, description="Max number of jobs to return"),
    current_user: str = Depends(get_current_user),
):
    """
    Phase 3: Fetch jobs from providers.
    Uses AdzunaProvider if configured, otherwise falls back to MockJobsProvider.
    """
    jobs = []
    if adzuna_provider.app_id and adzuna_provider.app_key:
        try:
            jobs = await adzuna_provider.fetch_jobs(query=query, location=location, limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch from AdzunaProvider: {e}")
            jobs = []

    if not jobs:
        logger.info("Falling back to MockJobsProvider")
        jobs = await mock_provider.fetch_jobs(query=query, location=location, limit=limit)

    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/jobs/match  — trigger batch matching for current user (Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/match")
async def trigger_job_matching(
    current_user: str = Depends(get_current_user),
):
    """
    Phase 5: Compute keyword-overlap match scores between the user's resume
    and every Job in the database, upsert UserJobMatch records.
    """
    resume_version, candidate_skills = await _extract_candidate_skills(current_user)

    if resume_version is None:
        return {"triggered": False, "reason": "no_resume", "total_jobs": 0}

    # Load all jobs (mock or DB-persisted)
    all_jobs = await Job.find_all().to_list()

    if not all_jobs:
        # Seed from mock provider if DB is empty
        seeded = await mock_provider.fetch_jobs(limit=50)
        for job in seeded:
            await job.insert()
        all_jobs = await Job.find_all().to_list()

    scored = 0
    for job in all_jobs:
        score, matched, missing = _score_resume_against_job(
            candidate_skills,
            job.required_skills,
        )

        job_id = str(job.id)

        # Upsert: delete old record then insert fresh one
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

    logger.info(f"Batch match complete for {current_user}: {scored} jobs scored")
    return {"triggered": True, "total_jobs": scored, "resume_version": resume_version}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/jobs/match/status  — polling status for the frontend (Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/match/status")
async def get_match_status(
    current_user: str = Depends(get_current_user),
):
    """
    Phase 5: Returns the current state of job matching for this user.
    status: 'no_resume' | 'computing' | 'ready'
    """
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
# GET /api/jobs/recommended  — enriched sorted results (Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/recommended")
async def get_recommended_jobs(
    min_score: int = Query(0, ge=0, le=100, description="Minimum match score filter (0 = return all)"),
    limit: int = Query(50, ge=1, le=100),
    current_user: str = Depends(get_current_user),
):
    """
    Phase 5: Return enriched, score-sorted job matches for the current user.
    Joins UserJobMatch → Job and filters by min_score.
    """
    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if not resume_doc:
        return []

    matches = await UserJobMatch.find(
        UserJobMatch.user_id == current_user,
        UserJobMatch.resume_version == resume_doc.resume_version,
        UserJobMatch.match_score >= min_score,
    ).to_list()

    # Sort by match_score descending
    matches.sort(key=lambda m: m.match_score, reverse=True)
    matches = matches[:limit]

    results = []
    for match in matches:
        try:
            from beanie import PydanticObjectId
            job = await Job.get(PydanticObjectId(match.job_id))
            if not job:
                continue
        except Exception:
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
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                },
            }
        )

    return results
@router.post("/admin")
async def create_admin_job(
    job_data: JobCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually create a job posting (Admin).
    application_url is required for applyable jobs.
    """
    # Simple check for admin role can be added here if roles existed
    new_job = Job(
        title=job_data.title,
        company=job_data.company,
        description=job_data.description,
        required_skills=job_data.required_skills,
        location=job_data.location,
        source="manual",
        application_url=job_data.application_url
    )
    await new_job.insert()
    return {"message": "Job created successfully", "job_id": str(new_job.id)}
