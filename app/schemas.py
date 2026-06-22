from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UploadMeta(BaseModel):
    fileName: str | None = None
    size: int | None = None
    lastModified: int | None = None
    savedAt: str | None = None
    validation: dict[str, Any] | None = None


class SubmissionPayload(BaseModel):
    kind: str = "helix.facility_preonboarding"
    schema_version: int = 3
    created_at: datetime | None = None
    updated_at: datetime | None = None
    submitted: bool = False
    submitted_at: datetime | None = None
    portal_phase: str = "checklist"
    answers: dict[str, Any] = Field(default_factory=dict)
    uploads: dict[str, UploadMeta | None] = Field(default_factory=dict)


class SubmissionCreate(SubmissionPayload):
    pass


class SubmissionUpdate(BaseModel):
    portal_phase: str | None = None
    answers: dict[str, Any] | None = None
    uploads: dict[str, UploadMeta | None] | None = None
    submitted: bool | None = None


class SubmissionOut(BaseModel):
    id: UUID
    kind: str
    schema_version: int
    status: str
    portal_phase: str
    submitted: bool
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    answers: dict[str, Any]
    uploads_meta: dict[str, Any]
    facility_name: str | None
    facility_email: str | None
    region: str | None
    city: str | None
    facility_type: str | None
    file_count: int = 0

    model_config = {"from_attributes": True}


class SubmissionFileOut(BaseModel):
    id: UUID
    upload_key: str
    file_name: str
    size: int
    content_type: str | None
    validation: dict[str, Any] | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    incomplete: int
    files_attached: int


class AdminFacilityListItem(BaseModel):
    id: str
    facility_name: str | None
    facility_email: str | None
    region: str | None
    city: str | None
    facility_type: str | None
    status: str
    submitted: bool = False
    submitted_at: datetime | None
    last_submitted_at: datetime | None = None
    updated_at: datetime | None = None
    fileCount: int
    completionPercentage: int


class AdminFacilityDetail(BaseModel):
    id: str
    facility_name: str | None
    facility_email: str | None
    facility_phone: str | None
    region: str | None
    city: str | None
    facility_address: str | None
    facility_type: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    secondary_contact_name: str | None
    secondary_contact_email: str | None
    secondary_contact_phone: str | None
    patient_load: str | None
    his_system: str | None
    it_support: str | None
    internet_quality: str | None
    submitted: bool = False
    submitted_at: datetime | None
    last_submitted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    portal_phase: str | None = None
    status: str
    fileCount: int
    files: list[dict[str, Any]]
    completionPercentage: int
    answers: dict[str, Any]
    uploads_meta: dict[str, Any]


class PaginatedSubmissions(BaseModel):
    items: list[AdminFacilityListItem]
    total: int
    page: int
    per_page: int
    pages: int


class StatusUpdate(BaseModel):
    status: str
