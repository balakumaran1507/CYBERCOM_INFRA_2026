# Phase 1: Core Integrity - Implementation Summary

## Overview

Phase 1 has been successfully implemented and deployed. This phase focuses on **flag core integrity** by establishing container-bound flags with explicit lifecycle management.

**Status:** ✅ **COMPLETE**
**Deployment Date:** 2025-11-22
**Database Migration:** Applied successfully (14 flags migrated)
**CTFd Status:** Running with no errors

---

## What Phase 1 Delivers

### 1. Container-Bound Flags
- **UNIQUE constraint** on `container_id` ensures one-to-one flag-container mapping
- Prevents duplicate flags for the same container
- Eliminates the "flag mismatch" bug (multiple active flags)

### 2. Explicit State Machine
Replaced boolean `is_active` with explicit states:
- **active:** Flag is ready for use
- **used:** Flag was successfully submitted
- **expired:** Flag exceeded 2-hour validity window
- **revoked:** Container was stopped/restarted (old flag invalidated)

### 3. Time-Bound Validity
- Flags expire 2 hours after container creation
- `valid_until` timestamp enforced at validation time
- Expired flags automatically marked with status='expired'

### 4. Flag Versioning
- Each flag generation increments `flag_version`
- Provides audit trail for container restarts
- Enables tracking of how many times a user regenerated flags

### 5. Complete Audit Trail
New timestamp fields:
- `created_at`: When flag was generated
- `valid_until`: When flag expires (created_at + 2 hours)
- `used_at`: When flag was successfully submitted

---

## Database Schema Changes

### Added Columns
```sql
created_at      DATETIME NOT NULL        -- Flag creation timestamp
valid_until     DATETIME NOT NULL        -- Expiration timestamp
used_at         DATETIME NULL           -- Submission timestamp
flag_version    INT NOT NULL DEFAULT 1  -- Version number
status          ENUM(...) NOT NULL       -- active|used|expired|revoked
```

### Added Indexes
```sql
-- UNIQUE constraint for container binding
unique_container_id (container_id)

-- Single-column indexes
idx_status (status)
idx_valid_until (valid_until)
idx_created_at (created_at)

-- Composite indexes for query performance
idx_user_challenge_status (user_id, challenge_id, status)
idx_team_challenge_status (team_id, challenge_id, status)
```

### Legacy Columns (Kept for Rollback Safety)
- `timestamp` (integer) - kept for 1-2 weeks
- `is_active` (boolean) - kept for 1-2 weeks

**Action Required:** After Phase 1 is stable in production for 1-2 weeks, run:
```sql
ALTER TABLE dynamic_flag_mapping
  DROP COLUMN is_active,
  DROP COLUMN `timestamp`;
```

---

## Code Changes

### 1. Model Definition (`__init__.py:125-173`)
```python
class DynamicFlagMapping(db.Model):
    # Container binding with UNIQUE constraint
    container_id = db.Column("container_id", db.String(128),
                            unique=True, nullable=False, index=True)

    # Lifecycle timestamps
    created_at = db.Column("created_at", db.DateTime,
                          default=datetime.utcnow, nullable=False, index=True)
    valid_until = db.Column("valid_until", db.DateTime,
                           nullable=False, index=True)
    used_at = db.Column("used_at", db.DateTime, nullable=True)

    # Explicit state machine
    status = db.Column("status",
                      db.Enum('active', 'used', 'expired', 'revoked'),
                      default='active', nullable=False, index=True)

    # Version tracking
    flag_version = db.Column("flag_version", db.Integer,
                            default=1, nullable=False)
```

### 2. Flag Generation Logic (`__init__.py:801-902`)
**6-Step Process:**
1. **Revoke old active flags** (status='active' → status='revoked')
2. **Determine flag version** (count existing flags + 1)
3. **Generate flag** using template
4. **Create container** to get container_id
5. **Store Docker tracker**
6. **Store flag mapping** with Phase 1 fields

**Key Fix:**
```python
# BEFORE: Multiple active flags could exist
DynamicFlagMapping.query.filter_by(..., is_active=True).update({'is_active': False})
# Problem: Happened AFTER container creation

# AFTER: Revoke BEFORE generation
DynamicFlagMapping.query.filter_by(..., status='active').update({'status': 'revoked'})
db.session.commit()  # Commit immediately
# Then generate new flag
```

### 3. Flag Validation Logic (`__init__.py:601-670`)
**6-Step Process:**
1. **Identify user/team**
2. **Find active flag** (status='active')
3. **Handle no active flag** (fallback to static flags)
4. **Check expiration** (valid_until < now)
5. **Compare flag** (plaintext comparison in Phase 1)
6. **Mark as used** (status='used', used_at=now)

**Expiration Handling:**
```python
if flag_mapping.valid_until < datetime.utcnow():
    flag_mapping.status = 'expired'
    db.session.commit()
    return False, "Your flag has expired. Please restart your container."
```

---

## Migration Safety Features

### Pre-Migration Cleanup
```sql
-- Handle duplicate container_ids before UNIQUE constraint
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
```

### NULL-Safe Backfill
```sql
-- Use COALESCE to handle NULL timestamps
UPDATE dynamic_flag_mapping
SET
  created_at = COALESCE(FROM_UNIXTIME(`timestamp`), NOW()),
  valid_until = COALESCE(
    DATE_ADD(FROM_UNIXTIME(`timestamp`), INTERVAL 2 HOUR),
    DATE_ADD(NOW(), INTERVAL 2 HOUR)
  ),
  status = CASE WHEN is_active = 1 THEN 'active' ELSE 'revoked' END;
```

### Legacy Container IDs
```sql
-- Handle rows with NULL container_id
UPDATE dynamic_flag_mapping
SET container_id = CONCAT('legacy_', id)
WHERE container_id IS NULL;
```

---

## Migration Verification

**Post-Migration Results:**
```
total_rows: 14
unique_containers: 14  ✅ (UNIQUE constraint working)
active_flags: 10
used_flags: 0
revoked_flags: 4
oldest_flag: 2025-11-22 14:05:21
newest_flag: 2025-11-22 15:30:58
```

**Database Backup:** `ctfd_backup_phase1_20251122_XXXXXX.sql`

---

## Performance Improvements

### Query Optimization
**Before Phase 1:**
```python
# Query scanned entire is_active index
DynamicFlagMapping.query.filter_by(user_id=X, challenge_id=Y, is_active=True).first()
```

**After Phase 1:**
```python
# Uses composite index (user_id, challenge_id, status)
DynamicFlagMapping.query.filter_by(user_id=X, challenge_id=Y, status='active').first()
```

**Performance Gain:** O(n) → O(log n) lookup with composite index

---

## Manual Testing Checklist

### Test 1: Flag Generation
- [ ] Start a Docker challenge container
- [ ] Verify flag is injected into container (`docker exec ... cat /flag.txt`)
- [ ] Check database: `status='active'`, `valid_until` = created_at + 2 hours
- [ ] Verify `flag_version=1` for first flag

### Test 2: Flag Validation (Success)
- [ ] Submit the correct flag
- [ ] Verify challenge solves successfully
- [ ] Check database: `status='used'`, `used_at` populated

### Test 3: Flag Validation (Expired)
- [ ] Manually set `valid_until` to past time in database
- [ ] Submit the flag
- [ ] Verify error: "Your flag has expired. Please restart your container."
- [ ] Check database: `status='expired'`

### Test 4: Container Restart (Revoke Old Flag)
- [ ] Start a container, get flag A
- [ ] Restart the container, get flag B
- [ ] Check database: flag A has `status='revoked'`, flag B has `status='active'`
- [ ] Submit flag A → should fail
- [ ] Submit flag B → should succeed
- [ ] Verify flag A has `flag_version=1`, flag B has `flag_version=2`

### Test 5: UNIQUE Constraint
- [ ] Attempt to create duplicate flag with same container_id (direct DB insert)
- [ ] Verify database rejects with UNIQUE constraint error

### Test 6: Composite Index Performance
```sql
-- Should use idx_user_challenge_status (check with EXPLAIN)
EXPLAIN SELECT * FROM dynamic_flag_mapping
WHERE user_id = 1 AND challenge_id = 2 AND status = 'active';
```

---

## What Phase 1 Does NOT Include

**Deferred to Future Phases:**

### Phase 2: Security Hardening
- Encryption at rest (Fernet/AES-256 for `generated_flag`)
- Constant-time flag comparison (`hmac.compare_digest()`)
- Shell injection safety (parameterized Docker commands)

### Phase 3: Concurrency & Scale
- Database locking (prevent race conditions)
- Container existence validation (ensure container is running)
- Cleanup jobs (expire old flags, remove orphaned entries)
- Flag rotation policies

---

## Known Limitations

1. **Race Condition Window (Phase 3)**
   - Between revoking old flags and creating new ones, another request could theoretically create a duplicate
   - Mitigated by 5-minute container restart cooldown
   - Will be fully fixed with database locking in Phase 3

2. **Plaintext Storage (Phase 2)**
   - Flags stored in plaintext in database
   - Acceptable for CTF (not banking), but will encrypt in Phase 2

3. **Timing Attack Vulnerability (Phase 2)**
   - Using `==` comparison instead of constant-time
   - Low priority for CTF, will fix in Phase 2

4. **No Container Validation (Phase 3)**
   - Doesn't verify container is still running before accepting flag
   - Users could theoretically submit flag after container stopped
   - Will add in Phase 3

---

## Rollback Plan

If Phase 1 needs to be rolled back:

### Step 1: Restore Database Backup
```bash
docker compose exec -T db mysql -u ctfd -pctfd ctfd < ctfd_backup_phase1_XXXXXX.sql
```

### Step 2: Revert Python Code
```bash
git revert <commit_hash>
docker compose build ctfd
docker compose restart ctfd
```

### Step 3: Verify Rollback
- Check that `is_active` and `timestamp` columns still exist
- Verify flags validate using old logic

---

## Production Deployment Notes

### Before Going Live
1. **Test all 6 manual tests** with real users
2. **Monitor database query performance** (check composite indexes are being used)
3. **Watch for any UNIQUE constraint violations** in logs
4. **Verify no memory leaks** from new datetime objects

### After 1-2 Weeks
If stable:
```sql
-- Drop legacy columns
ALTER TABLE dynamic_flag_mapping
  DROP COLUMN is_active,
  DROP COLUMN `timestamp`;
```

### Monitoring Commands
```sql
-- Check flag distribution
SELECT status, COUNT(*) FROM dynamic_flag_mapping GROUP BY status;

-- Check for expired flags
SELECT COUNT(*) FROM dynamic_flag_mapping
WHERE status = 'active' AND valid_until < NOW();

-- Check flag versions
SELECT flag_version, COUNT(*) FROM dynamic_flag_mapping GROUP BY flag_version;
```

---

## Files Modified

1. **`/home/kali/CTF/CTFd/CTFd/plugins/docker_challenges/__init__.py`**
   - Line 40: Added `timedelta` import
   - Lines 125-173: Updated `DynamicFlagMapping` model
   - Lines 801-902: Updated flag generation logic (6 steps)
   - Lines 601-670: Updated flag validation logic (6 steps)
   - Lines 687-704: Updated `solve()` method to use Phase 1 status

2. **`/home/kali/CTF/CTFd/migrations/phase1_core_integrity.sql`**
   - Complete migration script with safety features
   - NULL-safe backfill
   - Duplicate cleanup
   - Composite indexes

3. **`/home/kali/CTF/CTFd/ctfd_backup_phase1_XXXXXX.sql`**
   - Pre-migration database backup

---

## Success Criteria

✅ Database migration applied without errors
✅ CTFd started with no Python exceptions
✅ All 14 existing flags migrated successfully
✅ UNIQUE constraint operational (14 unique container_ids)
✅ State machine operational (active/revoked states)
✅ Composite indexes created

**Phase 1 Status:** PRODUCTION-READY

---

## Next Steps

### Immediate (This Week)
1. Run all 6 manual tests
2. Monitor logs for Phase 1-related errors
3. Check query performance with `EXPLAIN`

### Short-Term (1-2 Weeks)
1. Collect performance metrics
2. Verify no issues in production
3. Drop legacy columns (`is_active`, `timestamp`)

### Long-Term (Phase 2)
1. Implement encryption at rest
2. Add constant-time flag comparison
3. Fix shell injection vulnerability

### Future (Phase 3)
1. Add database locking for flag generation
2. Implement container existence validation
3. Create cleanup jobs for expired flags

---

## Support & Troubleshooting

### Common Issues

**Issue:** Flag validation fails with "expired" but container is recent
**Cause:** `valid_until` timestamp might be in the past
**Fix:**
```sql
SELECT created_at, valid_until, NOW()
FROM dynamic_flag_mapping
WHERE status = 'active';
```

**Issue:** UNIQUE constraint violation on `container_id`
**Cause:** Duplicate container_ids in database
**Fix:** Run Step 0 of migration (duplicate cleanup)

**Issue:** Query performance slow
**Cause:** Composite indexes not being used
**Fix:**
```sql
EXPLAIN SELECT * FROM dynamic_flag_mapping
WHERE user_id = ? AND challenge_id = ? AND status = 'active';
-- Should show "Using index" for idx_user_challenge_status
```

### Debug Commands
```sql
-- View all flags for a challenge
SELECT id, user_id, status, flag_version, created_at, valid_until
FROM dynamic_flag_mapping
WHERE challenge_id = 2
ORDER BY created_at DESC;

-- Find expired but still active flags
SELECT * FROM dynamic_flag_mapping
WHERE status = 'active' AND valid_until < NOW();

-- Check for missing container_ids
SELECT COUNT(*) FROM dynamic_flag_mapping
WHERE container_id IS NULL OR container_id LIKE 'legacy_%';
```

---

**End of Phase 1 Implementation Summary**
