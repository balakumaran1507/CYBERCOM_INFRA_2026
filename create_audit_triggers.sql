-- ============================================================================
-- CYBERCOM Phase 2 - Audit Trail Immutability Triggers
-- ============================================================================
-- Purpose: Enforce database-level immutability on verdict_history table
-- Security: Prevents UPDATE and DELETE operations (INSERT-only enforcement)
-- Reference: Red Team Attack C1 (Verdict Tampering)
-- ============================================================================

-- Use CTFd database
USE ctfd;

-- Change delimiter for trigger creation
DELIMITER $$

-- ============================================================================
-- TRIGGER 1: Prevent UPDATE on verdict_history
-- ============================================================================
-- Blocks any attempt to modify existing audit trail entries
-- Raises MySQL error 45000 with descriptive message
-- ============================================================================
CREATE TRIGGER prevent_verdict_update
BEFORE UPDATE ON phase2_verdict_history
FOR EACH ROW
BEGIN
    -- SECURITY: Audit trail is immutable
    -- Attempting to UPDATE an audit entry violates forensic integrity
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'SECURITY VIOLATION: Verdict history is immutable and cannot be modified. Use INSERT for new verdicts.';
END$$

-- ============================================================================
-- TRIGGER 2: Prevent DELETE on verdict_history
-- ============================================================================
-- Blocks any attempt to remove audit trail entries
-- Raises MySQL error 45000 with descriptive message
-- ============================================================================
CREATE TRIGGER prevent_verdict_delete
BEFORE DELETE ON phase2_verdict_history
FOR EACH ROW
BEGIN
    -- SECURITY: Audit trail is immutable
    -- Attempting to DELETE an audit entry violates forensic integrity
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'SECURITY VIOLATION: Verdict history is immutable and cannot be deleted. Audit trail must be preserved.';
END$$

-- Restore default delimiter
DELIMITER ;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Show created triggers
SHOW TRIGGERS WHERE `Table` = 'phase2_verdict_history';

-- Display trigger details
SELECT
    TRIGGER_NAME,
    EVENT_MANIPULATION,
    EVENT_OBJECT_TABLE,
    ACTION_TIMING,
    ACTION_STATEMENT
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = 'ctfd'
AND EVENT_OBJECT_TABLE = 'phase2_verdict_history';

-- ============================================================================
-- SECURITY NOTES
-- ============================================================================
-- 1. Triggers execute BEFORE operation, preventing mutation entirely
-- 2. SIGNAL SQLSTATE '45000' raises user-defined error
-- 3. Error message includes "SECURITY VIOLATION" for audit logging
-- 4. Triggers are PERSISTENT (survive database restarts)
-- 5. Only database admin (root) can DROP triggers
-- ============================================================================

-- End of script
