import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class EmailService:
    """
    Abstract layer for sending emails. 
    If SMTP variables are not set, it simulates sending by logging to the console.
    This prevents the app from breaking when no third-party email service provider is configured.
    """
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = os.getenv("SMTP_PORT", 587)
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.from_email = os.getenv("SMTP_FROM", "noreply@autotube.localhost")
        self.app_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")

    def _send(self, to_email: str, subject: str, html_content: str):
        if not all([self.smtp_host, self.smtp_user, self.smtp_pass]):
            logger.warning(f"📩 [MOCK EMAIL] To: {to_email} | Subject: {subject}")
            logger.info(f"Body: \n{html_content}\n")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email

            part = MIMEText(html_content, "html")
            msg.attach(part)

            with smtplib.SMTP(self.smtp_host, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, to_email, msg.as_string())
            logger.info(f"Email sent successfully to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")

    def send_verification_email(self, to_email: str, token: str):
        verify_link = f"{self.app_url}/verify?token={token}"
        subject = "Verify your AutoTube Account"
        html = f"""
        <html>
        <body>
            <h2>Welcome to AutoTube!</h2>
            <p>Please click the button below to verify your email address and activate your account.</p>
            <a href="{verify_link}" style="padding: 10px 20px; background-color: #ef4444; color: white; text-decoration: none; border-radius: 5px;">Verify Email</a>
            <p>If the button doesn't work, copy and paste this link: {verify_link}</p>
        </body>
        </html>
        """
        self._send(to_email, subject, html)

    def send_job_completion(self, to_email: str, job_id: int, status: str):
        subject = f"AutoTube Job #{job_id} {status.upper()}"
        color = "green" if status == "completed" else "red"
        html = f"""
        <html>
        <body>
            <h2>Your Video Generation Job has {status}</h2>
            <p style="color: {color};"><strong>Status: {status.upper()}</strong></p>
            <p>Login to your dashboard to view the results.</p>
            <a href="{self.app_url}/dashboard" style="padding: 10px 20px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px;">View Dashboard</a>
        </body>
        </html>
        """
        self._send(to_email, subject, html)

    def send_billing_alert(self, to_email: str, message: str):
        subject = "AutoTube Billing Alert"
        html = f"""
        <html>
        <body>
            <h2>Billing Update</h2>
            <p>{message}</p>
            <a href="{self.app_url}/billing" style="padding: 10px 20px; background-color: #eab308; color: white; text-decoration: none; border-radius: 5px;">Manage Billing</a>
        </body>
        </html>
        """
        self._send(to_email, subject, html)

email_service = EmailService()
