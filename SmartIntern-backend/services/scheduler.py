import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# ── Optional Resend (email) ───────────────────────────────────────────────────
_resend_key = os.getenv("RESEND_API_KEY")
if _resend_key:
    try:
        import resend
        resend.api_key = _resend_key
        _resend_available = True
    except ImportError:
        _resend_available = False
        logger.warning("resend package not installed. pip install resend")
else:
    _resend_available = False
    logger.info("RESEND_API_KEY not set — digest/reminder emails will use Gmail SMTP fallback.")


def _send_notification_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send a notification email.
    Tries Resend first (if key set), falls back to Gmail SMTP.
    Returns True if sent successfully.
    """
    if _resend_available:
        try:
            import resend
            resend.Emails.send({
                "from": "SmartIntern <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            })
            return True
        except Exception as e:
            logger.error(f"Resend send failed ({to_email}): {e}")

    # Gmail SMTP fallback
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if gmail_user and gmail_pass:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart("alternative")
            msg["From"] = gmail_user
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(gmail_user, gmail_pass)
                smtp.send_message(msg)
            logger.info(f"Gmail SMTP sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Gmail SMTP send failed ({to_email}): {e}")

    # Both failed — log mock
    logger.info(f"[MOCK EMAIL] Would send '{subject}' to {to_email}")
    return False


class NotificationScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    async def run_weekly_digest(self):
        """
        Weekly digest: Finds new UserJobMatch docs per user created in the last 7 days.
        Groups by user, sends email, creates Notification doc.
        """
        from api.models import UserJobMatch, Notification
        logger.info("Running weekly digest job...")
        seven_days_ago = datetime.now() - timedelta(days=7)

        matches = await UserJobMatch.find(UserJobMatch.computed_at >= seven_days_ago).to_list()

        user_match_counts: dict = {}
        for match in matches:
            user_match_counts[match.user_id] = user_match_counts.get(match.user_id, 0) + 1

        for user_email, count in user_match_counts.items():
            if count == 0:
                continue

            message = f"You have {count} new role{'s' if count > 1 else ''} matched this week!"
            payload = {"message": message, "count": count}

            # Create in-app notification
            notif = Notification(
                user_id=user_email,
                type="digest",
                payload=payload,
            )
            await notif.insert()

            # Send email
            html = (
                f"<h2>Weekly Digest</h2>"
                f"<p>{message}</p>"
                f"<p><a href='http://localhost:3000/applications'>View Recommendations</a></p>"
            )
            sent = _send_notification_email(user_email, "Your Weekly Job Matches", html)
            logger.info(f"Digest for {user_email}: sent={sent}")

    async def run_deadline_reminders(self):
        """
        Runs daily. Scans Application collection for interview_date or deadline_date within 48 hours.
        Creates Notification and sends email. Checks existing notifications to prevent duplicates.
        """
        from api.models import Application, Notification
        logger.info("Running deadline/interview reminders job...")
        now = datetime.now()
        upcoming_window = now + timedelta(hours=48)

        apps = await Application.find({
            "$or": [
                {"interview_date": {"$gte": now, "$lte": upcoming_window}},
                {"deadline_date": {"$gte": now, "$lte": upcoming_window}},
            ]
        }).to_list()

        for app in apps:
            if app.interview_date and now <= app.interview_date <= upcoming_window:
                await self._process_reminder(app, "interview", app.interview_date)
            if hasattr(app, "deadline_date") and app.deadline_date and now <= app.deadline_date <= upcoming_window:
                await self._process_reminder(app, "deadline", app.deadline_date)

    async def _process_reminder(self, app, r_type: str, date_val: datetime):
        from api.models import Notification
        # Deduplicate
        existing = await Notification.find_one(
            Notification.user_id == app.user_id,
            Notification.type == r_type,
        )
        if existing and existing.payload.get("application_id") == str(app.id):
            return

        company = app.company_name
        role = app.role
        date_str = date_val.strftime("%b %d, %Y at %I:%M %p")
        if r_type == "interview":
            message = f"Upcoming interview with {company} for {role} on {date_str}."
        else:
            message = f"Deadline approaching for {company} - {role} on {date_str}."

        payload = {
            "message": message,
            "application_id": str(app.id),
            "company": company,
            "role": role,
            "date": date_val.isoformat(),
        }
        notif = Notification(user_id=app.user_id, type=r_type, payload=payload)
        await notif.insert()

        html = f"<h2>Reminder</h2><p>{message}</p>"
        sent = _send_notification_email(app.user_id, f"Reminder: {company} {role}", html)
        logger.info(f"Reminder sent={sent} to {app.user_id}: {message[:80]}")

    async def run_jobs_sync(self):
        """
        Daily job sync: fetches Remotive + JSearch and upserts into DB.
        This is the scheduled counterpart to POST /jobs/sync.
        """
        from api.routes.jobs import remotive_provider, jsearch_provider, mock_provider
        from api.models import Job
        logger.info("Scheduled job sync starting...")

        fresh_jobs = []
        try:
            remotive_jobs = await remotive_provider.fetch_jobs(limit=100)
            fresh_jobs.extend(remotive_jobs)
            logger.info(f"Scheduled sync: {len(remotive_jobs)} from Remotive")
        except Exception as e:
            logger.error(f"Scheduled sync Remotive error: {e}")

        try:
            jsearch_jobs = await jsearch_provider.fetch_jobs(query="software intern", location="India", limit=50)
            fresh_jobs.extend(jsearch_jobs)
            logger.info(f"Scheduled sync: {len(jsearch_jobs)} from JSearch")
        except Exception as e:
            logger.error(f"Scheduled sync JSearch error: {e}")

        if not fresh_jobs:
            fresh_jobs = await mock_provider.fetch_jobs(limit=50)

        inserted = 0
        for fj in fresh_jobs:
            existing = None
            if fj.external_id:
                existing = await Job.find_one(Job.external_id == fj.external_id)
            if not existing:
                await fj.insert()
                inserted += 1

        logger.info(f"Scheduled job sync complete. Inserted {inserted} new jobs out of {len(fresh_jobs)} fetched.")

    def start(self):
        # Weekly digest: every Monday at 9AM
        self.scheduler.add_job(self.run_weekly_digest, "cron", day_of_week="mon", hour=9)
        # Deadline/interview reminders: every day at 8AM
        self.scheduler.add_job(self.run_deadline_reminders, "cron", hour=8)
        # Scheduled job ingestion: every day at 6AM
        self.scheduler.add_job(self.run_jobs_sync, "cron", hour=6)

        self.scheduler.start()
        logger.info("Notification + job sync scheduler started (weekly digest Mon 9AM, reminders 8AM, job sync 6AM).")
