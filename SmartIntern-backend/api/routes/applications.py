from fastapi import APIRouter, HTTPException, Depends
from typing import List
from beanie import PydanticObjectId
from ..models import Application, User, ApplicationCreate, ApplicationUpdate
from ..auth import get_current_user
from ..ai_utils import analyze_resume_match
from datetime import datetime

router = APIRouter(prefix="/api/applications", tags=["Applications"])

@router.get("", response_model=List[Application])
async def get_apps(current_user: str = Depends(get_current_user)):
    return await Application.find(Application.user_id == current_user).sort(-Application.created_at).to_list()

@router.get("/{id}", response_model=Application)
async def get_app(id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    app = await Application.get(id)
    if not app or app.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@router.post("", response_model=Application)
async def create_app(app_data: ApplicationCreate, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    match_score = None
    experience_alignment = None
    summary = None
    missing_skills = []
    suggestions = []

    if user.resume_text:
        try:
            job_desc = app_data.job_description if app_data.job_description else f"{app_data.role} at {app_data.company_name}"
            analysis = await analyze_resume_match(user.resume_text, job_desc)
            match_score = analysis.get("overall_match_score", 0)
            experience_alignment = analysis.get("experience_alignment", "Low")
            summary = analysis.get("summary", "")
            missing_skills = analysis.get("missing_skills", [])
            suggestions = analysis.get("improvement_suggestions", [])
        except Exception as e:
            print(f"Background AI Score Error: {e}")

    new_app = Application(
        user_id=user.email,
        company_name=app_data.company_name,
        role=app_data.role,
        status=app_data.status,
        applied_date=app_data.applied_date,
        interview_date=app_data.interview_date,
        notes=app_data.notes,
        job_description=app_data.job_description,
        ai_match_score=match_score,
        ai_experience_alignment=experience_alignment,
        ai_summary=summary,
        ai_missing_skills=missing_skills,
        ai_suggestions=suggestions
    )
    await new_app.insert()
    return new_app

@router.patch("/{id}", response_model=Application)
async def update_app(id: PydanticObjectId, app_data: ApplicationUpdate, current_user: str = Depends(get_current_user)):
    app = await Application.get(id)
    if not app or app.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found or unauthorized")
    
    if app_data.company_name is not None: app.company_name = app_data.company_name
    if app_data.role is not None: app.role = app_data.role
    if app_data.status is not None: app.status = app_data.status
    if app_data.applied_date is not None: app.applied_date = app_data.applied_date
    if app_data.interview_date is not None: app.interview_date = app_data.interview_date
    if app_data.notes is not None: app.notes = app_data.notes

    app.updated_at = datetime.now()
    await app.save()
    return app

@router.delete("/{id}")
async def delete_app(id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    app = await Application.get(id)
    if not app or app.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
    await app.delete()
    return {"message": "Application deleted", "id": str(id)}


@router.post("/{id}/score", response_model=Application)
async def score_single_app(id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    """Compute or re-compute AI match score for a single application."""
    app = await Application.get(id)
    if not app or app.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")

    user = await User.find_one(User.email == current_user)
    if not user or not user.resume_text:
        raise HTTPException(
            status_code=400,
            detail="Please upload your resume first before scoring applications."
        )

    job_desc = app.job_description or f"{app.role} at {app.company_name}"
    try:
        analysis = await analyze_resume_match(user.resume_text, job_desc)
        app.ai_match_score = analysis.get("overall_match_score", 0)
        app.ai_experience_alignment = analysis.get("experience_alignment", "Low")
        app.ai_summary = analysis.get("summary", "")
        app.ai_missing_skills = analysis.get("missing_skills", [])
        app.ai_suggestions = analysis.get("improvement_suggestions", [])
        app.updated_at = datetime.now()
        await app.save()
        return app
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI scoring failed: {str(e)}")


@router.post("/score-all")
async def score_all_pending(current_user: str = Depends(get_current_user)):
    """Score all applications that currently have no AI match score."""
    user = await User.find_one(User.email == current_user)
    if not user or not user.resume_text:
        raise HTTPException(
            status_code=400,
            detail="Please upload your resume first before scoring applications."
        )

    apps = await Application.find(Application.user_id == current_user).to_list()
    pending = [a for a in apps if a.ai_match_score is None]

    scored = 0
    errors = 0
    for app in pending:
        job_desc = app.job_description or f"{app.role} at {app.company_name}"
        try:
            analysis = await analyze_resume_match(user.resume_text, job_desc)
            app.ai_match_score = analysis.get("overall_match_score", 0)
            app.ai_experience_alignment = analysis.get("experience_alignment", "Low")
            app.ai_summary = analysis.get("summary", "")
            app.ai_missing_skills = analysis.get("missing_skills", [])
            app.ai_suggestions = analysis.get("improvement_suggestions", [])
            app.updated_at = datetime.now()
            await app.save()
            scored += 1
        except Exception as e:
            print(f"Score error for app {app.id}: {e}")
            errors += 1

    return {
        "message": f"Scored {scored} application(s).",
        "scored": scored,
        "errors": errors,
        "total_pending": len(pending),
    }
