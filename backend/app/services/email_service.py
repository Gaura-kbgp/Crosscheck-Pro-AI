import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import structlog
from app.core.config import settings

logger = structlog.get_logger(__name__)

class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL or self.username
        self.frontend_url = settings.FRONTEND_URL.rstrip("/")

    def _send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Helper to send an email via SMTP with graceful fallback if unconfigured."""
        if not self.username or not self.password or settings.APP_ENV == "test":
            logger.info(
                "SMTP credentials not configured or running in test mode. Email logged instead of sent.",
                recipient=to_email,
                subject=subject,
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"CrossCheckPro <{self.from_email}>"
            msg["To"] = to_email

            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.ehlo()
                if self.port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            logger.info("Email sent successfully", recipient=to_email, subject=subject)
            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP", error=str(e), recipient=to_email)
            return False

    def send_verification_email(self, email: str, token: str, full_name: str | None = None) -> bool:
        """Sends an email verification link to the newly registered user."""
        verification_link = f"{self.frontend_url}/verify-email?token={token}"
        name = full_name or "there"

        subject = "Verify your email address — CrossCheckPro"
        
        text_body = f"""Hi {name},

Thank you for signing up for CrossCheckPro. Please verify your email address by clicking the link below:

{verification_link}

This verification link will expire in 24 hours.

If you did not create an account, you can safely ignore this email.

— The CrossCheckPro Team
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify your email</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 30px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
    <div style="margin-bottom: 24px;">
      <span style="font-size: 20px; font-weight: bold; color: #0f172a;">CrossCheck<span style="color: #0284c7;">Pro</span></span>
    </div>
    <h2 style="font-size: 18px; font-weight: 600; color: #0f172a; margin-top: 0;">Verify your email address</h2>
    <p style="font-size: 14px; color: #475569; line-height: 1.6;">Hi {name},</p>
    <p style="font-size: 14px; color: #475569; line-height: 1.6;">Thank you for signing up for CrossCheckPro. Please verify your email address to access your construction document intelligence workspace.</p>
    <div style="margin: 28px 0;">
      <a href="{verification_link}" style="background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; display: inline-block;">Verify Email Address</a>
    </div>
    <p style="font-size: 12px; color: #94a3b8; line-height: 1.5;">This link will expire in 24 hours. If the button above doesn't work, copy and paste this URL into your browser:<br><a href="{verification_link}" style="color: #0284c7; word-break: break-all;">{verification_link}</a></p>
    <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 24px 0;">
    <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">If you did not sign up for CrossCheckPro, you can safely ignore this email.</p>
  </div>
</body>
</html>
"""
        return self._send_email(email, subject, html_body, text_body)

    def send_password_reset_email(self, email: str, token: str, full_name: str | None = None) -> bool:
        """Sends a password reset link to the user."""
        reset_link = f"{self.frontend_url}/reset-password?token={token}"
        name = full_name or "there"

        subject = "Reset your password — CrossCheckPro"
        
        text_body = f"""Hi {name},

We received a request to reset the password for your CrossCheckPro account. Click the link below to set a new password:

{reset_link}

This link will expire in 1 hour and can only be used once.

If you did not request a password reset, you can safely ignore this email.

— The CrossCheckPro Team
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Reset your password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 30px;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
    <div style="margin-bottom: 24px;">
      <span style="font-size: 20px; font-weight: bold; color: #0f172a;">CrossCheck<span style="color: #0284c7;">Pro</span></span>
    </div>
    <h2 style="font-size: 18px; font-weight: 600; color: #0f172a; margin-top: 0;">Reset your password</h2>
    <p style="font-size: 14px; color: #475569; line-height: 1.6;">Hi {name},</p>
    <p style="font-size: 14px; color: #475569; line-height: 1.6;">We received a request to reset your password. Click the button below to choose a new password for your account.</p>
    <div style="margin: 28px 0;">
      <a href="{reset_link}" style="background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; display: inline-block;">Reset Password</a>
    </div>
    <p style="font-size: 12px; color: #94a3b8; line-height: 1.5;">This link will expire in 1 hour. If the button above doesn't work, copy and paste this URL into your browser:<br><a href="{reset_link}" style="color: #0284c7; word-break: break-all;">{reset_link}</a></p>
    <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 24px 0;">
    <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">If you did not request this change, please ignore this email.</p>
  </div>
</body>
</html>
"""
        return self._send_email(email, subject, html_body, text_body)

email_service = EmailService()
