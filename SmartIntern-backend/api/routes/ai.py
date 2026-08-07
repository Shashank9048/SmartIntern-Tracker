"""
api/routes/ai.py
────────────────
AI Assistant endpoints:
  POST /api/ai/analyze-resume  — ATS scoring, skill extraction, improvements
  POST /api/ai/match-job       — resume-vs-JD fit percentage & match rating

Uses the shared ai_utils helpers (google-genai Client, multi-model retry).
"""

import json
import re
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from ..auth import get_current_user
from ..ai_utils import get_gemini_response, analyze_resume_match

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai")


# ─── Request / Response Models ────────────────────────────────────────────────

class ResumeAnalysisRequest(BaseModel):
    resume_text: str


class JobMatchRequest(BaseModel):
    resume_skills: List[str]
    job_description: str


class ColdEmailRequest(BaseModel):
    job_description: str
    role: str


# ─── Helper: clean & parse JSON from Gemini ───────────────────────────────────

def _parse_gemini_json(raw: str) -> dict:
    """Strip markdown fences and trailing commas, then JSON-parse."""
    clean = raw.replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        clean = m.group(0)
    clean = re.sub(r",\s*\}", "}", clean)
    clean = re.sub(r",\s*\]", "]", clean)
    return json.loads(clean)


# ─── POST /api/ai/analyze-resume ─────────────────────────────────────────────

@router.post("/analyze-resume")
async def analyze_resume(
    payload: ResumeAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Analyse a resume text with Gemini and return:
      - ats_score        (0–100)
      - extracted_skills (list[str])
      - strengths        (list[str])
      - missing_skills   (list[str] — common tech-role gaps)
      - improvements     (list[str] — actionable tips)
    """
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty.")

    prompt = f"""
You are an expert HR ATS analyzer. Analyze the following resume and return ONLY valid JSON (no markdown, no backticks):
{{
  "ats_score": <integer 0-100>,
  "extracted_skills": [<list of skill strings>],
  "strengths": [<list of strength strings>],
  "missing_skills": [<list of skills commonly required for tech roles that are missing>],
  "improvements": [<list of actionable resume improvement tips>]
}}

Resume Text:
{payload.resume_text[:6000]}
"""

    raw = await get_gemini_response(prompt)
    if not raw or raw.startswith("Error:"):
        logger.warning("[analyze-resume] Gemini error: %s", (raw or "")[:200])
        raise HTTPException(
            status_code=503,
            detail=f"AI service temporarily unavailable: {(raw or '')[:200]}",
        )

    try:
        result = _parse_gemini_json(raw)
    except Exception as e:
        logger.error("[analyze-resume] JSON parse error: %s. Raw: %s", e, raw[:300])
        raise HTTPException(
            status_code=500,
            detail="AI returned an unexpected format. Please try again.",
        )

    # Normalise types so the frontend never gets None
    return {
        "status": "success",
        "analysis": {
            "ats_score": int(result.get("ats_score") or 0),
            "extracted_skills": result.get("extracted_skills") or [],
            "strengths": result.get("strengths") or [],
            "missing_skills": result.get("missing_skills") or [],
            "improvements": result.get("improvements") or [],
        },
    }


# ─── POST /api/ai/match-job ───────────────────────────────────────────────────

@router.post("/match-job")
async def match_job(
    payload: JobMatchRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Evaluate the fit between a candidate's skills and a job description.
    Returns:
      - fit_percentage (0–100)
      - match_rating   ('Strong Fit' | 'Moderate Fit' | 'Weak Fit')
      - matched_skills (list[str])
      - missing_skills (list[str])
      - summary        (str)
    """
    if not payload.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")
    if not payload.resume_skills:
        raise HTTPException(status_code=400, detail="resume_skills list cannot be empty.")

    skills_str = ", ".join(payload.resume_skills[:80])

    prompt = f"""
You are an expert HR ATS analyzer. Evaluate the fit between the candidate's resume skills and this job description.
Return ONLY valid JSON (no markdown, no backticks):
{{
  "fit_percentage": <integer 0-100>,
  "match_rating": "<one of: 'Strong Fit' | 'Moderate Fit' | 'Weak Fit'>",
  "matched_skills": [<skills from resume_skills that appear in the JD>],
  "missing_skills": [<skills the JD requires that are NOT in resume_skills>],
  "summary": "<2-sentence evaluation of how well this candidate fits the role>"
}}

Candidate Resume Skills:
{skills_str}

Job Description:
{payload.job_description[:4000]}
"""

    raw = await get_gemini_response(prompt)
    if not raw or raw.startswith("Error:"):
        logger.warning("[match-job] Gemini error: %s", (raw or "")[:200])
        raise HTTPException(
            status_code=503,
            detail=f"AI service temporarily unavailable: {(raw or '')[:200]}",
        )

    try:
        result = _parse_gemini_json(raw)
    except Exception as e:
        logger.error("[match-job] JSON parse error: %s. Raw: %s", e, raw[:300])
        raise HTTPException(
            status_code=500,
            detail="AI returned an unexpected format. Please try again.",
        )

    return {
        "status": "success",
        "match": {
            "fit_percentage": int(result.get("fit_percentage") or 0),
            "match_rating": result.get("match_rating") or "Moderate Fit",
            "matched_skills": result.get("matched_skills") or [],
            "missing_skills": result.get("missing_skills") or [],
            "summary": result.get("summary") or "",
        },
    }


# ─── POST /api/ai/generate-cold-email ─────────────────────────────────────────

@router.post("/generate-cold-email")
async def generate_cold_email_endpoint(
    payload: ColdEmailRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Generate a cold email using Gemini.
    """
    if not payload.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    from ..ai_utils import generate_cold_email_ai
    body = await generate_cold_email_ai(payload.job_description, payload.role)
    
    if not body or body.startswith("Error:"):
        raise HTTPException(status_code=503, detail="AI generation failed")

    return {"body": body}
