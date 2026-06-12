# Helix Pre-Onboarding API — Endpoint Guide (Presentation)

**Base URL (local):** `http://localhost:8000/api/v1`  
**Interactive docs:** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger — best for live demos)  
**Health check:** `http://localhost:8000/health`

**Production portal:** [https://www.helixhealth.app/on-boarding/index.html](https://www.helixhealth.app/on-boarding/index.html)

---

## Overview

Two API groups serve different users:

| Group | Authentication | Used by |
|-------|----------------|---------|
| **Onboarding** | None (public) | Facility pre-onboarding portal |
| **Admin** | JWT Bearer token | Helix internal admin dashboard |

### End-to-end flow

1. A facility opens the pre-onboarding portal and fills the **Step 1 checklist** (facility info, contacts, staffing, services, staff systems).
2. The portal **autosaves** to PostgreSQL via `PATCH /onboarding/submissions/{id}` (debounced).
3. Optionally, the facility uploads **template CSV/Excel** files (Departments, Units, Staff, Roles, Patients) — these do **not** block submit.
4. On **Submit**, the API validates required checklist fields, sets status to **`pending`**, and may send a **Resend** confirmation email.
5. Helix staff use **admin** endpoints to list submissions, review detail, approve/reject, download files, and send **completion reminders** via Resend.

### Data stored

| Layer | Where |
|-------|--------|
| Checklist answers | `submissions.answers` (JSONB) + typed columns (`facility_name`, `region`, …) |
| Upload metadata | `submissions.uploads_meta` |
| File bytes | Server `uploads/` folder + `submission_files` table |
| Parsed CSV rows | `submission_departments`, `submission_units`, `submission_staff`, `submission_roles`, `submission_patients` |

### Submission status lifecycle

| Status | Meaning |
|--------|---------|
| `incomplete` | Draft; not yet submitted |
| `pending` | Submitted; awaiting Helix review |
| `approved` | Accepted for rollout |
| `rejected` | Not accepted |

---

## Health check

### `GET /health`

| | |
|---|---|
| **Auth** | None |
| **URL** | `http://localhost:8000/health` (no `/api/v1` prefix) |

**Purpose:** Confirm the API process is running.

**Test:**

```bash
curl http://localhost:8000/health
```

**Expected response:**

```json
{ "status": "ok" }
```

**Presenter note:** Use this first in a demo to show the backend is up.

---

## Onboarding endpoints (public)

No login required. The portal calls these automatically when `HELIX_API_BASE` is set. For demos, use Swagger (`/docs`) or the curl examples below.

---

### 1. Create draft

**`POST /api/v1/onboarding/submissions`**

| | |
|---|---|
| **Purpose** | Create a new facility pre-onboarding record |
| **Called by** | Portal on first server sync, or manual/API testing |
| **Success** | `201 Created` + submission JSON including `id` (UUID) |

**Sample body:**

```json
{
  "kind": "helix.facility_preonboarding",
  "schema_version": 3,
  "portal_phase": "checklist",
  "submitted": false,
  "answers": {
    "facility_name": "Demo Hospital",
    "facility_type": "District Hospital",
    "facility_region": "Greater Accra",
    "facility_city": "Accra",
    "facility_address": "123 Main Street",
    "facility_email": "demo@hospital.org",
    "facility_phone": "+233 201234567",
    "facility_phone_country": "GH"
  },
  "uploads": {
    "departments": null,
    "units": null,
    "staff": null,
    "roles": null,
    "patients": null
  }
}
```

**Test:**

```bash
curl -X POST http://localhost:8000/api/v1/onboarding/submissions \
  -H "Content-Type: application/json" \
  -d @sample-draft.json
```

**Presenter note:** Save the returned `id` for all following steps.

---

### 2. Get submission

**`GET /api/v1/onboarding/submissions/{submission_id}`**

| | |
|---|---|
| **Purpose** | Load one submission by UUID |
| **Success** | `200` + full submission object |

**Test:**

```bash
curl http://localhost:8000/api/v1/onboarding/submissions/{SUBMISSION_ID}
```

---

### 3. Update draft (autosave)

**`PATCH /api/v1/onboarding/submissions/{submission_id}`**

| | |
|---|---|
| **Purpose** | Partial update — answers, upload metadata, portal step |
| **Called by** | Portal on every debounced autosave (~800ms after typing) |
| **Success** | `200` + updated submission |
| **Behavior** | **Merges** into existing `answers` — partial PATCH never wipes other fields |

**Sample body:**

```json
{
  "portal_phase": "checklist",
  "answers": {
    "primary_name": "Dr. Kwame Mensah",
    "primary_phone": "+233 241234567",
    "primary_email": "kwame.mensah@hospital.org",
    "total_employees": "120"
  }
}
```

**Presenter note:** Typed DB columns (`facility_name`, `region`, etc.) are synced from `answers` on each update.

---

### 4. Replace full payload

**`PUT /api/v1/onboarding/submissions/{submission_id}`**

| | |
|---|---|
| **Purpose** | Replace entire submission (same shape as create) |
| **Called by** | Portal submit flow when a server `id` already exists |

**Test:** Same body as create; use `PUT` instead of `POST`.

---

### 5. Submit checklist

**`POST /api/v1/onboarding/submissions/{submission_id}/submit`**

| | |
|---|---|
| **Purpose** | Validate required Step 1 fields and mark as submitted |
| **Success** | `200`; `submitted: true`, `status: "pending"`, `submitted_at` set |
| **Failure** | `400` with `fields` array listing missing answer keys |

**Effects:**

- All required checklist fields must be present (including conditional fields when parent Yes/No is `"Yes"`).
- Optional template uploads are **not** required.
- If `RESEND_ENABLED=true`, sends a **confirmation email** to `facility_email`.

**Test:**

```bash
curl -X POST http://localhost:8000/api/v1/onboarding/submissions/{SUBMISSION_ID}/submit
```

**Presenter note:** This is the main “facility is done with Step 1” moment for the onboarding team.

---

### 6. Resume draft by email

**`GET /api/v1/onboarding/submissions/by-email?email={email}`** (preferred)

**`GET /api/v1/onboarding/submissions/by-email/{email}`** (path form; URL-encode `@` as `%40`)

| | |
|---|---|
| **Purpose** | Load the latest **unsubmitted** draft for a facility email |
| **Called by** | Portal when URL contains `?resume=facility@email.org` (from reminder emails) |
| **Failure** | `404` if no incomplete draft exists |

**Test:**

```bash
curl "http://localhost:8000/api/v1/onboarding/submissions/by-email?email=demo%40hospital.org"
```

**Presenter note:** Enables cross-device resume; not limited to the same browser as localStorage.

---

### 7. Import portal JSON (one shot)

**`POST /api/v1/onboarding/submissions/import`**

| | |
|---|---|
| **Purpose** | Create a submission from exported portal JSON; optionally submit in one request |
| **Body** | Full export payload; set `"submitted": true` to submit immediately |
| **Success** | `201` + submission |

**Use case:** Testing, migrations, or importing a JSON file downloaded from the portal.

---

### 8. Upload template file

**`POST /api/v1/onboarding/submissions/{submission_id}/files/{upload_key}`**

| | |
|---|---|
| **Purpose** | Upload CSV or Excel for a Helix data template |
| **Content-Type** | `multipart/form-data`; field name: `file` |
| **Success** | `200` + updated submission with `uploads_meta` |

**Valid `upload_key` values:**

| upload_key | Template |
|------------|----------|
| `departments` | Departments |
| `units` | Units |
| `staff` | Staff roster |
| `roles` | Operational roles |
| `patients` | Patient roster (PHI) |

**Behavior:**

- File saved under `uploads/{submission_id}/{upload_key}/`.
- **CSV:** Headers validated against Helix template; valid files parsed into row tables.
- **Excel:** Accepted; header check deferred (`validation.ok: null`).

**Test:**

```bash
curl -X POST "http://localhost:8000/api/v1/onboarding/submissions/{SUBMISSION_ID}/files/staff" \
  -F "file=@staff.csv"
```

**Presenter note:** Steps 2–6 never block Step 1 submit.

---

### 9. Delete uploaded file

**`DELETE /api/v1/onboarding/submissions/{submission_id}/files/{upload_key}`**

| | |
|---|---|
| **Purpose** | Remove stored file and clear parsed rows for that template |
| **Success** | `200` + updated submission |

---

## Admin endpoints (JWT required)

All admin routes except login require:

```http
Authorization: Bearer <access_token>
```

---

### 10. Admin login

**`POST /api/v1/admin/auth/login`**

| | |
|---|---|
| **Purpose** | Authenticate Helix staff; returns JWT |
| **Credentials** | From `.env`: `ADMIN_EMAIL`, `ADMIN_PASSWORD` |

**Body:**

```json
{
  "email": "admin@helix.health",
  "password": "your-admin-password"
}
```

**Success:**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Failure:** `401 Invalid email or password`

**Test:**

```bash
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@helix.health","password":"YOUR_PASSWORD"}'
```

**Presenter note:** Copy `access_token` into Swagger “Authorize” or use in curl for all admin calls below.

---

### 11. Dashboard statistics

**`GET /api/v1/admin/stats`**

| | |
|---|---|
| **Purpose** | Aggregate counts for admin home dashboard |

**Response fields:**

| Field | Meaning |
|-------|---------|
| `total` | All submissions |
| `pending` | Submitted, awaiting review |
| `approved` | Approved |
| `rejected` | Rejected |
| `incomplete` | Drafts not submitted |
| `files_attached` | Total uploaded files |

**Test:**

```bash
curl http://localhost:8000/api/v1/admin/stats \
  -H "Authorization: Bearer {TOKEN}"
```

---

### 12. List submissions

**`GET /api/v1/admin/submissions`**

| | |
|---|---|
| **Purpose** | Paginated, filterable list of facilities |

**Query parameters:**

| Parameter | Description |
|-----------|-------------|
| `search` | Match facility name, email, or city |
| `status` | `incomplete`, `pending`, `approved`, `rejected` |
| `region` | Ghana region filter |
| `facility_type` | Facility type filter |
| `date_from`, `date_to` | Submitted date range (ISO dates) |
| `sort` | e.g. `facility_name`, `submitted_at`, `status` |
| `order` | `asc` or `desc` |
| `page` | Page number (default 1) |
| `per_page` | Page size (max 100) |

**Test:**

```bash
curl "http://localhost:8000/api/v1/admin/submissions?status=pending&page=1" \
  -H "Authorization: Bearer {TOKEN}"
```

---

### 13. Facility detail

**`GET /api/v1/admin/submissions/{submission_id}`**

| | |
|---|---|
| **Purpose** | Full detail for admin review drawer |
| **Includes** | Contacts, address, staffing flags, file list, `answers`, `uploads_meta`, completion % |

---

### 14. Update review status

**`PATCH /api/v1/admin/submissions/{submission_id}/status`**

| | |
|---|---|
| **Purpose** | Helix team approves or rejects a submission |

**Body:**

```json
{ "status": "approved" }
```

**Allowed values:** `incomplete`, `pending`, `approved`, `rejected`

**Test:**

```bash
curl -X PATCH "http://localhost:8000/api/v1/admin/submissions/{SUBMISSION_ID}/status" \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'
```

---

### 15. Download attachment

**`GET /api/v1/admin/submissions/{submission_id}/files/{upload_key}/download`**

| | |
|---|---|
| **Purpose** | Download the stored CSV/Excel file |
| **Response** | File stream (not JSON) |
| **Failure** | `404` if file missing on disk |

**Valid `upload_key`:** `departments`, `units`, `staff`, `roles`, `patients`

---

### 16. Send reminders (all incomplete)

**`POST /api/v1/admin/reminders/send-incomplete`**

| | |
|---|---|
| **Purpose** | Email every incomplete submission that has a `facility_email` |
| **Provider** | [Resend](https://resend.com) (`RESEND_API_KEY`, `RESEND_ENABLED`) |

**Selection criteria:**

- `submitted = false`
- `facility_email` is not null

**Success response example:**

```json
{
  "message": "Sent 3 reminder emails",
  "sent": 3,
  "failed": 0,
  "total": 3
}
```

**Email content:** Link to portal with `?resume={facility_email}` so the facility can continue their draft.

**Test:**

```bash
curl -X POST http://localhost:8000/api/v1/admin/reminders/send-incomplete \
  -H "Authorization: Bearer {TOKEN}"
```

---

### 17. Send reminder (one facility)

**`POST /api/v1/admin/reminders/send-to-facility/{submission_id}`**

| | |
|---|---|
| **Purpose** | Send one completion reminder to that submission’s facility email |
| **Success** | `{ "message": "Reminder sent to ...", "success": true }` |
| **Failure** | `400` no email; `500` Resend misconfiguration |

---

## Suggested live demo script (5–7 minutes)

| Step | What to show | Endpoint |
|------|----------------|----------|
| 1 | API is running | `GET /health` |
| 2 | Open interactive docs | `/docs` |
| 3 | Create a facility draft | `POST /onboarding/submissions` |
| 4 | Add more answers (autosave) | `PATCH /onboarding/submissions/{id}` |
| 5 | Log in as admin | `POST /admin/auth/login` |
| 6 | Show list + stats | `GET /admin/stats`, `GET /admin/submissions` |
| 7 | Upload sample CSV | `POST .../files/staff` |
| 8 | Submit checklist | `POST .../submit` → status `pending` |
| 9 | Open facility detail | `GET /admin/submissions/{id}` |
| 10 | Approve facility | `PATCH .../status` → `approved` |
| 11 | (Optional) Reminder on incomplete draft | `POST /admin/reminders/send-to-facility/{id}` |

**Portal-only demo:** Open the onboarding page, type in the checklist, point at **“Saved to Helix”**, submit, then refresh the admin list.

---

## Quick reference

```
PUBLIC (no auth)                         ADMIN (Bearer JWT)
────────────────                         ────────────────────
GET    /health

POST   /onboarding/submissions           POST   /admin/auth/login
GET    /onboarding/submissions/{id}
PATCH  /onboarding/submissions/{id}      GET    /admin/stats
PUT    /onboarding/submissions/{id}      GET    /admin/submissions
POST   /onboarding/submissions/{id}/submit
GET    /onboarding/submissions/by-email/{email}
POST   /onboarding/submissions/import    GET    /admin/submissions/{id}
POST   /onboarding/submissions/{id}/files/{key}
DELETE /onboarding/submissions/{id}/files/{key}
                                         PATCH  /admin/submissions/{id}/status
                                         GET    /admin/submissions/{id}/files/{key}/download
                                         POST   /admin/reminders/send-incomplete
                                         POST   /admin/reminders/send-to-facility/{id}
```

---

## Environment (for Q&A)

| Variable | Role |
|----------|------|
| `DATABASE_URL` | PostgreSQL (Neon) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Admin login |
| `RESEND_API_KEY` / `RESEND_ENABLED` | Reminder + submit confirmation emails |
| `RESEND_FROM_EMAIL` | Verified sender in Resend |
| `ONBOARDING_PORTAL_URL` | Link in reminder emails |
| `CORS_ORIGINS` | Allowed frontend origins |

---

## Related documentation

- `README.md` — setup and configuration
- `on-boarding/BACKEND_ONBOARDING_SPEC.md` — full field and template schema
- Swagger UI — `http://localhost:8000/docs`
