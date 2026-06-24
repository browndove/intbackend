-- Align submission_patients with the facility onboarding guide (Unit, bed_number, room_number).

ALTER TABLE submission_patients ADD COLUMN IF NOT EXISTS unit VARCHAR(255);
ALTER TABLE submission_patients ADD COLUMN IF NOT EXISTS bed_number VARCHAR(64);
ALTER TABLE submission_patients ADD COLUMN IF NOT EXISTS room_number VARCHAR(64);

UPDATE submission_patients
SET unit = ward
WHERE unit IS NULL AND ward IS NOT NULL;

UPDATE submission_patients
SET bed_number = bed
WHERE bed_number IS NULL AND bed IS NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'submission_patients' AND column_name = 'ward'
  ) THEN
    ALTER TABLE submission_patients DROP COLUMN ward;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'submission_patients' AND column_name = 'bed'
  ) THEN
    ALTER TABLE submission_patients DROP COLUMN bed;
  END IF;
END $$;

ALTER TABLE submission_patients ALTER COLUMN unit SET NOT NULL;
ALTER TABLE submission_patients ALTER COLUMN unit SET DEFAULT '';

ALTER TABLE submission_staff ALTER COLUMN phone DROP NOT NULL;
