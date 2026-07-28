from beanie import Document, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List, Literal, Any, Dict

class DashboardInsightCache(BaseModel):
    last_updated: datetime = datetime.now()
    trends: str
    improvement_strategy: str
    follow_up_suggestions: List[str]
    learning_roadmap: str

# ─────────────────────────────────────────────────────────────────────────────
# JOBS — job postings (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

class Job(Document):
    title: str
    company: str
    description: str
    required_skills: List[str] = []
    location: str
    source: Literal["manual", "adzuna", "jsearch", "mock"] = "mock"
    external_id: Optional[str] = None
    application_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "jobs"

class UserJobMatch(Document):
    user_id: str
    job_id: str
    match_score: int
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    resume_version: str
    computed_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "user_job_matches"

# ─────────────────────────────────────────────────────────────────────────────
# TRACKED JOB — feed-sourced kanban tracker (Phase 6B)
# ─────────────────────────────────────────────────────────────────────────────

class TrackedJob(Document):
    """
    Created when a user clicks Apply or Save on a recommended job card.
    Distinct from Application (manual tracker) — this collection is linked
    to a Job document via job_id.
    """
    user_id: str                          # user email
    job_id: str                           # str(_id) of Job document
    status: Literal[
        "wishlist", "applied", "oa",
        "interview", "offer", "rejected"
    ] = "wishlist"
    match_score_at_save: int = 0          # locked from UserJobMatch at creation
    applied_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "tracked_jobs"


# ─────────────────────────────────────────────────────────────────────────────
# RESUME — structured storage (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

class Resume(Document):
    """
    One document per user (upserted on every upload).
    parsed_json holds the Gemini-extracted structure:
      { name, email, linkedin, phone, skills[], education[], experience[], projects[], certifications[] }
    resume_version is a short hash of raw_text so matching can skip re-scoring
    unchanged resumes.
    """
    user_id: str                          # user email (FK → User.email)
    raw_text: str                         # full extracted PDF/DOCX text
    parsed_json: Dict[str, Any] = {}      # Gemini-parsed structured data
    file_url: Optional[str] = None        # /static/resumes/<filename>
    original_filename: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)
    resume_version: str = ""              # sha256[:12] of raw_text for cache-busting
    status: str = "parsed"                # pending | parsed | failed
    cloudinary_public_id: Optional[str] = None

    class Settings:
        name = "resumes"

# --- AUTH MODELS ---
class User(Document):
    email: str
    password_hash: str
    full_name: str
    branch: str = ""
    graduation_year: str = ""
    skills: List[str] = []
    resume_text: Optional[str] = None       # kept for backward compat with existing AI features
    uploaded_file_url: Optional[str] = None
    profile_picture: Optional[str] = None
    # Phase 2 additions
    resume_id: Optional[str] = None         # str(_id) of the Resume document
    profile_complete_pct: int = 0           # 0-100, updated on each save
    preferences: dict = {"theme": "system", "notifications": {"email": True, "interview": True, "marketing": False}}
    dashboard_insights: Optional[DashboardInsightCache] = None
    created_at: datetime = datetime.now()

    class Settings:
        name = "users"

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    branch: Optional[str] = ""
    graduation_year: Optional[str] = ""
    skills: List[str] = []

class UserAuth(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ApplicationCreate(BaseModel):
    company_name: str
    role: str
    status: str
    applied_date: datetime
    interview_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    notes: Optional[str] = None
    job_description: Optional[str] = None

class ApplicationUpdate(BaseModel):
    company_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    applied_date: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    notes: Optional[str] = None
    job_description: Optional[str] = None

class ActionPlanItem(BaseModel):
    priority: str
    title: str
    description: str

class ResumeCompleteness(BaseModel):
    has_summary: bool
    has_projects: bool
    has_experience: bool
    has_skills_section: bool
    has_education: bool

class ApplicationAnalysis(BaseModel):
    overall_match_score: int
    experience_alignment: str
    skills_found: List[str]
    missing_skills: List[str]
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    ats_score: int
    summary: str
    resume_completeness: ResumeCompleteness
    resume_snapshot: str  # the resume text used at the time of analysis
    job_description: Optional[str] = None # the specific JD used

class Application(Document):
    user_id: str
    company_name: str
    role: str
    status: str = "Applied"
    applied_date: datetime = datetime.now()
    interview_date: Optional[datetime] = None
    notes: Optional[str] = None
    job_description: Optional[str] = None
    
    # Flattened AI Analysis Fields
    ai_match_score: Optional[int] = None 
    ai_experience_alignment: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_missing_skills: List[str] = []
    ai_suggestions: List[str] = []
    
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    class Settings:
        name = "applications"

class Reminder(Document):
    user_id: str
    application_id: str
    date: datetime = datetime.now()
    type: str = "Follow-up"

    class Settings:
        name = "reminders"

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = datetime.now()

class ChatHistory(Document):
    user_email: str
    messages: List[ChatMessage] = []
    created_at: datetime = datetime.now()

    class Settings:
        name = "chat_histories"

# --- RESUME ANALYSIS MODELS ---

class ResumeAnalysis(Document):
    user_email: str
    resume_text: str
    job_description: str
    overall_match_score: int
    experience_alignment: str
    skills_found: List[str]
    missing_skills: List[str]
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    ats_score: int
    summary: str
    resume_completeness: ResumeCompleteness
    created_at: datetime = datetime.now()

    class Settings:
        name = "resume_analyses"


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATION MODELS
# ─────────────────────────────────────────────────────────────────────────────

class AutomationCreate(BaseModel):
    application_id: str
    type: Literal["followup", "interview", "status"]
    scheduled_at: datetime
    email_enabled: bool = True
    ai_prep_enabled: bool = True

class AutomationUpdate(BaseModel):
    status: Optional[Literal["active", "paused", "completed"]] = None
    email_enabled: Optional[bool] = None
    ai_prep_enabled: Optional[bool] = None
    scheduled_at: Optional[datetime] = None

class Automation(Document):
    user_id: str                          # stores user email (matches Application.user_id)
    application_id: str
    type: str                             # followup | interview | status
    scheduled_at: datetime
    email_enabled: bool = True
    ai_prep_enabled: bool = True
    status: str = "active"               # active | paused | completed
    created_at: datetime = datetime.now()

    class Settings:
        name = "automations"

class AutomationLog(Document):
    automation_id: str
    user_id: str
    triggered_at: datetime = datetime.now()
    email_sent: bool = False
    ai_tips: Optional[str] = None
    error: Optional[str] = None

    class Settings:
        name = "automation_logs"

# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS — in-app bell & email tracking (Phase 7)
# ─────────────────────────────────────────────────────────────────────────────

class Notification(Document):
    user_id: str
    type: Literal["digest", "deadline", "interview"]
    payload: dict
    read_bool: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "notifications"