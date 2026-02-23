from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from ..auth import get_current_user
from ..models import User, DashboardInsightCache
from ..ai_utils import get_gemini_response
import json
import re
import ast

router = APIRouter(prefix="/api/insights", tags=["Insights"])

async def _generate_insights(apps_data: list) -> dict:
    if not apps_data:
        return {
            "trends": "No applications tracked yet.",
            "improvement_strategy": "Start tracking applications to see AI insights!",
            "follow_up_suggestions": [],
            "learning_roadmap": "Upload a resume and add applications to begin."
        }
    condensed = [{"role": a.get("role"), "company": a.get("company_name"), "score": a.get("ai_match_score", 0), "missing": a.get("ai_missing_skills", []), "status": a.get("status")} for a in apps_data]
    prompt = f"""
    Analyze this candidate's application history and give career insights:
    {json.dumps(condensed, indent=2)}
    
    Output ONLY raw JSON:
    {{
        "trends": "Detailed trend analysis paragraph",
        "improvement_strategy": "Concrete improvement strategy",
        "follow_up_suggestions": ["Company A - reason", "Company B - reason"],
        "learning_roadmap": "Focus on 2-3 missing skills roadmap"
    }}
    """
    raw = await get_gemini_response(prompt)
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m: clean = m.group(0)
        clean = re.sub(r',\s*\}', '}', clean)
        clean = re.sub(r',\s*\]', ']', clean)
        return json.loads(clean)
    except:
        return {"trends": "Unable to generate insights.", "improvement_strategy": "Keep applying!", "follow_up_suggestions": [], "learning_roadmap": "Continue building skills."}

@router.get("/dashboard")
async def get_dashboard_insights_route(current_user: str = Depends(get_current_user)):
    user = await User.find_one(User.email == current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Check cached insights (24h)
    now = datetime.now()
    if user.dashboard_insights:
         time_diff = (now - user.dashboard_insights.last_updated).total_seconds()
         if time_diff < 86400:
              return user.dashboard_insights
              
    from ..models import Application
    apps = await Application.find(Application.user_id == current_user).to_list()
    
    if not apps:
        return {
            "trends": "No applications yet. Start tracking to see AI insights!",
            "improvement_strategy": "Add your first application.",
            "follow_up_suggestions": [],
            "learning_roadmap": "Upload a resume and apply to get started.",
            "last_updated": now.isoformat()
        }
    
    apps_data = [a.dict() for a in apps]
    insights_data = await _generate_insights(apps_data)
    
    insight_cache = DashboardInsightCache(
         trends=insights_data.get("trends", ""),
         improvement_strategy=insights_data.get("improvement_strategy", ""),
         follow_up_suggestions=insights_data.get("follow_up_suggestions", []),
         learning_roadmap=insights_data.get("learning_roadmap", "")
    )
    
    user.dashboard_insights = insight_cache
    await user.save()
    
    return user.dashboard_insights
