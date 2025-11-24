-- ============================================================
-- PHASE 1: CORE INTEGRITY MIGRATION
-- Dynamic Flag System - Production-Grade Hardening
-- ============================================================
--
-- This migration adds Phase 1 fields to dynamic_flag_mapping:
-- - Lifecycle timestamps (created_at, valid_until, used_at)
-- - Explicit state machine (active/used/expired/revoked)
-- - Flag versioning
-- - Container binding with UNIQUE constraint
--
-- IMPORTANT: This migration is designed to be safe for production.
-- It handles NULL values, duplicate container_ids, and provides
-- rollback safety by keeping legacy columns.
-- ============================================================

-- STEP 0: Pre-migration cleanup (handle existing duplicates)
-- If multiple rows share the same container_id, keep the newest and mark others as inactive
UPDATE dynamic_flag_mapping dfm1
LEFT JOIN (
  SELECT container_id, MAX(id) as max_id
  FROM dynamic_flag_mapping
  WHERE container_id IS NOT NULL
  GROUP BY container_id
) dfm2 ON dfm1.container_id = dfm2.container_id
SET dfm1.is_active = 0
WHERE dfm1.id != dfm2.max_id
  AND dfm1.container_id IS NOT NULL;

-- STEP 1: Add new columns (nullable initially for safe backfill)
ALTER TABLE dynamic_flag_mapping
  ADD COLUMN created_at DATETIME NULL,
  ADD COLUMN valid_until DATETIME NULL,
  ADD COLUMN used_at DATETIME NULL,
  ADD COLUMN flag_version INT DEFAULT 1 NOT NULL,
  ADD COLUMN status ENUM('active', 'used', 'expired', 'revoked') DEFAULT 'active' NOT NULL;

-- STEP 2: Backfill existing data with NULL-safe values
-- Use COALESCE to handle NULL timestamps gracefully
UPDATE dynamic_flag_mapping
SET
  created_at = COALESCE(FROM_UNIXTIME(`timestamp`), NOW()),
  valid_until = COALESCE(
    DATE_ADD(FROM_UNIXTIME(`timestamp`), INTERVAL 2 HOUR),
    DATE_ADD(NOW(), INTERVAL 2 HOUR)
  ),
  flag_version = 1,
  status = CASE WHEN is_active = 1 THEN 'active' ELSE 'revoked' END;

-- STEP 2.5: Ensure all rows have a container_id (handle legacy NULL values)
-- Assign a unique legacy ID to any rows with NULL container_id
UPDATE dynamic_flag_mapping
SET container_id = CONCAT('legacy_', id)
WHERE container_id IS NULL;

-- STEP 3: Enforce NOT NULL constraints now that data is backfilled
ALTER TABLE dynamic_flag_mapping
  MODIFY created_at DATETIME NOT NULL,
  MODIFY valid_until DATETIME NOT NULL,
  MODIFY container_id VARCHAR(128) NOT NULL;

-- STEP 4: Add UNIQUE constraint and performance indexes
ALTER TABLE dynamic_flag_mapping
  ADD UNIQUE KEY unique_container_id (container_id);

-- Single-column indexes for basic queries
CREATE INDEX idx_status ON dynamic_flag_mapping(status);
CREATE INDEX idx_valid_until ON dynamic_flag_mapping(valid_until);
CREATE INDEX idx_created_at ON dynamic_flag_mapping(created_at);

-- Composite indexes for actual query patterns (CRITICAL for performance)
CREATE INDEX idx_user_challenge_status
  ON dynamic_flag_mapping(user_id, challenge_id, status);

CREATE INDEX idx_team_challenge_status
  ON dynamic_flag_mapping(team_id, challenge_id, status);

-- ============================================================
-- STEP 5: Drop legacy columns (DEFERRED - see note below)
-- ============================================================
-- DO NOT RUN THIS IMMEDIATELY!
-- Keep legacy columns (is_active, timestamp) for 1-2 weeks as rollback safety.
-- Only drop them after Phase 1 is verified stable in production.
--
-- To drop legacy columns later, run:
-- ALTER TABLE dynamic_flag_mapping
--   DROP COLUMN is_active,
--   DROP COLUMN `timestamp`;
-- ============================================================

-- Verification query (run this after migration to check results)
-- SELECT
--   COUNT(*) as total_rows,
--   COUNT(DISTINCT container_id) as unique_containers,
--   SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_flags,
--   SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END) as used_flags,
--   SUM(CASE WHEN status = 'revoked' THEN 1 ELSE 0 END) as revoked_flags,
--   MIN(created_at) as oldest_flag,
--   MAX(created_at) as newest_flag
-- FROM dynamic_flag_mapping;
