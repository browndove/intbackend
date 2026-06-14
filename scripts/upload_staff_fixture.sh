#!/usr/bin/env bash
# Upload backend/fixtures/staff_dummy.csv to a submission (creates draft if no SUBMISSION_ID).
set -euo pipefail

API="${BASE_URL:-https://intbackend-production.up.railway.app}/api/v1"
FIXTURE="$(cd "$(dirname "$0")/.." && pwd)/fixtures/staff_dummy.csv"
SUBMISSION_ID="${1:-}"
FACILITY_EMAIL="${FACILITY_EMAIL:-staff-fixture-$(date +%s)@helix-test.local}"

if [[ ! -f "$FIXTURE" ]]; then
  echo "Missing fixture: $FIXTURE" >&2
  exit 1
fi

if [[ -z "$SUBMISSION_ID" ]]; then
  echo "Creating draft submission for $FACILITY_EMAIL ..."
  curl -sS -X POST "$API/onboarding/submissions" \
    -H "Content-Type: application/json" \
    -d "{
      \"portal_phase\": \"staff\",
      \"answers\": {
        \"facility_name\": \"Staff Fixture Test Clinic\",
        \"facility_type\": \"District Hospital\",
        \"facility_region\": \"Greater Accra\",
        \"facility_city\": \"Accra\",
        \"facility_address\": \"12 Test Lane, Accra\",
        \"facility_email\": \"$FACILITY_EMAIL\",
        \"facility_phone\": \"233201234567\",
        \"primary_name\": \"Test Admin\",
        \"primary_email\": \"primary@helix-test.local\",
        \"primary_phone\": \"233209876543\"
      },
      \"uploads\": {}
    }" > /tmp/hx_staff_upload.json
  SUBMISSION_ID=$(python3 -c "import json; print(json.load(open('/tmp/hx_staff_upload.json'))['id'])")
  echo "  submission_id=$SUBMISSION_ID"
fi

echo "Uploading staff fixture to $SUBMISSION_ID ..."
HTTP=$(curl -sS -o /tmp/hx_staff_upload.json -w "%{http_code}" \
  -X POST "$API/onboarding/submissions/$SUBMISSION_ID/files/staff" \
  -F "file=@$FIXTURE;type=text/csv")

echo "HTTP $HTTP"
python3 - <<'PY'
import json
d = json.load(open("/tmp/hx_staff_upload.json"))
meta = (d.get("uploads_meta") or {}).get("staff") or {}
val = meta.get("validation") or {}
print("file:", meta.get("fileName"))
print("validation:", val.get("ok"), "-", val.get("message"))
if val.get("missing"):
    print("missing:", ", ".join(val["missing"]))
if val.get("found"):
    print("found:", ", ".join(val["found"]))
print("resume:", f"https://www.helixhealth.app/on-boarding/index.html?resume={d.get('answers', {}).get('facility_email') or d.get('facility_email', '')}")
PY

[[ "$HTTP" == "200" ]] || exit 1
