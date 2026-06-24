import html
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

SIGNOFF_TEXT = "The Helix Health Team"
SIGNOFF_HTML = "<p style=\"margin:0;font-size:13px;color:#64748b;\">The Helix Health Team</p>"
NEW_ONBOARDING_ALERT_RECIPIENTS = [
    "yakubuamin14@gmail.com",
    "michaelowusubudu@gmail.com",
    "briteaddae@gmail.com",
]


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


def _logo_url() -> str:
    return get_settings().email_logo_url.rstrip("/")


def _site_url() -> str:
    return get_settings().public_site_url.rstrip("/")


def _send_resend(*, to: str, subject: str, html_body: str, text: str) -> tuple[bool, str | None]:
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
                "html": html_body,
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


def _build_email_html(
    *,
    title: str,
    greeting: str,
    paragraphs: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    show_link_fallback: bool = False,
    extra_html: str = "",
) -> str:
    logo = _logo_url()
    site = _site_url()
    body_paragraphs = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.65;color:#334155;">{p}</p>'
        for p in paragraphs
    )
    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:28px 0 0;">
            <tr>
              <td style="border-radius:8px;background:#00B383;">
                <a href="{html.escape(cta_url, quote=True)}"
                   style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;
                          color:#ffffff;text-decoration:none;border-radius:8px;">
                  {html.escape(cta_label)}
                </a>
              </td>
            </tr>
          </table>
        """
    link_fallback = ""
    if show_link_fallback and cta_url:
        safe_url = html.escape(cta_url, quote=True)
        link_fallback = f"""
          <p style="margin:20px 0 0;font-size:13px;line-height:1.55;color:#64748b;">
            Or copy this link:<br>
            <a href="{safe_url}" style="color:#0A4676;word-break:break-all;">{safe_url}</a>
          </p>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f8;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
         style="background:#eef2f8;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;
                      border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(10,70,118,0.08);">
          <tr>
            <td style="padding:28px 32px 20px;background:linear-gradient(180deg,#f8fbff 0%,#ffffff 100%);
                       border-bottom:1px solid #e8eef5;">
              <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="padding-right:14px;vertical-align:middle;">
                    <img src="{html.escape(logo, quote=True)}" width="40" height="34" alt="Helix Health"
                         style="display:block;border:0;outline:none;text-decoration:none;">
                  </td>
                  <td style="vertical-align:middle;">
                    <p style="margin:0;font-size:18px;font-weight:700;letter-spacing:-0.02em;color:#0A4676;">
                      Helix Health
                    </p>
                    <p style="margin:4px 0 0;font-size:12px;font-weight:600;letter-spacing:0.08em;
                              text-transform:uppercase;color:#64748b;">
                      Facility pre-onboarding
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <h1 style="margin:0 0 20px;font-size:22px;line-height:1.35;font-weight:700;color:#0f172a;">
                {html.escape(greeting)}
              </h1>
              {body_paragraphs}
              {extra_html}
              {cta_block}
              {link_fallback}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 28px;background:#f8fafc;border-top:1px solid #e8eef5;">
              <p style="margin:0 0 8px;font-size:13px;line-height:1.55;color:#64748b;">
                Questions? Reply to this email or contact
                <a href="mailto:support@helixhealth.app" style="color:#0A4676;">support@helixhealth.app</a>.
              </p>
              {SIGNOFF_HTML}
              <p style="margin:14px 0 0;font-size:11px;color:#94a3b8;">
                <a href="{html.escape(site, quote=True)}" style="color:#94a3b8;text-decoration:none;">
                  helixhealth.app
                </a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _build_email_text(
    greeting: str,
    paragraphs: list[str],
    cta_url: str | None = None,
) -> str:
    lines = [greeting, ""]
    lines.extend(paragraphs)
    if cta_url:
        lines.extend(["", "Continue here:", cta_url])
    lines.extend(["", SIGNOFF_TEXT])
    return "\n".join(lines)


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
        subject = "Helix Health: Your application link has been updated"
        greeting = f"Hi {name},"
        paragraphs = [
            f"Your facility pre-onboarding application email was updated to {email}.",
            "All of your saved answers and uploads are still there. You do not need to start over. "
            "Use the button below to continue exactly where you left off.",
        ]
        cta = "Continue your application"
    else:
        subject = "Helix Health: Your pre-onboarding application has started"
        greeting = f"Hi {name},"
        paragraphs = [
            "You have started your Helix facility pre-onboarding application. "
            "Your progress is saved automatically, so you can close this tab and come back any time.",
            f"Use the link below to continue where you left off. This link is tied to {email} "
            "and will bring you back to your saved draft.",
        ]
        cta = "Continue your application"

    html_body = _build_email_html(
        title=subject,
        greeting=greeting,
        paragraphs=paragraphs,
        cta_label=cta,
        cta_url=resume_url,
        show_link_fallback=True,
    )
    plain_text = _build_email_text(greeting, paragraphs, resume_url)
    return _send_resend(to=email, subject=subject, html_body=html_body, text=plain_text)


def send_application_started_email_simple(submission: Submission) -> bool:
    ok, _ = send_application_started_email(submission)
    return ok


def send_new_facility_started_alerts(submission: Submission) -> bool:
    """Notify internal team when a new facility begins onboarding."""
    facility_name = (submission.facility_name or "Unknown facility").strip() or "Unknown facility"
    facility_email = (submission.facility_email or "not provided").strip() or "not provided"
    region = (submission.region or "not provided").strip() or "not provided"
    portal_url = get_settings().onboarding_portal_url.rstrip("/")
    subject = "Helix Alert: A new facility has began onboarding"
    greeting = "Hi team,"
    paragraphs = [
        "A new facility has began onboarding in Helix.",
        f"<strong>Facility:</strong> {html.escape(facility_name)}<br>"
        f"<strong>Email:</strong> {html.escape(facility_email)}<br>"
        f"<strong>Region:</strong> {html.escape(region)}",
    ]
    html_body = _build_email_html(
        title=subject,
        greeting=greeting,
        paragraphs=paragraphs,
        cta_label="Open onboarding portal",
        cta_url=portal_url,
    )
    plain_text = _build_email_text(
        greeting,
        [
            "A new facility has began onboarding in Helix.",
            f"Facility: {facility_name}",
            f"Email: {facility_email}",
            f"Region: {region}",
        ],
        portal_url,
    )

    sent_any = False
    for recipient in NEW_ONBOARDING_ALERT_RECIPIENTS:
        ok, err = _send_resend(
            to=recipient,
            subject=subject,
            html_body=html_body,
            text=plain_text,
        )
        sent_any = sent_any or ok
        if err and err != "Resend disabled":
            logger.warning("New onboarding alert email failed for %s: %s", recipient, err)
    return sent_any


def send_reminder_email_detailed(
    recipient_email: str, facility_name: str, last_step: str
) -> tuple[bool, str | None]:
    """Send a completion reminder; returns (success, resend_error)."""
    resume_url = _resume_url(recipient_email)
    subject = "Helix Health: Complete your facility pre-onboarding"
    greeting = f"Hi {facility_name},"
    safe_step = html.escape(last_step)
    paragraphs = [
        f"Your facility pre-onboarding draft is saved, but it has not been submitted yet. "
        f"You were last working on <strong>{safe_step}</strong>.",
        "Finishing the checklist only takes a few minutes and lets our team prepare your Helix rollout. "
        "You can add Departments, Staff, and other template files later. They do not block submission.",
    ]
    html_body = _build_email_html(
        title=subject,
        greeting=greeting,
        paragraphs=paragraphs,
        cta_label="Continue pre-onboarding",
        cta_url=resume_url,
        show_link_fallback=True,
    )
    plain_text = _build_email_text(
        greeting,
        [
            "Your facility pre-onboarding draft is saved, but it has not been submitted yet. "
            f"You were last working on: {last_step}.",
            "Finishing the checklist only takes a few minutes. Template file uploads "
            "(Departments, Staff, and others) can be added later and do not block submission.",
        ],
        resume_url,
    )
    return _send_resend(to=recipient_email, subject=subject, html_body=html_body, text=plain_text)


def send_reminder_email(recipient_email: str, facility_name: str, last_step: str) -> bool:
    ok, _ = send_reminder_email_detailed(recipient_email, facility_name, last_step)
    return ok


def send_submission_confirmation(submission: Submission) -> bool:
    """Optional confirmation after a facility submits the checklist."""
    email = submission.facility_email
    if not email:
        return False

    name = submission.facility_name or "your facility"
    subject = "Helix Health: Pre-onboarding received"
    portal_url = get_settings().onboarding_portal_url.rstrip("/")
    safe_portal = html.escape(portal_url, quote=True)
    greeting = f"Thank you, {name}"
    paragraphs = [
        f"We received your facility pre-onboarding submission. The Helix onboarding team will "
        f"review your details and follow up at <strong>{html.escape(email)}</strong>.",
        f'You can still upload Departments, Units, Staff, Roles, and Patients files from the '
        f'<a href="{safe_portal}" style="color:#0A4676;">pre-onboarding portal</a> '
        "whenever those exports are ready.",
    ]
    html_body = _build_email_html(
        title=subject,
        greeting=greeting,
        paragraphs=paragraphs,
        cta_label="Open pre-onboarding portal",
        cta_url=portal_url,
    )
    plain_text = _build_email_text(
        greeting,
        [
            "We received your facility pre-onboarding submission. "
            f"The Helix onboarding team will review your details and follow up at {email}.",
            f"You can still upload template files from the portal when ready: {portal_url}",
        ],
    )
    ok, _ = _send_resend(to=email, subject=subject, html_body=html_body, text=plain_text)
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
