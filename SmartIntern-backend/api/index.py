from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, PydanticObjectId
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import sys
import os
import asyncio
import hashlib
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Robust .env loading
current_dir = os.path.dirname(os.path.abspath(__file__))
while current_dir != os.path.dirname(current_dir): # Stop at root
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
        break
    current_dir = os.path.dirname(current_dir)
else:
    print("⚠️ WARNING: .env file not found in any parent directory")

# Import models
from .models import (
    Application, User, UserAuth, UserSignup, Token, ResumeAnalysis,
    ChatHistory, ApplicationCreate, ApplicationUpdate, Reminder,
    Automation, AutomationLog, AutomationCreate, AutomationUpdate,
    Resume, Job, UserJobMatch, TrackedJob
)
from .auth import get_password_hash, verify_password, create_access_token, get_current_user
from .ai_utils import parse_resume_json, generate_cold_email_ai, get_career_coach_response, get_interview_tips_ai
from .gmail_utils import send_email_smtp, scan_inbox_imap, send_automation_email
from .pdf_utils import extract_text_from_pdf
from .ai_utils import generate_interview_prep_tips

# Import route modules (use relative imports internally)
from .routes import applications, resume, insights

# ── Scheduler ────────────────────────────────────────────────────────────────

async def run_automation_scheduler():
    """Background job: fire due automations every 60 seconds."""
    while True:
        try:
            now = datetime.now()
            due = []
            try:
                due = await Automation.find(
                    Automation.status == "active",
                    Automation.scheduled_at <= now,
                ).to_list()
            except Exception as e:
                # DB not initialized or query failed
                pass

            for automation in due:
                try:
                    print(f"🔔 Firing automation {automation.id} [{automation.type}]")
                    app_doc = None
                    company = "Unknown Company"
                    role = "Unknown Role"
                    try:
                        app_doc = await Application.get(PydanticObjectId(automation.application_id))
                        if app_doc:
                            company = app_doc.company_name
                            role = app_doc.role
                    except Exception:
                        pass

                    ai_tips = None
                    if automation.ai_prep_enabled and automation.type in ("interview", "followup"):
                        try:
                            ai_tips = await generate_interview_prep_tips(role, company)
                        except Exception as e:
                            print(f"⚠️ AI tips error: {e}")

                    email_sent = False
                    email_error = None
                    if automation.email_enabled:
                        user = await User.find_one(User.email == automation.user_id)
                        to_email = user.email if user else automation.user_id
                        scheduled_str = automation.scheduled_at.strftime("%B %d, %Y at %I:%M %p")
                        result = send_automation_email(
                            to_email=to_email,
                            company=company,
                            role=role,
                            automation_type=automation.type,
                            scheduled_at=scheduled_str,
                            ai_tips=ai_tips,
                        )
                        email_sent = result.get("status") == "sent"
                        email_error = result.get("error")

                    # Mark completed
                    automation.status = "completed"
                    await automation.save()

                    # Log
                    log = AutomationLog(
                        automation_id=str(automation.id),
                        user_id=automation.user_id,
                        email_sent=email_sent,
                        ai_tips=ai_tips,
                        error=email_error,
                    )
                    await log.insert()
                    print(f"✅ Automation {automation.id} completed. Email sent: {email_sent}")

                except Exception as e:
                    print(f"❌ Error firing automation {automation.id}: {e}")
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
            import traceback
            traceback.print_exc()
            
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_url = os.environ.get("MONGODB_URL")
    if mongo_url:
        try:
            client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
            await init_beanie(
                database=client["smart_intern_tracker"],
                document_models=[
                    Application, User, ResumeAnalysis, ChatHistory,
                    Reminder, Automation, AutomationLog, Resume, Job,
                    UserJobMatch, TrackedJob
                ]
            )
            print("✅ Database Connected")
        except Exception as e:
            print(f"⚠️ Database Connection Error: {e}")
            print("⚠️ Server started, but MongoDB connection failed. Please check network/MONGODB_URL.")
    else:
        print("⚠️ WARNING: MONGODB_URL not found")

    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pass:
        print("⚠️ WARNING: Gmail credentials not found. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env for email automation.")
    else:
        print(f"✅ Gmail Credentials Found ({gmail_user})")

    # Start background automation scheduler native to event loop
    automation_task = asyncio.create_task(run_automation_scheduler())
    print("✅ Automation Scheduler Started (60s interval)")

    yield

    automation_task.cancel()
    print("🛑 Automation Scheduler Stopped")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import shutil
from fastapi.staticfiles import StaticFiles

# Setup local static folders for avatars and resumes
AVATAR_DIR = os.path.join(current_dir, "static", "avatars")
RESUME_DIR = os.path.join(current_dir, "static", "resumes")
os.makedirs(AVATAR_DIR, exist_ok=True)
os.makedirs(RESUME_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

# All new API routes added inline below (no router modules needed)
import json, re, ast


@app.get("/")
def root():
    return {"status": "Backend Running", "modules": ["Auth", "AI", "CRUD", "Automation"]}

@app.get("/ping")
def ping():
    return {"pong": True}

# 1. AUTHENTICATION

@app.post("/auth/signup", response_model=Token)
async def signup(user_data: UserSignup):
    try:
        # Check if email exists
        existing_user = await User.find_one(User.email == user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash the password
        hashed_pw = get_password_hash(user_data.password)

        # Create User document
        new_user = User(
            email=user_data.email,
            password_hash=hashed_pw,
            full_name=user_data.full_name,
            branch=user_data.branch or "",
            graduation_year=user_data.graduation_year or "",
            skills=user_data.skills
        )
        await new_user.insert()
        
        # Auto-login: Create access token
        access_token = create_access_token(data={"sub": new_user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Signup Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserAuth):
    user = await User.find_one(User.email == user_data.email)
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me")
async def auth_me(current_user: str = Depends(get_current_user)):
    """Spec-required alias for GET /user/me — returns the authenticated user's profile."""
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/auth/logout")
async def logout(current_user: str = Depends(get_current_user)):
    """JWT is stateless — actual token invalidation is client-side.
    This endpoint exists so the frontend can call it to ack logout
    (useful for audit logging or future server-side token blocklist)."""
    return {"message": "Logged out successfully", "email": current_user}

# ─── FORGOT PASSWORD (OTP-based) ─────────────────────────────────────────────

import random
import time as _time

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

@app.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """Send a 6-digit OTP to the user's email for password reset."""
    user = await User.find_one(User.email == data.email)
    if not user:
        # Return 200 even if user not found (security: don't reveal email existence)
        return {"message": "If this email is registered, a reset code has been sent."}

    otp = str(random.randint(100000, 999999))
    # Store OTP + expiry (10 min) in user record temporarily
    user.preferences["_otp"] = otp
    user.preferences["_otp_expires"] = _time.time() + 600
    await user.save()

    # Send via Gmail
    subject = "SmartIntern – Your Password Reset Code"
    body = f"""
Hi {user.full_name},

Your password reset code is:

  {otp}

This code expires in 10 minutes.
If you didn't request this, you can safely ignore this email.

– SmartIntern Team
"""
    try:
        result = send_email_smtp(data.email, subject, body)
        if result.get("status") != "sent":
            raise Exception(result.get("error", "Failed to send email"))
    except Exception as e:
        print(f"⚠️ OTP email error: {e}")
        raise HTTPException(status_code=500, detail="Could not send reset email. Check Gmail configuration.")

    return {"message": "Reset code sent to your email."}


@app.post("/auth/verify-otp")
async def verify_otp(data: VerifyOTPRequest):
    """Verify the OTP without resetting the password (pre-validation step)."""
    user = await User.find_one(User.email == data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stored_otp = user.preferences.get("_otp")
    otp_expires = user.preferences.get("_otp_expires", 0)

    if not stored_otp or data.otp != stored_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if _time.time() > otp_expires:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    return {"message": "OTP verified"}


@app.post("/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """Verify OTP and update the user's password."""
    user = await User.find_one(User.email == data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stored_otp = user.preferences.get("_otp")
    otp_expires = user.preferences.get("_otp_expires", 0)

    if not stored_otp or data.otp != stored_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if _time.time() > otp_expires:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Update password + clear OTP
    user.password_hash = get_password_hash(data.new_password)
    user.preferences.pop("_otp", None)
    user.preferences.pop("_otp_expires", None)
    await user.save()

    return {"message": "Password reset successfully. You can now log in."}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferences: Optional[dict] = None
    resume_text: Optional[str] = None

@app.get("/user/me", response_model=User)
async def get_current_user_profile(current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.patch("/user/me", response_model=User)
async def update_user_profile(data: UpdateProfileRequest, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.resume_text is not None:
        user.resume_text = data.resume_text
    if data.email and data.email != user.email:
        # Check if new email is taken
        existing = await User.find_one(User.email == data.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = data.email
    if data.preferences:
        user.preferences = data.preferences
        
    await user.save()
    return user

@app.delete("/user/me", status_code=204)
async def delete_account(current_user: str = Depends(get_current_user)):
    """Permanently delete the authenticated user's account and all associated data."""
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_email = user.email

    # Delete all applications for this user
    try:
        await Application.find(Application.user_id == user_email).delete()
    except Exception as e:
        print(f"⚠️ Deleting applications error: {e}")

    # Delete all automations and their logs
    try:
        await Automation.find(Automation.user_id == user_email).delete()
        await AutomationLog.find(AutomationLog.user_id == user_email).delete()
    except Exception as e:
        print(f"⚠️ Deleting automations error: {e}")

    # Delete chat history
    try:
        await ChatHistory.find(ChatHistory.user_email == user_email).delete()
    except Exception as e:
        print(f"⚠️ Deleting chat history error: {e}")

    # Delete resume analyses
    try:
        await ResumeAnalysis.find(ResumeAnalysis.user_email == user_email).delete()
    except Exception as e:
        print(f"⚠️ Deleting resume analyses error: {e}")

    # Delete structured Resume document (Phase 2)
    try:
        resume_doc = await Resume.find_one(Resume.user_id == user_email)
        if resume_doc:
            await resume_doc.delete()
    except Exception as e:
        print(f"⚠️ Deleting resume doc error: {e}")

    # Delete avatar file from disk if it's a local file
    try:
        if user.profile_picture and not user.profile_picture.startswith("http"):
            avatar_path = os.path.join(
                os.path.dirname(__file__), "..", user.profile_picture.lstrip("/").replace("/", os.sep)
            )
            if os.path.exists(avatar_path):
                os.remove(avatar_path)
                print(f"🗑️ Deleted avatar: {avatar_path}")
    except Exception as e:
        print(f"⚠️ Deleting avatar error: {e}")

    # Finally delete the user document itself
    await user.delete()
    print(f"✅ Account deleted: {user_email}")
    return  # 204 No Content


@app.post("/user/upload-avatar")
async def upload_avatar(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
        
    # Generate unique filename
    ext = file.filename.split(".")[-1]
    safe_filename = f"{current_user.replace('@', '_').replace('.', '_')}_{int(datetime.now().timestamp())}.{ext}"
    filepath = os.path.join(AVATAR_DIR, safe_filename)
    
    # Save file
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")
        
    # Update user DB URL (pointing to mounted static path)
    # Assuming FastAPI matches the host server IP/port in production
    profile_url = f"/static/avatars/{safe_filename}"
    user.profile_picture = profile_url
    await user.save()
    
    return {"message": "Avatar uploaded successfully", "profile_picture_url": profile_url, "user": user}

@app.post("/user/change-password")
async def change_password(data: ChangePasswordRequest, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    user.password_hash = get_password_hash(data.new_password)
    await user.save()
    return {"message": "Password updated successfully"}

@app.get("/dashboard/stats")
async def get_dashboard_stats(current_user: str = Depends(get_current_user)):
    # FIXED: use user_id (not user_email)
    apps = await Application.find(Application.user_id == current_user).to_list()
    
    total = len(apps)
    interviews = sum(1 for app in apps if app.status.lower() == "interview")
    offers = sum(1 for app in apps if app.status.lower() in ("offer", "selected"))
    rejected = sum(1 for app in apps if app.status.lower() == "rejected")
    
    import calendar
    from collections import defaultdict
    monthly_counts = defaultdict(int)
    for app in apps:
        try:
            month_name = calendar.month_abbr[app.applied_date.month]
            monthly_counts[month_name] += 1
        except Exception:
            pass
        
    chart_data = [{"month": k, "applications": v} for k, v in monthly_counts.items()]
    
    return {
        "total": total,
        "interviews": interviews,
        "offers": offers,
        "rejected": rejected,
        "chartData": chart_data
    }

# 2. APPLICATIONS CRUD (Protected)
@app.get("/api/applications/interviews")
async def get_upcoming_interviews(current_user: str = Depends(get_current_user)):
    apps = await Application.find(Application.user_id == current_user).to_list()
    interviews = []
    for app in apps:
        if app.status.lower() == "interview":
            time_str = "Scheduled"
            if app.interview_date:
                time_str = app.interview_date.strftime("%b %d, %I:%M %p")
            interviews.append({
                "company_name": app.company_name,
                "time": time_str
            })
    return interviews

class FollowUpRequest(BaseModel):
    applicationId: str
    type: str

@app.post("/api/followup")
async def create_followup(data: FollowUpRequest, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    app_doc = await Application.get(PydanticObjectId(data.applicationId))
    if not app_doc or app_doc.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
        
    rem = Reminder(
        user_id=current_user,
        application_id=data.applicationId,
        type=data.type,
        date=datetime.now()
    )
    await rem.insert()
    return {"message": "Follow-up reminder created"}

class ParseResumeRequest(BaseModel):
    resume_text: str

@app.post("/ai/parse_resume")
async def api_parse_resume(req: ParseResumeRequest, current_user: str = Depends(get_current_user)):
    return await parse_resume_json(req.resume_text)

# 3. AI FEATURES
class EmailRequest(BaseModel):
    job_description: str
    recruiter_email: Optional[str] = None
    role: Optional[str] = "Developer"

@app.post("/automation/send-cold-email")
async def send_cold_email_endpoint(req: EmailRequest, current_user: str = Depends(get_current_user)):
    email_body = await generate_cold_email_ai(req.job_description, req.role)
    if req.recruiter_email:
        result = send_email_smtp(req.recruiter_email, f"Application for {req.role}", email_body)
        if "error" in result:
             raise HTTPException(status_code=500, detail=result["error"])
        return {"message": "Email sent!", "body": email_body}
    return {"message": "Email generated (not sent)", "body": email_body}

# 4. CHAT ASSISTANT
class ChatRequest(BaseModel):
    message: str

@app.post("/ai/chat")
async def ai_chat(req: ChatRequest, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resume_context = user.resume_text if user.resume_text else "No resume provided."

    # Fetch History
    chat_history_doc = await ChatHistory.find_one(ChatHistory.user_email == current_user)
    if not chat_history_doc:
        chat_history_doc = ChatHistory(user_email=current_user, messages=[])
        await chat_history_doc.insert()

    # Pass previous conversation context
    # Get last 5 messages to preserve token window
    history_context = "\n".join([f"{m.role}: {m.content}" for m in chat_history_doc.messages[-5:]])
    
    full_prompt_context = f"PREVIOUS CHAT HISTORY:\n{history_context}\n\nRESUME CONTEXT:\n{resume_context}"

    # Generate response
    response = await get_career_coach_response(req.message, resume_context=full_prompt_context)

    # Save to history
    from .models import ChatMessage
    chat_history_doc.messages.append(ChatMessage(role="user", content=req.message))
    chat_history_doc.messages.append(ChatMessage(role="assistant", content=response))
    await chat_history_doc.save()

    return {"reply": response}

class InterviewTipsRequest(BaseModel):
    position: str

@app.post("/ai/interview-tips")
async def ai_interview_tips(req: InterviewTipsRequest, current_user: str = Depends(get_current_user)):
    return await get_interview_tips_ai(req.position)

# 5. SMART AUTOMATION & REMINDERS
@app.get("/automation/scan-inbox")
async def scan_inbox_endpoint(current_user: str = Depends(get_current_user)):
    updates = scan_inbox_imap()
    if isinstance(updates, dict) and "error" in updates:
        raise HTTPException(status_code=500, detail=updates["error"])
    return {"updates": updates}

@app.get("/automation/run")
async def run_automation(current_user: str = Depends(get_current_user)):
    # FIXED: use user_id (not user_email) and company_name (not company)
    apps = await Application.find(Application.user_id == current_user).to_list()
    notifications = []
    today = datetime.now()
    for app in apps:
        if app.interview_date:
            diff = (app.interview_date - today).total_seconds() / 3600
            if 0 < diff < 24:
                notifications.append({
                    "id": str(app.id),
                    "type": "alert",
                    "message": f"🚀 Good luck! Interview with {app.company_name} is tomorrow!"
                })
        days_since_applied = (today - app.applied_date).days
        if app.status == "Applied" and days_since_applied > 14:
             notifications.append({
                 "id": str(app.id),
                 "type": "info",
                 "message": f"No news from {app.company_name} in 2 weeks. Time to follow up?"
             })
    return {"notifications": notifications}


# ─────────────────────────────────────────────────────────────────────────────
# NEW: /api/applications  CRUD
# ─────────────────────────────────────────────────────────────────────────────
from .ai_utils import analyze_resume_match

class AppCreateInline(BaseModel):
    company_name: str
    role: str
    status: str = "Applied"
    applied_date: datetime = None
    interview_date: Optional[datetime] = None
    notes: Optional[str] = None
    job_description: Optional[str] = None

class AppUpdateInline(BaseModel):
    company_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    applied_date: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    notes: Optional[str] = None

@app.get("/api/applications")
async def list_apps(current_user: str = Depends(get_current_user)):
    return await Application.find(Application.user_id == current_user).sort(-Application.created_at).to_list()

@app.get("/api/applications/{app_id}")
async def get_single_app(app_id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    app_doc = await Application.get(app_id)
    if not app_doc or app_doc.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_doc

@app.post("/api/applications")
async def add_app(data: AppCreateInline, current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ai_score = None
    ai_alignment = None
    ai_summary_text = None
    ai_missing = []
    ai_suggestions_list = []

    resume_text_to_use = None
    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if resume_doc and resume_doc.raw_text:
        resume_text_to_use = resume_doc.raw_text
    elif user.resume_text:
        resume_text_to_use = user.resume_text

    if resume_text_to_use:
        try:
            jd = data.job_description or f"{data.role} at {data.company_name}"
            result = await analyze_resume_match(resume_text_to_use, jd)
            ai_score = result.get("overall_match_score") or result.get("match_score", 0)
            ai_alignment = result.get("experience_alignment", "Low")
            ai_summary_text = result.get("summary", "")
            ai_missing = result.get("missing_skills", [])
            ai_suggestions_list = result.get("improvement_suggestions") or [
                a.get("description", "") for a in result.get("action_plan", [])
            ]
        except Exception as e:
            print(f"AI scoring error: {e}")

    new_app = Application(
        user_id=current_user,
        company_name=data.company_name,
        role=data.role,
        status=data.status,
        applied_date=data.applied_date or datetime.now(),
        interview_date=data.interview_date,
        notes=data.notes,
        job_description=data.job_description,
        ai_match_score=ai_score,
        ai_experience_alignment=ai_alignment,
        ai_summary=ai_summary_text,
        ai_missing_skills=ai_missing,
        ai_suggestions=ai_suggestions_list,
    )
    await new_app.insert()
    return new_app


@app.post("/api/applications/score-all")
async def api_score_all_applications(current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resume_text_to_use = None
    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if resume_doc and resume_doc.raw_text:
        resume_text_to_use = resume_doc.raw_text
    elif user.resume_text:
        resume_text_to_use = user.resume_text

    if not resume_text_to_use:
        return {"scored": 0, "message": "No resume available for scoring"}

    unscored_apps = await Application.find(
        Application.user_id == current_user,
        Application.ai_match_score == None
    ).to_list()

    count = 0
    for app_doc in unscored_apps:
        try:
            jd = app_doc.job_description or f"{app_doc.role} at {app_doc.company_name}"
            result = await analyze_resume_match(resume_text_to_use, jd)
            app_doc.ai_match_score = result.get("overall_match_score") or result.get("match_score", 0)
            app_doc.ai_experience_alignment = result.get("experience_alignment", "Low")
            app_doc.ai_summary = result.get("summary", "")
            app_doc.ai_missing_skills = result.get("missing_skills", [])
            app_doc.ai_suggestions = result.get("improvement_suggestions") or [
                a.get("description", "") for a in result.get("action_plan", [])
            ]
            await app_doc.save()
            count += 1
        except Exception as e:
            print(f"Error scoring app {app_doc.id}: {e}")

    return {"scored": count, "message": f"Successfully scored {count} applications"}

@app.patch("/api/applications/{app_id}")
@app.put("/api/applications/{app_id}")
async def modify_app(app_id: PydanticObjectId, data: AppUpdateInline, current_user: str = Depends(get_current_user)):
    app_doc = await Application.get(app_id)
    if not app_doc or app_doc.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
    if data.company_name is not None: app_doc.company_name = data.company_name
    if data.role is not None: app_doc.role = data.role
    if data.status is not None: app_doc.status = data.status
    if data.applied_date is not None: app_doc.applied_date = data.applied_date
    if data.interview_date is not None: app_doc.interview_date = data.interview_date
    if data.notes is not None: app_doc.notes = data.notes
    app_doc.updated_at = datetime.now()
    await app_doc.save()
    return app_doc

@app.delete("/api/applications/{app_id}")
async def remove_app(app_id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    app_doc = await Application.get(app_id)
    if not app_doc or app_doc.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")
    await app_doc.delete()
    return {"message": "Deleted", "id": str(app_id)}



# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: RESUME STORAGE & ASYNC AI PARSING
# ─────────────────────────────────────────────────────────────────────────────



def delete_physical_resume_file(file_url: Optional[str], cloudinary_id: Optional[str] = None):
    """
    Safely deletes resume file from local storage and Cloudinary if configured.
    """
    if cloudinary_id:
        try:
            import cloudinary.uploader
            cloudinary.uploader.destroy(cloudinary_id, resource_type="raw")
            print(f"✅ Cloudinary file deleted: {cloudinary_id}")
        except Exception as e:
            print(f"⚠️ Cloudinary delete failed for {cloudinary_id}: {e}")

    if file_url and file_url.startswith("/static/resumes/"):
        filename = os.path.basename(file_url)
        disk_path = os.path.join(RESUME_DIR, filename)
        if os.path.exists(disk_path):
            try:
                os.remove(disk_path)
                print(f"✅ Local resume file deleted: {disk_path}")
            except Exception as e:
                print(f"⚠️ Failed deleting local file {disk_path}: {e}")



async def process_resume_parsing_task(user_email: str, clean_text: str):
    """
    FastAPI BackgroundTask: Parses structured JSON from cleaned text,
    then updates the Resume document status to 'parsed' (or 'failed' on error).
    """
    try:
        parsed = await parse_resume_json(clean_text)
        if isinstance(parsed, dict) and "error" in parsed:
            print(f"⚠️ Resume parse warning for {user_email}: {parsed.get('error')}")
            parsed = {}

        resume_doc = await Resume.find_one(Resume.user_id == user_email)
        if resume_doc:
            resume_doc.parsed_json = parsed if isinstance(parsed, dict) else {}
            resume_doc.status = "parsed"
            await resume_doc.save()
            print(f"✅ Background resume parse completed for {user_email}")
    except Exception as e:
        print(f"❌ Background resume parse failed for {user_email}: {e}")
        resume_doc = await Resume.find_one(Resume.user_id == user_email)
        if resume_doc:
            resume_doc.status = "failed"
            await resume_doc.save()


class ResumeAnalyzeRequest(BaseModel):
    job_description: str
    resume_text: Optional[str] = None  # inline fallback from upload response


@app.post("/api/resume/upload")
@app.post("/users/me/resume")
async def api_resume_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """
    Phase 2 — Structured Resume Storage with Asynchronous Background Parsing.
    1. Removes any existing physical file to prevent orphan files.
    2. Saves new file to disk.
    3. Extracts & cleans text.
    4. Upserts a Resume document with status="pending".
    5. Returns IMMEDIATELY (< 100ms) while background task runs Gemini parse.
    """
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # ── Orphan Cleanup: remove old file if exists ─────────────────────────
        existing_resume = await Resume.find_one(Resume.user_id == current_user)
        if existing_resume:
            try:
                delete_physical_resume_file(existing_resume.file_url, existing_resume.cloudinary_public_id)
            except Exception as oe:
                print(f"⚠️ Orphan file deletion warning: {oe}")

        # ── Save new file ─────────────────────────────────────────────────────
        ext = (file.filename or "resume.pdf").rsplit(".", 1)[-1].lower()
        safe_name = f"{current_user.replace('@','_').replace('.','_')}_{int(datetime.now().timestamp())}.{ext}"
        filepath = os.path.join(RESUME_DIR, safe_name)

        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        await file.seek(0)

        # ── Extract & clean text ──────────────────────────────────────────────
        raw_text = await extract_text_from_pdf(file)
        from .ai_utils import clean_extracted_text
        cleaned_text = clean_extracted_text(raw_text)

        version_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()[:12] if cleaned_text else ""
        file_url = f"/static/resumes/{safe_name}"

        # ── Upsert Resume document with status="pending" ──────────────────────
        if existing_resume:
            existing_resume.raw_text = cleaned_text
            existing_resume.parsed_json = {}
            existing_resume.file_url = file_url
            existing_resume.original_filename = file.filename or safe_name
            existing_resume.uploaded_at = datetime.now()
            existing_resume.resume_version = version_hash
            existing_resume.status = "pending"
            await existing_resume.save()
            resume_doc = existing_resume
        else:
            resume_doc = Resume(
                user_id=current_user,
                raw_text=cleaned_text,
                parsed_json={},
                file_url=file_url,
                original_filename=file.filename or safe_name,
                resume_version=version_hash,
                status="pending",
            )
            await resume_doc.insert()

        # ── Update User profile ───────────────────────────────────────────────
        user.resume_text = cleaned_text
        user.uploaded_file_url = file_url
        user.resume_id = str(resume_doc.id)
        await user.save()

        # ── Enqueue Background Gemini Parse Task ──────────────────────────────
        background_tasks.add_task(process_resume_parsing_task, current_user, cleaned_text)

        return {
            "status": "pending",
            "message": "Resume uploaded successfully. Parsing structured profile in background...",
            "full_text": cleaned_text,
            "text_preview": cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text,
            "uploaded_file_url": file_url,
            "filename": file.filename,
            "characters": len(cleaned_text),
            "resume_version": version_hash,
            "parsed": {},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.get("/api/resume/me")
@app.get("/users/me/resume")
async def api_get_resume(current_user: str = Depends(get_current_user)):
    """
    Phase 2 — Return the user's stored structured Resume document with status.
    """
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if not resume_doc:
        if user.resume_text:
            return {
                "id": None,
                "user_id": current_user,
                "status": "parsed",
                "raw_text": user.resume_text,
                "parsed_json": {},
                "file_url": user.uploaded_file_url,
                "original_filename": None,
                "uploaded_at": None,
                "resume_version": "",
            }
        raise HTTPException(status_code=404, detail="No resume uploaded yet")

    return {
        "id": str(resume_doc.id),
        "user_id": resume_doc.user_id,
        "status": getattr(resume_doc, "status", "parsed"),
        "raw_text": resume_doc.raw_text,
        "parsed_json": resume_doc.parsed_json,
        "file_url": resume_doc.file_url,
        "original_filename": resume_doc.original_filename,
        "uploaded_at": resume_doc.uploaded_at.isoformat() if resume_doc.uploaded_at else None,
        "resume_version": resume_doc.resume_version,
    }


@app.delete("/api/resume/me")
@app.delete("/users/me/resume")
async def api_delete_resume(current_user: str = Depends(get_current_user)):
    """
    Phase 2 — Hard Delete Resume:
    1. Physical file deletion (disk & Cloudinary).
    2. Drops Resume document.
    3. Clears User profile fields.
    4. Invalidates all stale ResumeAnalysis records for this user.
    """
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if not resume_doc and not user.resume_text and not user.uploaded_file_url:
        raise HTTPException(status_code=404, detail="No stored resume found to delete")

    # 1. Physical file deletion & Resume document drop
    if resume_doc:
        try:
            delete_physical_resume_file(resume_doc.file_url, getattr(resume_doc, "cloudinary_public_id", None))
        except Exception as e:
            print(f"⚠️ Physical file deletion warning: {e}")
        await resume_doc.delete()
    elif user.uploaded_file_url:
        try:
            delete_physical_resume_file(user.uploaded_file_url)
        except Exception as e:
            print(f"⚠️ Physical file deletion warning: {e}")

    # 2. Clear user profile fields
    user.resume_text = None
    user.uploaded_file_url = None
    user.resume_id = None
    await user.save()

    # 3. Invalidate stale ResumeAnalysis records computed against this resume
    try:
        deleted_count = await ResumeAnalysis.find(ResumeAnalysis.user_email == current_user).delete()
        print(f"✅ Invalidated {deleted_count} stale ResumeAnalysis records for {current_user}")
    except Exception as ae:
        print(f"⚠️ Warning: could not delete ResumeAnalysis records: {ae}")

    return {"success": True, "message": "Resume deleted successfully and job match records invalidated"}


@app.post("/api/resume/analyze")
async def api_resume_analyze(data: ResumeAnalyzeRequest, current_user: str = Depends(get_current_user)):
    """
    Phase 2 — Analyzes resume vs. a job description.
    Text priority: stored Resume.raw_text > User.resume_text > inline request.resume_text
    """
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Resolve resume text — prefer stored Resume doc, then user profile, then inline fallback
    resume_text_to_use: Optional[str] = None
    resume_doc = await Resume.find_one(Resume.user_id == current_user)
    if resume_doc and resume_doc.raw_text:
        resume_text_to_use = resume_doc.raw_text
    elif user.resume_text:
        resume_text_to_use = user.resume_text
    elif data.resume_text:
        resume_text_to_use = data.resume_text

    if not resume_text_to_use:
        raise HTTPException(
            status_code=400,
            detail="No resume text found. Please upload your resume first."
        )

    try:
        result = await analyze_resume_match(resume_text_to_use, data.job_description)
        # Normalize key names so both old and new frontend keys work
        result["overall_match_score"] = result.get("overall_match_score") or result.get("match_score", 0)
        result["improvement_suggestions"] = result.get("improvement_suggestions") or [
            a.get("description", "") for a in result.get("action_plan", [])
        ]
        result["summary"] = result.get("summary", "")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {e}")




# ─────────────────────────────────────────────────────────────────────────────
# NEW: /api/insights/dashboard
# ─────────────────────────────────────────────────────────────────────────────
from .models import DashboardInsightCache

@app.get("/api/insights/dashboard")
async def api_dashboard_insights(current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return cached if < 24h old
    if user.dashboard_insights:
        diff = (datetime.now() - user.dashboard_insights.last_updated).total_seconds()
        if diff < 86400:
            return user.dashboard_insights

    apps = await Application.find(Application.user_id == current_user).to_list()
    if not apps:
        return {
            "trends": "No applications yet. Start tracking to see AI insights!",
            "improvement_strategy": "Add your first application to get started.",
            "follow_up_suggestions": [],
            "learning_roadmap": "Upload a resume and apply to unlock personalized insights.",
        }

    condensed = [{"role": a.role, "company": a.company_name, "score": a.ai_match_score, "missing": a.ai_missing_skills, "status": a.status} for a in apps]
    prompt = f"""
You are an expert Career Coach. Analyze this candidate's internship application history:
{json.dumps(condensed, indent=2)}

Identify skill gaps, trends, and recommendations.

Output ONLY raw JSON:
{{
    "trends": "Detailed trend analysis paragraph.",
    "improvement_strategy": "Concrete improvement strategy.",
    "follow_up_suggestions": ["Company A - reason", "Company B - reason"],
    "learning_roadmap": "Focus on top 2-3 missing skills with resources."
}}
"""
    from .ai_utils import get_gemini_response
    raw = await get_gemini_response(prompt)
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m: clean = m.group(0)
        clean = re.sub(r',\s*\}', '}', clean)
        clean = re.sub(r',\s*\]', ']', clean)
        insights_data = json.loads(clean)
    except Exception:
        insights_data = {"trends": "Could not generate insights now.", "improvement_strategy": "Keep applying!", "follow_up_suggestions": [], "learning_roadmap": "Build core skills."}

    cache = DashboardInsightCache(
        trends=insights_data.get("trends", ""),
        improvement_strategy=insights_data.get("improvement_strategy", ""),
        follow_up_suggestions=insights_data.get("follow_up_suggestions", []),
        learning_roadmap=insights_data.get("learning_roadmap", ""),
    )
    user.dashboard_insights = cache
    await user.save()
    return cache


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATION CRUD ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/automations/stats")
async def get_automation_stats(current_user: str = Depends(get_current_user)):
    """Overview counts for the automation dashboard section."""
    now = datetime.now()
    from datetime import timedelta
    week_end = now + timedelta(days=7)

    all_autos = await Automation.find(Automation.user_id == current_user).to_list()
    active = [a for a in all_autos if a.status == "active"]
    upcoming = [a for a in active if now <= a.scheduled_at <= week_end]

    # Interview automations this week
    interview_ids = [a.application_id for a in upcoming if a.type == "interview"]
    interviews_this_week = len(set(interview_ids))

    # Follow-ups due (overdue active)
    followups_due = len([a for a in active if a.type == "followup" and a.scheduled_at <= now])

    return {
        "total_active": len(active),
        "upcoming_reminders": len(upcoming),
        "interviews_this_week": interviews_this_week,
        "followups_due": followups_due,
    }


@app.get("/api/automations")
async def list_automations(current_user: str = Depends(get_current_user)):
    """Return all automations for the current user with application context."""
    automations = await Automation.find(
        Automation.user_id == current_user
    ).sort(-Automation.created_at).to_list()

    result = []
    for auto in automations:
        app_doc = None
        company = "Unknown"
        role = "Unknown"
        try:
            app_doc = await Application.get(PydanticObjectId(auto.application_id))
            if app_doc:
                company = app_doc.company_name
                role = app_doc.role
        except Exception:
            pass
        result.append({
            "id": str(auto.id),
            "application_id": auto.application_id,
            "company": company,
            "role": role,
            "type": auto.type,
            "scheduled_at": auto.scheduled_at.isoformat(),
            "email_enabled": auto.email_enabled,
            "ai_prep_enabled": auto.ai_prep_enabled,
            "status": auto.status,
            "created_at": auto.created_at.isoformat(),
        })
    return result


@app.post("/api/automations", status_code=201)
async def create_automation(data: AutomationCreate, current_user: str = Depends(get_current_user)):
    """Create a new automation rule for the current user."""
    # Verify the application belongs to the user
    try:
        app_doc = await Application.get(PydanticObjectId(data.application_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application_id")
    if not app_doc or app_doc.user_id != current_user:
        raise HTTPException(status_code=404, detail="Application not found")

    auto = Automation(
        user_id=current_user,
        application_id=data.application_id,
        type=data.type,
        scheduled_at=data.scheduled_at,
        email_enabled=data.email_enabled,
        ai_prep_enabled=data.ai_prep_enabled,
        status="active",
        created_at=datetime.now(),
    )
    await auto.insert()

    return {
        "id": str(auto.id),
        "application_id": auto.application_id,
        "company": app_doc.company_name,
        "role": app_doc.role,
        "type": auto.type,
        "scheduled_at": auto.scheduled_at.isoformat(),
        "email_enabled": auto.email_enabled,
        "ai_prep_enabled": auto.ai_prep_enabled,
        "status": auto.status,
        "created_at": auto.created_at.isoformat(),
    }


@app.put("/api/automations/{auto_id}")
async def update_automation(auto_id: PydanticObjectId, data: AutomationUpdate, current_user: str = Depends(get_current_user)):
    """Toggle status (active/paused/completed) or update fields."""
    auto = await Automation.get(auto_id)
    if not auto or auto.user_id != current_user:
        raise HTTPException(status_code=404, detail="Automation not found")

    if data.status is not None:
        auto.status = data.status
    if data.email_enabled is not None:
        auto.email_enabled = data.email_enabled
    if data.ai_prep_enabled is not None:
        auto.ai_prep_enabled = data.ai_prep_enabled
    if data.scheduled_at is not None:
        auto.scheduled_at = data.scheduled_at

    await auto.save()
    return {"id": str(auto.id), "status": auto.status, "message": "Automation updated"}


@app.delete("/api/automations/{auto_id}")
async def delete_automation(auto_id: PydanticObjectId, current_user: str = Depends(get_current_user)):
    """Delete an automation rule."""
    auto = await Automation.get(auto_id)
    if not auto or auto.user_id != current_user:
        raise HTTPException(status_code=404, detail="Automation not found")
    await auto.delete()
    return {"success": True, "message": "Automation deleted", "id": str(auto_id)}

from .routes.jobs import router as jobs_router
app.include_router(jobs_router)

from .routes.tracked_jobs import router as tracked_jobs_router
app.include_router(tracked_jobs_router)
