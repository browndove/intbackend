# Helix Pre-Onboarding API (FastAPI + PostgreSQL)

Backend for the facility **on-boarding** portal and **admin** dashboard.

## Setup

```bash
cd backend
python3.11 -m venv .venv          # use 3.11 — 3.14 may fail on psycopg2
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD (never commit .env)
```

Start the server **with the venv** (not system `python` / `uvicorn`):

```bash
./run.sh
# or:
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

**Presentation:** [API_PRESENTATION_SUMMARY.md](./API_PRESENTATION_SUMMARY.md) (short) · [API_PRESENTATION.md](./API_PRESENTATION.md) (full) · [READINESS.md](./READINESS.md) · Smoke test: `./scripts/smoke_test_endpoints.sh`

## Environment

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon/Postgres URL (`postgresql://...?sslmode=require`) |
| `SECRET_KEY` | JWT signing secret |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Admin login |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `UPLOAD_DIR` | Local folder for CSV/Excel uploads (default `uploads`) |
| `RESEND_API_KEY` | [Resend](https://resend.com) API key for completion reminder emails |
| `RESEND_FROM_EMAIL` | Verified sender (e.g. `Helix Health <onboarding@yourdomain.com>`) |
| `RESEND_ENABLED` | Set `true` to send emails |
| `ONBOARDING_PORTAL_URL` | Link in reminder emails (default production portal URL) |
| `SEND_SUBMIT_CONFIRMATION` | Send a Resend confirmation when a facility submits |

## API overview

### Onboarding (public)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/onboarding/submissions` | Create draft |
| `GET` | `/api/v1/onboarding/submissions/{id}` | Get submission |
| `PATCH` | `/api/v1/onboarding/submissions/{id}` | Update answers / phase |
| `PUT` | `/api/v1/onboarding/submissions/{id}` | Replace full payload |
| `POST` | `/api/v1/onboarding/submissions/{id}/submit` | Validate & submit (status → `pending`) |
| `POST` | `/api/v1/onboarding/submissions/import` | Import full portal JSON in one shot |
| `POST` | `/api/v1/onboarding/submissions/{id}/files/{upload_key}` | Upload file (`departments`, `units`, `staff`, `roles`, `patients`) |
| `DELETE` | `/api/v1/onboarding/submissions/{id}/files/{upload_key}` | Remove file |

### Admin (Bearer JWT)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/admin/auth/login` | `{ email, password }` → token |
| `GET` | `/api/v1/admin/stats` | Dashboard counts |
| `GET` | `/api/v1/admin/submissions` | List + filters (`search`, `status`, `region`, `facility_type`, `date_from`, `date_to`, `sort`, `order`, `page`, `per_page`) |
| `GET` | `/api/v1/admin/submissions/{id}` | Detail drawer payload |
| `PATCH` | `/api/v1/admin/submissions/{id}/status` | `{ status: pending\|approved\|rejected\|incomplete }` |
| `GET` | `/api/v1/admin/submissions/{id}/files/{upload_key}/download` | Download attachment |

## Frontend configuration

The onboarding portal auto-sets `HELIX_API_BASE` on `helixhealth.app` → `https://api.helixhealth.app/api/v1` and on `localhost` → `http://localhost:8000/api/v1`. Override with an explicit script tag if needed.

Drafts **autosave to PostgreSQL** on every keystroke (debounced API sync). Reminder emails use Resend:

- `POST /api/v1/admin/reminders/send-incomplete` — all incomplete drafts with a facility email
- `POST /api/v1/admin/reminders/send-to-facility/{id}` — one facility

Reminder links include `?resume={facility_email}` so the portal reloads the server draft.

## Database

Tables are created on startup. `migrations/001_onboarding_schema.sql` adds checklist columns to existing `submissions` rows.

| Table | Purpose |
|-------|---------|
| `submissions` | Step 1 checklist (typed columns + `answers` JSONB) |
| `submission_files` | Uploaded CSV/Excel per `upload_key` |
| `submission_departments` | Parsed Departments rows |
| `submission_units` | Parsed Units rows |
| `submission_staff` | Parsed Staff rows |
| `submission_roles` | Parsed Roles rows |
| `submission_patients` | Parsed Patients rows (PHI) |

Validated CSV uploads are parsed into the row tables automatically. Field keys match `on-boarding/BACKEND_ONBOARDING_SPEC.md` and [the live portal](https://www.helixhealth.app/on-boarding/index.html).

## Security notes

- Do **not** commit `.env` or database credentials.
- Rotate any credentials that were shared in chat.
- Restrict CORS origins in production.
- Use a strong `SECRET_KEY` and bcrypt-hashed `ADMIN_PASSWORD` for production admin accounts.
