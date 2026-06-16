import logging
from urllib.parse import quote

import resend

from app.config import get_settings
from app.models import Submission

logger = logging.getLogger(__name__)

PHASE_LABELS = {
    "checklist": "Facility checklist",
    "departments": "Departments file upload",
    "units": "Units file upload",
    "staff": "Staff file upload",
    "roles": "Roles file upload",
    "patients": "Patients file upload",
}


def _phase_label(portal_phase: str | None) -> str:
    if not portal_phase:
        return "Facility checklist"
    return PHASE_LABELS.get(portal_phase, portal_phase.replace("_", " ").title())


def _resume_url(facility_email: str | None) -> str:
    settings = get_settings()
    base = settings.onboarding_portal_url.rstrip("/")
    if facility_email:
        return f"{base}?resume={quote(facility_email)}"
    return base


def _send_resend(*, to: str, subject: str, html: str, text: str) -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.resend_enabled or not settings.resend_api_key:
        logger.info("Resend disabled; skipping email to %s", to)
        return False, "Resend disabled"

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
        return True, None
    except Exception as exc:
        logger.exception("Resend failed for %s: %s", to, exc)
        return False, str(exc)


def resend_configured() -> bool:
    settings = get_settings()
    return bool(settings.resend_enabled and settings.resend_api_key)


def send_application_started_email(
    submission: Submission, *, email_changed: bool = False
) -> tuple[bool, str | None]:
    """Welcome / resume email when a facility saves or updates their draft email."""
    email = submission.facility_email
    if not email:
        return False, "No facility email"

    name = submission.facility_name or "your facility"
    resume_url = _resume_url(email)

    if email_changed:
        subject = "Helix Health — Your application link has been updated"
        intro_html = (
            f"<p>Your Helix facility pre-onboarding application email was updated to "
            f"<strong>{email}</strong>.</p>"
            "<p>All of your saved answers and uploads are still there — you do not need to "
            "start over. Use the link below to continue exactly where you left off.</p>"
        )
        intro_text = (
            f"Your Helix facility pre-onboarding application email was updated to {email}.\n\n"
            "All of your saved answers and uploads are still there — you do not need to start over. "
            "Use the link below to continue exactly where you left off."
        )
        cta = "Continue your application"
    else:
        subject = "Helix Health — Your pre-onboarding application has started"
        intro_html = (
            "<p>You have started your Helix facility pre-onboarding application. Your progress "
            "is saved automatically — you can close this tab and come back any time.</p>"
            f"<p>Use the link below to continue where you left off. This link is tied to "
            f"<strong>{email}</strong> and will always bring you back to your saved draft.</p>"
        )
        intro_text = (
            "You have started your Helix facility pre-onboarding application. Your progress "
            "is saved automatically — you can close this tab and come back any time.\n\n"
            f"Continue where you left off. This link is tied to {email} and will bring you "
            "back to your saved draft."
        )
        cta = "Continue your application"

    html_body = f"""
    <html>
      <body style="font-family: Inter, Arial, sans-serif; line-height: 1.6; color: #1a1a1a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
          <h2 style="color: #0a0a0a;">Hi {name},</h2>
          {intro_html}
          <p style="margin-top: 28px;">
            <a href="{resume_url}"
               style="background-color: #00B383; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; display: inline-block;
                      font-weight: 600;">
              {cta}
            </a>
          </p>
          <p style="margin-top: 24px; font-size: 13px; color: #666;">
            Or copy this link: <a href="{resume_url}">{resume_url}</a>
          </p>
          <p style="margin-top: 32px; font-size: 13px; color: #666;">
            Questions? Reply to this email or contact support@helixhealth.app.
          </p>
          <p style="font-size: 13px; color: #666;">— The Helix Health Team</p>
        </div>
      </body>
    </html>
    """

    plain_text = f"""Hi {name},

{intro_text}

Continue here (bookmark this link):
{resume_url}

— The Helix Health Team
"""

    return _send_resend(to=email, subject=subject, html=html_body, text=plain_text)


def send_application_started_email_simple(submission: Submission) -> bool:
    ok, _ = send_application_started_email(submission)
    return ok


def send_reminder_email_detailed(
    recipient_email: str, facility_name: str, last_step: str
) -> tuple[bool, str | None]:
    """Send a completion reminder; returns (success, resend_error)."""
    resume_url = _resume_url(recipient_email)
    subject = "Helix Health — Complete your facility pre-onboarding"

    html_body = f"""
    <html>
      <body style="font-family: Inter, Arial, sans-serif; line-height: 1.6; color: #1a1a1a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
          <h2 style="color: #0a0a0a;">Hi {facility_name},</h2>
          <p>Your Helix facility pre-onboarding draft is saved, but it has not been submitted yet.
          You were last working on <strong>{last_step}</strong>.</p>
          <p>Finishing the checklist only takes a few minutes and lets our team prepare your
          Helix rollout. You can add Departments, Staff, and other template files later — they
          do not block submission.</p>
          <p style="margin-top: 28px;">
            <a href="{resume_url}"
               style="background-color: #00B383; color: #ffffff; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; display: inline-block;
                      font-weight: 600;">
              Continue pre-onboarding
            </a>
          </p>
          <p style="margin-top: 32px; font-size: 13px; color: #666;">
            Questions? Reply to this email or contact support@helixhealth.app.
          </p>
          <p style="font-size: 13px; color: #666;">
            — The Helix Health Team
          </p>
        </div>
      </body>
    </html>
    """

    plain_text = f"""Hi {facility_name},

Your Helix facility pre-onboarding draft is saved, but it has not been submitted yet.
You were last working on: {last_step}.

Continue here: {resume_url}

Finishing the checklist only takes a few minutes. Template file uploads (Departments, Staff, etc.)
can be added later — they do not block submission.

— The Helix Health Team
"""

    return _send_resend(to=recipient_email, subject=subject, html=html_body, text=plain_text)


def send_reminder_email(recipient_email: str, facility_name: str, last_step: str) -> bool:
    ok, _ = send_reminder_email_detailed(recipient_email, facility_name, last_step)
    return ok


def send_submission_confirmation(submission: Submission) -> bool:
    """Optional confirmation after a facility submits the checklist."""
    email = submission.facility_email
    if not email:
        return False

    name = submission.facility_name or "your facility"
    subject = "Helix Health — Pre-onboarding received"
    portal_url = get_settings().onboarding_portal_url.rstrip("/")

    html_body = f"""
    <html>
      <body style="font-family: Inter, Arial, sans-serif; line-height: 1.6; color: #1a1a1a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
          <h2 style="color: #0a0a0a;">Thank you, {name}</h2>
          <p>We received your facility pre-onboarding submission. The Helix onboarding team will
          review your details and follow up at <strong>{email}</strong>.</p>
          <p>You can still upload Departments, Units, Staff, Roles, and Patients files from the
          <a href="{portal_url}">pre-onboarding portal</a> whenever those exports are ready.</p>
          <p style="margin-top: 32px; font-size: 13px; color: #666;">— The Helix Health Team</p>
        </div>
      </body>
    </html>
    """

    plain_text = f"""Thank you, {name}.

We received your facility pre-onboarding submission. The Helix onboarding team will review
your details and follow up at {email}.

You can still upload template files from the portal when ready: {portal_url}

— The Helix Health Team
"""

    ok, _ = _send_resend(to=email, subject=subject, html=html_body, text=plain_text)
    return ok


def send_batch_reminders(submissions: list[Submission]) -> dict:
    """Send completion reminders to incomplete submissions via Resend."""
    sent = 0
    failed = 0

    for submission in submissions:
        if not submission.facility_email:
            failed += 1
            continue
        last_step = _phase_label(submission.portal_phase)
        if send_reminder_email(
            submission.facility_email,
            submission.facility_name or "your facility",
            last_step,
        ):
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed, "total": len(submissions)}
