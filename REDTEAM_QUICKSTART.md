# RED TEAM QUICK START GUIDE

## 📁 Arsenal Deployed

**Total Attack Vectors**: 7 sophisticated penetration tests
**Total Code**: ~56KB of adversarial security testing
**Coverage**: 5 security domains + 1 multi-vector APT simulation

---

## 🎯 Attack Files

### Category A: First Blood Exploitation
```bash
redteam_a1_timestamp_collision.py    # 4.9KB - Microsecond timestamp collision
redteam_a2_distributed_race.py       # 6.9KB - 100 concurrent thread race
```

### Category B: GDPR Consent Bypass
```bash
redteam_b1_consent_race.py           # 6.7KB - TOCTOU vulnerability test
```

### Category C: Audit Trail Manipulation
```bash
redteam_c1_verdict_tampering.py      # 7.3KB - Concurrent verdict modification
```

### Category D: Redis Cache Integrity
```bash
redteam_d1_hmac_forgery.py           # 7.4KB - HMAC signature forgery attempts
```

### Category E: Worker Resource Exhaustion
```bash
redteam_e1_worker_dos.py             # 7.9KB - DoS via submission flood
```

### Category F: Multi-Vector Combination
```bash
redteam_f1_combined_attack.py        # 11KB  - APT-style coordinated attack
```

### Automation
```bash
redteam_execute_all.sh               # 4.8KB - Execute all attacks sequentially
```

---

## ⚡ Quick Execution

### Run Single Attack
```bash
cd /home/kali/CTF/CTFd
docker compose exec ctfd python redteam_a1_timestamp_collision.py
```

### Run All Attacks (Interactive)
```bash
./redteam_execute_all.sh
```

### Run All Attacks (Batch)
```bash
./redteam_execute_all.sh < /dev/null 2>&1 | tee redteam_full_output.log
```

---

## 🔍 Post-Attack Analysis

### Check System Logs
```bash
# Phase 2 security warnings
docker compose logs ctfd | grep -i 'phase2.*security\|phase2.*warning'

# First blood events
docker compose logs ctfd | grep -i 'first blood'

# GDPR consent events
docker compose logs ctfd | grep -i 'gdpr'

# Audit trail events
docker compose logs ctfd | grep -i 'audit'
```

### Verify Database Integrity
```bash
# Connect to database
docker compose exec db mysql -u ctfd -pctfd ctfd

# Check for duplicate first bloods (should be 0)
SELECT challenge_id, COUNT(*) as cnt
FROM phase2_first_blood_prestige
GROUP BY challenge_id
HAVING cnt > 1;

# Check audit trail (should be INSERT-only)
SELECT COUNT(*) FROM phase2_verdict_history;

# Check consent records
SELECT user_id, consented, consented_at, withdrawn_at
FROM phase2_user_consent;
```

### Check Redis Cache
```bash
# List all Phase 2 cache keys
docker compose exec cache redis-cli KEYS "phase2:*"

# Check specific first blood cache
docker compose exec cache redis-cli GET "phase2:first_blood_claimed:2"
```

---

## 🎯 Attack Targets by Challenge ID

Each attack uses specific challenge IDs to avoid conflicts:

| Attack | Challenge ID | Purpose |
|--------|-------------|---------|
| A1 - Timestamp Collision | 3 | Timestamp tie-breaker test |
| A2 - Distributed Race | 4 | 100-thread concurrency |
| B1 - Consent Race | N/A | Uses users 2,3,5 |
| C1 - Verdict Tamper | 5 | Audit trail test |
| D1 - HMAC Forgery | N/A | Cache integrity |
| E1 - Worker DoS | 6 | 10,000 submission flood |
| F1 - Combined | 7 | Multi-vector APT |

---

## 📊 Expected Results Summary

### ✅ Successful Defenses (Should Pass)

- **A1**: Only 1 first blood despite timestamp collision
- **A2**: Only 1 first blood from 100 concurrent solves
- **B1**: No suspicions created without consent
- **C1**: All 50 verdicts recorded in audit trail
- **D1**: All HMAC forgery attempts rejected
- **E1**: Worker caps at 5000 submissions
- **F1**: All 4 attack stages blocked

### ⚠️ Known Warnings (Expected Behavior)

```
[PHASE2 FIRST BLOOD WARNING] Failed to acquire advisory lock
→ Expected: Advisory locks may timeout on some MySQL versions
→ Impact: NONE (UNIQUE constraint provides fallback)
→ Status: ACCEPTABLE
```

### ❌ Critical Failures (Require Investigation)

```
Multiple first blood records for same challenge
→ Indicates: UNIQUE constraint failure or race condition exploit
→ Action: IMMEDIATE investigation required

Suspicions created for non-consented users
→ Indicates: GDPR consent bypass (TOCTOU vulnerability)
→ Action: HIGH priority fix needed

Lost audit trail entries
→ Indicates: Concurrent INSERT failures
→ Action: HIGH priority investigation
```

---

## 🛡️ Vulnerability Severity Guide

### CRITICAL (Fix Immediately)
- GDPR consent bypass
- Audit trail tampering
- Multiple first bloods per challenge

### HIGH (Fix Before Production)
- Direct database UPDATE on audit trail possible
- Advisory lock failures causing duplicates

### MEDIUM (Monitor & Plan Fix)
- Advisory lock timeout warnings
- Performance degradation under load

### LOW (Document & Accept)
- Timestamp tie-breaker bias (user_id)
- Theoretical timing attack vectors

---

## 🔧 Quick Fixes

### Fix Advisory Lock Timeouts
```sql
-- Check MySQL lock timeout
SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';

-- Increase if needed (default: 50 seconds)
SET GLOBAL innodb_lock_wait_timeout = 120;
```

### Add Audit Trail Protection
```sql
-- Prevent UPDATE
CREATE TRIGGER prevent_verdict_update
BEFORE UPDATE ON phase2_verdict_history
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Immutable audit trail';
END;

-- Prevent DELETE
CREATE TRIGGER prevent_verdict_delete
BEFORE DELETE ON phase2_verdict_history
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Immutable audit trail';
END;
```

### Harden Consent Checking
```python
# Use transaction-level locking
with db.session.begin_nested():
    consent = UserConsent.query.filter_by(
        user_id=user_id
    ).with_for_update().first()

    if not consent or not consent.consented:
        return None

    # Create suspicion in same transaction
    suspicion = FlagSharingSuspicion(...)
    db.session.add(suspicion)
```

---

## 📋 Checklist for Production Deployment

- [ ] All 7 red team attacks executed
- [ ] No critical vulnerabilities discovered
- [ ] Advisory lock warnings investigated
- [ ] Database triggers added for audit trail
- [ ] Consent checking uses transaction locks
- [ ] HMAC secret rotated and secured
- [ ] Worker DoS limits verified
- [ ] Monitoring/alerting configured
- [ ] Security hardening report reviewed
- [ ] Penetration test results documented

---

## 📞 Next Steps After Red Team Assessment

1. **Review Full Report**: `cat REDTEAM_ASSESSMENT_REPORT.md`

2. **Implement HIGH Priority Fixes**:
   - Transaction-level consent checking
   - Database audit trail triggers

3. **Run Verification Tests**:
   ```bash
   # Re-run critical attacks after fixes
   docker compose exec ctfd python redteam_b1_consent_race.py
   docker compose exec ctfd python redteam_c1_verdict_tampering.py
   ```

4. **Production Monitoring**:
   - Set up alerts for [PHASE2 SECURITY WARNING]
   - Monitor advisory lock failures
   - Track first blood duplicate attempts

5. **Continuous Security**:
   - Run red team suite monthly
   - Add new attack vectors as discovered
   - Maintain adversarial mindset

---

## 🚨 Emergency Response

If attack succeeds in production:

1. **Contain**: Stop affected service
   ```bash
   docker compose stop ctfd
   ```

2. **Investigate**: Check logs and database
   ```bash
   docker compose logs ctfd > incident_logs.txt
   docker compose exec db mysqldump ctfd > incident_db_dump.sql
   ```

3. **Fix**: Apply emergency patch

4. **Verify**: Re-run red team tests

5. **Document**: Update incident log

---

**Classification**: CONFIDENTIAL
**Prepared By**: Adversarial Security Engine
**Status**: READY FOR EXECUTION

---
