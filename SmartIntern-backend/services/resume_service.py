import os
import shutil
from datetime import datetime
from fastapi import UploadFile
from api.models import User, ResumeAnalysis
from api.pdf_utils import extract_text_from_pdf
from services.ai_service import analyze_resume_match

# We can store RESUME_DIR in a unified config or here
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME_DIR = os.path.join(current_dir, "static", "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)

async def upload_and_parse_resume(file: UploadFile, user: User) -> dict:
    ext = file.filename.split(".")[-1]
    safe_filename = f"{user.email.replace('@', '_').replace('.', '_')}_{int(datetime.now().timestamp())}.{ext}"
    filepath = os.path.join(RESUME_DIR, safe_filename)
    
    file_content = await file.read()
    with open(filepath, "wb") as buffer:
         buffer.write(file_content)
         
    await file.seek(0)
    text = await extract_text_from_pdf(file)
         
    resume_url = f"/static/resumes/{safe_filename}"
    user.resume_text = text
    user.uploaded_file_url = resume_url
    await user.save()
    
    return {
        "text": text,
        "url": resume_url
    }

async def generate_resume_analysis(user: User, job_description: str) -> ResumeAnalysis:
    """Analyze the user's resume and generate detailed suggestions for a job description."""
    analysis_dict = await analyze_resume_match(user.resume_text, job_description)

    analysis_doc = ResumeAnalysis(
        user_email=user.email,
        resume_text=user.resume_text,
        job_description=job_description,
        overall_match_score=analysis_dict.get("overall_match_score", 0),
        experience_alignment=analysis_dict.get("experience_alignment", "Low"),
        skills_found=analysis_dict.get("skills_found", []),
        missing_skills=analysis_dict.get("missing_skills", []),
        strengths=analysis_dict.get("strengths", []),
        weaknesses=analysis_dict.get("weaknesses", []),
        improvement_suggestions=analysis_dict.get("improvement_suggestions", []),
        ats_score=analysis_dict.get("ats_score", 0),
        summary=analysis_dict.get("summary", ""),
        resume_completeness=analysis_dict.get("resume_completeness", {
            "has_summary": False, "has_projects": False, "has_experience": False, "has_skills_section": False, "has_education": False
        })
    )
    
    await analysis_doc.insert()
    return analysis_doc
