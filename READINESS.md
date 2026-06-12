# API readiness checklist

Last verified by automated smoke test: `scripts/smoke_test_endpoints.sh`

## Run the smoke test

```bash
cd backend
./run.sh   # in another terminal
./scripts/smoke_test_endpoints.sh
```

Expect **all checks OK** (reminder may show `502` until Resend sender domain is verified — acceptable for staging).

---

## Endpoint status

| # | Endpoint | Ready | Notes |
|---|----------|-------|-------|
| — | `GET /health` | Yes | |
| 1 | `POST /onboarding/submissions` | Yes | Creates draft in PostgreSQL |
| 2 | `GET /onboarding/submissions/{id}` | Yes | |
| 3 | `PATCH /onboarding/submissions/{id}` | Yes | **Merges** partial `answers` (autosave-safe) |
| 4 | `PUT /onboarding/submissions/{id}` | Yes | Accepts `uploads_meta` from GET responses |
| 5 | `POST /onboarding/submissions/{id}/submit` | Yes | Validates checklist → `pending` |
| 6 | `GET /onboarding/submissions/by-email?email=` | Yes | **Preferred** for resume links |
| 6b | `GET /onboarding/submissions/by-email/{email}` | Yes | Use `{email:path}` or URL-encode `@` |
| 7 | `POST /onboarding/submissions/import` | Yes | |
| 8 | `POST .../files/{upload_key}` | Yes | CSV parsed into row tables when headers valid |
| 9 | `DELETE .../files/{upload_key}` | Yes | |
| 10 | `POST /admin/auth/login` | Yes | Uses `.env` admin credentials |
| 11 | `GET /admin/stats` | Yes | |
| 12 | `GET /admin/submissions` | Yes | Filters + pagination |
| 13 | `GET /admin/submissions/{id}` | Yes | |
| 14 | `PATCH /admin/submissions/{id}/status` | Yes | |
| 15 | `GET .../files/{key}/download` | Yes | `404` if no file uploaded |
| 16 | `POST /admin/reminders/send-incomplete` | Yes* | *Requires verified Resend domain |
| 17 | `POST /admin/reminders/send-to-facility/{id}` | Yes* | Returns `502` if Resend rejects sender |

---

## Fixes applied for production readiness

1. **PATCH merges `answers`** — partial autosave no longer wipes other fields.
2. **`flag_modified` on JSONB** — SQLAlchemy persists merged `answers` / `uploads_meta`.
3. **Resume by email** — query route registered before `{submission_id}`; portal uses `?email=`.
4. **PUT accepts `uploads_meta`** — round-trip from GET/SubmissionOut works.
5. **Smoke test script** — repeatable verification in `scripts/smoke_test_endpoints.sh`.

---

## Before go-live

- [ ] `DATABASE_URL` — production Neon/Postgres
- [ ] `SECRET_KEY` — long random value
- [ ] `ADMIN_PASSWORD` — strong password
- [ ] `CORS_ORIGINS` — includes `https://www.helixhealth.app`
- [ ] `RESEND_FROM_EMAIL` — domain verified in [Resend](https://resend.com/domains)
- [ ] API deployed at `https://api.helixhealth.app` (portal expects this host)
- [ ] Run `./scripts/smoke_test_endpoints.sh` against production base URL:
  ```bash
  BASE_URL=https://api.helixhealth.app ./scripts/smoke_test_endpoints.sh
  ```

---

## Portal integration

| Feature | Status |
|---------|--------|
| Autosave to API | Yes — when `HELIX_API_BASE` is set (auto on helixhealth.app / localhost) |
| File upload to API | Yes |
| Submit to API | Yes |
| Resume from reminder link | Yes — `?resume={email}` + `by-email?email=` |

---

## Related docs

- [API_PRESENTATION.md](./API_PRESENTATION.md) — presenter guide
- [README.md](./README.md) — setup
