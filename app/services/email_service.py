import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


async def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email using Gmail SMTP."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.default_from_email
    message["To"] = to
    message.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.email_host,
        port=settings.email_port,
        username=settings.email_host_user,
        password=settings.email_host_password,
        start_tls=settings.email_use_tls,
    )


async def send_password_reset_email(to: str, token: str) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">Password Reset Request</h2>
        <p>You requested a password reset for your AI Knowledge Base account.</p>
        <p>Click the button below to reset your password. This link expires in <strong>1 hour</strong>.</p>
        <a href="{reset_url}"
           style="display: inline-block; padding: 12px 24px; background-color: #4F46E5;
                  color: white; text-decoration: none; border-radius: 6px; margin: 16px 0;">
            Reset Password
        </a>
        <p style="color: #666; font-size: 14px;">
            If you did not request this, ignore this email. Your password will not change.
        </p>
        <p style="color: #666; font-size: 14px;">
            Or copy this link: <a href="{reset_url}">{reset_url}</a>
        </p>
    </body>
    </html>
    """
    await send_email(to, "Reset your AI Knowledge Base password", html)


async def send_workspace_invite_email(
    to: str,
    invited_by: str,
    workspace_name: str,
    role: str,
) -> None:
    login_url = f"{settings.frontend_url}/login"
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333;">You've been invited to a workspace</h2>
        <p><strong>{invited_by}</strong> has invited you to join
           <strong>{workspace_name}</strong> on AI Knowledge Base
           as a <strong>{role}</strong>.</p>
        <p>As a {role}, you can:</p>
        {"<ul><li>Upload and manage documents</li><li>Chat with the knowledge base</li><li>View analytics</li></ul>"
          if role == "editor"
          else "<ul><li>Chat with the knowledge base</li><li>Search documents</li><li>View analytics</li></ul>"}
        <a href="{login_url}"
           style="display: inline-block; padding: 12px 24px; background-color: #4F46E5;
                  color: white; text-decoration: none; border-radius: 6px; margin: 16px 0;">
            Go to AI Knowledge Base
        </a>
        <p style="color: #666; font-size: 14px;">
            Log in with your existing account or create one using this email address.
        </p>
    </body>
    </html>
    """
    await send_email(to, f"You've been invited to {workspace_name}", html)