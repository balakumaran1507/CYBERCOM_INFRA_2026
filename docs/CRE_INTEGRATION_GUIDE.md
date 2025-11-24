# CRE Integration Guide

**Purpose**: Wire CYBERCOM Runtime Engine into existing docker_challenges plugin without breaking functionality.

---

## Integration Points

### 1. Update `__init__.py` Imports

**Location**: Top of file (after existing imports)

```python
# === CRE IMPORTS (ADD THESE) ===
from .models_cre import ContainerEvent, ContainerRuntimePolicy
from .cre import cre, RuntimePolicy
from .cleanup_worker import cleanup_worker
```

### 2. Start Cleanup Worker

**Location**: `load(app)` function

```python
def load(app):
    """Plugin initialization"""
    # ... existing code ...

    # === START CRE CLEANUP WORKER ===
    cleanup_worker.start()
    print("[CRE] ✅ Cleanup worker started")

    # Register blueprints...
    app.register_blueprint(blueprint)
```

### 3. Update Container Creation (Enhanced Runtime Tracking)

**Location**: Around line 860 where `DockerChallengeTracker` is created

**BEFORE:**
```python
entry = DockerChallengeTracker(
    team_id=session.id if is_teams_mode() else None,
    user_id=session.id if not is_teams_mode() else None,
    docker_image=container,
    timestamp=unix_time(datetime.utcnow()),
    revert_time=unix_time(datetime.utcnow()) + 300,  # ← 5 minutes (OLD)
    instance_id=container_id,
    ports=','.join([p[0]['HostPort'] for p in ports]),
    host=str(docker.hostname).split(':')[0],
    challenge=challenge
)
```

**AFTER:**
```python
# Get runtime policy for this challenge
policy = RuntimePolicy.from_challenge(challenge_id)

entry = DockerChallengeTracker(
    team_id=session.id if is_teams_mode() else None,
    user_id=session.id if not is_teams_mode() else None,
    docker_image=container,
    timestamp=unix_time(datetime.utcnow()),
    revert_time=unix_time(datetime.utcnow()) + policy.base_runtime_seconds,  # ← 15 minutes (CRE)
    instance_id=container_id,
    ports=','.join([p[0]['HostPort'] for p in ports]),
    host=str(docker.hostname).split(':')[0],
    challenge=challenge,
    # === CRE FIELDS ===
    extension_count=0,
    created_at=datetime.utcnow(),
    last_extended_at=None
)
```

### 4. Add Audit Logging to Container Creation

**Location**: After `db.session.commit()` at end of container creation

```python
db.session.commit()

# === CRE AUDIT LOG ===
try:
    event = ContainerEvent(
        user_id=session.id if not is_teams_mode() else None,
        challenge_id=challenge_id,
        container_id=container_id,
        action="created",
        timestamp=datetime.utcnow(),
        metadata={
            "docker_image": container,
            "base_runtime": policy.base_runtime_seconds,
            "expiry_time": entry.revert_time
        }
    )
    db.session.add(event)
    db.session.commit()
except Exception as e:
    print(f"[CRE ERROR] Failed to log creation event: {e}")

return
```

### 5. Add API Endpoint for Extension

**Location**: Add new route in `blueprint` section (around line 950)

```python
@blueprint.route("/api/v1/container/extend", methods=["POST"])
@authed_only
def extend_container_endpoint():
    """
    Extend container lifetime.

    Request JSON:
        {
            "challenge_id": 5
        }

    Response JSON:
        {
            "success": true,
            "message": "Container extended by 15 minutes (extension 1/5)"
        }

    Errors:
        - 400: Missing challenge_id
        - 404: No active container
        - 403: Max extensions reached
        - 500: Internal error
    """
    from CTFd.utils.user import get_current_user
    from CTFd.utils.modes import is_teams_mode

    # Parse request
    data = request.get_json()
    if not data or 'challenge_id' not in data:
        return jsonify({
            'success': False,
            'message': 'challenge_id required'
        }), 400

    challenge_id = data['challenge_id']

    # Validate challenge_id is integer
    try:
        challenge_id = int(challenge_id)
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'message': 'Invalid challenge_id'
        }), 400

    # Get current user/team
    user = get_current_user()
    team_id = user.team_id if is_teams_mode() else None

    # Call CRE
    success, message = cre.extend_instance(
        user_id=user.id,
        challenge_id=challenge_id,
        team_id=team_id
    )

    status_code = 200 if success else 400
    return jsonify({
        'success': success,
        'message': message
    }), status_code
```

### 6. Add Status Endpoint (Optional - for UI polling)

**Location**: Same section as extend endpoint

```python
@blueprint.route("/api/v1/container/status", methods=["GET"])
@authed_only
def container_status_endpoint():
    """
    Get container status (for UI updates).

    Query params:
        challenge_id: int

    Response:
        {
            "active": true,
            "container_id": "abc123...",
            "remaining_seconds": 450,
            "extension_count": 2,
            "max_extensions": 5
        }
    """
    from CTFd.utils.user import get_current_user
    from CTFd.utils.modes import is_teams_mode

    challenge_id = request.args.get('challenge_id', type=int)
    if not challenge_id:
        return jsonify({'success': False, 'message': 'challenge_id required'}), 400

    user = get_current_user()
    team_id = user.team_id if is_teams_mode() else None

    status = cre.get_instance_status(
        user_id=user.id,
        challenge_id=challenge_id,
        team_id=team_id
    )

    if not status:
        return jsonify({'active': False}), 200

    return jsonify(status), 200
```

### 7. Rate Limiting (Security Enhancement)

**Location**: Before API endpoint handlers

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Apply to CTFd app
limiter.init_app(current_app)
```

**Apply to extend endpoint:**

```python
@blueprint.route("/api/v1/container/extend", methods=["POST"])
@limiter.limit("10 per minute")  # ← Prevent extension spam
@authed_only
def extend_container_endpoint():
    ...
```

---

## UI Integration (Frontend)

### Update `view.js` for Extend Button

**Location**: `assets/view.js` around line 89 (where Revert/Stop buttons are)

**BEFORE:**
```javascript
'<a onclick="start_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
'<small style="color:white;"><i class="fas fa-redo"></i> Revert</small></a> '+
'<a onclick="stop_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
'<small style="color:white;"><i class="fas fa-stop"></i> Stop</small></a>'
```

**AFTER:**
```javascript
// Extend button (only show if extensions available)
var extendBtn = '';
if (item.extension_count < 5) {
    extendBtn = '<a onclick="extend_container(' + CTFd._internal.challenge.data.id + ');" class="btn btn-success">' +
                '<small style="color:white;"><i class="fas fa-clock"></i> Extend (+15 min)</small></a> ';
}

// Revert and Stop buttons
'<div>' +
    extendBtn +
    '<a onclick="start_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-redo"></i> Revert</small></a> '+
    '<a onclick="stop_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-stop"></i> Stop</small></a>' +
'</div>'
```

**Add extend_container function:**

```javascript
function extend_container(challenge_id) {
    CTFd.fetch("/api/v1/container/extend", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            challenge_id: challenge_id
        })
    })
    .then(function (response) {
        return response.json().then(function (json) {
            if (response.ok) {
                updateWarningModal({
                    title: "Success!",
                    warningText: json.message,
                    buttonText: "Close",
                    onClose: function () {
                        get_docker_status(CTFd._internal.challenge.data.docker_image);
                    }
                });
            } else {
                throw new Error(json.message || 'Failed to extend container');
            }
        });
    })
    .catch(function (error) {
        updateWarningModal({
            title: "Error",
            warningText: error.message,
            buttonText: "Close"
        });
    });
}
```

---

## Testing Checklist

### Pre-Deployment Tests

- [ ] Database migration completes without errors
- [ ] user_id/team_id converted from VARCHAR to INT
- [ ] Foreign keys created successfully
- [ ] Indexes created successfully
- [ ] Cleanup worker starts on plugin load
- [ ] Extend endpoint returns 200 on success
- [ ] Extend endpoint returns 400 on invalid input
- [ ] Extend endpoint returns 403 on max extensions

### Functional Tests

- [ ] Create container → extension_count = 0, created_at set
- [ ] Extend container → extension_count++, revert_time += 900
- [ ] Extend 5 times → 6th attempt returns "Max extensions reached"
- [ ] Container expires → cleanup worker deletes it
- [ ] Container deleted → flag deleted (CASCADE)
- [ ] Audit log records all actions

### Security Tests

- [ ] User A cannot extend User B's container
- [ ] Team member can extend team container
- [ ] Non-team member cannot extend team container
- [ ] Rate limiting prevents spam (11th request in 1 min blocked)

### Performance Tests

- [ ] Extension query takes < 50ms (row lock)
- [ ] Cleanup worker handles 100 expirations in < 30s
- [ ] No database deadlocks under concurrent extension requests

---

## Deployment Procedure

### Step 1: Backup

```bash
# Stop CTFd
docker compose stop ctfd

# Backup database
docker compose exec -T db mysqldump -u ctfd -pctfd ctfd > backup_pre_cre_$(date +%Y%m%d_%H%M%S).sql

# Backup code
cp -r CTFd/plugins/docker_challenges CTFd/plugins/docker_challenges.backup
```

### Step 2: Apply Migration

```bash
# Start database
docker compose start db

# Apply SQL migration
docker compose exec -T db mysql -u ctfd -pctfd ctfd < migrations/cre_v1_implementation.sql

# Verify
docker compose exec -T db mysql -u ctfd -pctfd ctfd -e "DESCRIBE docker_challenge_tracker;"
```

### Step 3: Deploy Code

```bash
# Code is already updated (models_cre.py, cre.py, cleanup_worker.py created)
# Just need to integrate into __init__.py as per guide above

# Rebuild CTFd
docker compose build ctfd

# Start CTFd
docker compose up -d ctfd
```

### Step 4: Verify

```bash
# Check logs
docker compose logs ctfd --tail=50 | grep CRE

# Expected:
# [CRE] ✅ Cleanup worker started (interval=60s, thread=CRE-Cleanup)

# Test extend endpoint
curl -X POST http://localhost:8000/api/v1/container/extend \
  -H "Content-Type: application/json" \
  -d '{"challenge_id": 1}' \
  -b "session=<your-session-cookie>"
```

---

## Rollback Procedure

If anything goes wrong:

```bash
# Stop CTFd
docker compose stop ctfd

# Restore database
docker compose exec -T db mysql -u ctfd -pctfd ctfd < backup_pre_cre_<timestamp>.sql

# Restore code
rm -rf CTFd/plugins/docker_challenges
mv CTFd/plugins/docker_challenges.backup CTFd/plugins/docker_challenges

# Restart
docker compose up -d
```

---

## Success Criteria

CRE is successfully deployed when:

✅ Cleanup worker runs without errors
✅ Containers have 15-minute base runtime (not 5 minutes)
✅ Extension button appears in UI
✅ Extension works (adds 15 minutes)
✅ Max 5 extensions enforced
✅ Container events logged to database
✅ Expired containers auto-deleted
✅ No errors in CTFd logs