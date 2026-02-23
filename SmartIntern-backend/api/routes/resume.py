from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from pydantic import BaseModel
from ..auth import get_current_user
from ..models import User, ResumeAnalysis
from ..ai_utils import analyze_resume_match, get_gemini_response
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

@router.post("/upload")
async def upload_resume_endpoint(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
         raise HTTPException(status_code=404, detail="User not found")
         
    try:
        ext = file.filename.split(".")[-1]
        safe_filename = f"{current_user.replace('@', '_').replace('.', '_')}_{int(datetime.now().timestamp())}.{ext}"
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
            "message": "Resume parsed and saved", 
            "text_preview": text[:100] + "...", 
            "uploaded_file_url": resume_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@router.post("/analyze")
async def analyze_resume_endpoint(data: ResumeAnalysisRequest, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.resume_text:
        raise HTTPException(status_code=400, detail="No resume uploaded yet. Please upload a resume first.")
        
    try:
        analysis_data = await analyze_resume_match(user.resume_text, data.job_description)
        
        # Build and save ResumeAnalysis document
        rc = analysis_data.get("resume_completeness", {})
        from ..models import ResumeCompleteness
        
        doc = ResumeAnalysis(
            user_email=current_user,
            resume_text=user.resume_text,
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
                has_education=rc.get("has_education", False)
            )
        )
        await doc.insert()
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis Failed: {str(e)}")
