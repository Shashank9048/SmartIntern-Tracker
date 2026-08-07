"""
api/routes/automation.py
─────────────────────────
Cold-email and automation helper endpoints:

  POST /api/automation/send-cold-email
      Queues an HTML cold email via FastAPI BackgroundTasks.
      Returns immediately (200 OK) while SMTP runs asynchronously.

  GET  /api/automation/email-status
      Quick health-check: confirms SMTP credentials are loaded so the
      frontend can show a meaningful error before the user even sends.

Environment variables (from root .env):
  SMTP_SENDER   — the Gmail address to send from
  SMTP_PASSWORD — Gmail App Password (not the account password)
  SMTP_SERVER   — defaults to smtp.gmail.com
  SMTP_PORT     — defaults to 587 (STARTTLS)
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, Any

from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Helper: Safe Port Parser ────────────────────────────────────────────────

def _get_smtp_port() -> int:
    """Safely parse SMTP_PORT from environment variables, defaulting to 587."""
    port_str = os.getenv("SMTP_PORT", "587").strip()
    try:
        return int(port_str) if port_str else 587
    except ValueError:
        logger.warning("[smtp] Invalid SMTP_PORT '%s' in .env. Defaulting to 587.", port_str)
        return 587


# ─── SMTP Sender ─────────────────────────────────────────────────────────────

def _get_smtp_credentials() -> tuple[str, str]:
    """Return (sender, password) or raise RuntimeError if not configured."""
    sender = os.getenv("SMTP_SENDER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not sender or not password:
        raise RuntimeError(
            "SMTP credentials missing. Set SMTP_SENDER and SMTP_PASSWORD in .env"
        )
    return sender, password


def send_smtp_email(recipient: str, subject: str, body: str) -> None:
    """
    Send a single HTML email via Gmail SMTP (STARTTLS, port 587).
    Includes explicit timeout and UTF-8 encoding for reliable delivery.
    """
    try:
        sender, password = _get_smtp_credentials()
    except RuntimeError as e:
        logger.error("[smtp] %s", e)
        return  # Credentials missing — cannot dispatch in background

    server_host = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
    server_port = _get_smtp_port()

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")

    # Explicit UTF-8 encoding prevents mojibake/crashes with special characters
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        # timeout=15 prevents background threads from hanging on network stalls
        with smtplib.SMTP(server_host, server_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info("[smtp] ✅ Email sent to %s | Subject: %s", recipient, subject)
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "[smtp] ❌ Authentication failed for %s. "
            "Verify SMTP_SENDER and SMTP_PASSWORD (ensure you are using a Gmail App Password).",
            sender,
        )
    except Exception as e:
        logger.error("[smtp] ❌ Failed to send email to %s: %s", recipient, str(e))


# ─── Request Models ──────────────────────────────────────────────────────────

class EmailPayload(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    custom_note: Optional[str] = None


# ─── POST /api/automation/send-cold-email ────────────────────────────────────

@router.post("/api/automation/send-cold-email")
async def trigger_cold_email(
    payload: EmailPayload,
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(get_current_user),
):
    """
    Enqueue a cold email for background dispatch.
    Returns 200 immediately; SMTP runs asynchronously.
    """
    # Validate credentials exist before queuing (fail fast)
    try:
        _get_smtp_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Safely format user identifier for logging
    user_id = (
        current_user.get("email") or current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "email", str(current_user))
    )

    # Build structured HTML email body
    meta_parts = [part for part in [payload.company_name, payload.role_title] if part]
    meta_header = (
        f"<p style='margin-bottom:16px;'><strong>Re: {' — '.join(meta_parts)}</strong></p>"
        if meta_parts
        else ""
    )
    custom_note_html = (
        f"<div style='margin-top:24px; padding:12px; border-left:3px solid #0070f3; background:#f8f9fa;'>"
        f"<strong>Note:</strong> {payload.custom_note}</div>"
        if payload.custom_note
        else ""
    )

    final_body = (
        f"<div style='font-family: Arial, sans-serif; line-height: 1.6; color: #333;'>"
        f"{meta_header}"
        f"<div>{payload.body}</div>"
        f"{custom_note_html}"
        f"</div>"
    )

    background_tasks.add_task(
        send_smtp_email,
        recipient=payload.recipient_email,
        subject=payload.subject,
        body=final_body,
    )

    logger.info(
        "[cold-email] Queued email to %s (from user: %s)",
        payload.recipient_email,
        user_id,
    )
    return {
        "status": "success",
        "message": "Email scheduled for background dispatch.",
        "recipient": payload.recipient_email,
    }


# ─── GET /api/automation/email-status ────────────────────────────────────────

@router.get("/api/automation/email-status")
async def email_service_status(current_user: Any = Depends(get_current_user)):
    """
    Health-check: returns whether SMTP credentials are configured.
    The frontend can use this to show a warning before the user tries to send.
    """
    sender = os.getenv("SMTP_SENDER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    configured = bool(sender and password)

    return {
        "configured": configured,
        "sender": sender if configured else None,
        "server": os.getenv("SMTP_SERVER", "smtp.gmail.com").strip(),
        "port": _get_smtp_port(),
        "message": (
            "Email service is ready."
            if configured
            else "SMTP_SENDER or SMTP_PASSWORD is not set in .env"
        ),
    }
