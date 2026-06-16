import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

UPLOAD_KEYS = ("departments", "units", "staff", "roles", "patients")


class SubmissionStatus(str, enum.Enum):
    incomplete = "incomplete"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Submission(Base):
    """
    Facility pre-onboarding submission (portal Step 1 checklist + file metadata).

    `answers` keeps the full portal JSON for forward compatibility; typed columns
    mirror every field from on-boarding/assets/data.js for querying and admin views.
    """

    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64), default="helix.facility_preonboarding")
    schema_version: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(32), default=SubmissionStatus.incomplete.value, index=True)

    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    uploads_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    portal_phase: Mapped[str] = mapped_column(String(32), default="checklist")

    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Facility information (section: facility) ---
    facility_name: Mapped[str | None] = mapped_column(String(255), index=True)
    facility_type: Mapped[str | None] = mapped_column(String(128), index=True)
    region: Mapped[str | None] = mapped_column(String(128), index=True)
    city: Mapped[str | None] = mapped_column(String(128), index=True)
    facility_address: Mapped[str | None] = mapped_column(Text)
    facility_email: Mapped[str | None] = mapped_column(String(255), index=True)
    facility_phone: Mapped[str | None] = mapped_column(String(64))
    facility_phone_country: Mapped[str | None] = mapped_column(String(2))

    # --- Primary contact (section: primary_contact) ---
    primary_name: Mapped[str | None] = mapped_column(String(255))
    primary_phone: Mapped[str | None] = mapped_column(String(64))
    primary_phone_country: Mapped[str | None] = mapped_column(String(2))
    primary_email: Mapped[str | None] = mapped_column(String(255), index=True)

    # --- Secondary contact (section: secondary_contact, optional) ---
    secondary_name: Mapped[str | None] = mapped_column(String(255))
    secondary_phone: Mapped[str | None] = mapped_column(String(64))
    secondary_phone_country: Mapped[str | None] = mapped_column(String(2))
    secondary_email: Mapped[str | None] = mapped_column(String(255))

    # --- Staffing (section: staffing) ---
    total_employees: Mapped[int | None] = mapped_column(Integer)
    total_clinical_staff: Mapped[int | None] = mapped_column(Integer)
    total_nonclinical_staff: Mapped[int | None] = mapped_column(Integer)
    has_it_team: Mapped[str | None] = mapped_column(String(8))
    total_it_staff: Mapped[int | None] = mapped_column(Integer)

    # --- Services & infrastructure (section: services) ---
    has_emergency: Mapped[str | None] = mapped_column(String(8))
    has_inpatient_wards: Mapped[str | None] = mapped_column(String(8))
    total_inpatient_beds: Mapped[int | None] = mapped_column(Integer)
    has_ambulance: Mapped[str | None] = mapped_column(String(8))
    has_medical_director: Mapped[str | None] = mapped_column(String(8))

    # --- Staff systems & directory (section: staff_systems) ---
    staff_has_id: Mapped[str | None] = mapped_column(String(8))
    staff_has_work_email: Mapped[str | None] = mapped_column(String(8))
    staff_uses_personal_email: Mapped[str | None] = mapped_column(String(8))
    has_employee_directory: Mapped[str | None] = mapped_column(String(8))
    staff_list_by_department: Mapped[str | None] = mapped_column(String(8))
    staff_list_by_role: Mapped[str | None] = mapped_column(String(8))

    files: Mapped[list["SubmissionFile"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    department_rows: Mapped[list["SubmissionDepartment"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    unit_rows: Mapped[list["SubmissionUnit"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    staff_rows: Mapped[list["SubmissionStaff"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    role_rows: Mapped[list["SubmissionRole"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    patient_rows: Mapped[list["SubmissionPatient"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    upload_key: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(Text)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submission: Mapped["Submission"] = relationship(back_populates="files")


class _SubmissionRowMixin:
    """Shared columns for parsed template upload rows."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submission_files.id", ondelete="SET NULL"), nullable=True
    )
    row_number: Mapped[int] = mapped_column(Integer, default=1)


class SubmissionDepartment(_SubmissionRowMixin, Base):
    """Departments template rows (upload_key: departments)."""

    __tablename__ = "submission_departments"

    building_block: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255), index=True)
    department_description: Mapped[str | None] = mapped_column(Text)
    subspecialty: Mapped[str | None] = mapped_column(String(255))
    subspecialty_description: Mapped[str | None] = mapped_column(Text)
    floor: Mapped[str] = mapped_column(String(128))
    ward_list: Mapped[str] = mapped_column(Text)

    submission: Mapped["Submission"] = relationship(back_populates="department_rows")


class SubmissionUnit(_SubmissionRowMixin, Base):
    """Units template rows (upload_key: units)."""

    __tablename__ = "submission_units"

    building_block: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(255), index=True)
    floor: Mapped[str | None] = mapped_column(String(128))

    submission: Mapped["Submission"] = relationship(back_populates="unit_rows")


class SubmissionStaff(_SubmissionRowMixin, Base):
    """Staff template rows (upload_key: staff)."""

    __tablename__ = "submission_staff"

    email: Mapped[str] = mapped_column(String(255), index=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    job_title: Mapped[str | None] = mapped_column(String(255))
    rank: Mapped[str | None] = mapped_column(String(128))
    middle_name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32))
    gender: Mapped[str] = mapped_column(String(32))
    department: Mapped[str] = mapped_column(String(255), index=True)
    subspecialty: Mapped[str | None] = mapped_column(String(255))
    patient_access: Mapped[str] = mapped_column(String(8))
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    highest_qualifications: Mapped[str] = mapped_column(String(255))

    submission: Mapped["Submission"] = relationship(back_populates="staff_rows")


class SubmissionRole(_SubmissionRowMixin, Base):
    """Roles template rows (upload_key: roles)."""

    __tablename__ = "submission_roles"

    role_name: Mapped[str] = mapped_column(String(255), index=True)
    role_description: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str] = mapped_column(String(255), index=True)
    subspecialty: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(String(32))
    restricted_signin: Mapped[str] = mapped_column(String(8))
    permitted_signin_emails: Mapped[str | None] = mapped_column(Text)
    external_communication: Mapped[str] = mapped_column(String(8))
    escalation: Mapped[str | None] = mapped_column(Text)

    submission: Mapped["Submission"] = relationship(back_populates="role_rows")


class SubmissionPatient(_SubmissionRowMixin, Base):
    """Patients template rows (upload_key: patients) — treat as PHI at rest."""

    __tablename__ = "submission_patients"

    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    middle_name: Mapped[str | None] = mapped_column(String(128))
    dob: Mapped[date | None] = mapped_column(Date)
    medical_record_number: Mapped[str] = mapped_column(String(128), index=True)
    gender: Mapped[str] = mapped_column(String(32))
    department: Mapped[str] = mapped_column(String(255), index=True)
    subspecialty: Mapped[str | None] = mapped_column(String(255))
    floor: Mapped[str] = mapped_column(String(128))
    ward: Mapped[str] = mapped_column(String(255))
    bed: Mapped[str | None] = mapped_column(String(64))

    submission: Mapped["Submission"] = relationship(back_populates="patient_rows")
