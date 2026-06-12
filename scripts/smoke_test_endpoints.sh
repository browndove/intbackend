#!/usr/bin/env bash
# Smoke-test all API endpoints. Run with API on localhost:8000.
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
API="$BASE/api/v1"
PASS=0
FAIL=0

ok() { echo "  OK  $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL $1"; echo "       $2"; FAIL=$((FAIL + 1)); }

code() { curl -s -o /tmp/hx_body.json -w "%{http_code}" "$@"; }

echo "=== Helix API smoke test ==="
echo "Base: $API"
echo

# Health
c=$(code "$BASE/health")
[[ "$c" == "200" ]] && ok "GET /health ($c)" || bad "GET /health" "status $c: $(cat /tmp/hx_body.json)"

# Create draft
c=$(code -X POST "$API/onboarding/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "helix.facility_preonboarding",
    "schema_version": 3,
    "portal_phase": "checklist",
    "answers": {
      "facility_name": "Smoke Test Hospital",
      "facility_type": "District Hospital",
      "facility_region": "Greater Accra",
      "facility_city": "Accra",
      "facility_address": "1 Test Road",
      "facility_email": "smoke-test-'$(date +%s)'@helix-test.local",
      "facility_phone": "+233 201111111",
      "primary_name": "Test Contact",
      "primary_phone": "+233 202222222",
      "primary_email": "primary@helix-test.local",
      "total_employees": "50",
      "total_clinical_staff": "30",
      "total_nonclinical_staff": "20",
      "has_it_team": "No",
      "has_emergency": "Yes",
      "has_inpatient_wards": "No",
      "has_ambulance": "No",
      "has_medical_director": "Yes",
      "staff_has_id": "Yes",
      "staff_has_work_email": "No",
      "staff_uses_personal_email": "Yes",
      "has_employee_directory": "Yes",
      "staff_list_by_department": "No",
      "staff_list_by_role": "No"
    },
    "uploads": {}
  }')
[[ "$c" == "201" ]] && ok "POST /onboarding/submissions ($c)" || bad "POST /onboarding/submissions" "status $c: $(cat /tmp/hx_body.json)"

SUB_ID=$(python3 -c "import json; print(json.load(open('/tmp/hx_body.json'))['id'])" 2>/dev/null || true)
FACILITY_EMAIL=$(python3 -c "import json; d=json.load(open('/tmp/hx_body.json')); print(d.get('facility_email') or d.get('answers',{}).get('facility_email',''))" 2>/dev/null || true)
echo "$FACILITY_EMAIL" > /tmp/hx_email.txt

if [[ -z "${SUB_ID:-}" ]]; then
  echo "Cannot continue without submission id"
  exit 1
fi
echo "  (submission_id=$SUB_ID)"

# GET submission
c=$(code "$API/onboarding/submissions/$SUB_ID")
[[ "$c" == "200" ]] && ok "GET /onboarding/submissions/{id} ($c)" || bad "GET submission" "$c"

# PATCH
c=$(code -X PATCH "$API/onboarding/submissions/$SUB_ID" \
  -H "Content-Type: application/json" \
  -d '{"portal_phase": "staff", "answers": {"facility_name": "Smoke Test Hospital Updated"}}')
[[ "$c" == "200" ]] && ok "PATCH /onboarding/submissions/{id} ($c)" || bad "PATCH" "$c"

# Lookup by email (query param — reliable for @)
FACILITY_EMAIL=$(cat /tmp/hx_email.txt)
enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$FACILITY_EMAIL")
c=$(code "$API/onboarding/submissions/by-email?email=$enc")
[[ "$c" == "200" ]] && ok "GET /onboarding/submissions/by-email?email= ($c)" || bad "by-email" "$c"

# PUT (reload full record first)
c=$(code "$API/onboarding/submissions/$SUB_ID")
cp /tmp/hx_body.json /tmp/hx_put.json
c=$(code -X PUT "$API/onboarding/submissions/$SUB_ID" \
  -H "Content-Type: application/json" \
  -d @/tmp/hx_put.json)
[[ "$c" == "200" ]] && ok "PUT /onboarding/submissions/{id} ($c)" || bad "PUT" "$c: $(cat /tmp/hx_body.json | head -c 200)"

# Submit
c=$(code -X POST "$API/onboarding/submissions/$SUB_ID/submit")
[[ "$c" == "200" ]] && ok "POST /onboarding/submissions/{id}/submit ($c)" || bad "submit" "$c: $(cat /tmp/hx_body.json)"

# Submit again should still 200 (idempotent enough) or check status pending
STATUS=$(python3 -c "import json; print(json.load(open('/tmp/hx_body.json')).get('status',''))" 2>/dev/null || echo "")
[[ "$STATUS" == "pending" ]] && ok "submit status=pending" || bad "submit status" "got $STATUS"

# Import
c=$(code -X POST "$API/onboarding/submissions/import" \
  -H "Content-Type: application/json" \
  -d '{"kind":"helix.facility_preonboarding","schema_version":3,"submitted":false,"portal_phase":"checklist","answers":{"facility_name":"Import Test","facility_email":"import-'$(date +%s)'@helix-test.local"},"uploads":{}}')
[[ "$c" == "201" ]] && ok "POST /onboarding/submissions/import ($c)" || bad "import" "$c"

# File upload - minimal valid staff CSV header
STAFF_CSV="/tmp/hx_staff.csv"
echo "email,first_name,last_name,job_title,rank,middle_name,phone,gender,department,subspecialty,patient_access,employee_id,highest_qualifications" > "$STAFF_CSV"
echo "a@t.com,A,B,,,,233201234567,Male,Med,,Yes,E1,MBChB" >> "$STAFF_CSV"

# Need incomplete submission for file test - create another
c=$(code -X POST "$API/onboarding/submissions" \
  -H "Content-Type: application/json" \
  -d '{"portal_phase":"checklist","answers":{"facility_name":"File Test","facility_email":"file-'$(date +%s)'@helix-test.local"},"uploads":{}}')
FILE_SUB=$(python3 -c "import json; print(json.load(open('/tmp/hx_body.json'))['id'])")
c=$(code -X POST "$API/onboarding/submissions/$FILE_SUB/files/staff" -F "file=@$STAFF_CSV")
[[ "$c" == "200" ]] && ok "POST /onboarding/.../files/staff ($c)" || bad "file upload" "$c: $(cat /tmp/hx_body.json | head -c 300)"

# Delete file
c=$(code -X DELETE "$API/onboarding/submissions/$FILE_SUB/files/staff")
[[ "$c" == "200" ]] && ok "DELETE /onboarding/.../files/staff ($c)" || bad "file delete" "$c"

# Invalid upload key
c=$(code -X POST "$API/onboarding/submissions/$FILE_SUB/files/invalid" -F "file=@$STAFF_CSV")
[[ "$c" == "400" ]] && ok "POST invalid upload_key returns 400 ($c)" || bad "invalid upload_key" "expected 400 got $c"

# Admin login — env vars override backend/.env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
ADMIN_PASS="${ADMIN_PASSWORD:-start}"
ADMIN_MAIL="${ADMIN_EMAIL:-admin@helix.health}"
if [[ -f "$ENV_FILE" ]]; then
  if [[ -z "${ADMIN_PASSWORD:-}" ]]; then
    ADMIN_PASS=$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "start")
  fi
  if [[ -z "${ADMIN_EMAIL:-}" ]]; then
    ADMIN_MAIL=$(grep -E '^ADMIN_EMAIL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' || echo "admin@helix.health")
  fi
fi

c=$(code -X POST "$API/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_MAIL\",\"password\":\"$ADMIN_PASS\"}")
[[ "$c" == "200" ]] && ok "POST /admin/auth/login ($c)" || bad "admin login" "$c: $(cat /tmp/hx_body.json)"

TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/hx_body.json'))['access_token'])" 2>/dev/null || true)
if [[ -z "${TOKEN:-}" ]]; then
  bad "admin token" "missing token"
else
  AUTH="Authorization: Bearer $TOKEN"
  c=$(code "$API/admin/stats" -H "$AUTH")
  [[ "$c" == "200" ]] && ok "GET /admin/stats ($c)" || bad "stats" "$c"

  c=$(code "$API/admin/submissions?page=1&per_page=5" -H "$AUTH")
  [[ "$c" == "200" ]] && ok "GET /admin/submissions ($c)" || bad "list submissions" "$c"

  c=$(code "$API/admin/submissions/$SUB_ID" -H "$AUTH")
  [[ "$c" == "200" ]] && ok "GET /admin/submissions/{id} ($c)" || bad "detail" "$c"

  c=$(code -X PATCH "$API/admin/submissions/$SUB_ID/status" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"status":"approved"}')
  [[ "$c" == "200" ]] && ok "PATCH /admin/submissions/{id}/status ($c)" || bad "status update" "$c"

  c=$(code -o /dev/null -w "%{http_code}" "$API/admin/submissions/$SUB_ID/files/staff/download" -H "$AUTH")
  # 404 ok if no file on submitted record
  [[ "$c" == "200" || "$c" == "404" ]] && ok "GET file download ($c)" || bad "download" "$c"

  c=$(code -X POST "$API/admin/reminders/send-to-facility/$FILE_SUB" -H "$AUTH")
  if [[ "$c" == "200" ]]; then
    ok "POST reminders/send-to-facility ($c)"
  elif [[ "$c" == "502" || "$c" == "503" ]]; then
    ok "POST reminders/send-to-facility ($c — Resend/from-domain; configure for prod)"
  else
    bad "single reminder" "$c: $(cat /tmp/hx_body.json)"
  fi

  c=$(code -X POST "$API/admin/reminders/send-incomplete" -H "$AUTH")
  [[ "$c" == "200" ]] && ok "POST reminders/send-incomplete ($c)" || bad "batch reminders" "$c"
fi

# Bad admin creds
c=$(code -X POST "$API/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"wrong","password":"wrong"}')
[[ "$c" == "401" ]] && ok "admin login rejects bad creds ($c)" || bad "bad login" "expected 401 got $c"

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ "$FAIL" -eq 0 ]]
