# 🚀 CYBERCOM PHASE 2 - DEPLOYMENT GUIDE

**Version**: 2.0.0-MVP
**Status**: READY FOR TESTING
**Date**: 2025-11-23

---

## 📋 OVERVIEW

Phase 2 Intelligence Layer adds three production-grade capabilities to CYBERCOM CTF:

1. **First Blood Prestige System** - Race-safe first solve tracking with prestige leaderboard
2. **Flag Sharing Detection** - Intelligence-only pattern detection (admin-reviewed, NO auto-punishment)
3. **Challenge Health Monitoring** - Hourly quality snapshots

**Performance**: <20ms overhead on submission flow (optimized with Redis caching)

---

## 🏗️ ARCHITECTURE

```
CTFd/plugins/phase2/
├── __init__.py       # Plugin registration
├── config.py         # Feature flags
├── models.py         # 3 new database tables
├── hooks.py          # SQLAlchemy event hooks (first blood)
├── workers.py        # APScheduler background workers
├── api.py            # REST API endpoints
├── detection.py      # Pattern detection algorithms
└── utils.py          # Helper functions
```

**Database Tables** (all prefixed with `phase2_`):
- `phase2_first_blood_prestige` - First solve records
- `phase2_flag_sharing_suspicion` - Detection results
- `phase2_challenge_health_snapshot` - Hourly metrics

**NO modifications to core CTFd tables** (schema-safe design)

---

## ⚠️ CRITICAL PREREQUISITE

### Add `user_agent` Column to Submissions Table

Phase 2 flag sharing detection requires storing user-agent strings.

**Option 1: Create Alembic Migration (Recommended)**

```bash
# 1. Create migration
cd /home/kali/CTF/CTFd
docker compose exec ctfd flask db migrate -m "Add user_agent to submissions for Phase 2"

# 2. Edit the migration file to add:
# op.add_column('submissions', sa.Column('user_agent', sa.String(512), nullable=True))
# op.create_index('idx_submissions_user_agent', 'submissions', ['user_agent'], mysql_length=255)

# 3. Apply migration
docker compose exec ctfd flask db upgrade
```

**Option 2: Manual SQL (Quick Test)**

```sql
-- Connect to database
docker compose exec db mysql -u ctfd -p ctfd

-- Add column
ALTER TABLE submissions ADD COLUMN user_agent VARCHAR(512) DEFAULT NULL;
CREATE INDEX idx_submissions_user_agent ON submissions(user_agent(255));
```

**Option 3: Modify Submissions Model Directly**

Edit `/CTFd/models/__init__.py` around line 871:

```python
class Submissions(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(...)
    user_id = db.Column(...)
    team_id = db.Column(...)
    ip = db.Column(db.String(46))
    provided = db.Column(db.Text)
    type = db.Column(db.String(32))
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # ✅ ADD THIS LINE
    user_agent = db.Column(db.String(512), nullable=True, index=True)
```

Then create tables:
```bash
docker compose exec ctfd python
>>> from CTFd import create_app
>>> app = create_app()
>>> with app.app_context():
...     from CTFd.models import db
...     db.create_all()
```

---

## 📦 INSTALLATION

### Step 1: Verify Plugin Files

```bash
ls -la /home/kali/CTF/CTFd/CTFd/plugins/phase2/

# Should show:
# __init__.py
# api.py
# config.py
# detection.py
# hooks.py
# models.py
# utils.py
# workers.py
```

### Step 2: Enable Phase 2

**Option A: Environment Variables (Recommended)**

Edit `docker-compose.yml`:

```yaml
services:
  ctfd:
    environment:
      - PHASE2_ENABLED=1
      - PHASE2_FIRST_BLOOD_ENABLED=1
      - PHASE2_HEALTH_ENABLED=1
      - PHASE2_SUSPICION_ENABLED=1
      - PHASE2_SUSPICION_THRESHOLD=0.75
      - PHASE2_RETENTION_DAYS=90
```

**Option B: Runtime (Testing)**

```bash
docker compose exec ctfd bash
export PHASE2_ENABLED=1
export PHASE2_FIRST_BLOOD_ENABLED=1
# ... etc
```

### Step 3: Restart CTFd

```bash
docker compose restart ctfd
```

### Step 4: Verify Initialization

```bash
docker compose logs ctfd | grep PHASE2

# Should show:
# [PHASE2] 🚀 Initializing CYBERCOM Phase 2 Intelligence Layer...
# [PHASE2] ✅ Database tables created/verified
# [PHASE2] ✅ API namespace registered (/api/v1/phase2)
# [PHASE2] ✅ SQLAlchemy event hooks registered
# [PHASE2] ✅ Background workers started
# [PHASE2] 🎯 Phase 2 Intelligence Layer initialized successfully
```

---

## 🧪 TESTING

### Test 1: System Status

```bash
curl http://localhost:8000/api/v1/phase2/status

# Expected:
# {
#   "success": true,
#   "data": {
#     "enabled": true,
#     "features": {...},
#     "version": "2.0.0-MVP"
#   }
# }
```

### Test 2: First Blood Detection

1. Create a test challenge
2. Have User A solve it
3. Check database:

```sql
SELECT * FROM phase2_first_blood_prestige;
-- Should show User A's first blood record
```

4. Have User B solve same challenge
5. Check database again - should NOT create duplicate

### Test 3: Challenge Health

Wait 1 hour (or reduce `PHASE2_HEALTH_INTERVAL_HOURS` for testing):

```bash
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/v1/phase2/challenge_health

# Should return health snapshots for all challenges
```

### Test 4: Flag Sharing Detection

1. Have User A submit wrong answer from IP 1.2.3.4
2. Within 60 seconds, have User B submit same wrong answer from 1.2.3.4
3. Wait 30 seconds for analytics worker
4. Check database:

```sql
SELECT * FROM phase2_flag_sharing_suspicion;
-- Should show suspicion record with confidence >= 0.75
```

---

## 🔧 CONFIGURATION

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `PHASE2_ENABLED` | `1` | Master switch (0=disable all) |
| `PHASE2_FIRST_BLOOD_ENABLED` | `1` | Enable first blood system |
| `PHASE2_HEALTH_ENABLED` | `1` | Enable health monitoring |
| `PHASE2_SUSPICION_ENABLED` | `1` | Enable flag sharing detection |
| `PHASE2_SUSPICION_THRESHOLD` | `0.75` | Confidence threshold (0.0-1.0) |
| `PHASE2_RETENTION_DAYS` | `90` | Data retention period |
| `PHASE2_HEALTH_INTERVAL_HOURS` | `1` | Health check frequency |
| `PHASE2_ANALYTICS_INTERVAL_SECONDS` | `30` | Analytics worker frequency |

### Performance Tuning

**For high-traffic events** (>1000 users):
- Increase `PHASE2_ANALYTICS_INTERVAL_SECONDS` to 60+
- Increase `PHASE2_HEALTH_INTERVAL_HOURS` to 2+
- Consider disabling suspicion detection during peak hours

**For small events** (<100 users):
- Decrease intervals for more responsive detection
- Enable debug logging

---

## 📊 API ENDPOINTS

### Public Endpoints

**GET `/api/v1/phase2/status`**
- System status and configuration
- No auth required

### Admin-Only Endpoints

**GET `/api/v1/phase2/first_blood_leaderboard`**
- First blood prestige leaderboard
- Query params: `limit` (default 100)

**GET `/api/v1/phase2/challenge_health`**
- Health status for all challenges
- Query params: `status` (HEALTHY, UNDERPERFORMING, BROKEN)

**GET `/api/v1/phase2/challenge_health/<id>`**
- Health history for specific challenge
- Query params: `limit` (default 24)

**GET `/api/v1/phase2/suspicious_activity`**
- Flag sharing suspicions
- Query params: `status`, `risk_level`, `limit`

**PUT `/api/v1/phase2/suspicious_activity/<id>/review`**
- Submit admin verdict
- Body: `{"verdict": "innocent|suspicious|confirmed"}`

---

## 🚨 TROUBLESHOOTING

### Issue: "Phase 2 is DISABLED"

**Cause**: `PHASE2_ENABLED=0` or not set

**Fix**:
```bash
docker compose exec ctfd bash
echo $PHASE2_ENABLED  # Check value
export PHASE2_ENABLED=1
# Restart container
```

### Issue: "Database initialization failed"

**Cause**: Tables already exist or migration conflict

**Fix**:
```sql
-- Drop Phase 2 tables and recreate
DROP TABLE IF EXISTS phase2_challenge_health_snapshot;
DROP TABLE IF EXISTS phase2_flag_sharing_suspicion;
DROP TABLE IF EXISTS phase2_first_blood_prestige;

-- Restart CTFd
```

### Issue: "Worker startup failed"

**Cause**: Flask-APScheduler not installed

**Fix**:
```bash
docker compose exec ctfd pip install Flask-APScheduler==1.11.0
docker compose restart ctfd
```

### Issue: First blood not detecting

**Checks**:
1. Is `PHASE2_FIRST_BLOOD_ENABLED=1`?
2. Check logs: `docker compose logs ctfd | grep "FIRST BLOOD"`
3. Check Redis: `docker compose exec cache redis-cli KEYS "phase2:*"`
4. Verify event hook registered: Look for "Registered first_blood hook" in startup logs

### Issue: Suspicion detection not working

**Checks**:
1. Is `PHASE2_SUSPICION_ENABLED=1`?
2. Is user_agent column added to submissions table?
3. Check analytics worker logs: `docker compose logs ctfd | grep "ANALYTICS"`
4. Verify submissions have user_agent data: `SELECT user_agent FROM submissions LIMIT 10;`

---

## 🔒 SECURITY CONSIDERATIONS

### Data Privacy

- **User-agent storage**: May contain sensitive browser info
- **IP addresses**: Already stored by CTFd, Phase 2 just analyzes them
- **Suspicion records**: Only accessible to admins

### False Positives

- **Same IP detection**: May flag users behind NAT/shared networks
- **Duplicate wrong answers**: May flag common mistakes (e.g., "flag{test}")
- **Similar user-agents**: May flag default browsers (e.g., all Chrome users)

**Mitigation**: Human review required (NO auto-punishment)

### Rate Limiting

Phase 2 does NOT implement rate limiting. Use CTFd's built-in rate limiting:
- `incorrect_submissions_per_min` (default: 10)

---

## 📈 MONITORING

### Key Metrics

```bash
# First blood count
SELECT COUNT(*) FROM phase2_first_blood_prestige;

# Suspicions by risk level
SELECT risk_level, COUNT(*) FROM phase2_flag_sharing_suspicion GROUP BY risk_level;

# Unhealthy challenges
SELECT challenge_id, status, health_score
FROM phase2_challenge_health_snapshot
WHERE status != 'HEALTHY'
ORDER BY health_score ASC;

# Pending admin reviews
SELECT COUNT(*) FROM phase2_flag_sharing_suspicion WHERE admin_verdict IS NULL;
```

### Performance Monitoring

```bash
# Check worker status
docker compose logs ctfd | grep "PHASE2 WORKERS"

# Check event hook performance (should be <20ms)
docker compose logs ctfd | grep "FIRST BLOOD" | tail -20

# Check analytics worker performance
docker compose logs ctfd | grep "ANALYTICS" | tail -20
```

---

## 🎯 ROLLBACK PROCEDURE

If Phase 2 causes issues:

### Quick Disable (No Data Loss)

```bash
# Set env var
export PHASE2_ENABLED=0

# Restart
docker compose restart ctfd

# Verify
docker compose logs ctfd | grep "Phase 2 is DISABLED"
```

### Full Removal

```sql
-- 1. Drop tables
DROP TABLE IF EXISTS phase2_challenge_health_snapshot;
DROP TABLE IF EXISTS phase2_flag_sharing_suspicion;
DROP TABLE IF EXISTS phase2_first_blood_prestige;

-- 2. Remove user_agent column (optional)
ALTER TABLE submissions DROP COLUMN user_agent;
```

```bash
# 3. Delete plugin files
rm -rf /home/kali/CTF/CTFd/CTFd/plugins/phase2/

# 4. Restart
docker compose restart ctfd
```

---

## 🎓 BEST PRACTICES

### For Competition Organizers

1. **Pre-event**: Run Phase 2 for 24h before competition to verify stability
2. **During event**: Monitor suspicion dashboard every 2-4 hours
3. **Post-event**: Make first blood leaderboard public
4. **Review suspicions**: Within 7 days of event end

### For Developers

1. **Testing**: Always test in staging environment first
2. **Logs**: Monitor `[PHASE2]` logs during deployment
3. **Performance**: Check submission latency before/after enabling
4. **Backups**: Backup database before enabling Phase 2

---

## 📞 SUPPORT

**Issues**: Check logs first (`docker compose logs ctfd | grep PHASE2`)
**Questions**: Review this guide and architecture report
**Bugs**: Document exact reproduction steps + logs

---

**END OF DEPLOYMENT GUIDE**
