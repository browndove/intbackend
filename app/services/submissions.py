import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Submission, SubmissionFile, SubmissionStatus, UPLOAD_KEYS
from app.schemas import (
    AdminFacilityDetail,
    AdminFacilityListItem,
    AdminStats,
    SubmissionOut,
    SubmissionPayload,
)

logger = logging.getLogger(__name__)


def normalize_facility_email(email: str | None) -> str | None:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized if "@" in normalized else None


def find_open_draft_by_email(db: Session, email: str | None) -> Submission | None:
    """Latest unsubmitted draft for this facility email, if any."""
    normalized = normalize_facility_email(email)
    if not normalized:
        return None
    return db.execute(
        select(Submission)
        .where(Submission.facility_email == normalized)
        .where(Submission.submitted.is_(False))
        .order_by(Submission.updated_at.desc())
        .limit(1)
    ).scalars().first()


def touch_submission_updated_at(submission: Submission) -> None:
    submission.updated_at = datetime.now(timezone.utc)


REQUIRED_ANSWER_KEYS = [
    "facility_name",
    "facility_type",
    "facility_region",
    "facility_city",
    "facility_address",
    "facility_email",
    "facility_phone",
    "primary_name",
    "primary_phone",
    "primary_email",
    "total_employees",
    "total_clinical_staff",
    "total_nonclinical_staff",
    "has_it_team",
    "has_emergency",
    "has_inpatient_wards",
    "has_ambulance",
    "has_medical_director",
    "staff_has_id",
    "staff_has_work_email",
    "staff_uses_personal_email",
    "has_employee_directory",
    "staff_list_by_department",
    "staff_list_by_role",
]

CONDITIONAL_REQUIRED = {
    "total_it_staff": ("has_it_team", "Yes"),
    "total_inpatient_beds": ("has_inpatient_wards", "Yes"),
}


def _is_answered(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() != ""


def validate_required_answers(answers: dict[str, Any]) -> list[str]:
    missing = []
    for key in REQUIRED_ANSWER_KEYS:
        if not _is_answered(answers.get(key)):
            missing.append(key)
    for key, (dep, expected) in CONDITIONAL_REQUIRED.items():
        if answers.get(dep) == expected and not _is_answered(answers.get(key)):
            missing.append(key)
    return missing


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _phone_country(answers: dict[str, Any], prefix: str) -> str | None:
    return _str_or_none(answers.get(f"{prefix}_country") or answers.get(f"{prefix}_iso"))


def sync_denormalized(submission: Submission) -> None:
    answers = submission.answers or {}

    submission.facility_name = _str_or_none(answers.get("facility_name"))
    submission.facility_type = _str_or_none(answers.get("facility_type"))
    submission.region = _str_or_none(answers.get("facility_region"))
    submission.city = _str_or_none(answers.get("facility_city"))
    submission.facility_address = _str_or_none(answers.get("facility_address"))
    submission.facility_email = (answers.get("facility_email") or "").strip().lower() or None
    submission.facility_phone = _str_or_none(answers.get("facility_phone"))
    submission.facility_phone_country = _phone_country(answers, "facility_phone")

    submission.primary_name = _str_or_none(answers.get("primary_name"))
    submission.primary_phone = _str_or_none(answers.get("primary_phone"))
    submission.primary_phone_country = _phone_country(answers, "primary_phone")
    submission.primary_email = _str_or_none(answers.get("primary_email"))

    submission.secondary_name = _str_or_none(answers.get("secondary_name"))
    submission.secondary_phone = _str_or_none(answers.get("secondary_phone"))
    submission.secondary_phone_country = _phone_country(answers, "secondary_phone")
    submission.secondary_email = _str_or_none(answers.get("secondary_email"))

    submission.total_employees = _int_or_none(answers.get("total_employees"))
    submission.total_clinical_staff = _int_or_none(answers.get("total_clinical_staff"))
    submission.total_nonclinical_staff = _int_or_none(answers.get("total_nonclinical_staff"))
    submission.has_it_team = _str_or_none(answers.get("has_it_team"))
    submission.total_it_staff = _int_or_none(answers.get("total_it_staff"))

    submission.has_emergency = _str_or_none(answers.get("has_emergency"))
    submission.has_inpatient_wards = _str_or_none(answers.get("has_inpatient_wards"))
    submission.total_inpatient_beds = _int_or_none(answers.get("total_inpatient_beds"))
    submission.has_ambulance = _str_or_none(answers.get("has_ambulance"))
    submission.has_medical_director = _str_or_none(answers.get("has_medical_director"))

    submission.staff_has_id = _str_or_none(answers.get("staff_has_id"))
    submission.staff_has_work_email = _str_or_none(answers.get("staff_has_work_email"))
    submission.staff_uses_personal_email = _str_or_none(answers.get("staff_uses_personal_email"))
    submission.has_employee_directory = _str_or_none(answers.get("has_employee_directory"))
    submission.staff_list_by_department = _str_or_none(answers.get("staff_list_by_department"))
    submission.staff_list_by_role = _str_or_none(answers.get("staff_list_by_role"))


def completion_percentage(answers: dict[str, Any]) -> int:
    missing = validate_required_answers(answers)
    total = len(REQUIRED_ANSWER_KEYS) + len(CONDITIONAL_REQUIRED)
    done = total - len(missing)
    return max(0, min(100, round((done / total) * 100) if total else 0))


def uploads_meta_to_dict(uploads: dict | None) -> dict:
    if not uploads:
        return {k: None for k in UPLOAD_KEYS}
    out = {k: None for k in UPLOAD_KEYS}
    for key in UPLOAD_KEYS:
        val = uploads.get(key)
        if val is None:
            continue
        if hasattr(val, "model_dump"):
            out[key] = val.model_dump()
        elif isinstance(val, dict):
            out[key] = val
    return out


def apply_payload(submission: Submission, payload: SubmissionPayload, *, uploads_meta: dict | None = None) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    touch_submission_updated_at(submission)
    submission.kind = payload.kind
    submission.schema_version = payload.schema_version
    submission.portal_phase = payload.portal_phase
    submission.answers = payload.answers
    flag_modified(submission, "answers")
    meta = uploads_meta if uploads_meta is not None else uploads_meta_to_dict(payload.uploads)
    submission.uploads_meta = meta
    flag_modified(submission, "uploads_meta")
    submission.submitted = payload.submitted
    if payload.submitted_at:
        submission.submitted_at = payload.submitted_at
    sync_denormalized(submission)


def submission_to_out(submission: Submission) -> SubmissionOut:
    file_count = len(submission.files) if submission.files else 0
    return SubmissionOut(
        id=submission.id,
        kind=submission.kind,
        schema_version=submission.schema_version,
        status=submission.status,
        portal_phase=submission.portal_phase,
        submitted=submission.submitted,
        submitted_at=submission.submitted_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        answers=submission.answers or {},
        uploads_meta=submission.uploads_meta or {},
        facility_name=submission.facility_name,
        facility_email=submission.facility_email,
        region=submission.region,
        city=submission.city,
        facility_type=submission.facility_type,
        file_count=file_count,
    )


def last_submitted_at_for_email(db: Session, facility_email: str | None) -> datetime | None:
    if not facility_email:
        return None
    return db.scalar(
        select(func.max(Submission.submitted_at)).where(
            Submission.facility_email == facility_email.strip().lower(),
            Submission.submitted.is_(True),
        )
    )


def last_submitted_at_by_emails(db: Session, emails: list[str]) -> dict[str, datetime]:
    normalized = [e.strip().lower() for e in emails if e]
    if not normalized:
        return {}
    rows = db.execute(
        select(Submission.facility_email, func.max(Submission.submitted_at))
        .where(
            Submission.facility_email.in_(normalized),
            Submission.submitted.is_(True),
        )
        .group_by(Submission.facility_email)
    ).all()
    return {email: ts for email, ts in rows if email and ts}


def answers_to_admin_detail(submission: Submission, db: Session | None = None) -> AdminFacilityDetail:
    a = submission.answers or {}
    files = []
    for f in submission.files or []:
        val = f.validation or {}
        ok = val.get("ok")
        status = "valid" if ok is True else ("invalid" if ok is False else "pending")
        files.append(
            {
                "name": f.file_name,
                "size": f.size,
                "uploadedAt": f.uploaded_at.isoformat() if f.uploaded_at else None,
                "status": status,
                "upload_key": f.upload_key,
            }
        )

    total_emp = a.get("total_employees")
    patient_load = f"{total_emp} staff" if total_emp else None

    last_submitted = None
    email = submission.facility_email or a.get("facility_email")
    if db and email:
        last_submitted = last_submitted_at_for_email(db, email)

    return AdminFacilityDetail(
        id=str(submission.id),
        facility_name=submission.facility_name or a.get("facility_name"),
        facility_email=submission.facility_email or a.get("facility_email"),
        facility_phone=submission.facility_phone or a.get("facility_phone"),
        region=submission.region or a.get("facility_region"),
        city=submission.city or a.get("facility_city"),
        facility_address=submission.facility_address or a.get("facility_address"),
        facility_type=submission.facility_type or a.get("facility_type"),
        primary_contact_name=submission.primary_name or a.get("primary_name"),
        primary_contact_email=submission.primary_email or a.get("primary_email"),
        primary_contact_phone=submission.primary_phone or a.get("primary_phone"),
        secondary_contact_name=submission.secondary_name or a.get("secondary_name"),
        secondary_contact_email=submission.secondary_email or a.get("secondary_email"),
        secondary_contact_phone=submission.secondary_phone or a.get("secondary_phone"),
        patient_load=patient_load,
        his_system=submission.has_emergency or a.get("has_emergency"),
        it_support=submission.has_it_team or a.get("has_it_team"),
        internet_quality=None,
        submitted=submission.submitted,
        submitted_at=submission.submitted_at,
        last_submitted_at=last_submitted,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        portal_phase=submission.portal_phase,
        status=submission.status,
        fileCount=len(files),
        files=files,
        completionPercentage=completion_percentage(a),
        answers=a,
        uploads_meta=submission.uploads_meta or {},
    )


def list_item_from_submission(
    s: Submission,
    *,
    last_submitted_at: datetime | None = None,
) -> AdminFacilityListItem:
    return AdminFacilityListItem(
        id=str(s.id),
        facility_name=s.facility_name,
        facility_email=s.facility_email,
        region=s.region,
        city=s.city,
        facility_type=s.facility_type,
        status=s.status,
        submitted=s.submitted,
        submitted_at=s.submitted_at,
        last_submitted_at=last_submitted_at,
        updated_at=s.updated_at,
        fileCount=len(s.files) if s.files else 0,
        completionPercentage=completion_percentage(s.answers or {}),
    )


def get_stats(db: Session) -> AdminStats:
    rows = db.execute(
        select(Submission.status, func.count()).group_by(Submission.status)
    ).all()
    counts = {status: count for status, count in rows}
    files_attached = db.scalar(select(func.count()).select_from(SubmissionFile)) or 0
    return AdminStats(
        total=sum(counts.values()),
        pending=counts.get(SubmissionStatus.pending.value, 0),
        approved=counts.get(SubmissionStatus.approved.value, 0),
        rejected=counts.get(SubmissionStatus.rejected.value, 0),
        incomplete=counts.get(SubmissionStatus.incomplete.value, 0),
        files_attached=files_attached,
    )


def query_submissions(
    db: Session,
    *,
    search: str = "",
    status: str = "",
    region: str = "",
    facility_type: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    sort_field: str = "submitted_at",
    sort_direction: str = "desc",
    page: int = 1,
    per_page: int = 25,
    submitted_only: bool = False,
) -> tuple[list[Submission], int]:
    q = select(Submission).options(joinedload(Submission.files))
    if submitted_only:
        q = q.where(Submission.submitted.is_(True))
    if search:
        like = f"%{search.lower()}%"
        q = q.where(
            or_(
                func.lower(Submission.facility_name).like(like),
                func.lower(Submission.facility_email).like(like),
                func.lower(Submission.city).like(like),
            )
        )
    if status:
        q = q.where(Submission.status == status)
    if region:
        q = q.where(Submission.region == region)
    if facility_type:
        q = q.where(Submission.facility_type == facility_type)
    if date_from:
        q = q.where(Submission.submitted_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(Submission.submitted_at <= datetime.fromisoformat(f"{date_to}T23:59:59"))

    sort_map = {
        "facility_name": Submission.facility_name,
        "facility_email": Submission.facility_email,
        "region": Submission.region,
        "city": Submission.city,
        "facility_type": Submission.facility_type,
        "submitted_at": Submission.submitted_at,
        "status": Submission.status,
    }
    col = sort_map.get(sort_field, Submission.submitted_at)
    q = q.order_by(col.desc() if sort_direction == "desc" else col.asc())

    count_q = select(func.count()).select_from(Submission)
    if submitted_only:
        count_q = count_q.where(Submission.submitted.is_(True))
    if search:
        like = f"%{search.lower()}%"
        count_q = count_q.where(
            or_(
                func.lower(Submission.facility_name).like(like),
                func.lower(Submission.facility_email).like(like),
                func.lower(Submission.city).like(like),
            )
        )
    if status:
        count_q = count_q.where(Submission.status == status)
    if region:
        count_q = count_q.where(Submission.region == region)
    if facility_type:
        count_q = count_q.where(Submission.facility_type == facility_type)
    if date_from:
        count_q = count_q.where(Submission.submitted_at >= datetime.fromisoformat(date_from))
    if date_to:
        count_q = count_q.where(Submission.submitted_at <= datetime.fromisoformat(f"{date_to}T23:59:59"))

    total = db.scalar(count_q) or 0
    page = max(1, page)
    per_page = min(100, max(1, per_page))
    items = db.execute(q.offset((page - 1) * per_page).limit(per_page)).scalars().unique().all()
    return list(items), total


def maybe_send_application_started_email(
    db: Session, submission: Submission, *, previous_email: str | None = None
) -> bool:
    """Send welcome email on first save, or updated resume link when email changes."""
    settings = get_settings()
    if not settings.send_application_started_email or not settings.resend_enabled:
        return False
    if not submission.facility_email:
        return False

    current = (submission.facility_email or "").strip().lower()
    previous = (previous_email or "").strip().lower() or None
    if not current:
        return False

    from app.services.email import (
        send_application_started_email,
        send_new_facility_started_alerts,
    )

    email_changed = bool(previous and current != previous)

    if submission.submitted:
        if not email_changed:
            return False
    elif submission.started_email_sent_at and not email_changed:
        return False

    first_onboarding_start = (
        not submission.submitted
        and not submission.started_email_sent_at
        and not email_changed
    )

    ok, err = send_application_started_email(
        submission,
        email_changed=email_changed and bool(submission.started_email_sent_at or submission.submitted),
    )
    if ok:
        if first_onboarding_start:
            send_new_facility_started_alerts(submission)
        if not submission.started_email_sent_at:
            submission.started_email_sent_at = datetime.now(timezone.utc)
        db.flush()
        return True
    if err and err != "Resend disabled":
        logger.warning(
            "Application started email failed for %s: %s",
            submission.facility_email,
            err,
        )
    return False


def delete_submission(db: Session, submission: Submission) -> None:
    """Permanently remove a submission, uploaded files, and ingested rows."""
    settings = get_settings()
    upload_root = Path(settings.upload_dir) / str(submission.id)

    for record in list(submission.files or []):
        try:
            Path(record.storage_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete file at %s", record.storage_path)

    if upload_root.is_dir():
        shutil.rmtree(upload_root, ignore_errors=True)

    db.delete(submission)
    db.commit()


def submit_submission(db: Session, submission: Submission) -> None:
    missing = validate_required_answers(submission.answers or {})
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"message": "Required fields missing", "fields": missing},
        )
    now = datetime.now(timezone.utc)
    submission.submitted = True
    submission.submitted_at = now
    submission.status = SubmissionStatus.pending.value
    sync_denormalized(submission)

    settings = get_settings()
    if settings.send_submit_confirmation and settings.resend_enabled:
        from app.services.email import send_submission_confirmation

        send_submission_confirmation(submission)
