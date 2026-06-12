-- Expand submissions with typed columns for the pre-onboarding portal checklist.
-- Safe to re-run (IF NOT EXISTS). Child tables are created via SQLAlchemy create_all.

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS facility_address TEXT;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS facility_phone VARCHAR(64);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS facility_phone_country VARCHAR(2);

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS primary_name VARCHAR(255);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS primary_phone VARCHAR(64);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS primary_phone_country VARCHAR(2);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS primary_email VARCHAR(255);

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS secondary_name VARCHAR(255);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS secondary_phone VARCHAR(64);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS secondary_phone_country VARCHAR(2);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS secondary_email VARCHAR(255);

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS total_employees INTEGER;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS total_clinical_staff INTEGER;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS total_nonclinical_staff INTEGER;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_it_team VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS total_it_staff INTEGER;

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_emergency VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_inpatient_wards VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS total_inpatient_beds INTEGER;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_ambulance VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_medical_director VARCHAR(8);

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS staff_has_id VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS staff_has_work_email VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS staff_uses_personal_email VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS has_employee_directory VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS staff_list_by_department VARCHAR(8);
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS staff_list_by_role VARCHAR(8);

CREATE INDEX IF NOT EXISTS ix_submissions_primary_email ON submissions (primary_email);
