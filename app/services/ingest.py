import csv
import io
from datetime import date
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import (
    Submission,
    SubmissionDepartment,
    SubmissionPatient,
    SubmissionRole,
    SubmissionStaff,
    SubmissionUnit,
)
from app.template_schema import TEMPLATE_HEADERS

INGEST_MODELS = {
    "departments": SubmissionDepartment,
    "units": SubmissionUnit,
    "staff": SubmissionStaff,
    "roles": SubmissionRole,
    "patients": SubmissionPatient,
}


def _cell(row: dict[str, str], key: str) -> str | None:
    val = row.get(key, "")
    if val is None:
        return None
    stripped = str(val).strip()
    return stripped or None


def _parse_dob(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _row_to_department(submission_id: UUID, source_file_id: UUID | None, row_num: int, row: dict) -> SubmissionDepartment:
    return SubmissionDepartment(
        submission_id=submission_id,
        source_file_id=source_file_id,
        row_number=row_num,
        building_block=_cell(row, "building_block") or "",
        department=_cell(row, "department") or "",
        department_description=_cell(row, "department_description"),
        subspecialty=_cell(row, "subspecialty"),
        subspecialty_description=_cell(row, "subspecialty_description"),
        floor=_cell(row, "floor") or "",
        ward_list=_cell(row, "ward_list") or "",
    )


def _row_to_unit(submission_id: UUID, source_file_id: UUID | None, row_num: int, row: dict) -> SubmissionUnit:
    return SubmissionUnit(
        submission_id=submission_id,
        source_file_id=source_file_id,
        row_number=row_num,
        building_block=_cell(row, "building_block") or "",
        unit=_cell(row, "unit") or "",
        floor=_cell(row, "floor"),
    )


def _row_to_staff(submission_id: UUID, source_file_id: UUID | None, row_num: int, row: dict) -> SubmissionStaff:
    return SubmissionStaff(
        submission_id=submission_id,
        source_file_id=source_file_id,
        row_number=row_num,
        email=_cell(row, "email") or "",
        first_name=_cell(row, "first_name") or "",
        last_name=_cell(row, "last_name") or "",
        job_title=_cell(row, "job_title"),
        rank=_cell(row, "rank"),
        middle_name=_cell(row, "middle_name"),
        phone=_cell(row, "phone") or "",
        gender=_cell(row, "gender") or "",
        department=_cell(row, "department") or "",
        subspecialty=_cell(row, "subspecialty"),
        patient_access=_cell(row, "patient_access") or "",
        employee_id=_cell(row, "employee_id") or "",
        highest_qualifications=_cell(row, "highest_qualifications") or "",
    )


def _row_to_role(submission_id: UUID, source_file_id: UUID | None, row_num: int, row: dict) -> SubmissionRole:
    return SubmissionRole(
        submission_id=submission_id,
        source_file_id=source_file_id,
        row_number=row_num,
        role_name=_cell(row, "role_name") or "",
        role_description=_cell(row, "role_description"),
        department=_cell(row, "department") or "",
        subspecialty=_cell(row, "subspecialty"),
        priority=_cell(row, "priority") or "",
        restricted_signin=_cell(row, "restricted_signin") or "",
        permitted_signin_emails=_cell(row, "permitted_signin_emails"),
        external_communication=_cell(row, "external_communication") or "",
        escalation=_cell(row, "escalation"),
    )


def _row_to_patient(submission_id: UUID, source_file_id: UUID | None, row_num: int, row: dict) -> SubmissionPatient:
    return SubmissionPatient(
        submission_id=submission_id,
        source_file_id=source_file_id,
        row_number=row_num,
        first_name=_cell(row, "first_name") or "",
        last_name=_cell(row, "last_name") or "",
        middle_name=_cell(row, "middle_name"),
        dob=_parse_dob(_cell(row, "dob")),
        medical_record_number=_cell(row, "medical_record_number") or "",
        gender=_cell(row, "gender") or "",
        department=_cell(row, "department") or "",
        subspecialty=_cell(row, "subspecialty"),
        floor=_cell(row, "floor") or "",
        ward=_cell(row, "ward") or "",
        bed=_cell(row, "bed"),
    )


ROW_BUILDERS = {
    "departments": _row_to_department,
    "units": _row_to_unit,
    "staff": _row_to_staff,
    "roles": _row_to_role,
    "patients": _row_to_patient,
}


def _is_data_row(row: dict[str, str]) -> bool:
    return any(v and str(v).strip() for v in row.values())


def ingest_csv_rows(
    db: Session,
    submission: Submission,
    upload_key: str,
    content: bytes,
    source_file_id: UUID | None,
) -> int:
    """
    Parse a validated CSV into typed rows for the given upload_key.
    Replaces any existing rows for that submission + template type.
    Extra columns in the CSV are ignored; matching is case-insensitive.
    """
    model = INGEST_MODELS.get(upload_key)
    headers = TEMPLATE_HEADERS.get(upload_key)
    builder = ROW_BUILDERS.get(upload_key)
    if not model or not headers or not builder:
        return 0

    db.execute(delete(model).where(model.submission_id == submission.id))

    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        db.flush()
        return 0

    # Build a case-insensitive mapping: csv_column_lower -> actual csv_column_name
    field_map = {f.strip().lower(): f for f in reader.fieldnames}

    count = 0
    for idx, raw in enumerate(reader, start=1):
        # Map our expected headers to the CSV's actual column names (case-insensitive)
        row = {}
        for k in headers:
            csv_col = field_map.get(k.lower())
            row[k] = (raw.get(csv_col) or "").strip() if csv_col else ""
        if not _is_data_row(row):
            continue
        db.add(builder(submission.id, source_file_id, idx, row))
        count += 1

    db.flush()
    return count


def clear_ingested_rows(db: Session, submission_id: UUID, upload_key: str) -> None:
    model = INGEST_MODELS.get(upload_key)
    if model:
        db.execute(delete(model).where(model.submission_id == submission_id))
