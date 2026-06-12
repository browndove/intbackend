# Helix Pre-Onboarding API — Summary (readable)

**Local API:** http://localhost:8000/api/v1  
**Try it in the browser:** http://localhost:8000/docs  
**Health check:** http://localhost:8000/health → should return `{"status":"ok"}`  
**Facility portal:** https://www.helixhealth.app/on-boarding/index.html

---

## What this API does

Helix has two sides:

**Public onboarding (no login)** — the facility portal saves drafts, uploads template files, and submits the checklist.

**Admin (login required)** — Helix staff review facilities, change status, download files, and send reminder emails.

**Typical flow:** A hospital fills Step 1 on the portal (name, contacts, staffing, services, etc.). Answers autosave to PostgreSQL. They can upload CSV/Excel later (Departments, Units, Staff, Roles, Patients) — uploads are optional before submit. When they submit, the API checks required fields, marks the record **pending**, and can email a confirmation via Resend. Your team reviews in admin, approves or rejects, and can nudge incomplete drafts with reminder emails.

**Statuses:** `incomplete` (draft) → `pending` (submitted) → `approved` or `rejected`.

**What's stored:** Checklist in `submissions` (JSON + searchable columns), file metadata, actual files on disk, and parsed CSV rows in separate tables when headers are valid.

---

## Public endpoints (9 + health)

1. **GET /health** — Is the server up?

2. **POST /onboarding/submissions** — Create a new draft. Returns an `id` (UUID). Portal does this on first save.

3. **GET /onboarding/submissions/{id}** — Load one submission.

4. **PATCH /onboarding/submissions/{id}** — Update draft (autosave). Merges new fields into existing answers so partial saves don't wipe data.

5. **PUT /onboarding/submissions/{id}** — Replace the full record (used on submit when a draft already exists).

6. **POST /onboarding/submissions/{id}/submit** — Final submit. Validates Step 1 required fields → status **pending**. Template files not required.

7. **GET /onboarding/submissions/by-email?email=...** — Resume the latest unsubmitted draft for that facility email (reminder links use `?resume=email`).

8. **POST /onboarding/submissions/import** — Load a full JSON export in one request (testing/migration).

9. **POST /onboarding/submissions/{id}/files/{key}** — Upload a file. Keys: `departments`, `units`, `staff`, `roles`, `patients`. CSV gets header checks; valid CSV rows go into the database.

10. **DELETE /onboarding/submissions/{id}/files/{key}** — Remove an upload.

---

## Admin endpoints (8 + login)

All except login need: `Authorization: Bearer <token>`

1. **POST /admin/auth/login** — Email + password from `.env` → JWT token.

2. **GET /admin/stats** — Dashboard counts (total, pending, approved, rejected, incomplete, files).

3. **GET /admin/submissions** — List facilities with search, filters (status, region, type, dates), sorting, pagination.

4. **GET /admin/submissions/{id}** — Full detail for review (contacts, answers, files, completion %).

5. **PATCH /admin/submissions/{id}/status** — Set `approved`, `rejected`, `pending`, or `incomplete`.

6. **GET /admin/submissions/{id}/files/{key}/download** — Download the uploaded file.

7. **POST /admin/reminders/send-incomplete** — Email all drafts that aren't submitted but have a facility email (Resend).

8. **POST /admin/reminders/send-to-facility/{id}** — Email one facility.

Reminders link back to the portal with `?resume={email}` so they can continue where they left off.

---

## 5–7 minute demo script

1. Hit `/health` — API is live.
2. Open `/docs` (Swagger).
3. Create a draft (`POST /onboarding/submissions`).
4. Patch a few fields — autosave merge.
5. Admin login → show stats and list.
6. Upload a sample `staff.csv`.
7. Submit → status `pending`.
8. Open admin detail for that facility.
9. Approve (`PATCH` status → `approved`).
10. Optional: send a reminder on another incomplete draft.

**Simpler demo:** Use the live portal — type in the form, show "Saved to Helix", submit, refresh admin.

---

## Config you may be asked about

- **DATABASE_URL** — Postgres (e.g. Neon)
- **ADMIN_EMAIL / ADMIN_PASSWORD** — Admin login
- **RESEND_API_KEY, RESEND_ENABLED, RESEND_FROM_EMAIL** — Emails (sender domain must be verified in Resend)
- **ONBOARDING_PORTAL_URL** — Link in reminder emails
- **CORS_ORIGINS** — Which frontends can call the API

Production API host expected by the portal: `https://api.helixhealth.app/api/v1`

---

## One-line cheat sheet

**Public:** create → get → patch (autosave) → put → submit → resume by email → import → upload/delete files.

**Admin:** login → stats → list → detail → approve/reject → download file → send reminders.

---

## Related files

- **API_PRESENTATION.md** — full endpoint guide with curl examples and sample JSON
- **READINESS.md** — smoke test and go-live checklist
- **README.md** — setup and environment variables
