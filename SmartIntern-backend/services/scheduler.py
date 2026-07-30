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

# Warn at module load if neither email channel is configured
_gmail_user = os.getenv("GMAIL_USER")
_gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
if not _resend_available and not (_gmail_user and _gmail_pass):
    logger.warning(
        "[scheduler] Neither RESEND_API_KEY nor GMAIL_USER+GMAIL_APP_PASSWORD are set. "
        "Emails will be logged as [MOCK EMAIL] only and never actually sent."
    )


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
        logger.info("[scheduler] run_weekly_digest starting...")
        seven_days_ago = datetime.now() - timedelta(days=7)

        matches = await UserJobMatch.find(UserJobMatch.computed_at >= seven_days_ago).to_list()

        user_match_counts: dict = {}
        for match in matches:
            user_match_counts[match.user_id] = user_match_counts.get(match.user_id, 0) + 1

        sent_count = 0
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
            sent_count += 1

        logger.info(
            "[scheduler] run_weekly_digest complete. Users notified=%d, total matches=%d",
            sent_count, len(matches)
        )

    async def run_deadline_reminders(self):
        """
        Runs daily. Scans Application collection for interview_date or deadline_date within 48 hours.
        Creates Notification and sends email. Checks existing notifications to prevent duplicates.
        """
        from api.models import Application, Notification
        logger.info("[scheduler] run_deadline_reminders starting...")
        now = datetime.now()
        upcoming_window = now + timedelta(hours=48)

        apps = await Application.find({
            "$or": [
                {"interview_date": {"$gte": now, "$lte": upcoming_window}},
                {"deadline_date": {"$gte": now, "$lte": upcoming_window}},
            ]
        }).to_list()

        logger.info("[scheduler] Found %d apps with upcoming interview/deadlines", len(apps))
        reminder_count = 0
        for app in apps:
            if app.interview_date and now <= app.interview_date <= upcoming_window:
                await self._process_reminder(app, "interview", app.interview_date)
                reminder_count += 1
            if hasattr(app, "deadline_date") and app.deadline_date and now <= app.deadline_date <= upcoming_window:
                await self._process_reminder(app, "deadline", app.deadline_date)
                reminder_count += 1

        logger.info("[scheduler] run_deadline_reminders complete. Reminders processed=%d", reminder_count)

    async def _process_reminder(self, app, r_type: str, date_val: datetime):
        from api.models import Notification
        # Deduplicate: check for existing notification of this type for this specific application
        existing = await Notification.find_one(
            {
                "user_id": app.user_id,
                "type": r_type,
                "payload.application_id": str(app.id),
            }
        )
        if existing:
            logger.info(
                "[scheduler] Skipping duplicate %s reminder for app %s (user %s)",
                r_type, app.id, app.user_id
            )
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
        Scheduled job sync: fetches Adzuna + Remotive + JSearch and upserts into DB.
        This is the scheduled counterpart to POST /jobs/sync.

        Provider schedule (all rate-limit guards respected by in-memory caches):
          - Adzuna   : primary source, 8h in-memory cache (~3 actual fetches/day)
          - Remotive : 6h in-memory cache (no more than ~4 syncs/day per ToS)
          - JSearch  : 23h rate-limit guard (~1 actual fetch/day)
          - Mock     : fallback only when ALL three live sources return 0 jobs

        Direct-link pre-filter: only jobs with a real http(s):// apply URL are inserted.
        """
        from api.routes.jobs import adzuna_provider, remotive_provider, jsearch_provider, mock_provider
        from api.models import Job
        from services.jobs_provider import _is_real_url
        logger.info("Scheduled job sync starting (Adzuna + Remotive + JSearch)...")

        fresh_jobs = []

        # 1. Adzuna (primary)
        try:
            adzuna_jobs = await adzuna_provider.fetch_jobs(
                query="software developer intern", location="India", limit=150
            )
            fresh_jobs.extend(adzuna_jobs)
            logger.info(f"Scheduled sync: {len(adzuna_jobs)} from Adzuna")
        except Exception as e:
            logger.error(f"Scheduled sync Adzuna error: {e}")

        # 2. Remotive
        try:
            remotive_jobs = await remotive_provider.fetch_jobs(limit=100)
            fresh_jobs.extend(remotive_jobs)
            logger.info(f"Scheduled sync: {len(remotive_jobs)} from Remotive")
        except Exception as e:
            logger.error(f"Scheduled sync Remotive error: {e}")

        # 3. JSearch
        try:
            jsearch_jobs = await jsearch_provider.fetch_jobs(
                query="software developer intern",
                location="India",
                limit=50,
            )
            fresh_jobs.extend(jsearch_jobs)
            logger.info(f"Scheduled sync: {len(jsearch_jobs)} from JSearch")
        except Exception as e:
            logger.error(f"Scheduled sync JSearch error: {e}")

        if not fresh_jobs:
            logger.info("Scheduled sync: all live providers returned 0 jobs — using mock fallback")
            fresh_jobs = await mock_provider.fetch_jobs(limit=50)

        inserted = 0
        for fj in fresh_jobs:
            # Hard-discard: skip jobs with no real apply URL
            if not _is_real_url(getattr(fj, 'application_url', None)):
                continue
            existing = None
            if fj.external_id:
                existing = await Job.find_one(Job.external_id == fj.external_id)
            else:
                existing = await Job.find_one(
                    Job.title == fj.title,
                    Job.company == fj.company,
                )
            if not existing:
                await fj.insert()
                inserted += 1

        logger.info(f"Scheduled job sync complete. Inserted {inserted} new jobs out of {len(fresh_jobs)} fetched.")

    def start(self):
        # Weekly digest: every Monday at 9AM
        self.scheduler.add_job(self.run_weekly_digest, "cron", day_of_week="mon", hour=9)
        # Deadline/interview reminders: every day at 8AM
        self.scheduler.add_job(self.run_deadline_reminders, "cron", hour=8)
        # Scheduled job ingestion: every day at 6AM (Adzuna 8h cache, Remotive 6h cache, JSearch 23h guard)
        self.scheduler.add_job(self.run_jobs_sync, "cron", hour=6)

        self.scheduler.start()
        logger.info("Notification + job sync scheduler started (weekly digest Mon 9AM, reminders 8AM, job sync 6AM — Adzuna/Remotive/JSearch).")
