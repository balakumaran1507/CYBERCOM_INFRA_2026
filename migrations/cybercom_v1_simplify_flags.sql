-- ============================================================
-- CYBERCOM CTF v1.0 - Simplified Flag System Migration
-- ============================================================
--
-- This migration transforms the complex Phase 1 flag system into
-- a simplified, production-grade, encrypted flag system.
--
-- Changes:
-- - Removes state machine (status, valid_until, used_at, flag_version)
-- - Adds encrypted flag storage (encrypted_flag)
-- - Adds key rotation support (encryption_key_id)
-- - Keeps minimal audit trail (created_at)
-- - Maintains container binding (UNIQUE container_id)
--
-- BACKUP FIRST: This migration is NOT reversible without backup!
-- ============================================================

-- STEP 0: VERIFICATION
-- Confirm table exists before proceeding
SELECT COUNT(*) as table_exists
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'dynamic_flag_mapping';

-- ============================================================
-- STEP 1: ADD NEW COLUMNS
-- ============================================================

-- Add encrypted_flag column (nullable initially for migration)
ALTER TABLE dynamic_flag_mapping
  ADD COLUMN encrypted_flag TEXT NULL AFTER container_id;

-- Add encryption key ID for future key rotation
ALTER TABLE dynamic_flag_mapping
  ADD COLUMN encryption_key_id INT DEFAULT 1 NOT NULL AFTER encrypted_flag;

-- ============================================================
-- STEP 2: MIGRATE EXISTING DATA
-- ============================================================
--
-- IMPORTANT: This step requires running a Python script to:
-- 1. Read each row's generated_flag (plaintext)
-- 2. Encrypt it using Fernet
-- 3. Store in encrypted_flag column
--
-- Run this Python script BEFORE proceeding to STEP 3:
--
-- ```python
-- from CTFd import create_app
-- from CTFd.plugins.docker_challenges import DynamicFlagMapping
-- from CTFd.plugins.docker_challenges.crypto_utils import encrypt_flag
-- from CTFd.models import db
--
-- app = create_app()
-- with app.app_context():
--     # Migrate all existing flags
--     flags = DynamicFlagMapping.query.filter(
--         DynamicFlagMapping.encrypted_flag.is_(None)
--     ).all()
--
--     print(f"Migrating {len(flags)} flags...")
--
--     for flag_mapping in flags:
--         if flag_mapping.generated_flag:
--             # Encrypt plaintext flag
--             encrypted = encrypt_flag(flag_mapping.generated_flag)
--             flag_mapping.encrypted_flag = encrypted
--             flag_mapping.encryption_key_id = 1
--
--     db.session.commit()
--     print("Migration complete!")
-- ```
--
-- After running the Python script, verify:
SELECT
    COUNT(*) as total_flags,
    SUM(CASE WHEN encrypted_flag IS NOT NULL THEN 1 ELSE 0 END) as encrypted_flags,
    SUM(CASE WHEN encrypted_flag IS NULL THEN 1 ELSE 0 END) as unencrypted_flags
FROM dynamic_flag_mapping;

-- Expected: unencrypted_flags = 0

-- ============================================================
-- STEP 3: ENFORCE NOT NULL ON ENCRYPTED_FLAG
-- ============================================================

-- Make encrypted_flag required
ALTER TABLE dynamic_flag_mapping
  MODIFY encrypted_flag TEXT NOT NULL;

-- ============================================================
-- STEP 4: DROP OLD COLUMNS
-- ============================================================
--
-- Remove all Phase 1 complexity:
-- - State machine (status)
-- - Expiration tracking (valid_until, used_at)
-- - Version tracking (flag_version)
-- - Plaintext storage (generated_flag)
-- - Legacy fields (timestamp, is_active)

-- Drop status ENUM and related columns
ALTER TABLE dynamic_flag_mapping
  DROP COLUMN IF EXISTS status,
  DROP COLUMN IF EXISTS valid_until,
  DROP COLUMN IF EXISTS used_at,
  DROP COLUMN IF EXISTS flag_version,
  DROP COLUMN IF EXISTS generated_flag,
  DROP COLUMN IF EXISTS timestamp,
  DROP COLUMN IF EXISTS is_active;

-- ============================================================
-- STEP 5: VERIFY FINAL SCHEMA
-- ============================================================

-- Expected columns:
-- - id (primary key)
-- - user_id (nullable, indexed)
-- - team_id (nullable, indexed)
-- - challenge_id (not null, indexed)
-- - container_id (not null, unique, indexed)
-- - encrypted_flag (not null)
-- - created_at (not null, indexed)
-- - encryption_key_id (not null, default 1)

DESCRIBE dynamic_flag_mapping;

-- Verify UNIQUE constraint still exists on container_id
SHOW INDEX FROM dynamic_flag_mapping WHERE Column_name = 'container_id';

-- ============================================================
-- STEP 6: VERIFY DATA INTEGRITY
-- ============================================================

-- Check for NULL values in critical columns
SELECT
    COUNT(*) as total_rows,
    SUM(CASE WHEN container_id IS NULL THEN 1 ELSE 0 END) as null_container_ids,
    SUM(CASE WHEN encrypted_flag IS NULL THEN 1 ELSE 0 END) as null_encrypted_flags,
    SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END) as null_created_at
FROM dynamic_flag_mapping;

-- Expected: All NULL counts = 0

-- ============================================================
-- ROLLBACK PLAN (Only works if you have a backup!)
-- ============================================================
--
-- If something goes wrong, restore from backup:
--
-- 1. Stop CTFd:
--    docker compose stop ctfd
--
-- 2. Restore database backup:
--    docker compose exec -T db mysql -u ctfd -pctfd ctfd < backup.sql
--
-- 3. Restart CTFd:
--    docker compose start ctfd
--
-- ============================================================

-- MIGRATION COMPLETE
-- The dynamic_flag_mapping table is now simplified and production-ready.
-- All flags are encrypted at rest.
-- Validation uses constant-time comparison.
-- System is ready for CTFd Whale integration.
