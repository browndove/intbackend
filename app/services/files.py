import csv
import io
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Submission, SubmissionFile, UPLOAD_KEYS
from app.services.ingest import clear_ingested_rows, ingest_csv_rows
from app.template_schema import TEMPLATE_HEADERS


def validate_csv_headers(content: bytes, upload_key: str) -> dict:
    expected = TEMPLATE_HEADERS.get(upload_key)
    if not expected:
        return {"ok": False, "message": "Unknown template type"}
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        row = next(reader, None)
        if not row:
            return {"ok": False, "message": "The file looks empty — no header row found."}
        got = [c.strip().replace("\ufeff", "") for c in row]
        while got and got[-1] == "":
            got.pop()
        if len(got) != len(expected):
            return {
                "ok": False,
                "message": f"Expected {len(expected)} columns; found {len(got)}.",
            }
        for i, exp in enumerate(expected):
            if got[i] != exp:
                return {
                    "ok": False,
                    "message": f'Column {i + 1}: expected "{exp}" but found "{got[i] or "(blank)"}".',
                }
        return {"ok": True, "message": "First row matches the Helix template headers."}
    except Exception:
        return {"ok": False, "message": "Could not parse CSV headers."}


async def save_submission_file(
    db: Session,
    submission: Submission,
    upload_key: str,
    file: UploadFile,
) -> SubmissionFile:
    if upload_key not in UPLOAD_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid upload_key. Use one of: {UPLOAD_KEYS}")

    settings = get_settings()
    upload_root = Path(settings.upload_dir) / str(submission.id) / upload_key
    upload_root.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    safe_name = Path(file.filename or "upload.bin").name
    dest = upload_root / safe_name
    dest.write_bytes(content)

    validation: dict
    name_lower = safe_name.lower()
    if name_lower.endswith(".csv"):
        validation = validate_csv_headers(content, upload_key)
    elif name_lower.endswith((".xlsx", ".xls")):
        validation = {
            "ok": None,
            "message": "Excel file noted — Helix validates spreadsheets on intake.",
        }
    else:
        validation = {
            "ok": None,
            "message": "Save as CSV to validate headers automatically.",
        }

    existing = db.execute(
        select(SubmissionFile).where(
            SubmissionFile.submission_id == submission.id,
            SubmissionFile.upload_key == upload_key,
        )
    ).scalars().first()
    if existing:
        try:
            Path(existing.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
        clear_ingested_rows(db, submission.id, upload_key)
        db.delete(existing)

    record = SubmissionFile(
        submission_id=submission.id,
        upload_key=upload_key,
        file_name=safe_name,
        content_type=file.content_type,
        size=len(content),
        storage_path=str(dest),
        validation=validation,
    )
    db.add(record)
    db.flush()

    if name_lower.endswith(".csv") and validation.get("ok") is True:
        ingest_csv_rows(db, submission, upload_key, content, record.id)

    meta = submission.uploads_meta or {}
    meta[upload_key] = {
        "fileName": safe_name,
        "size": len(content),
        "savedAt": record.uploaded_at.isoformat() if record.uploaded_at else None,
        "validation": validation,
    }
    submission.uploads_meta = meta
    db.commit()
    db.refresh(record)
    return record


def delete_submission_file(db: Session, submission: Submission, upload_key: str) -> None:
    record = db.execute(
        select(SubmissionFile).where(
            SubmissionFile.submission_id == submission.id,
            SubmissionFile.upload_key == upload_key,
        )
    ).scalars().first()
    if record:
        try:
            Path(record.storage_path).unlink(missing_ok=True)
        except OSError:
            pass
        db.delete(record)
    clear_ingested_rows(db, submission.id, upload_key)
    meta = submission.uploads_meta or {}
    meta[upload_key] = None
    submission.uploads_meta = meta
    db.commit()
