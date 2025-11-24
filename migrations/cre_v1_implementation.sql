-- ============================================================
-- CYBERCOM RUNTIME ENGINE (CRE) v1.0 - Database Migration
-- ============================================================
--
-- This migration adds container lifecycle management to CTFd.
--
-- Changes:
-- 1. Fix DockerChallengeTracker data types (user_id/team_id VARCHAR → INT)
-- 2. Add extension tracking fields (extension_count, created_at, last_extended_at)
-- 3. Add audit log table (container_events)
-- 4. Add optional runtime policies table (container_runtime_policies)
-- 5. Add performance indexes
--
-- BACKUP FIRST: mysqldump -u ctfd -pctfd ctfd > backup_pre_cre_$(date +%Y%m%d).sql
-- ============================================================

-- STEP 0: VERIFICATION
-- Confirm tables exist before proceeding
SELECT COUNT(*) as tracker_exists
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'docker_challenge_tracker';

-- ============================================================
-- STEP 1: FIX DATA TYPE ISSUES (CRITICAL)
-- ============================================================
--
-- Current: user_id VARCHAR(64), team_id VARCHAR(64)
-- Problem: These should be INT to match foreign keys in users/teams tables
-- Impact: Can't add proper foreign key constraints, queries are slower
--
-- We need to convert existing string IDs to integers.
-- Assumption: Existing IDs are numeric strings (e.g., "1", "42", etc.)
--
-- DANGER: If any IDs are non-numeric, this will fail!
-- Verify first:

SELECT user_id, team_id
FROM docker_challenge_tracker
WHERE (user_id IS NOT NULL AND user_id NOT REGEXP '^[0-9]+$')
   OR (team_id IS NOT NULL AND team_id NOT REGEXP '^[0-9]+$');

-- Expected result: 0 rows (all IDs are numeric)
-- If you see rows: STOP and investigate!

-- Convert VARCHAR to INT
ALTER TABLE docker_challenge_tracker
  MODIFY user_id INT NULL,
  MODIFY team_id INT NULL;

-- Add proper foreign keys (with CASCADE for cleanup)
ALTER TABLE docker_challenge_tracker
  ADD CONSTRAINT fk_tracker_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE;

ALTER TABLE docker_challenge_tracker
  ADD CONSTRAINT fk_tracker_team
    FOREIGN KEY (team_id) REFERENCES teams(id)
    ON DELETE CASCADE;

-- Verify
SHOW CREATE TABLE docker_challenge_tracker;

-- ============================================================
-- STEP 2: ADD CRE LIFECYCLE FIELDS
-- ============================================================

-- Add extension tracking
ALTER TABLE docker_challenge_tracker
  ADD COLUMN extension_count INT NOT NULL DEFAULT 0
    COMMENT 'Number of times container was extended (max 5)'
    AFTER revert_time;

-- Add creation timestamp (better than unix timestamp)
ALTER TABLE docker_challenge_tracker
  ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    COMMENT 'Container creation timestamp'
    AFTER extension_count;

-- Add last extension timestamp (for rate limiting)
ALTER TABLE docker_challenge_tracker
  ADD COLUMN last_extended_at DATETIME NULL
    COMMENT 'When was last extension applied'
    AFTER created_at;

-- Add constraint: extension_count must be non-negative
ALTER TABLE docker_challenge_tracker
  ADD CONSTRAINT chk_extension_count_positive
    CHECK (extension_count >= 0);

-- Verify new schema
DESCRIBE docker_challenge_tracker;

-- ============================================================
-- STEP 3: CREATE AUDIT LOG TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS container_events (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Who performed the action (NULL if system/cleanup worker)
    user_id INT NULL,

    -- Which challenge
    challenge_id INT NULL,

    -- Which container (may be NULL if creation failed)
    container_id VARCHAR(128) NULL,

    -- What happened
    action VARCHAR(50) NOT NULL
        COMMENT 'Action: created, extended, stopped_manual, stopped_auto, failed_*',

    -- When it happened
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Additional context (flexible JSON)
    -- Note: Cannot use 'metadata' (reserved by SQLAlchemy)
    event_metadata JSON NULL
        COMMENT 'Context: {old_expiry, new_expiry, extension_number, error, etc}',

    -- Indexes for common queries
    INDEX idx_events_user_time (user_id, timestamp),
    INDEX idx_events_challenge_time (challenge_id, timestamp),
    INDEX idx_events_container_time (container_id, timestamp),
    INDEX idx_events_action_time (action, timestamp),

    -- Foreign keys (SET NULL instead of CASCADE to preserve audit trail)
    CONSTRAINT fk_events_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_events_challenge
        FOREIGN KEY (challenge_id) REFERENCES challenges(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='CRE audit log - tracks all container lifecycle events';

-- Verify
DESCRIBE container_events;

-- ============================================================
-- STEP 4: CREATE RUNTIME POLICIES TABLE (OPTIONAL)
-- ============================================================
--
-- Allows per-challenge runtime configuration.
-- If no policy exists for a challenge, CRE uses defaults.
--

CREATE TABLE IF NOT EXISTS container_runtime_policies (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Which challenge (NULL = global default)
    challenge_id INT NULL UNIQUE,

    -- Runtime configuration (seconds)
    base_runtime_seconds INT NOT NULL DEFAULT 900
        COMMENT 'Initial container lifetime (default 15 min)',

    extension_increment_seconds INT NOT NULL DEFAULT 900
        COMMENT 'Time added per extension (default 15 min)',

    max_extensions INT NOT NULL DEFAULT 5
        COMMENT 'Maximum number of extensions allowed',

    max_lifetime_seconds INT NOT NULL DEFAULT 5400
        COMMENT 'Hard cap on total lifetime (default 90 min)',

    -- Metadata
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

    -- Foreign keys
    CONSTRAINT fk_policy_challenge
        FOREIGN KEY (challenge_id) REFERENCES challenges(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_policy_creator
        FOREIGN KEY (created_by) REFERENCES users(id)
        ON DELETE SET NULL

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Per-challenge runtime policies (optional overrides)';

-- Verify
DESCRIBE container_runtime_policies;

-- ============================================================
-- STEP 5: ADD PERFORMANCE INDEXES
-- ============================================================

-- Optimize cleanup worker query (finds expired containers)
CREATE INDEX idx_tracker_expiry_lookup
  ON docker_challenge_tracker(revert_time)
  COMMENT 'Fast lookup for cleanup worker';

-- Optimize user container lookup (for extend/stop operations)
CREATE INDEX idx_tracker_user_challenge
  ON docker_challenge_tracker(user_id, challenge)
  COMMENT 'Fast user + challenge lookup';

CREATE INDEX idx_tracker_team_challenge
  ON docker_challenge_tracker(team_id, challenge)
  COMMENT 'Fast team + challenge lookup (teams mode)';

-- Verify indexes
SHOW INDEX FROM docker_challenge_tracker;

-- ============================================================================
-- STEP 6: DATA MIGRATION (Initialize existing containers)
-- ============================================================================
--
-- Set extension_count = 0 for all existing containers
-- (already done by DEFAULT 0, but explicit for clarity)
--
-- Set created_at = FROM_UNIXTIME(timestamp) for existing containers
-- (converts unix timestamp to datetime)

UPDATE docker_challenge_tracker
SET
    extension_count = 0,
    created_at = FROM_UNIXTIME(timestamp),
    last_extended_at = NULL
WHERE created_at IS NULL OR created_at = '0000-00-00 00:00:00';

-- Verify
SELECT
    COUNT(*) as total_containers,
    SUM(CASE WHEN extension_count = 0 THEN 1 ELSE 0 END) as zero_extensions,
    SUM(CASE WHEN created_at IS NOT NULL THEN 1 ELSE 0 END) as has_created_at
FROM docker_challenge_tracker;

-- Expected: total_containers = zero_extensions = has_created_at

-- ============================================================================
-- STEP 7: VERIFY SCHEMA INTEGRITY
-- ============================================================================

-- Check docker_challenge_tracker schema
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'docker_challenge_tracker'
ORDER BY ORDINAL_POSITION;

-- Expected columns:
-- - id (INT, PK)
-- - team_id (INT, NULL, FK to teams)
-- - user_id (INT, NULL, FK to users)
-- - docker_image (VARCHAR)
-- - timestamp (INT)
-- - revert_time (INT)
-- - extension_count (INT, DEFAULT 0)
-- - created_at (DATETIME)
-- - last_extended_at (DATETIME, NULL)
-- - instance_id (VARCHAR)
-- - ports (VARCHAR)
-- - host (VARCHAR)
-- - challenge (VARCHAR)

-- Check foreign keys
SELECT
    CONSTRAINT_NAME,
    TABLE_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('docker_challenge_tracker', 'container_events', 'container_runtime_policies')
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- Check indexes
SELECT
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX,
    INDEX_COMMENT
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'docker_challenge_tracker'
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- ============================================================================
-- STEP 8: FINAL VALIDATION
-- ============================================================================

-- Test query: Find containers expiring in next 5 minutes
SELECT
    id,
    user_id,
    team_id,
    challenge,
    instance_id,
    FROM_UNIXTIME(revert_time) as expires_at,
    extension_count,
    created_at
FROM docker_challenge_tracker
WHERE revert_time BETWEEN UNIX_TIMESTAMP() AND (UNIX_TIMESTAMP() + 300)
ORDER BY revert_time;

-- Test query: Audit trail for a specific user
SELECT
    action,
    timestamp,
    challenge_id,
    container_id,
    metadata
FROM container_events
WHERE user_id = 1  -- Replace with actual user ID
ORDER BY timestamp DESC
LIMIT 10;

-- ============================================================================
-- ROLLBACK PLAN (Only works if you have a backup!)
-- ============================================================================
--
-- If something goes wrong, restore from backup:
--
-- 1. Stop CTFd:
--    docker compose stop ctfd
--
-- 2. Restore database backup:
--    docker compose exec -T db mysql -u ctfd -pctfd ctfd < backup_pre_cre_$(date +%Y%m%d).sql
--
-- 3. Restart CTFd:
--    docker compose start ctfd
--
-- 4. Verify rollback:
--    docker compose exec -T db mysql -u ctfd -pctfd ctfd -e "DESCRIBE docker_challenge_tracker;"
--    # Should show old schema (user_id/team_id as VARCHAR, no extension_count)
--
-- ============================================================================

-- MIGRATION COMPLETE
-- CRE v1.0 database schema is ready.
-- Next steps:
-- 1. Restart CTFd to load new code
-- 2. Test extend functionality
-- 3. Verify cleanup worker is running
