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

AVAILABLE_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-1.5-flash',
]

async def get_gemini_response(prompt: str, retries: int = 3, delay: int = 5):
    if not client:
        return "Error: Gemini API Key not configured."
        
    last_error = None
    
    for model_name in AVAILABLE_MODELS:
        try:
            for attempt in range(retries):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=prompt,
                    )
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    last_error = e
                    
                    if "429" in error_str or "quota" in error_str.lower():
                        match_seconds = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_str)
                        match_text_seconds = re.search(r"retry in (\d+\.?\d*)s", error_str)
                        
                        wait_time = delay * (2 ** attempt)
                        
                        if match_seconds:
                            wait_time = int(match_seconds.group(1)) + 1
                        elif match_text_seconds:
                            wait_time = float(match_text_seconds.group(1)) + 1
                            
                        if attempt == 0 and model_name != AVAILABLE_MODELS[-1]:
                            print(f"⚠️ Quota exceeded on {model_name}. Switching model...")
                            break 
                            
                        print(f"⚠️ Quota exceeded on {model_name}. Retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    print(f"❌ Gemini Error ({model_name}): {e}")
                    break 

        except Exception as e:
            print(f"❌ Setup Error ({model_name}): {e}")
            continue

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
