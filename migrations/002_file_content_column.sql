-- Store file bytes in the database so downloads survive Railway's ephemeral filesystem.
-- Safe to re-run (IF NOT EXISTS not available for ADD COLUMN in all PG versions,
-- but the DO block handles it).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'submission_files' AND column_name = 'content'
    ) THEN
        ALTER TABLE submission_files ADD COLUMN content BYTEA;
    END IF;
END $$;
