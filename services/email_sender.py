"""
Send emails directly from the application via SMTP.
Tracks sends. Prevents daily limit breaches.
Adds human-like delays between sends.
"""

import smtplib
import random
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import settings
from database import get_db, OutreachDB


class EmailSender:

    def __init__(self):
        self.sends_today = self._count_sends_today()

    def _count_sends_today(self) -> int:
        """Count emails sent today from DB."""
        today = datetime.now().date().isoformat()
        with get_db() as db:
            return OutreachDB.count_sent_today(db, today)

    def can_send(self) -> tuple:
        """Check if we can send another email."""
        if self.sends_today >= settings.MAX_EMAILS_PER_DAY:
            return False, f"Daily limit reached ({settings.MAX_EMAILS_PER_DAY})"
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            return False, "SMTP not configured in .env"
        return True, "OK"

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        outreach_id: int = None
    ) -> dict:
        """
        Send one email via SMTP.
        Returns result dict with success status.
        """

        can, reason = self.can_send()
        if not can:
            return {"success": False, "error": reason}

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = (
                f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
                if settings.FROM_NAME
                else settings.FROM_EMAIL
            )
            msg["To"] = to_email

            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            html_body = body.replace("\n", "<br>")
            html_part = MIMEText(
                f"<html><body style='font-family:Arial,sans-serif;"
                f"font-size:14px;line-height:1.6;color:#333;'>"
                f"{html_body}</body></html>",
                "html", "utf-8"
            )
            msg.attach(html_part)

            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT
            ) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)

            sent_at = datetime.now().isoformat()

            if outreach_id:
                with get_db() as db:
                    OutreachDB.mark_sent(db, outreach_id, sent_at)

            self.sends_today += 1

            delay = random.uniform(45, 120)
            time.sleep(delay)

            return {
                "success": True,
                "sent_at": sent_at,
                "to": to_email,
                "subject": subject,
                "sends_today": self.sends_today
            }

        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "SMTP authentication failed. Check credentials."
            }
        except smtplib.SMTPRecipientsRefused:
            return {
                "success": False,
                "error": f"Email address rejected: {to_email}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self) -> dict:
        """Test SMTP connection without sending."""
        if not settings.SMTP_USER:
            return {"success": False, "error": "SMTP not configured"}
        try:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT
            ) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            return {"success": True, "message": "SMTP connection working"}
        except Exception as e:
            return {"success": False, "error": str(e)}
