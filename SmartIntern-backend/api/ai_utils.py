import os
import json
import logging
from dotenv import load_dotenv
from google import genai as google_genai
# If the above fails, you might need:
# from google.genai import genai as google_genai

load_dotenv()

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
client = None
if api_key:
    client = google_genai.Client(api_key=api_key)

import asyncio
import time
import re
import ast

logger = logging.getLogger(__name__)

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
    Tries each model in AVAILABLE_MODELS in order.
    - 404 NOT_FOUND  → immediately skip to next model (model removed/deprecated)
    - 429 RESOURCE_EXHAUSTED → skip to next model (quota exceeded)
    - Other errors   → log and skip to next model
    Returns the text response, or an Error: prefixed string.
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
                    logger.info(f"[Gemini] Success with model '{model_name}' (attempt {attempt + 1})")
                    return response.text
                # Empty response — skip to next attempt/model
                logger.warning(f"[Gemini] Model '{model_name}' returned empty response")
                break

            except Exception as e:
                error_str = str(e)
                last_error = e

                # 404 = model not found/deprecated → skip immediately
                if "404" in error_str or "NOT_FOUND" in error_str:
                    logger.warning(
                        f"[Gemini] Model '{model_name}' returned 404/NOT_FOUND. "
                        f"Skipping to next model."
                    )
                    break  # exit retry loop, try next model

                # 429 = quota/rate limit → skip to next model (no point waiting)
                if ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                        or "quota" in error_str.lower()):
                    logger.warning(
                        f"[Gemini] Model '{model_name}' quota exhausted. "
                        f"Skipping to next model."
                    )
                    break  # exit retry loop, try next model

                # Transient/unknown error — exponential backoff then retry
                wait_time = delay * (2 ** attempt)
                logger.warning(
                    f"[Gemini] Model '{model_name}' error (attempt {attempt + 1}/{retries}): "
                    f"{error_str[:120]}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(min(wait_time, 8))

    logger.error(
        f"[Gemini] All models exhausted. Last error: {last_error}"
    )
    return f"Error: AI service is currently busy. Please try again later. (Details: {str(last_error)})"

async def analyze_resume_match(resume_text: str, job_desc: str):
    prompt = f"""
    You are an elite, highly critical AI Technical Recruiter & Resume Evaluation Engine.
    Your objective is to deeply and strictly evaluate a candidate's resume against a SPECIFIC job description and calculate a highly accurate, dynamic compatibility score (0-100).
    You must NOT be generous. A score of 100 means the candidate is a literal perfect match with years of experience in every required technology.

    TARGET JOB DESCRIPTION:
    {job_desc[:4000]}

    CANDIDATE RESUME:
    {resume_text[:4000]}

    Follow these rules STRICTLY:

    1. Deep Semantic Matching: Look for underlying semantic matches (e.g., "NodeJS" matches "Node", "Backend APIs" matches "Express.js REST APIs", "PostgreSQL" satisfies "SQL"). Understand tech stack synonyms and acronyms.
    2. Strict Penalization: If the JD explicitly requires a core technology (e.g., Python, React, Java) or years of experience, and the candidate's resume completely lacks it or only mentions it as a passing hobby, heavily penalize the score. 
    3. Dynamic Compatibility Score (0-100) using this stringent weighting:
       - 50% Core Technical Skills & Frameworks (Must have the primary stack).
       - 30% Experience relevance (If the JD wants 3+ years and they have 0, this gets 0/30).
       - 10% Tools & Cloud (AWS, Docker, Git).
       - 10% Soft Skills & Domain Knowledge.
       Realistic score distributions: 
       - < 30: Unqualified. Missing core stack.
       - 30-55: Weak match. Missing major requirements.
       - 55-75: Average/Good match. Has most core skills but maybe lacks niche tools or experience.
       - 75-90: Strong match. Fits almost perfectly.
       - > 90: Exceptional, unicorn candidate.
    4. Missing Skills: List ONLY the critical technical skills from the JD that are completely missing from the resume. Do NOT list soft skills here.
    5. Improvement Suggestions: Actionable, specific steps (e.g., "Build a project using Docker and Kubernetes to satisfy the cloud requirements").
    6. Experience Alignment: Return exactly one of: "High", "Medium", "Low".
    7. Strengths: List 3-5 specific, strong points in the resume that match this exact JD.
    8. Weaknesses: List 2-4 specific technical weaknesses or experience gaps.
    9. Summary: Write a punchy 2-3 sentence AI summary of their exact fit.
    10. Resume Completeness: Check basic structure.

    Output ONLY valid JSON in EXACTLY this structure. Do NOT use markdown or backticks:
    {{
      "overall_match_score": 0,
      "ats_score": 0,
      "experience_alignment": "Low",
      "summary": "",
      "skills_found": [],
      "missing_skills": [],
      "strengths": [],
      "weaknesses": [],
      "improvement_suggestions": [],
      "resume_completeness": {{
        "has_summary": false,
        "has_projects": false,
        "has_experience": false,
        "has_skills_section": false,
        "has_education": false
      }}
    }}
    """

    raw_text = await get_gemini_response(prompt)

    # Default safe response
    default = {
        "overall_match_score": 0,
        "ats_score": 0,
        "experience_alignment": "Low",
        "summary": "Analysis could not be completed. Please try again.",
        "skills_found": [],
        "missing_skills": [],
        "strengths": [],
        "weaknesses": [],
        "improvement_suggestions": ["Please try analyzing again."],
        "resume_completeness": {
            "has_summary": False,
            "has_projects": False,
            "has_experience": False,
            "has_skills_section": False,
            "has_education": False,
        }
    }

    try:
        # Strip markdown code fences
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()

        # Extract the outermost JSON object
        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)

        # Fix single-quote JSON from AI
        if clean_json.startswith("'"):
            clean_json = clean_json.replace("'", '"')

        # Strip trailing commas
        clean_json = re.sub(r',\s*\}', '}', clean_json)
        clean_json = re.sub(r',\s*\]', ']', clean_json)

        try:
            result = json.loads(clean_json)
        except json.JSONDecodeError:
            result = ast.literal_eval(clean_json)

        # Normalise: support both old 'match_score' and new 'overall_match_score'
        if "match_score" in result and "overall_match_score" not in result:
            result["overall_match_score"] = result.pop("match_score")

        # Ensure all keys exist (merge with defaults)
        for key, val in default.items():
            result.setdefault(key, val)

        return result

    except Exception as e:
        print(f"JSON Parse Error in analyze_resume_match: {e}. Raw: {raw_text[:300]}")
        return default


async def batch_analyze_job_matches(resume_text: str, jobs: list) -> list:
    """
    Score a batch of jobs against a resume using Gemini.
    jobs is a list of dicts: [{"job_id": "...", "title": "...", "description": "...", "skills": [...]}]
    Returns a list of dicts: [{"job_id": "...", "match_score": 0-100, "matched_skills": [...], "missing_skills": [...]}]
    """
    if not jobs:
        return []
        
    jobs_json = json.dumps([{
        "job_id": j["job_id"],
        "title": j["title"],
        "description": j.get("description", "")[:1000],  # truncated to save tokens
        "required_skills": j.get("skills", [])
    } for j in jobs])

    prompt = f"""
    You are an elite AI Technical Recruiter Engine.
    Evaluate the following candidate's resume against a BATCH of Job Descriptions.
    
    CANDIDATE RESUME:
    {resume_text[:4000]}
    
    JOBS BATCH (JSON):
    {jobs_json}
    
    For EACH job in the batch, calculate a STRICT dynamic compatibility score (0-100) based on:
    - 60% Core Skills & Tech Stack match (Does the candidate actually have the required core languages/frameworks?)
    - 30% Experience relevance (Does their background match the seniority/domain of the job?)
    - 10% Tools & secondary requirements.
    
    CRITICAL RULES:
    1. Be rigorous. Do not give high scores easily. A score of 95+ means they perfectly match every single requirement.
    2. Deep Semantic Matching: If the JD needs "React" and they have "Next.js", that's a match. If the JD needs "SQL" and they have "PostgreSQL", that's a match.
    3. Severe Penalties: If a core skill (e.g., Python, C++, Java) is fundamentally missing from the resume, the score MUST drop significantly (below 50).
    4. Extract the exact matched skills and missing skills.
    
    Realistic scores: 
    - < 30: Unqualified. Missing core stack.
    - 30-55: Weak match. Missing major requirements.
    - 55-75: Average/Good match. Has most core skills but lacks niche tools.
    - 75-90: Strong match. Fits almost perfectly.
    - > 90: Exceptional candidate.
    
    Output ONLY a valid JSON array of objects in EXACTLY this structure, with NO markdown formatting or backticks:
    [
      {{
        "job_id": "the_job_id",
        "match_score": 0,
        "matched_skills": ["Skill1", "Skill2"],
        "missing_skills": ["Skill3"]
      }}
    ]
    """

    raw_text = await get_gemini_response(prompt)
    
    default_results = []
    for j in jobs:
        default_results.append({
            "job_id": j["job_id"],
            "match_score": 0,
            "matched_skills": [],
            "missing_skills": j.get("skills", [])
        })

    try:
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\[.*\]', clean_json, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
            
        if clean_json.startswith("'"):
            clean_json = clean_json.replace("'", '"')
            
        try:
            results = json.loads(clean_json)
        except json.JSONDecodeError:
            results = ast.literal_eval(clean_json)
            
        if not isinstance(results, list):
            return default_results
            
        # Ensure all requested jobs are in the result
        final_results = []
        result_map = {str(r.get("job_id")): r for r in results if isinstance(r, dict)}
        
        for j in jobs:
            job_id = str(j["job_id"])
            if job_id in result_map:
                r = result_map[job_id]
                final_results.append({
                    "job_id": job_id,
                    "match_score": int(r.get("match_score", 0)),
                    "matched_skills": r.get("matched_skills", []),
                    "missing_skills": r.get("missing_skills", [])
                })
            else:
                final_results.append({
                    "job_id": job_id,
                    "match_score": 0,
                    "matched_skills": [],
                    "missing_skills": j.get("skills", [])
                })
        return final_results

    except Exception as e:
        print(f"JSON Parse Error in batch_analyze_job_matches: {e}. Raw: {raw_text[:300]}")
        return default_results



def clean_extracted_text(text: str) -> str:
    """
    Cleans raw extracted text from PDF/DOCX before sending to Gemini:
    - Normalizes line endings (\r\n and \r -> \n)
    - Removes non-printable control characters
    - Strips page number artifacts (e.g. 'Page 1 of 2', 'Page 3')
    - Cleans hyperlink artifacts (e.g. '|Link', '[Link]')
    - Collapses 3+ newlines to 2 newlines
    - Collapses multiple horizontal spaces/tabs per line
    - Trims leading/trailing whitespace
    """
    if not text:
        return ""
    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # 2. Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 3. Strip page number artifacts & horizontal dividers & link tags
    text = re.sub(r'(?i)^\s*page\s+\d+(\s+of\s+\d+)?\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[\-\_\*\=]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|\s*Link\b', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\[Link\]', '', text, flags=re.IGNORECASE)

    # 4. Collapse multiple spaces per line
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
    text = "\n".join(lines)

    # 5. Collapse 3+ newlines to 2 newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


RESUME_LIST_FIELDS = ("skills", "education", "experience", "projects", "certifications")


def _empty_resume_payload() -> dict:
    return {
        "name": None,
        "email": None,
        "linkedin": None,
        "phone": None,
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
    }


def _clean_scalar(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n,;|")
    if not value or value.lower() in {"null", "none", "n/a", "na", "not available"}:
        return None
    return value


def _dedupe_list(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, sort_keys=True, default=str) if isinstance(item, dict) else str(item).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _ensure_list(value, split_strings: bool = False) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, list):
                items.extend(_ensure_list(item, split_strings=split_strings))
            elif isinstance(item, str):
                cleaned = _clean_scalar(item)
                if cleaned:
                    if split_strings and re.search(r"[,;\n|]", cleaned):
                        items.extend(_ensure_list(cleaned, split_strings=True))
                    else:
                        items.append(cleaned)
            elif item:
                items.append(item)
        return _dedupe_list(items)
    if isinstance(value, dict):
        if split_strings:
            items = []
            for nested in value.values():
                items.extend(_ensure_list(nested, split_strings=True))
            return _dedupe_list(items)
        return [value]
    if isinstance(value, str):
        cleaned = _clean_scalar(value)
        if not cleaned:
            return []
        if split_strings:
            pieces = re.split(r"[,;\n|]+", cleaned)
            return _dedupe_list([p.strip(" -\t") for p in pieces if _clean_scalar(p)])
        return [cleaned]
    return [value]


def _nested_sources(data: dict) -> list:
    sources = [data]
    for key in (
        "candidate",
        "profile",
        "personal_info",
        "personalInformation",
        "contact",
        "contact_info",
        "contactInformation",
        "basics",
    ):
        nested = data.get(key)
        if isinstance(nested, dict):
            sources.append(nested)
    return sources


def _first_alias(data: dict, aliases: tuple[str, ...]):
    for source in _nested_sources(data):
        for alias in aliases:
            if alias in source:
                value = _clean_scalar(source.get(alias))
                if value:
                    return value
    return None


def _first_list_alias(data: dict, aliases: tuple[str, ...], split_strings: bool = False) -> list:
    for source in _nested_sources(data):
        for alias in aliases:
            if alias in source:
                values = _ensure_list(source.get(alias), split_strings=split_strings)
                if values:
                    return values
    return []


def _extract_linkedin(text: str) -> str | None:
    match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s,;)\]]+", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(0).rstrip(".")


def _name_like(candidate: str) -> str | None:
    """Return candidate if it looks like a plausible person's name, else None."""
    compact = re.sub(r"[^A-Za-z .'-]", "", candidate).strip()
    words = [w for w in compact.split() if w]
    if 2 <= len(words) <= 5 and len(compact) <= 70 and all(len(w) >= 2 for w in words):
        return compact
    return None


def _extract_name_from_text(text: str) -> str | None:
    """
    Extract a candidate name from the first 15 lines of resume text.

    FIX: modern resume headers often put name, email and phone on the same line,
    e.g. "Shashank Singh | shashank@gmail.com | +91-9876543210".
    Split on common separators and test each piece.
    """
    disqualifying_tokens = ("linkedin", "github", "http", "resume", "curriculum vitae", "page ", "contact")
    for raw_line in text.splitlines()[:15]:
        line = _clean_scalar(raw_line)
        if not line:
            continue
        lower = line.lower()

        # Common case: a clean line with just the name, nothing else.
        if not any(token in lower for token in disqualifying_tokens) and not re.search(r"\d", line) and "@" not in line:
            found = _name_like(line)
            if found:
                return found

        # Combined-header case: "Shashank Singh | shashank@example.com | +91-..."
        # Split on common separators and email/phone patterns, and test each piece.
        pieces = re.split(r"[|•·,;]|\s[-\u2013\u2014]\s|(?:\s{2,})|(?=\S+@)|(?:\+?\d[\d\s().-]{7,}\d)", line)
        for piece in pieces:
            piece = piece.strip(" -–—\t")
            if not piece or "@" in piece or re.search(r"\d", piece):
                continue
            if any(token in piece.lower() for token in disqualifying_tokens):
                continue
            found = _name_like(piece)
            if found:
                return found
    return None




def _extract_skills_from_text(text: str) -> list[str]:
    skills: list[str] = []
    section_match = re.search(
        r"(?is)\b(?:technical\s+skills|skills|technologies)\b\s*:?\s*(.*?)(?=\n\s*(?:education|experience|work\s+experience|projects|certifications|achievements|publications|summary|objective)\b|$)",
        text,
    )
    if section_match:
        body = section_match.group(1)[:1500]
        for piece in re.split(r"[,;\n|\u2022]+", body):
            skill = re.sub(r"^[\-\*\s]+", "", piece).strip()
            if 2 <= len(skill) <= 40 and not re.search(r"\b(?:and|with|using)\b.{20,}", skill, re.IGNORECASE):
                skills.append(skill)

    known_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "React", "Next.js", "Node.js",
        "Express", "MongoDB", "SQL", "PostgreSQL", "MySQL", "HTML", "CSS",
        "Tailwind", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git",
        "C++", "C#", "Go", "Django", "Flask", "FastAPI", "Pandas", "NumPy",
        "TensorFlow", "PyTorch", "Machine Learning", "Data Structures", "Algorithms",
    ]
    lower_text = text.lower()
    for skill in known_skills:
        pattern = r"\b" + re.escape(skill.lower()).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, lower_text):
            skills.append(skill)

    return [s for s in _dedupe_list(skills) if isinstance(s, str)][:80]


def _fallback_resume_from_text(text: str) -> dict:
    payload = _empty_resume_payload()
    if not text:
        return payload

    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    phone_match = re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text)

    payload["name"] = _extract_name_from_text(text)
    payload["email"] = email_match.group(0) if email_match else None
    payload["linkedin"] = _extract_linkedin(text)
    payload["phone"] = phone_match.group(0).strip() if phone_match else None
    payload["skills"] = _extract_skills_from_text(text)
    return payload


def _payload_has_content(payload: dict) -> bool:
    return any(payload.get(key) for key in ("name", "email", "linkedin", "phone")) or any(
        payload.get(key) for key in RESUME_LIST_FIELDS
    )


def _balanced_json_slice(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def _parse_jsonish_object(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    text = re.sub(r",\s*([}\]])", r"\1", text)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text[match.start():])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    balanced = _balanced_json_slice(text)
    if balanced:
        balanced = re.sub(r",\s*([}\]])", r"\1", balanced)
        try:
            parsed = json.loads(balanced)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        pythonish = re.sub(r"\bnull\b", "None", balanced, flags=re.IGNORECASE)
        pythonish = re.sub(r"\btrue\b", "True", pythonish, flags=re.IGNORECASE)
        pythonish = re.sub(r"\bfalse\b", "False", pythonish, flags=re.IGNORECASE)
        parsed = ast.literal_eval(pythonish)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Gemini response did not contain a parseable JSON object")


def _normalise_resume_payload(data: dict, source_text: str) -> dict:
    payload = _empty_resume_payload()
    fallback = _fallback_resume_from_text(source_text)

    payload["name"] = _first_alias(data, ("name", "full_name", "fullName", "candidate_name", "candidateName")) or fallback["name"]
    payload["email"] = _first_alias(data, ("email", "email_address", "emailAddress")) or fallback["email"]
    payload["linkedin"] = (
        _first_alias(data, ("linkedin", "linkedin_url", "linkedinUrl", "linkedin_profile", "linkedIn"))
        or fallback["linkedin"]
    )
    payload["phone"] = _first_alias(data, ("phone", "phone_number", "phoneNumber", "mobile", "contact_number")) or fallback["phone"]

    payload["skills"] = _first_list_alias(
        data,
        ("skills", "technical_skills", "technicalSkills", "technologies", "tools", "programming_languages"),
        split_strings=True,
    ) or fallback["skills"]
    payload["education"] = _first_list_alias(data, ("education", "educations", "academic_background", "academics"))
    payload["experience"] = _first_list_alias(
        data,
        ("experience", "work_experience", "workExperience", "employment", "internships", "professional_experience"),
    )
    payload["projects"] = _first_list_alias(data, ("projects", "project_experience", "portfolio"))
    payload["certifications"] = _first_list_alias(
        data,
        ("certifications", "certificates", "licenses", "courses"),
        split_strings=True,
    )

    return payload


def _fallback_or_error(cleaned_text: str, error_message: str, raw_snippet: str = "") -> dict:
    fallback = _fallback_resume_from_text(cleaned_text)
    # Always return the fallback even if name is None — skills, email, phone are still useful.
    # Only fall back to the hard error dict if the text itself is completely empty.
    if cleaned_text.strip():
        fallback["_parse_error"] = error_message
        return fallback
    return {
        "error": error_message,
        "raw_snippet": raw_snippet[:300],
    }


async def parse_resume_json(resume_text: str):
    cleaned = clean_extracted_text(resume_text)
    if not cleaned:
        return {"error": "No readable text extracted from resume"}

    logger.info("[parse_resume_json] Sending %d chars to Gemini. Preview: %s", len(cleaned), cleaned[:200])

    prompt = f"""
    You are a professional resume parsing assistant.

    Extract the following structured information from the cleaned resume text provided below:

    - Full Name
    - Email Address (use regex: [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-z]{{2,}})
    - LinkedIn URL (match linkedin.com profile links)
    - Phone Number
    - Skills (list format)
    - Education
    - Work Experience
    - Projects
    - Certifications (if available)

    Return the result strictly in this JSON format:

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

    Resume Content:
    \"\"\"
    {cleaned}
    \"\"\"

    If any field is missing, return null.
    Do not hallucinate.
    Only extract information explicitly present in the resume.
    """

    raw_text = await get_gemini_response(prompt)
    logger.info("[parse_resume_json] Gemini raw response (first 500 chars): %s", (raw_text or "")[:500])

    if not raw_text or raw_text.startswith("Error:"):
        message = (raw_text or "Gemini returned an empty response")[:300]
        logger.warning("[parse_resume_json] Gemini returned an error; using text fallback if possible: %s", message)
        return _fallback_or_error(cleaned, message, raw_text or "")

    try:
        data = _parse_jsonish_object(raw_text)
        normalised = _normalise_resume_payload(data, cleaned)
        if _payload_has_content(normalised):
            field_count = sum(1 for v in normalised.values() if v)
            logger.info("[parse_resume_json] Successfully parsed %d non-empty fields. Name=%s Skills=%d",
                        field_count, normalised.get('name'), len(normalised.get('skills', [])))
            return normalised
        logger.warning("[parse_resume_json] Gemini JSON had no expected resume fields. Raw snippet: %s", raw_text[:300])
        return _fallback_or_error(
            cleaned,
            "Gemini returned JSON, but it did not contain expected resume fields",
            raw_text,
        )
    except Exception as e:
        message = f"Failed to parse Gemini resume JSON: {e}"
        logger.warning("[parse_resume_json] %s. Raw snippet: %s", message, raw_text[:300])
        return _fallback_or_error(cleaned, message, raw_text)

async def generate_cold_email_ai(job_desc: str, user_role: str = "Developer"):
    prompt = f"""
    Write a professional, concise cold email to a recruiter for this Job Description.
    My Role: {user_role}
    Job Description: {job_desc}
    
    Output ONLY the email body text. No subject line placeholders.
    """
    return await get_gemini_response(prompt)

async def get_career_coach_response(message: str, resume_context: str = ""):
    """
    Career Coach Chat with Resume Context. 
    """
    system_instruction = "You are an expert Career Coach for Computer Science students. Use the user's resume context to give specific, actionable advice. Keep answers under 150 words."
    
    prompt = f"""
    {system_instruction}
    
    User Resume Context: {resume_context[:2000]}
    
    User Question: {message}
    
    Assistant Answer:
    """
    return await get_gemini_response(prompt)

async def chat_with_gemini(message: str, context: str = ""):
    # Wrapper for consistency if needed, but get_career_coach_response is the main one now
    return await get_career_coach_response(message, context)

async def get_interview_tips_ai(position: str):
    prompt = f"""
    Provide 5 essential interview tips for a candidate applying for the position of "{position}".
    Focus on technical concepts, behavioral questions, and common pitfalls for this specific role.
    
    Output a JSON object with this EXACT structure:
    {{
        "tips": [
            "Tip 1...",
            "Tip 2...",
            "Tip 3...",
            "Tip 4...",
            "Tip 5..."
        ]
    }}
    """
    response_text = await get_gemini_response(prompt)
    
    # Cleanup and parse
    clean_json = response_text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(clean_json)
        return data
    except Exception:
        return {
            "tips": [
                f"Prepare for common {position} interview questions.",
                "Review the job description thoroughly.",
                "Practice the STAR method for behavioral questions.",
                "Research the company's recent news and culture.",
                "Prepare questions to ask the interviewer."
            ]
        }


async def generate_interview_prep_tips(role: str, company: str) -> str:
    """Generate rich interview prep tips for automation emails."""
    prompt = f"""Generate comprehensive interview preparation tips for a {role} position at {company}.

Include:
1. Top 5 technical topics to review
2. 3 common behavioral questions with brief STAR-method hints
3. A last-minute day-of checklist (5 items)

Format the output as clear, readable plain text (no JSON). Use numbered lists. Keep it concise but actionable.
"""
    response = await get_gemini_response(prompt)
    if response.startswith("Error:"):
        return f"Review key concepts for {role} roles, practice common algorithms, prepare STAR stories, research {company}'s recent projects, and get a good night's rest!"
    return response
