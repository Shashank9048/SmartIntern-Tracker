import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
import re

GMAIL_USER = os.environ.get("SMTP_SENDER") or os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")

def send_email_smtp(to_email: str, subject: str, body: str):
    if not GMAIL_USER or not GMAIL_PASS:
        return {"error": "Gmail credentials not set"}

    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to Gmail SMTP Server (SSL)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(GMAIL_USER, GMAIL_PASS)
            smtp_server.send_message(msg)
        
        return {"status": "sent", "to": to_email}
    except Exception as e:
        print(f"SMTP Error: {e}")
        return {"error": str(e)}

def clean_text(text):
    if not text: return ""
    return str(text).strip()

def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                return part.get_payload(decode=True).decode()
    else:
        return msg.get_payload(decode=True).decode()
    return ""

def scan_inbox_imap():
    if not GMAIL_USER or not GMAIL_PASS:
        return {"error": "Gmail credentials not set"}

    updates = []
    keywords = ["Interview", "Offer", "Unfortunately", "Assessment", "Reject", "Next Steps"]

    try:
        # Connect to Gmail IMAP Server
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select('inbox')

        # Search for all emails (or filter by date if needed)
        # Fetching last 20 emails
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        latest_email_ids = email_ids[-20:] # Last 20

        for e_id in reversed(latest_email_ids):
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    sender = msg.get("From")
                    body = get_email_body(msg)

                    # Simple Keyword Matching
                    matching_keyword = None
                    for kw in keywords:
                        if kw.lower() in subject.lower() or kw.lower() in body.lower():
                            matching_keyword = kw
                            break
                    
                    if matching_keyword:
                        # Extract Company Name (Simple Heuristic or just return subject)
                        # In a real app, we'd use Named Entity Recognition (NER) or Regex
                        updates.append({
                            "subject": subject,
                            "sender": sender,
                            "keyword": matching_keyword,
                            "snippet": body[:100]
                        })

        mail.logout()
        return updates

    except Exception as e:
        print(f"IMAP Error: {e}")
        return {"error": str(e)}


TYPE_LABELS = {
    "followup": "Follow-up Reminder",
    "interview": "Interview Reminder",
    "status": "Status Change Notification",
}

def send_automation_email(
    to_email: str,
    company: str,
    role: str,
    automation_type: str,
    scheduled_at: str,
    ai_tips: str = None,
) -> dict:
    """
    Send a styled automation notification email.
    Returns {"status": "sent"} or {"error": "..."}.
    """
    if not GMAIL_USER or not GMAIL_PASS:
        return {"error": "Gmail credentials not configured (GMAIL_USER or GMAIL_APP_PASSWORD missing)"}

    type_label = TYPE_LABELS.get(automation_type, automation_type.capitalize())
    subject = f"SmartIntern: {type_label} – {company}"

    ai_section = ""
    if ai_tips:
        ai_section = f"""
        <div style="
            background: #1e293b;
            border-left: 4px solid #6366f1;
            border-radius: 8px;
            padding: 16px 20px;
            margin-top: 20px;
        ">
            <h3 style="color:#a5b4fc;margin:0 0 12px;">🤖 AI-Generated Preparation Tips</h3>
            <pre style="
                color:#cbd5e1;
                font-family:inherit;
                font-size:13px;
                white-space:pre-wrap;
                margin:0;
                line-height:1.6;
            ">{ai_tips}</pre>
        </div>
        """

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#0f172a;font-family:'Segoe UI',Arial,sans-serif;">
      <div style="max-width:600px;margin:32px auto;background:#1e293b;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.4);">
        <!-- Header -->
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;">
          <h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;">
            🔔 SmartIntern Notification
          </h1>
          <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:14px;">{type_label}</p>
        </div>

        <!-- Body -->
        <div style="padding:28px 32px;">
          <div style="background:#0f172a;border-radius:12px;padding:20px 24px;border:1px solid rgba(99,102,241,0.3);">
            <table style="width:100%;border-collapse:collapse;">
              <tr>
                <td style="color:#94a3b8;font-size:13px;padding:6px 0;width:140px;">🏢 Company</td>
                <td style="color:#f1f5f9;font-size:14px;font-weight:600;padding:6px 0;">{company}</td>
              </tr>
              <tr>
                <td style="color:#94a3b8;font-size:13px;padding:6px 0;">💼 Role</td>
                <td style="color:#f1f5f9;font-size:14px;padding:6px 0;">{role}</td>
              </tr>
              <tr>
                <td style="color:#94a3b8;font-size:13px;padding:6px 0;">📅 Scheduled</td>
                <td style="color:#f1f5f9;font-size:14px;padding:6px 0;">{scheduled_at}</td>
              </tr>
              <tr>
                <td style="color:#94a3b8;font-size:13px;padding:6px 0;">📌 Type</td>
                <td style="color:#a5b4fc;font-size:14px;font-weight:600;padding:6px 0;">{type_label}</td>
              </tr>
            </table>
          </div>

          {ai_section}

          <p style="color:#64748b;font-size:12px;margin-top:24px;text-align:center;">
            This notification was automatically sent by <strong style="color:#6366f1;">SmartIntern Tracker</strong>.
          </p>
        </div>
      </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.send_message(msg)

        print(f"✅ Automation email sent to {to_email} [{type_label} – {company}]")
        return {"status": "sent", "to": to_email}
    except Exception as e:
        print(f"❌ SMTP Error (automation): {e}")
        return {"error": str(e)}