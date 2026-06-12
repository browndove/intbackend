import math
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import create_access_token, get_current_admin, verify_admin_password
from app.config import get_settings
from app.database import get_db
from app.models import Submission, SubmissionFile, SubmissionStatus
from app.schemas import (
    AdminFacilityDetail,
    AdminFacilityListItem,
    AdminLoginRequest,
    AdminStats,
    PaginatedSubmissions,
    StatusUpdate,
    TokenResponse,
)
from app.services.email import send_batch_reminders
from app.services.submissions import (
    answers_to_admin_detail,
    get_stats,
    list_item_from_submission,
    query_submissions,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: AdminLoginRequest):
    settings = get_settings()
    if body.email != settings.admin_email or not verify_admin_password(
        body.password, settings.admin_password
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(settings.admin_email)
    return TokenResponse(access_token=token)


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _: str = Depends(get_current_admin)):
    return get_stats(db)


@router.get("/submissions", response_model=PaginatedSubmissions)
def list_submissions(
    search: str = Query(""),
    status: str = Query(""),
    region: str = Query(""),
    facility_type: str = Query(""),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort: str = Query("submitted_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    items, total = query_submissions(
        db,
        search=search,
        status=status,
        region=region,
        facility_type=facility_type,
        date_from=date_from,
        date_to=date_to,
        sort_field=sort,
        sort_direction=order,
        page=page,
        per_page=per_page,
    )
    for s in items:
        db.refresh(s, attribute_names=["files"])
    pages = max(1, math.ceil(total / per_page)) if total else 1
    return PaginatedSubmissions(
        items=[list_item_from_submission(s) for s in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/submissions/{submission_id}", response_model=AdminFacilityDetail)
def get_submission_detail(
    submission_id: UUID,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    submission = (
        db.query(Submission)
        .options(joinedload(Submission.files))
        .filter(Submission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return answers_to_admin_detail(submission)


@router.patch("/submissions/{submission_id}/status", response_model=AdminFacilityDetail)
def update_status(
    submission_id: UUID,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    allowed = {s.value for s in SubmissionStatus}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of: {sorted(allowed)}")
    submission = (
        db.query(Submission)
        .options(joinedload(Submission.files))
        .filter(Submission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission.status = body.status
    db.commit()
    db.refresh(submission)
    return answers_to_admin_detail(submission)


@router.get("/submissions/{submission_id}/files/{upload_key}/download")
def download_file(
    submission_id: UUID,
    upload_key: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    record = (
        db.query(SubmissionFile)
        .filter(
            SubmissionFile.submission_id == submission_id,
            SubmissionFile.upload_key == upload_key,
        )
        .first()
    )
    if not record or not Path(record.storage_path).is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=record.storage_path,
        filename=record.file_name,
        media_type=record.content_type or "application/octet-stream",
    )


@router.post("/reminders/send-incomplete")
def send_incomplete_reminders(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """
    Send reminder emails to all facilities with incomplete onboarding submissions.
    
    This endpoint finds all submissions that are:
    - Not submitted (submitted = False)
    - Have a facility email
    
    And sends reminder emails to prompt completion.
    """
    # Query all incomplete submissions
    incomplete = db.execute(
        select(Submission)
        .where(Submission.submitted.is_(False))
        .filter(Submission.facility_email.is_not(None))
    ).scalars().all()
    
    if not incomplete:
        return {
            "message": "No incomplete submissions found",
            "sent": 0,
            "failed": 0,
            "total": 0
        }
    
    # Send reminders and get results
    results = send_batch_reminders(incomplete)
    
    return {
        "message": f"Sent {results['sent']} reminder emails",
        "sent": results["sent"],
        "failed": results["failed"],
        "total": results["total"]
    }


@router.post("/reminders/send-to-facility/{submission_id}")
def send_facility_reminder(
    submission_id: UUID,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    """
    Send a reminder email to a specific facility.
    """
    submission = db.get(Submission, submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if not submission.facility_email:
        raise HTTPException(status_code=400, detail="Submission has no facility email")
    
    from app.services.email import send_reminder_email
    
    last_step = submission.portal_phase or "facility information"
    success = send_reminder_email(
        submission.facility_email,
        submission.facility_name or "Facility",
        last_step
    )
    
    if success:
        return {
            "message": f"Reminder sent to {submission.facility_email}",
            "success": True,
        }
    from app.services.email import resend_configured

    if not resend_configured():
        raise HTTPException(
            status_code=503,
            detail="Email not configured. Set RESEND_API_KEY and RESEND_ENABLED=true in .env.",
        )
    raise HTTPException(
        status_code=502,
        detail=(
            "Resend rejected the email. Verify RESEND_FROM_EMAIL uses a domain "
            "verified in your Resend dashboard."
        ),
    )
