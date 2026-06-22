from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models import Submission, SubmissionStatus
from app.schemas import SubmissionCreate, SubmissionOut, SubmissionPayload, SubmissionUpdate
from app.services.files import delete_submission_file, save_submission_file
from app.services.submissions import (
    apply_payload,
    find_open_draft_by_email,
    maybe_send_application_started_email,
    normalize_facility_email,
    submission_to_out,
    submit_submission,
    sync_denormalized,
    touch_submission_updated_at,
    uploads_meta_to_dict,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _get_submission_or_404(db: Session, submission_id: UUID) -> Submission:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(body: SubmissionCreate, db: Session = Depends(get_db)):
    email = normalize_facility_email(body.answers.get("facility_email"))
    if email:
        existing = find_open_draft_by_email(db, email)
        if existing:
            previous_email = existing.facility_email
            apply_payload(existing, body)
            sync_denormalized(existing)
            maybe_send_application_started_email(db, existing, previous_email=previous_email)
            db.commit()
            db.refresh(existing)
            return submission_to_out(existing)

    submission = Submission(status=SubmissionStatus.incomplete.value)
    apply_payload(submission, body)
    db.add(submission)
    db.flush()
    maybe_send_application_started_email(db, submission)
    db.commit()
    db.refresh(submission)
    return submission_to_out(submission)


@router.get("/submissions/by-email", response_model=SubmissionOut)
def lookup_draft_by_query(email: str = Query(..., min_length=3), db: Session = Depends(get_db)):
    """Preferred for addresses with @ — avoids URL encoding issues in some clients."""
    return _lookup_draft_by_email(db, email)


@router.get("/submissions/by-email/{email:path}", response_model=SubmissionOut)
def lookup_draft_by_path(email: str, db: Session = Depends(get_db)):
    return _lookup_draft_by_email(db, email)


def _lookup_draft_by_email(db: Session, email: str) -> SubmissionOut:
    submission = find_open_draft_by_email(db, email)
    if not submission:
        raise HTTPException(status_code=404, detail="No draft found for this email")
    return submission_to_out(submission)


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: UUID, db: Session = Depends(get_db)):
    return submission_to_out(_get_submission_or_404(db, submission_id))


@router.patch("/submissions/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: UUID,
    body: SubmissionUpdate,
    db: Session = Depends(get_db),
):
    submission = _get_submission_or_404(db, submission_id)
    previous_email = submission.facility_email
    if body.portal_phase is not None:
        submission.portal_phase = body.portal_phase
    if body.answers is not None:
        submission.answers = {**(submission.answers or {}), **body.answers}
        flag_modified(submission, "answers")
    if body.uploads is not None:
        merged_uploads = {**(submission.uploads_meta or {}), **uploads_meta_to_dict(body.uploads)}
        submission.uploads_meta = merged_uploads
        flag_modified(submission, "uploads_meta")
    if body.submitted is not None:
        submission.submitted = body.submitted
    touch_submission_updated_at(submission)
    sync_denormalized(submission)
    maybe_send_application_started_email(db, submission, previous_email=previous_email)
    db.commit()
    db.refresh(submission)
    return submission_to_out(submission)


@router.put("/submissions/{submission_id}", response_model=SubmissionOut)
async def replace_submission(
    submission_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    submission = _get_submission_or_404(db, submission_id)
    previous_email = submission.facility_email
    data = await request.json()
    if not data.get("uploads") and data.get("uploads_meta"):
        data["uploads"] = data["uploads_meta"]
    payload = SubmissionCreate.model_validate(data)
    apply_payload(submission, payload)
    sync_denormalized(submission)
    maybe_send_application_started_email(db, submission, previous_email=previous_email)
    db.commit()
    db.refresh(submission)
    return submission_to_out(submission)


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionOut)
def submit(submission_id: UUID, db: Session = Depends(get_db)):
    submission = _get_submission_or_404(db, submission_id)
    submit_submission(db, submission)
    db.commit()
    db.refresh(submission)
    return submission_to_out(submission)


@router.post("/submissions/{submission_id}/files/{upload_key}", response_model=SubmissionOut)
async def upload_file(
    submission_id: UUID,
    upload_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    submission = _get_submission_or_404(db, submission_id)
    await save_submission_file(db, submission, upload_key, file)
    db.refresh(submission)
    return submission_to_out(submission)


@router.delete("/submissions/{submission_id}/files/{upload_key}", response_model=SubmissionOut)
def remove_file(submission_id: UUID, upload_key: str, db: Session = Depends(get_db)):
    submission = _get_submission_or_404(db, submission_id)
    delete_submission_file(db, submission, upload_key)
    db.refresh(submission)
    return submission_to_out(submission)


@router.post("/submissions/import", response_model=SubmissionOut, status_code=201)
def import_payload(body: SubmissionPayload, db: Session = Depends(get_db)):
    """Accept full portal JSON (submit or export) in one request."""
    email = normalize_facility_email(body.answers.get("facility_email"))
    existing = find_open_draft_by_email(db, email) if email and not body.submitted else None
    if existing:
        submission = existing
    else:
        submission = Submission()
        db.add(submission)

    apply_payload(submission, body)
    if body.submitted:
        submit_submission(db, submission)
    else:
        submission.status = SubmissionStatus.incomplete.value
    db.commit()
    db.refresh(submission)
    return submission_to_out(submission)
