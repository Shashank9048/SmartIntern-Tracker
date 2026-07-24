import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import resend

from api.models import UserJobMatch, Application, Notification, User

logger = logging.getLogger(__name__)

class NotificationScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        if self.resend_api_key:
            resend.api_key = self.resend_api_key
        else:
            logger.warning("RESEND_API_KEY is missing. Emails will be logged instead of sent.")

    async def run_weekly_digest(self):
        """
        Weekly digest: Finds new UserJobMatch docs per user created in the last 7 days.
        Groups by user, sends email via Resend, creates Notification doc.
        """
        logger.info("Running weekly digest job...")
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Aggregate matches per user
        matches = await UserJobMatch.find(UserJobMatch.computed_at >= seven_days_ago).to_list()
        
        user_match_counts = {}
        for match in matches:
            user_match_counts[match.user_id] = user_match_counts.get(match.user_id, 0) + 1

        for user_email, count in user_match_counts.items():
            if count == 0:
                continue

            payload = {
                "message": f"You have {count} new role{'s' if count > 1 else ''} matched this week!",
                "count": count
            }

            # Create notification
            notif = Notification(
                user_id=user_email,
                type="digest",
                payload=payload
            )
            await notif.insert()

            # Send Email
            email_body = f"<h2>Weekly Digest</h2><p>{payload['message']}</p><p><a href='http://localhost:3000/applications'>View Recommendations</a></p>"
            if self.resend_api_key:
                try:
                    resend.Emails.send({
                        "from": "SmartIntern <onboarding@resend.dev>",
                        "to": [user_email],
                        "subject": "Your Weekly Job Matches",
                        "html": email_body
                    })
                except Exception as e:
                    logger.error(f"Failed to send digest to {user_email}: {e}")
            else:
                logger.info(f"[MOCK EMAIL] Would have sent digest to {user_email}: {payload['message']}")

    async def run_deadline_reminders(self):
        """
        Runs daily. Scans Application collection for interview_date or deadline_date within 24-48 hours.
        Creates Notification and sends email via Resend. Checks existing notifications to prevent duplicates.
        """
        logger.info("Running deadline/interview reminders job...")
        now = datetime.now()
        upcoming_window = now + timedelta(hours=48)

        # Get applications with upcoming dates
        apps = await Application.find(
            {"$or": [
                {"interview_date": {"$gte": now, "$lte": upcoming_window}},
                {"deadline_date": {"$gte": now, "$lte": upcoming_window}}
            ]}
        ).to_list()

        for app in apps:
            # Check for interview
            if app.interview_date and now <= app.interview_date <= upcoming_window:
                await self._process_reminder(app, "interview", app.interview_date)
            
            # Check for deadline
            if app.deadline_date and now <= app.deadline_date <= upcoming_window:
                await self._process_reminder(app, "deadline", app.deadline_date)

    async def _process_reminder(self, app: Application, r_type: str, date_val: datetime):
        # Check if we already reminded for this app and type
        existing = await Notification.find_one(
            Notification.user_id == app.user_id,
            Notification.type == r_type,
            Notification.payload["application_id"] == str(app.id)
        )
        if existing:
            return # Already sent

        company = app.company_name
        role = app.role
        date_str = date_val.strftime("%b %d, %Y at %I:%M %p")
        
        message = ""
        if r_type == "interview":
            message = f"Upcoming interview with {company} for {role} on {date_str}."
        else:
            message = f"Deadline approaching for {company} - {role} on {date_str}."

        payload = {
            "message": message,
            "application_id": str(app.id),
            "company": company,
            "role": role,
            "date": date_val.isoformat()
        }

        notif = Notification(
            user_id=app.user_id,
            type=r_type,
            payload=payload
        )
        await notif.insert()

        email_body = f"<h2>Reminder</h2><p>{message}</p>"
        if self.resend_api_key:
            try:
                resend.Emails.send({
                    "from": "SmartIntern <onboarding@resend.dev>",
                    "to": [app.user_id],
                    "subject": f"Reminder: {company} {role}",
                    "html": email_body
                })
            except Exception as e:
                logger.error(f"Failed to send reminder to {app.user_id}: {e}")
        else:
            logger.info(f"[MOCK EMAIL] Would have sent reminder to {app.user_id}: {message}")

    def start(self):
        # Schedule jobs
        # Weekly digest on Monday at 9AM (for dev, let's run it once every day at 9AM to test or use an interval)
        self.scheduler.add_job(self.run_weekly_digest, 'cron', day_of_week='mon', hour=9)
        # Reminders run every day at 8AM
        self.scheduler.add_job(self.run_deadline_reminders, 'cron', hour=8)
        
        self.scheduler.start()
        logger.info("Notification scheduler started.")
