import logging
import smtplib
from email.message import EmailMessage
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachments: Optional[list[tuple[str, bytes, str]]] = None,
) -> bool:
    """
    Send an email via configured SMTP (Mailpit local server in dev/test).
    Does not log credentials or sensitive tokens.
    """
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body_text)

    if body_html:
        message.add_alternative(body_html, subtype="html")
    for filename, content, content_type in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    try:
        if settings.SMTP_SSL:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=10
            ) as smtp:
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=10
            ) as smtp:
                if settings.SMTP_STARTTLS:
                    smtp.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        return True
    except Exception as exc:
        logger.error("Failed to deliver email: %s", type(exc).__name__)
        return False


def send_password_reset_email(to_email: str, recipient_name: str, raw_token: str) -> bool:
    settings = get_settings()
    reset_url = f"{settings.FRONTEND_ORIGIN}/reset-password?token={raw_token}"
    subject = "Reset your Brightloop password"
    body_text = f"""Hello {recipient_name},

A password reset was requested for your Brightloop account.
To reset your password, please open the following link within 30 minutes:

{reset_url}

If you did not request a password reset, you can safely ignore this email.

Best regards,
The Brightloop Team
"""
    body_html = f"""<p>Hello {recipient_name},</p>
<p>A password reset was requested for your Brightloop account.</p>
<p>To reset your password, please click the button below or copy the link into your browser. This link expires in 30 minutes:</p>
<p><a href="{reset_url}" style="background-color: #2563eb; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a></p>
<p>Or visit: <a href="{reset_url}">{reset_url}</a></p>
<p>If you did not request a password reset, you can safely ignore this email.</p>
<p>Best regards,<br>The Brightloop Team</p>
"""
    return send_email(to_email, subject, body_text, body_html)


def send_customer_verification_email(to_email: str, recipient_name: str, raw_token: str) -> bool:
    settings = get_settings()
    verify_url = f"{settings.FRONTEND_ORIGIN}/register?token={raw_token}"
    subject = "Verify and connect your Brightloop account"
    body_text = f"""Hello {recipient_name},

An existing customer profile with this email address was found in Brightloop.
To complete your account registration and link your customer records, please verify your email address within 24 hours:

{verify_url}

If you did not create an account on Brightloop, please contact our support team.

Best regards,
The Brightloop Team
"""
    body_html = f"""<p>Hello {recipient_name},</p>
<p>An existing customer profile with this email address was found in Brightloop.</p>
<p>To complete your account registration and link your customer records, please click the link below within 24 hours:</p>
<p><a href="{verify_url}" style="background-color: #2563eb; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify and Link Account</a></p>
<p>Or visit: <a href="{verify_url}">{verify_url}</a></p>
<p>If you did not create an account on Brightloop, please contact support.</p>
<p>Best regards,<br>The Brightloop Team</p>
"""
    return send_email(to_email, subject, body_text, body_html)
