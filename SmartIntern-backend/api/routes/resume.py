from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..auth import get_current_user
from ..models import User, ResumeAnalysis
from ..ai_utils import analyze_resume_match
from ..pdf_utils import extract_text_from_pdf
import os
import json
import re
import ast
from datetime import datetime

router = APIRouter(prefix="/api/resume", tags=["Resume"])

# --- Resume dir within api/static ---
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME_DIR = os.path.join(_api_dir, "static", "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)


class ResumeAnalysisRequest(BaseModel):
    job_description: str
    resume_text: Optional[str] = None  # If provided, use this; otherwise fall back to DB


@router.post("/upload")
async def upload_resume_endpoint(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "doc", "docx"):
        raise HTTPException(status_code=400, detail="Only PDF, DOC, or DOCX files are allowed")

    try:
        safe_filename = (
            f"{current_user.replace('@', '_').replace('.', '_')}"
            f"_{int(datetime.now().timestamp())}.{ext}"
        )
        filepath = os.path.join(RESUME_DIR, safe_filename)

        # Save file to disk
        file_content = await file.read()
        with open(filepath, "wb") as buffer:
            buffer.write(file_content)

        # Reset and extract text
        await file.seek(0)
        text = await extract_text_from_pdf(file)

        resume_url = f"/static/resumes/{safe_filename}"
        user.resume_text = text
        user.uploaded_file_url = resume_url
        await user.save()

        return {
            "message": "Resume parsed and saved successfully",
            "full_text": text,                              # Full extracted text for preview
            "text_preview": text[:200] + "..." if len(text) > 200 else text,
            "uploaded_file_url": resume_url,
            "filename": file.filename,
            "characters": len(text),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.post("/analyze")
async def analyze_resume_endpoint(
    data: ResumeAnalysisRequest,
    current_user: str = Depends(get_current_user)
):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use resume_text from request body if provided, otherwise fall back to DB
    resume_text = data.resume_text or user.resume_text
    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No resume text found. Please upload a resume or paste your resume text first."
        )

    if not data.job_description or not data.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description is required.")

    # If we got resume_text from body, sync it back to the user profile silently
    if data.resume_text and data.resume_text != user.resume_text:
        user.resume_text = data.resume_text
        await user.save()

    try:
        analysis_data = await analyze_resume_match(resume_text, data.job_description)

        rc = analysis_data.get("resume_completeness", {})
        from ..models import ResumeCompleteness

        doc = ResumeAnalysis(
            user_email=current_user,
            resume_text=resume_text,
            job_description=data.job_description,
            overall_match_score=analysis_data.get("overall_match_score", 0),
            experience_alignment=analysis_data.get("experience_alignment", "Low"),
            skills_found=analysis_data.get("skills_found", []),
            missing_skills=analysis_data.get("missing_skills", []),
            strengths=analysis_data.get("strengths", []),
            weaknesses=analysis_data.get("weaknesses", []),
            improvement_suggestions=analysis_data.get("improvement_suggestions", []),
            ats_score=analysis_data.get("ats_score", 0),
            summary=analysis_data.get("summary", ""),
            resume_completeness=ResumeCompleteness(
                has_summary=rc.get("has_summary", False),
                has_projects=rc.get("has_projects", False),
                has_experience=rc.get("has_experience", False),
                has_skills_section=rc.get("has_skills_section", False),
                has_education=rc.get("has_education", False),
            )
        )
        await doc.insert()
        return doc

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis Failed: {str(e)}")
