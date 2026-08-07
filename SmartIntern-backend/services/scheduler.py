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
_smtp_sender = os.getenv("SMTP_SENDER") or os.getenv("GMAIL_USER")
_smtp_pass = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD")
if not _resend_available and not (_smtp_sender and _smtp_pass):
    logger.warning(
        "[scheduler] Neither RESEND_API_KEY nor SMTP_SENDER+SMTP_PASSWORD are set. "
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

    # SMTP fallback
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_sender = os.getenv("SMTP_SENDER") or os.getenv("GMAIL_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD")
    
    if smtp_sender and smtp_password:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart("alternative")
            msg["From"] = smtp_sender
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))
            
            with smtplib.SMTP(smtp_server, smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(smtp_sender, smtp_password)
                smtp.send_message(msg)
                
            logger.info(f"SMTP sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"SMTP send failed ({to_email}): {e}")

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
        now = datetime.utcnow()
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

    async def run_due_automations(self):
        """
        Runs regularly to sweep ALL active automations (followup, interview, status)
        whose scheduled_at <= now, send emails/in-app notifications, and mark them completed.
        """
        from api.models import Automation, Application, Notification, User
        from beanie import PydanticObjectId

        logger.info("[scheduler] run_due_automations starting...")
        now = datetime.utcnow()
        due = await Automation.find(
            Automation.status == "active",
            Automation.scheduled_at <= now
        ).to_list()

        logger.info("[scheduler] Found %d active due automations to process", len(due))
        for auto in due:
            try:
                company = "Company"
                role = "Position"
                if auto.application_id:
                    try:
                        app_doc = await Application.get(PydanticObjectId(auto.application_id))
                        if app_doc:
                            company = app_doc.company_name
                            role = app_doc.role
                    except Exception:
                        pass

                # Send email if enabled
                sent = False
                if auto.email_enabled:
                    if auto.type == "interview":
                        subject = f"Interview Reminder: {company} - {role}"
                        body = f"<h2>Interview Reminder</h2><p>This is a reminder for your upcoming interview for <strong>{role}</strong> at <strong>{company}</strong>.</p>"
                    elif auto.type == "status":
                        subject = f"Status Update Reminder: {company} - {role}"
                        body = f"<h2>Status Check Reminder</h2><p>This is a reminder to check for a status update on your application for <strong>{role}</strong> at <strong>{company}</strong>.</p>"
                    else:
                        subject = f"Follow-up Reminder: {company} - {role}"
                        body = f"<h2>Follow-up Reminder</h2><p>This is a reminder to follow up on your application for <strong>{role}</strong> at <strong>{company}</strong>.</p>"
                        
                    sent = _send_notification_email(auto.user_id, subject, body)

                # Always insert in-app notification
                try:
                    if auto.type == "interview":
                        msg = f"Interview reminder for {company} - {role}"
                        notif_type = "interview"
                    elif auto.type == "status":
                        msg = f"Check status for {company} - {role}"
                        notif_type = "deadline"
                    else:
                        msg = f"Follow-up reminder for {company} - {role}"
                        notif_type = "deadline"

                    notif = Notification(
                        user_id=auto.user_id,
                        type=notif_type,
                        payload={
                            "message": msg,
                            "application_id": auto.application_id,
                            "company": company,
                            "role": role
                        }
                    )
                    await notif.insert()
                except Exception as ne:
                    logger.error(f"[scheduler] Notification insert error: {ne}")

                # Transition status to completed (or failed) so it clears from active/overdue!
                auto.status = "completed" if (sent or not auto.email_enabled) else "failed"
                await auto.save()
                logger.info("[scheduler] Processed automation %s for user %s: status=%s", auto.id, auto.user_id, auto.status)
            except Exception as e:
                logger.error("[scheduler] Error processing automation %s: %s", auto.id, e)

    async def run_jobs_sync(self):
        """
        Scheduled job sync: fetches all 7 live providers and upserts into DB.
        This is the scheduled counterpart to POST /jobs/sync.

        Provider priority order (same as the manual sync endpoint):
          1. Arbeitnow   : no auth, 3h cache — TOP PRIORITY, native ATS links
          2. Adzuna      : ADZUNA_APP_ID/KEY, 8h cache (~1,000 calls/month)
          3. Remotive    : free, no auth, 6h cache (max ~4 syncs/day)
          4. JSearch     : RAPIDAPI_KEY, 23h rate-limit guard (~200 req/month)
          5. Himalayas   : free, no auth, 3h cache (yields 0 under strict rule)
          6. Jooble      : JOOBLE_API_KEY, ~500 req/day
          7. CareerOneStop: US-only, low yield — CAREERONESTOP credentials

        Schedule: every 3 hours (matches Arbeitnow/Himalayas 3h TTL)
        Direct-link pre-filter: only jobs with a real http(s):// apply URL are inserted.
        """
        import os as _os
        import re as _re
        from api.routes.jobs import (
            arbeitnow_provider, adzuna_provider, remotive_provider, jsearch_provider,
            himalayas_provider, jooble_provider, careeronestop_provider, mock_provider
        )
        from api.models import Job
        from services.jobs_provider import _is_real_url

        logger.info("Scheduled job sync starting (7-source engine)...")

        def _normalise_sig(title: str, company: str) -> str:
            combined = f"{title.lower().strip()} {company.lower().strip()}"
            return _re.sub(r'[^a-z0-9 ]', '', combined).strip()

        fresh_jobs: list = []
        combined_sigs: set = set()
        provider_status: dict = {}

        async def _sync_provider(provider, name, **kwargs):
            try:
                raw_jobs = await provider.fetch_jobs(**kwargs)
                valid_jobs = [j for j in raw_jobs if _is_real_url(j.application_url)]
                deduped = []
                cross_deduped = 0
                for j in valid_jobs:
                    sig = _normalise_sig(j.title, j.company)
                    if sig in combined_sigs:
                        cross_deduped += 1
                    else:
                        deduped.append(j)
                        combined_sigs.add(sig)
                fresh_jobs.extend(deduped)
                provider_status[name.lower()] = {
                    "fetched": len(raw_jobs), "kept": len(deduped),
                    "discarded_no_link": len(raw_jobs) - len(valid_jobs),
                    "deduped_cross_source": cross_deduped, "status": "ok",
                }
                logger.info(f"Scheduled sync: kept {len(deduped)} from {name} (cross-deduped {cross_deduped})")
            except Exception as e:
                provider_status[name.lower()] = {"fetched": 0, "kept": 0, "status": f"error: {e}"}
                logger.error(f"Scheduled sync error from {name}: {e}")

        # Fetch in priority order — each gated behind its env vars
        await _sync_provider(arbeitnow_provider, "Arbeitnow", limit=150)

        if _os.getenv("ADZUNA_APP_ID") and _os.getenv("ADZUNA_APP_KEY"):
            await _sync_provider(adzuna_provider, "Adzuna", query="software developer intern", location="India", limit=150)
        else:
            provider_status["adzuna"] = {"fetched": 0, "kept": 0, "status": "skipped: credentials not set"}

        await _sync_provider(remotive_provider, "Remotive", limit=100)

        if _os.getenv("RAPIDAPI_KEY"):
            await _sync_provider(jsearch_provider, "JSearch", query="software developer intern", location="India", limit=50)
        else:
            provider_status["jsearch"] = {"fetched": 0, "kept": 0, "status": "skipped: RAPIDAPI_KEY not set"}

        await _sync_provider(himalayas_provider, "Himalayas", limit=100)

        if _os.getenv("JOOBLE_API_KEY"):
            await _sync_provider(jooble_provider, "Jooble", query="software", location="India", limit=50)
        else:
            provider_status["jooble"] = {"fetched": 0, "kept": 0, "status": "skipped: JOOBLE_API_KEY not set"}

        if _os.getenv("CAREERONESTOP_USER_ID") and _os.getenv("CAREERONESTOP_TOKEN"):
            await _sync_provider(careeronestop_provider, "CareerOneStop", query="software", location="US", limit=50)
        else:
            provider_status["careeronestop"] = {"fetched": 0, "kept": 0, "status": "skipped: credentials not set"}

        # Mock fallback if all live providers returned nothing
        if not fresh_jobs:
            mock_jobs = await mock_provider.fetch_jobs(limit=50)
            fresh_jobs.extend(mock_jobs)
            provider_status["mock"] = {"fetched": len(mock_jobs), "kept": len(mock_jobs), "status": "fallback"}
            logger.info("Scheduled sync: all live providers returned 0 — using mock fallback")

        inserted = 0
        for fj in fresh_jobs:
            if not _is_real_url(getattr(fj, 'application_url', None)):
                continue
            existing = None
            if fj.external_id:
                existing = await Job.find_one(Job.external_id == fj.external_id)
            else:
                existing = await Job.find_one(Job.title == fj.title, Job.company == fj.company)
            if not existing:
                await fj.insert()
                inserted += 1

        logger.info(
            f"Scheduled job sync complete. "
            f"total_fresh={len(fresh_jobs)}, inserted={inserted}. "
            f"Providers: {provider_status}"
        )

    def start(self):
        # Weekly digest: every Monday at 9AM
        self.scheduler.add_job(self.run_weekly_digest, "cron", day_of_week="mon", hour=9)
        # Deadline/interview reminders: every day at 8AM
        self.scheduler.add_job(self.run_deadline_reminders, "cron", hour=8)
        # Overdue automation sweeper (all types): every 60 seconds
        self.scheduler.add_job(self.run_due_automations, "interval", seconds=60)
        # Scheduled job ingestion: every 3 hours
        # Interval matches the shortest provider TTL (Arbeitnow=3h, Himalayas=3h).
        # Remotive (6h) and Adzuna (8h) have longer TTLs and return cached results on
        # intermediate runs, so they don't burn extra API quota.
        self.scheduler.add_job(self.run_jobs_sync, "interval", hours=3)

        self.scheduler.start()
        logger.info(
            "Notification + job sync scheduler started ("
            "weekly digest Mon 9AM | reminders 8AM daily | "
            "job sync every 3h — 7-source engine: "
            "Arbeitnow(#1) > Adzuna > Remotive > JSearch > Himalayas > Jooble > CareerOneStop"
            ")."
        )
