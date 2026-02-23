from datetime import datetime
from typing import List, Optional
from beanie import PydanticObjectId
from api.models import Application, User, ApplicationCreate, ApplicationUpdate
from services.ai_service import analyze_resume_match

async def get_user_applications(user_email: str) -> List[Application]:
    return await Application.find(Application.user_id == user_email).sort(-Application.created_at).to_list()

async def get_application(app_id: PydanticObjectId, user_email: str) -> Optional[Application]:
    app = await Application.get(app_id)
    if not app or app.user_id != user_email:
        return None
    return app

async def create_application(app_data: ApplicationCreate, user: User) -> Application:
    match_score = None
    experience_alignment = None
    summary = None
    missing_skills = []
    suggestions = []

    if user.resume_text:
        try:
            job_desc = app_data.job_description if app_data.job_description else f"{app_data.role} at {app_data.company_name}"
            analysis = await analyze_resume_match(user.resume_text, job_desc)
            
            # Extract standard fields
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
        
        # Flatted AI Fields
        ai_match_score=match_score,
        ai_experience_alignment=experience_alignment,
        ai_summary=summary,
        ai_missing_skills=missing_skills,
        ai_suggestions=suggestions
    )
    
    await new_app.insert()
    return new_app

async def update_application(app_id: PydanticObjectId, app_data: ApplicationUpdate, user_email: str) -> Optional[Application]:
    app = await Application.get(app_id)
    if not app or app.user_id != user_email:
        return None

    if app_data.company_name: app.company_name = app_data.company_name
    if app_data.role: app.role = app_data.role
    if app_data.status: app.status = app_data.status
    if app_data.applied_date: app.applied_date = app_data.applied_date
    if app_data.interview_date is not None: app.interview_date = app_data.interview_date
    if app_data.notes is not None: app.notes = app_data.notes
    if app_data.job_description is not None: app.job_description = app_data.job_description

    app.updated_at = datetime.now()
    await app.save()
    return app

async def delete_application(app_id: PydanticObjectId, user_email: str) -> bool:
    app = await Application.get(app_id)
    if not app or app.user_id != user_email:
        return False
    await app.delete()
    return True
