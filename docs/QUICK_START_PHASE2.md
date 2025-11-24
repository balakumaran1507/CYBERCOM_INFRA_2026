# Phase 2 Quick Start: Whale Integration

**Status**: 📋 Ready to Begin
**Prerequisites**: ✅ Phase 1 Complete (Flag System v1.0)

---

## Quick Overview

**What we're building:**
- Container lifecycle: Start → Extend → Stop
- Whale API integration (Docker Swarm orchestration)
- Admin UI for container management
- Maintain flag encryption compatibility

**Why Whale:**
- Production-grade orchestration (vs our custom Docker API)
- Auto cleanup and resource limits
- Reverse proxy support (FRP)
- Multi-host scaling (Docker Swarm)

---

## Phase 2 Steps (In Order)

### Step 1: Install Whale (2-4 hours)
```bash
cd /home/kali/CTF/CTFd/CTFd/plugins
git clone https://github.com/frankli0324/ctfd-whale.git whale
cd whale
pip install -r requirements.txt

# Configure Whale
# Visit: http://localhost:8000/plugins/whale/admin/settings
# Set: Docker Swarm URL, timeout (3600s), max containers (1)
```

### Step 2: Create Abstraction Layer (4-6 hours)
```bash
# Create new file:
# CTFd/plugins/docker_challenges/container_manager.py

# Contains:
# - ContainerManager (abstract base class)
# - DockerAPIManager (current implementation)
# - WhaleAPIManager (new Whale API implementation)
# - get_container_manager() factory function
```

### Step 3: Implement WhaleAPIManager (6-8 hours)
- Implement create_container() → POST /ctfd-whale-user/container
- Implement delete_container() → DELETE /ctfd-whale-user/container
- Implement extend_container() → PATCH /ctfd-whale-user/container
- Implement get_container_status() → GET /ctfd-whale-user/container

### Step 4: Update API Endpoints (3-4 hours)
- Update /api/v1/container to use manager
- Add /api/v1/container/extend endpoint
- Add error handling and logging

### Step 5: Update UI (2-3 hours)
- Add "Extend" button to view.js
- Add extend_container() JavaScript function
- Update button styling and icons

### Step 6: Admin Panel (6-8 hours)
- Create admin_containers.html template
- Add /admin/containers page
- Add /api/v1/admin/containers endpoint (list, delete)
- JavaScript for auto-refresh and actions

### Step 7: Testing (8-10 hours)
- Unit tests for WhaleAPIManager
- Integration tests (start, extend, stop)
- Performance tests (< 3s container start)
- Multi-user testing

### Step 8: Documentation (4-6 hours)
- User guide (how to extend containers)
- Admin guide (container management)
- Developer guide (container abstraction)

---

## Configuration Required

**Environment Variables:**
```bash
# Add to docker-compose.yml or .env
WHALE_ENABLED=true
WHALE_API_URL=http://localhost:8000
```

**Whale Settings** (via admin panel):
- Docker Swarm endpoint
- Auto cleanup timeout: 3600s (1 hour)
- Max containers per user: 1
- Max renewal count: 5
- Renewal cooldown: 300s (5 min)

---

## Testing Checklist

**Before going live:**
- [ ] Whale installed and configured
- [ ] Test container creation (Whale API)
- [ ] Test container deletion (Whale API)
- [ ] Test container extend (Whale API)
- [ ] Test flag generation (encrypted)
- [ ] Test flag validation (constant-time)
- [ ] Test CASCADE delete (container → flag)
- [ ] Test admin panel (view all containers)
- [ ] Test multi-user (no cross-contamination)
- [ ] Performance test (< 3s start time)

---

## Rollback Plan

**If something breaks:**
1. Set `WHALE_ENABLED=false` in environment
2. Restart CTFd: `docker compose restart ctfd`
3. System reverts to Docker API (Phase 1 implementation)
4. All data intact (same database tables)

**No data migration needed** - both systems use same DockerChallengeTracker and DynamicFlagMapping tables.

---

## File Structure After Phase 2

```
CTFd/plugins/docker_challenges/
├── __init__.py                    (updated: use manager)
├── container_manager.py           (NEW: abstraction layer)
├── crypto_utils.py                (unchanged from Phase 1)
├── models.py                      (unchanged)
├── assets/
│   └── view.js                    (updated: add extend button)
├── templates/
│   ├── view.html                  (unchanged)
│   └── admin_containers.html      (NEW: admin panel)
└── tests/
    └── test_container_manager.py  (NEW: unit tests)

CTFd/plugins/whale/                (NEW: Whale plugin)
└── (Whale plugin files)

docs/
├── CYBERCOM_FLAG_SYSTEM_V1_SUMMARY.md  (Phase 1 complete)
├── PHASE_2_WHALE_INTEGRATION_ROADMAP.md (Phase 2 plan)
└── QUICK_START_PHASE2.md              (this file)
```

---

## Key Code Patterns

**Using Container Manager:**
```python
from CTFd.plugins.docker_challenges.container_manager import get_container_manager

# Get appropriate manager (Whale or Docker API)
manager = get_container_manager()

# Create container
result = manager.create_container(
    challenge_id=5,
    user_id=1,
    team_id=None
)

# Extend container
manager.extend_container(challenge_id=5)

# Delete container
manager.delete_container(container_id='abc123')
```

**Whale API Calls:**
```python
# Create
POST /api/v1/ctfd-whale-user/container?challenge_id=5
Response: {success: true, data: {container_id, host, ports}}

# Delete
DELETE /api/v1/ctfd-whale-user/container
Response: {success: true, message: "Removed"}

# Extend
PATCH /api/v1/ctfd-whale-user/container?challenge_id=5
Response: {success: true, message: "Renewed"}

# Status
GET /api/v1/ctfd-whale-user/container?challenge_id=5
Response: {success: true, data: {instance_id, host, ports, remaining_time}}
```

---

## Timeline

**Full-time (8 hours/day):**
- Week 1: Steps 1-4 (Whale setup + API implementation)
- Week 2: Steps 5-8 (UI + Admin + Testing + Docs)

**Part-time (4 hours/day):**
- Week 1-2: Steps 1-4
- Week 3-4: Steps 5-8

**Total Effort**: 35-49 hours

---

## Success Criteria

**Phase 2 is complete when:**
- ✅ User can click "Start" → container created via Whale
- ✅ User can click "Extend" → container lifetime extended
- ✅ User can click "Stop" → container removed via Whale
- ✅ Admin can view all containers in admin panel
- ✅ Admin can stop any user's container
- ✅ Flags still work (encrypted, validated correctly)
- ✅ No cross-user flag leakage
- ✅ Performance targets met (< 3s start time)
- ✅ All tests passing
- ✅ Documentation complete

---

## Common Issues & Solutions

**Issue**: Whale API connection refused
- **Solution**: Check `WHALE_API_URL` in config, verify Whale plugin installed

**Issue**: Container creation fails with "max containers exceeded"
- **Solution**: Check Whale settings, increase max_containers or delete old containers

**Issue**: Flag validation fails after Whale integration
- **Solution**: Verify container_id matches between Whale and DynamicFlagMapping

**Issue**: Extend button doesn't work
- **Solution**: Check browser console, verify /api/v1/container/extend endpoint exists

**Issue**: Admin panel shows no containers
- **Solution**: Check DockerChallengeTracker table has data, verify API endpoint returns JSON

---

## Next Immediate Action

```bash
# Start Phase 2.1: Install Whale
cd /home/kali/CTF/CTFd/CTFd/plugins
git clone https://github.com/frankli0324/ctfd-whale.git whale
cd whale
cat README.md  # Read Whale documentation
```

**Ready to begin!** 🚀

---

**Document Version**: 1.0
**Created**: 2025-11-23
**Phase 1 Snapshot**: `ca9d0ca8` (git), `cybercom-ctf-flag-v1` (docker)
