import os
import json
import asyncio
import re
import ast
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client(api_key=api_key)

# ── Confirmed-working models (tested 2026-08-04, ordered by preference) ─────────
# Verified live against this API key – models that return generateContent.
# gemini-3.x series have their own free-tier quotas (unexhausted).
# gemini-2.x series are quota-exhausted on the free tier; kept as last-resort
# fallback in case daily quotas reset mid-day.
DEFAULT_MODELS = [
    # --- Confirmed working (tested 2026-08-04) ---
    'gemini-3.5-flash',            # Best quality among working models
    'gemini-3.6-flash',            # Slightly newer backup
    'gemini-3.5-flash-lite',       # Faster/lighter version
    'gemini-3.1-flash-lite',       # Stable, confirmed working
    'gemini-flash-lite-latest',    # Latest flash-lite alias
    'gemini-flash-latest',         # Latest flash alias
    'gemini-3.1-flash-lite-preview',  # Preview fallback
    'gemini-3-flash-preview',      # Older preview, confirmed working
    # --- Quota-exhausted on free tier (fallback when quotas reset) ---
    'gemini-2.5-flash',            # Quota exhausted but real model
    'gemini-2.0-flash',            # Quota exhausted but real model
    'gemini-2.0-flash-lite',       # Quota exhausted but real model
]

# Allow overriding the primary model via env variable (insert it at position 0)
# NOTE: Do NOT set GEMINI_MODEL to old models like gemini-1.5-flash (removed from API).
env_model = os.environ.get("GEMINI_MODEL", "").strip()
if env_model and env_model not in DEFAULT_MODELS:
    AVAILABLE_MODELS = [env_model] + DEFAULT_MODELS
elif env_model:
    AVAILABLE_MODELS = [env_model] + [m for m in DEFAULT_MODELS if m != env_model]
else:
    AVAILABLE_MODELS = DEFAULT_MODELS

async def get_gemini_response(prompt: str, retries: int = 2, delay: int = 2):
    """
    Calls Gemini with automatic model fallback.
    - 404 NOT_FOUND       → immediately skip to next model (model removed/deprecated)
    - 429 RESOURCE_EXHAUSTED → skip to next model (quota exceeded)
    - Other errors        → exponential backoff then skip to next model
    Returns text response, or Error: prefixed string if all models fail.
    """
    if not client:
        return "Error: Gemini API Key not configured."

    last_error = None

    for model_name in AVAILABLE_MODELS:
        for attempt in range(retries):
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=prompt,
                )
                if response and hasattr(response, 'text') and response.text:
                    print(f"[Gemini] Success with model '{model_name}' (attempt {attempt + 1})")
                    return response.text
                # Empty response — try next attempt/model
                print(f"[Gemini] Model '{model_name}' returned empty response")
                break

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 404 = model not found/deprecated → skip immediately
                if "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"[Gemini] Model '{model_name}' returned 404/NOT_FOUND. Skipping to next model.")
                    break

                # 429 = quota/rate limit → skip to next model
                if ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                        or "quota" in error_str.lower()):
                    print(f"[Gemini] Model '{model_name}' quota exhausted. Skipping to next model.")
                    break

                # Transient error — exponential backoff
                wait_time = delay * (2 ** attempt)
                print(f"[Gemini] Model '{model_name}' error (attempt {attempt + 1}/{retries}): {error_str[:100]}. Retrying in {wait_time}s...")
                await asyncio.sleep(min(wait_time, 8))

    print(f"[Gemini] All models exhausted. Last error: {last_error}")
    return f"Error: AI service is currently busy. Please try again later. (Details: {str(last_error)})"

async def _parse_gemini_json_safe(raw_text: str) -> dict:
    """Helper to safely parse Gemini JSON responses handling trailing commas and ticks."""
    try:
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()

        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)

        if clean_json.startswith("'"):
            clean_json = clean_json.replace("'", '"')
            
        clean_json = re.sub(r',\s*\}', '}', clean_json)
        clean_json = re.sub(r',\s*\]', ']', clean_json)

        try:
            return json.loads(clean_json)
        except json.JSONDecodeError:
            return ast.literal_eval(clean_json)
    except Exception as e:
        print(f"JSON Parse Error: {e}. Raw: {raw_text}")
        raise ValueError(f"Failed to parse AI response: {str(e)}")

async def analyze_resume_match(resume_text: str, job_desc: str):
    prompt = f"""
    You are an advanced AI Resume Evaluation Engine connecting engineering candidates with early-career roles.
    Deeply analyze a candidate’s resume against a SPECIFIC job description and calculate a customized match score.

    TARGET JOB DESCRIPTION:
    {job_desc[:4000]}...

    CANDIDATE RESUME:
    {resume_text[:4000]}...

    Rules STRICTLY:
    1. Score matching: Core Skills (40%), Experience (30%), Tools (20%), Soft Skills (10%).
    2. NEVER give 0% if the candidate has partial skills. 

    Output ONLY raw JSON in this exact structure format: 
    {{
      "overall_match_score": 0,
      "experience_alignment": "Low",
      "skills_found": [],
      "missing_skills": [],
      "strengths": [],
      "weaknesses": [],
      "improvement_suggestions": [],
      "ats_score": 0,
      "summary": "Detailed explanation of why they got this score",
      "resume_completeness": {{
        "has_summary": true,
        "has_projects": true,
        "has_experience": true,
        "has_skills_section": true,
        "has_education": true
      }}
    }}
    
    Do NOT give explanations outside JSON. Return valid JSON only.
    """
    
    raw_text = await get_gemini_response(prompt)
    
    try:
        return await _parse_gemini_json_safe(raw_text)
    except Exception as e:
        return {
            "overall_match_score": 0, 
            "experience_alignment": "Low",
            "skills_found": [],
            "missing_skills": [],
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [f"AI Error: {str(e)}"],
            "ats_score": 0,
            "summary": "AI matching service failed to interpret resume details.",
            "resume_completeness": {"has_summary": False, "has_projects": False, "has_experience": False, "has_skills_section": False, "has_education": False}
        }

async def generate_dashboard_insights(applications_data: list):
    """
    Analyzes multiple applications to find trends in missing skills, low scores, etc.
    """
    if not applications_data:
        return {
            "trends": "Not enough data yet.",
            "improvement_strategy": "Start applying and pasting Job Descriptions so we can generate insights!",
            "follow_up_suggestions": [],
            "learning_roadmap": "Focus on the core skills listed in your preferred job descriptions."
        }

    # Condense data to avoid token limits
    condensed_apps = []
    for app in applications_data:
        condensed_apps.append({
            "role": app.get("role", "Unknown"),
            "company": app.get("company_name", "Unknown"),
            "score": app.get("ai_match_score", 0),
            "missing_skills": app.get("ai_missing_skills", []),
            "status": app.get("status", "Applied")
        })

    prompt = f"""
    You are an expert Career Coach analyzing a candidate's recent internship/job applications.
    Look at the following application history (role, match score, missing skills identified):
    
    {json.dumps(condensed_apps, indent=2)}
    
    Provide comprehensive insights for the user. Identify trends (e.g., repeatedly missing 'React' or low scores on Backend roles).
    Suggest a concrete learning roadmap based on their most frequent missing skills.
    Suggest companies or roles they should follow up with immediately based on high scores or recent applications.
    
    Output ONLY raw JSON in this exact structure:
    {{
        "trends": "Detailed paragraph identifying trends in their applications.",
        "improvement_strategy": "Concrete strategy for improvement.",
        "follow_up_suggestions": ["Company A - high match score", "Company B - Needs follow up"],
        "learning_roadmap": "A roadmap focusing on the 2-3 most critical missing skills."
    }}
    
    Do NOT give explanations outside JSON. Return valid JSON only.
    """
    
    raw_text = await get_gemini_response(prompt)
    
    try:
        return await _parse_gemini_json_safe(raw_text)
    except Exception as e:
        return {
            "trends": "Unable to generate trends at this moment due to an AI error.",
            "improvement_strategy": "Keep applying to jobs and tracking them here.",
            "follow_up_suggestions": [],
            "learning_roadmap": "Continue building core skills."
        }

# Other helpers ported from api_utils
async def parse_resume_json(resume_text: str):
    prompt = f"""
    Extract basic info from this raw resume text:
    - Full Name
    - Email Address 
    - LinkedIn URL 
    - Phone Number
    - Skills 
    - Education
    - Work Experience
    - Projects
    - Certifications

    Return JSON:
    {{
      "name": "",
      "email": "",
      "linkedin": "",
      "phone": "",
      "skills": [],
      "education": [],
      "experience": [],
      "projects": [],
      "certifications": []
    }}
    
    Resume Content: {resume_text[:3000]}
    """
    raw_text = await get_gemini_response(prompt)
    try:
        return await _parse_gemini_json_safe(raw_text)
    except:
        return {"error": "Failed to parse resume JSON"}

async def generate_cold_email_ai(job_desc: str, user_role: str = "Developer"):
    prompt = f"Write a professional, concise cold email to a recruiter for this Job Description.\nMy Role: {user_role}\nJob Description: {job_desc}\nOutput ONLY the email body text."
    return await get_gemini_response(prompt)

async def get_career_coach_response(message: str, resume_context: str = ""):
    prompt = f"You are an expert Career Coach. Give actionable advice.\nResume Context: {resume_context[:2000]}\nQuestion: {message}\nAnswer:"
    return await get_gemini_response(prompt)

async def get_interview_tips_ai(position: str):
    prompt = f"""Provide 5 essential interview tips for a "{position}".
    Output JSON: {{"tips": ["Tip 1", "Tip 2"]}}"""
    raw = await get_gemini_response(prompt)
    try:
        return await _parse_gemini_json_safe(raw)
    except:
        return {"tips": ["Prepare thoroughly.", "Review job description.", "Practice STAR method."]}
