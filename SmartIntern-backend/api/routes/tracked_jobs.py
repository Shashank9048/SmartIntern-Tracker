from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal, List, Optional
from datetime import datetime
import logging

from ..models import TrackedJob, Job, UserJobMatch
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tracked-jobs", tags=["TrackedJobs"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response shapes
# ─────────────────────────────────────────────────────────────────────────────

class TrackedJobCreate(BaseModel):
    job_id: str
    status: Literal[
        "wishlist", "applied", "oa", "interview", "offer", "rejected"
    ] = "wishlist"


class TrackedJobStatusUpdate(BaseModel):
    status: Literal[
        "wishlist", "applied", "oa", "interview", "offer", "rejected"
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build enriched response dict for a TrackedJob
# ─────────────────────────────────────────────────────────────────────────────

async def _enrich(tracked: TrackedJob) -> dict:
    """Return a TrackedJob doc enriched with the job's title/company/location."""
    job_title = "Unknown Role"
    job_company = "Unknown Company"
    job_location = "Unknown Location"

    try:
        from beanie import PydanticObjectId
        job = await Job.get(PydanticObjectId(tracked.job_id))
        if job:
            job_title = job.title
            job_company = job.company
            job_location = job.location
    except Exception as e:
        logger.warning(f"Could not enrich tracked job {tracked.id}: {e}")

    return {
        "_id": str(tracked.id),
        "job_id": tracked.job_id,
        "status": tracked.status,
        "match_score_at_save": tracked.match_score_at_save,
        "applied_at": tracked.applied_at.isoformat() if tracked.applied_at else None,
        "updated_at": tracked.updated_at.isoformat() if tracked.updated_at else None,
        "job": {
            "title": job_title,
            "company": job_company,
            "location": job_location,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/tracked-jobs  — create or return existing record
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_tracked_job(
    body: TrackedJobCreate,
    current_user: str = Depends(get_current_user),
):
    """
    Phase 6B: Track a job from the recommended feed.
    Idempotent — returns the existing TrackedJob if already tracked.
    Locks match_score_at_save from the current UserJobMatch score.
    """
    # Validate the Job exists
    try:
        from beanie import PydanticObjectId
        job = await Job.get(PydanticObjectId(body.job_id))
    except Exception:
        job = None

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {body.job_id} not found")

    # Idempotency: return existing if already tracked by this user
    existing = await TrackedJob.find_one(
        TrackedJob.user_id == current_user,
        TrackedJob.job_id == body.job_id,
    )
    if existing:
        return await _enrich(existing)

    # Lock match score from UserJobMatch (0 if not computed yet)
    match_score = 0
    match_doc = await UserJobMatch.find_one(
        UserJobMatch.user_id == current_user,
        UserJobMatch.job_id == body.job_id,
    )
    if match_doc:
        match_score = match_doc.match_score

    tracked = TrackedJob(
        user_id=current_user,
        job_id=body.job_id,
        status=body.status,
        match_score_at_save=match_score,
    )
    await tracked.insert()

    logger.info(f"Tracked job {body.job_id} for {current_user} as '{body.status}'")
    return await _enrich(tracked)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/tracked-jobs  — list all tracked jobs for the user
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_tracked_jobs(current_user: str = Depends(get_current_user)):
    """
    Phase 6B: Return all TrackedJobs for the current user,
    each enriched with the real job title/company/location.
    """
    tracked_docs = await TrackedJob.find(
        TrackedJob.user_id == current_user
    ).sort(-TrackedJob.applied_at).to_list()

    results = []
    for doc in tracked_docs:
        results.append(await _enrich(doc))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/tracked-jobs/{id}  — update status (drag-and-drop)
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{id}")
async def update_tracked_job_status(
    id: str,
    body: TrackedJobStatusUpdate,
    current_user: str = Depends(get_current_user),
):
    """
    Phase 6B: Update the status of a tracked job (called by kanban drag-and-drop).
    """
    try:
        from beanie import PydanticObjectId
        tracked = await TrackedJob.get(PydanticObjectId(id))
    except Exception:
        tracked = None

    if not tracked or tracked.user_id != current_user:
        raise HTTPException(status_code=404, detail="TrackedJob not found or unauthorized")

    tracked.status = body.status
    tracked.updated_at = datetime.now()
    await tracked.save()

    logger.info(f"TrackedJob {id} status updated to '{body.status}' for {current_user}")
    return await _enrich(tracked)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/tracked-jobs/{id}  — remove from tracker
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{id}")
async def delete_tracked_job(
    id: str,
    current_user: str = Depends(get_current_user),
):
    try:
        from beanie import PydanticObjectId
        tracked = await TrackedJob.get(PydanticObjectId(id))
    except Exception:
        tracked = None

    if not tracked or tracked.user_id != current_user:
        raise HTTPException(status_code=404, detail="TrackedJob not found or unauthorized")

    await tracked.delete()
    return {"message": "TrackedJob deleted", "id": id}
