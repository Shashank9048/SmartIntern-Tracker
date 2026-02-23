import re

file_path = "SmartIntern-backend/api/index.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Mount routers
mount_code = """app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

# Mount new API routers
app.include_router(applications.router)
app.include_router(resume.router)
app.include_router(insights.router)
"""
content = content.replace('app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")', mount_code)

# 2. Fix imports: add ai_service imports explicitly
import_fix = """# Import explicit routes
from .routes import applications, resume, insights
from services.ai_service import parse_resume_json, generate_cold_email_ai, get_career_coach_response, get_interview_tips_ai
"""
content = content.replace("""# Import explicit routes
from .routes import applications, resume, insights""", import_fix)

# 3. Strip deprecated /user/upload-resume
content = re.sub(r'@app\.post\("/user/upload-resume"\).*?(?=# 2\. APPLICATIONS CRUD \(Protected\))', '', content, flags=re.DOTALL)

# 4. Strip old CRUD for applications
content = re.sub(r'# 2\. APPLICATIONS CRUD \(Protected\)\n@app\.get\("/api/applications"\).*?(?=@app\.get\("/api/applications/interviews"\))', '# 2. APPLICATIONS CRUD (Protected)\n', content, flags=re.DOTALL)
content = re.sub(r'@app\.delete\("/api/applications/\{id\}"\).*?(?=class FollowUpRequest)', '', content, flags=re.DOTALL)

# 5. Strip old AI analysis logic but KEEP chat/email automation
content = re.sub(r'# 3\. AI FEATURES\nclass AnalyzeRequest.*?@app\.get\("/api/insights"\).*?(?=class EmailRequest)', '# 3. AI FEATURES\n', content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("index.py refactored successfully.")
