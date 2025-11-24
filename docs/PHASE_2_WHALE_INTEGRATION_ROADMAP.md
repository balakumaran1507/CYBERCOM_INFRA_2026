# CYBERCOM CTF - Phase 2: Whale Integration Roadmap

**Project**: CYBERCOM CTF (Commercial-Grade CTF Platform)
**Phase**: CTFd Whale Integration
**Status**: 📋 PLANNING
**Previous Phase**: Flag System v1.0 (✅ COMPLETE)

---

## Executive Summary

This phase integrates CTFd Whale container orchestration system to replace the current direct Docker API implementation. Whale provides production-grade container lifecycle management with Docker Swarm support, automatic cleanup, and advanced networking via FRP (Fast Reverse Proxy).

**Objectives:**
1. Replace direct Docker API calls with Whale API
2. Implement container lifecycle: Start, Stop, Extend
3. Add admin UI controls for container management
4. Maintain flag system compatibility (container_id binding)
5. Improve scalability and resource management

---

## 1. Current State Analysis

### 1.1 Current Docker Implementation

**Architecture:**
```
CTFd Plugin (docker_challenges)
    ↓
Direct Docker API (HTTP/HTTPS + TLS)
    ↓
Docker Engine (single host)
    ↓
Container Creation (create + start)
```

**Key Functions:**
- `create_container(docker, image, team, portbl, flag)` - Lines 399-479
- `delete_container(docker, instance_id)` - Lines 482-485
- API Endpoint: `/api/v1/container` - Handles start/stop
- UI Functions: `start_container()`, `stop_container()` - `assets/view.js`

**Current Flow (Start Container):**
```
User clicks "Start Docker Instance"
    ↓
JavaScript: start_container(container_name)
    ↓
API: GET /api/v1/container?name=X&challenge=Y&challenge_id=Z
    ↓
Backend: create_container() → Docker API
    ↓
Store: DockerChallengeTracker + DynamicFlagMapping
    ↓
Response: Container info (host, ports, instance_id)
    ↓
UI: Display connection info + countdown timer
```

**Current Flow (Stop Container):**
```
User clicks "Stop"
    ↓
JavaScript: stop_container(container_name)
    ↓
API: GET /api/v1/container?stopcontainer=True
    ↓
Backend: delete_container() → Docker API DELETE
    ↓
Database: CASCADE delete DockerChallengeTracker + DynamicFlagMapping
    ↓
Response: Success message
    ↓
UI: Refresh to show "Start" button
```

### 1.2 Current Limitations

**Scalability:**
- Single Docker host (no load balancing)
- Manual port management (30000-60000 range)
- No automatic cleanup on timeout

**Resource Management:**
- No container renewal/extension
- No max container limits per user
- No automatic revert after timeout

**Networking:**
- Direct port exposure (security concern)
- No reverse proxy support
- No dynamic DNS/subdomain mapping

**Administration:**
- No admin panel for container management
- No visibility into all running containers
- No bulk operations (stop all, cleanup)

---

## 2. Target State: Whale Integration

### 2.1 Whale Architecture

```
CTFd Plugin (docker_challenges)
    ↓
Whale API Layer (abstraction)
    ↓
Whale Backend (container orchestration)
    ↓
Docker Swarm (multi-host support)
    ↓
Containers + FRP (reverse proxy)
```

**Whale Components:**
1. **API Layer**: RESTful endpoints for container CRUD
2. **Control Utilities**: Container lifecycle management
3. **Docker Swarm**: Distributed container orchestration
4. **FRP Client**: Reverse proxy for network isolation
5. **Database Models**: Container tracking (Whale maintains its own tables)

### 2.2 Whale API Endpoints

**User Endpoints** (`/ctfd-whale-user/container`):
- **POST** - Create/Start container
  - Params: `challenge_id`
  - Returns: `{success, message, container_info}`
  - Constraints: Max containers per user, frequency limit

- **DELETE** - Stop/Remove container
  - Returns: `{success, message}`
  - Constraints: Frequency limit (5 min cooldown)

- **PATCH** - Renew/Extend container
  - Params: `challenge_id`
  - Returns: `{success, message}`
  - Constraints: Max renewal count

- **GET** - Get container status
  - Params: `challenge_id`
  - Returns: `{uuid, host, port, remaining_time}`

**Admin Endpoints** (`/ctfd-whale-admin/container`):
- **GET** - List all containers (paginated)
  - Params: `page`, `per_page`
  - Returns: `{containers[], total, pages}`

- **PATCH** - Admin renew container
  - Params: `user_id`
  - Returns: `{success, message}`

- **DELETE** - Admin remove container
  - Params: `user_id`
  - Returns: `{success, message}`

### 2.3 Integration Benefits

**Scalability:**
- ✅ Docker Swarm support (multi-host orchestration)
- ✅ Automatic load balancing across nodes
- ✅ Built-in container limits and quotas

**Resource Management:**
- ✅ Automatic container timeout and cleanup
- ✅ Container renewal/extension (extend time before timeout)
- ✅ Max renewal count enforcement

**Networking:**
- ✅ FRP reverse proxy (no direct port exposure)
- ✅ Dynamic subdomain mapping (container1.ctf.example.com)
- ✅ Network isolation and security

**Administration:**
- ✅ Admin panel for container visibility
- ✅ Bulk operations (stop all, cleanup dead containers)
- ✅ Container statistics and monitoring

---

## 3. Implementation Plan

### Phase 2.1: Whale Setup and Configuration

**Goal**: Install and configure Whale plugin alongside docker_challenges

**Tasks:**

1. **Install Whale Plugin**
   ```bash
   cd /home/kali/CTF/CTFd/CTFd/plugins
   git clone https://github.com/frankli0324/ctfd-whale.git whale
   cd whale
   pip install -r requirements.txt
   ```

2. **Configure Whale Settings**
   - Access: `/plugins/whale/admin/settings`
   - Configure:
     - Docker Swarm connection
     - FRP server settings (if using reverse proxy)
     - Auto cleanup timeout (default: 3600s = 1 hour)
     - Max containers per user (default: 1)
     - Max renewal count (default: 5)
     - Renewal cooldown (default: 300s = 5 min)

3. **Database Migrations**
   - Whale creates its own tables:
     - `whale_containers` - Active container tracking
     - `whale_container_profiles` - Challenge-specific config
   - No changes to our tables (DockerChallengeTracker, DynamicFlagMapping remain)

4. **Test Whale Independently**
   - Create test challenge with Whale
   - Verify container creation/deletion
   - Verify automatic cleanup
   - Verify renewal functionality

**Files Created:**
- None (Whale is separate plugin)

**Estimated Time**: 2-4 hours

---

### Phase 2.2: API Abstraction Layer

**Goal**: Create abstraction layer to support both Docker API and Whale API

**Why Abstraction?**
- Gradual migration (run both systems simultaneously)
- Fallback mechanism (if Whale fails, use Docker API)
- Clean separation of concerns
- Easy testing and validation

**Architecture:**
```python
# CTFd/plugins/docker_challenges/container_manager.py

class ContainerManager:
    """Abstract interface for container management"""

    def create_container(self, challenge_id, user_id, team_id):
        """Create and start a container"""
        pass

    def delete_container(self, container_id):
        """Stop and remove a container"""
        pass

    def extend_container(self, container_id):
        """Extend container lifetime"""
        pass

    def get_container_status(self, container_id):
        """Get container info (host, port, remaining_time)"""
        pass


class DockerAPIManager(ContainerManager):
    """Legacy Docker API implementation (current)"""

    def create_container(self, challenge_id, user_id, team_id):
        # Use existing create_container() function
        pass


class WhaleAPIManager(ContainerManager):
    """Whale API implementation (new)"""

    def create_container(self, challenge_id, user_id, team_id):
        # Call Whale API: POST /ctfd-whale-user/container
        pass

    def delete_container(self, container_id):
        # Call Whale API: DELETE /ctfd-whale-user/container
        pass

    def extend_container(self, container_id):
        # Call Whale API: PATCH /ctfd-whale-user/container
        pass

    def get_container_status(self, container_id):
        # Call Whale API: GET /ctfd-whale-user/container
        pass


# Factory pattern for manager selection
def get_container_manager():
    """Returns appropriate container manager based on config"""
    use_whale = current_app.config.get('WHALE_ENABLED', False)

    if use_whale:
        return WhaleAPIManager()
    else:
        return DockerAPIManager()
```

**Implementation Steps:**

1. **Create Abstraction Layer**
   - File: `CTFd/plugins/docker_challenges/container_manager.py`
   - Classes: `ContainerManager`, `DockerAPIManager`, `WhaleAPIManager`
   - Config: Add `WHALE_ENABLED` flag to `CTFd/config.py`

2. **Update Existing Code**
   - Replace direct `create_container()` calls with `manager.create_container()`
   - Replace direct `delete_container()` calls with `manager.delete_container()`
   - Update API endpoint to use manager

3. **Add Configuration Toggle**
   ```python
   # CTFd/config.py
   WHALE_ENABLED = os.environ.get('WHALE_ENABLED', 'false').lower() == 'true'
   ```

4. **Testing**
   - Test with `WHALE_ENABLED=false` (should work as before)
   - Test with `WHALE_ENABLED=true` (should use Whale)

**Files Modified:**
- `CTFd/plugins/docker_challenges/__init__.py` (update to use manager)
- `CTFd/config.py` (add WHALE_ENABLED flag)

**Files Created:**
- `CTFd/plugins/docker_challenges/container_manager.py` (abstraction layer)

**Estimated Time**: 4-6 hours

---

### Phase 2.3: Whale API Implementation

**Goal**: Implement WhaleAPIManager with all required methods

**Implementation:**

```python
# CTFd/plugins/docker_challenges/container_manager.py

import requests
from flask import current_app
from CTFd.models import db
from CTFd.utils.user import get_current_user
from .models import DockerChallengeTracker, DynamicFlagMapping, DockerConfig
from .crypto_utils import encrypt_flag
from .flag_utils import generate_dynamic_flag
from datetime import datetime


class WhaleAPIManager(ContainerManager):
    """Whale API implementation for container management"""

    def __init__(self):
        self.base_url = current_app.config.get('WHALE_API_URL', 'http://localhost:8000')
        self.session = requests.Session()

    def _get_headers(self):
        """Get headers with user authentication"""
        # Whale uses CTFd session authentication
        return {
            'Content-Type': 'application/json'
        }

    def create_container(self, challenge_id, user_id, team_id):
        """
        Create container via Whale API

        Steps:
        1. Call Whale API to create container
        2. Generate dynamic flag
        3. Store DockerChallengeTracker
        4. Store encrypted DynamicFlagMapping
        5. Return container info
        """
        from CTFd.utils.modes import get_model
        from CTFd.plugins.docker_challenges import DockerChallenge

        # Get challenge info
        docker_challenge = DockerChallenge.query.filter_by(
            challenge_id=challenge_id
        ).first()

        if not docker_challenge:
            raise ValueError(f"No Docker challenge found for challenge_id={challenge_id}")

        # STEP 1: Call Whale API to create container
        url = f"{self.base_url}/api/v1/ctfd-whale-user/container"
        params = {'challenge_id': challenge_id}

        try:
            response = self.session.post(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('success'):
                raise Exception(result.get('message', 'Unknown error'))

            # Extract container info from Whale response
            container_data = result.get('data', {})
            container_id = container_data.get('container_id')
            instance_id = container_data.get('instance_id', container_id)
            host = container_data.get('host', 'localhost')
            ports = container_data.get('ports', [])

        except requests.exceptions.RequestException as e:
            raise Exception(f"Whale API error: {e}")

        # STEP 2: Generate dynamic flag
        flag_template = docker_challenge.flag_template or "default_<hex>"
        flag = generate_dynamic_flag(flag_template)

        # STEP 3: Store DockerChallengeTracker
        Model = get_model()
        session_id = user_id if Model == 'users' else team_id

        tracker = DockerChallengeTracker(
            user_id=user_id,
            docker_image=docker_challenge.docker_image,
            instance_id=instance_id,
            timestamp=int(datetime.utcnow().timestamp()),
            revert_time=int(datetime.utcnow().timestamp()) + 3600  # 1 hour
        )
        db.session.add(tracker)

        # STEP 4: Encrypt and store flag
        encrypted = encrypt_flag(flag)
        flag_mapping = DynamicFlagMapping(
            user_id=user_id if Model == 'users' else None,
            team_id=team_id if Model == 'teams' else None,
            challenge_id=challenge_id,
            container_id=instance_id,
            encrypted_flag=encrypted,
            created_at=datetime.utcnow(),
            encryption_key_id=1
        )
        db.session.add(flag_mapping)
        db.session.commit()

        # STEP 5: Return container info
        return {
            'success': True,
            'instance_id': instance_id,
            'host': host,
            'ports': ports,
            'revert_time': tracker.revert_time
        }

    def delete_container(self, container_id):
        """
        Delete container via Whale API

        Steps:
        1. Call Whale API to remove container
        2. Database cleanup handled by CASCADE
        """
        url = f"{self.base_url}/api/v1/ctfd-whale-user/container"

        try:
            response = self.session.delete(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('success'):
                raise Exception(result.get('message', 'Unknown error'))

            return True

        except requests.exceptions.RequestException as e:
            raise Exception(f"Whale API error: {e}")

    def extend_container(self, challenge_id):
        """
        Extend container lifetime via Whale API

        Steps:
        1. Call Whale API to renew container
        2. Update DockerChallengeTracker.revert_time
        """
        url = f"{self.base_url}/api/v1/ctfd-whale-user/container"
        params = {'challenge_id': challenge_id}

        try:
            response = self.session.patch(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('success'):
                raise Exception(result.get('message', 'Unknown error'))

            # Update revert_time in our tracker
            tracker = DockerChallengeTracker.query.filter_by(
                user_id=get_current_user().id
            ).first()

            if tracker:
                tracker.revert_time = int(datetime.utcnow().timestamp()) + 3600
                db.session.commit()

            return {
                'success': True,
                'message': 'Container extended successfully',
                'new_revert_time': tracker.revert_time if tracker else None
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Whale API error: {e}")

    def get_container_status(self, challenge_id):
        """
        Get container status via Whale API

        Returns:
            dict: {
                'active': bool,
                'instance_id': str,
                'host': str,
                'ports': list,
                'remaining_time': int (seconds)
            }
        """
        url = f"{self.base_url}/api/v1/ctfd-whale-user/container"
        params = {'challenge_id': challenge_id}

        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('success'):
                return {'active': False}

            container_data = result.get('data', {})

            return {
                'active': True,
                'instance_id': container_data.get('instance_id'),
                'host': container_data.get('host'),
                'ports': container_data.get('ports'),
                'remaining_time': container_data.get('remaining_time', 0)
            }

        except requests.exceptions.RequestException as e:
            print(f"[WHALE ERROR] Status check failed: {e}")
            return {'active': False}
```

**Configuration:**
```python
# CTFd/config.py
WHALE_ENABLED = os.environ.get('WHALE_ENABLED', 'false').lower() == 'true'
WHALE_API_URL = os.environ.get('WHALE_API_URL', 'http://localhost:8000')
```

**Files Modified:**
- `CTFd/plugins/docker_challenges/container_manager.py` (add WhaleAPIManager)
- `CTFd/config.py` (add WHALE_API_URL)

**Estimated Time**: 6-8 hours

---

### Phase 2.4: Update API Endpoints

**Goal**: Update `/api/v1/container` endpoint to use container manager

**Current Endpoint** (Lines ~760-820 in `__init__.py`):
```python
@blueprint.route("/api/v1/container", methods=["GET"])
@authed_only
def container_handler():
    # Get parameters
    stopcontainer = request.args.get("stopcontainer", "false")
    container_name = request.args.get("name")
    challenge_id = request.args.get("challenge_id")

    if stopcontainer == "True":
        # Stop container logic
        delete_container(docker, instance_id)
    else:
        # Start container logic
        create_container(docker, image, team, portbl, flag)
```

**Updated Endpoint**:
```python
@blueprint.route("/api/v1/container", methods=["GET"])
@authed_only
def container_handler():
    """
    Container lifecycle endpoint (start/stop)

    Query Parameters:
        - name: Container/image name
        - challenge_id: Challenge ID
        - stopcontainer: "True" to stop container

    Returns:
        JSON: {success, message, data}
    """
    from CTFd.utils.user import get_current_user, is_admin
    from CTFd.utils.modes import get_model

    # Get container manager (Whale or Docker API)
    manager = get_container_manager()

    # Get parameters
    stopcontainer = request.args.get("stopcontainer", "false")
    challenge_id = request.args.get("challenge_id")

    try:
        if stopcontainer == "True":
            # STOP CONTAINER
            user = get_current_user()
            Model = get_model()
            session_id = user.id

            # Get tracker to find instance_id
            tracker = DockerChallengeTracker.query.filter_by(
                user_id=session_id
            ).first()

            if not tracker:
                return jsonify({
                    'success': False,
                    'message': 'No active container found'
                }), 404

            # Delete via manager
            manager.delete_container(tracker.instance_id)

            return jsonify({
                'success': True,
                'message': 'Container stopped successfully'
            }), 200

        else:
            # START CONTAINER
            user = get_current_user()
            Model = get_model()
            session_id = user.id
            team_id = user.team_id if Model == 'teams' else None

            # Create via manager
            result = manager.create_container(
                challenge_id=challenge_id,
                user_id=session_id,
                team_id=team_id
            )

            return jsonify({
                'success': True,
                'message': 'Container started successfully',
                'data': result
            }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
```

**Add New Endpoint for Extend**:
```python
@blueprint.route("/api/v1/container/extend", methods=["POST"])
@authed_only
def extend_container_endpoint():
    """
    Extend container lifetime

    JSON Body:
        {challenge_id: int}

    Returns:
        JSON: {success, message, new_revert_time}
    """
    manager = get_container_manager()

    data = request.get_json()
    challenge_id = data.get('challenge_id')

    if not challenge_id:
        return jsonify({
            'success': False,
            'message': 'challenge_id required'
        }), 400

    try:
        result = manager.extend_container(challenge_id)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
```

**Files Modified:**
- `CTFd/plugins/docker_challenges/__init__.py` (update container_handler, add extend endpoint)

**Estimated Time**: 3-4 hours

---

### Phase 2.5: Update UI for Extend Functionality

**Goal**: Add "Extend" button to UI alongside Stop/Revert

**Current UI** (`assets/view.js` lines 88-93):
```javascript
CTFd.lib.$("#container_revert").html(
    '<a onclick="start_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-redo"></i> Revert</small></a> '+
    '<a onclick="stop_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-redo"></i> Stop</small></a>'
);
```

**Updated UI**:
```javascript
// Add Extend button
CTFd.lib.$("#container_revert").html(
    '<a onclick="extend_container(\'' + item.docker_image + '\', ' + CTFd._internal.challenge.data.id + ');" class="btn btn-success">' +
    '<small style="color:white;"><i class="fas fa-clock"></i> Extend (+1 hour)</small></a> '+
    '<a onclick="start_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-redo"></i> Revert</small></a> '+
    '<a onclick="stop_container(\'' + item.docker_image + '\');" class="btn btn-dark">' +
    '<small style="color:white;"><i class="fas fa-stop"></i> Stop</small></a>'
);

// Add extend_container function
function extend_container(container, challenge_id) {
    if (confirm("Extend container lifetime by 1 hour?")) {
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
                        warningText: "Container lifetime extended by 1 hour.",
                        buttonText: "Close",
                        onClose: function () {
                            get_docker_status(container);
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
                warningText: error.message || "Failed to extend container. You may have reached the maximum renewal limit.",
                buttonText: "Close"
            });
        });
    }
}
```

**Files Modified:**
- `CTFd/plugins/docker_challenges/assets/view.js` (add extend_container, update button HTML)

**Estimated Time**: 2-3 hours

---

### Phase 2.6: Admin UI Controls

**Goal**: Add admin panel for container management

**Implementation:**

1. **Create Admin Template**
   - File: `CTFd/plugins/docker_challenges/templates/admin_containers.html`
   - Features:
     - Table listing all active containers
     - Columns: User, Challenge, Container ID, Host, Ports, Time Remaining
     - Actions: Extend, Stop, View Details
     - Pagination

2. **Create Admin API Endpoint**
   ```python
   @blueprint.route("/admin/containers", methods=["GET"])
   @admins_only
   def admin_containers():
       """Admin container management page"""
       return render_template('admin_containers.html')

   @blueprint.route("/api/v1/admin/containers", methods=["GET"])
   @admins_only
   def admin_containers_api():
       """List all active containers (admin)"""
       page = request.args.get('page', 1, type=int)
       per_page = request.args.get('per_page', 50, type=int)

       # Query all active containers
       trackers = DockerChallengeTracker.query.paginate(
           page=page,
           per_page=per_page
       )

       containers = []
       for tracker in trackers.items:
           # Get user info
           from CTFd.models import Users
           user = Users.query.filter_by(id=tracker.user_id).first()

           # Get challenge info
           from CTFd.models import Challenges
           flag_mapping = DynamicFlagMapping.query.filter_by(
               container_id=tracker.instance_id
           ).first()

           if flag_mapping:
               challenge = Challenges.query.filter_by(
                   id=flag_mapping.challenge_id
               ).first()
           else:
               challenge = None

           containers.append({
               'user_id': tracker.user_id,
               'username': user.name if user else 'Unknown',
               'challenge_id': flag_mapping.challenge_id if flag_mapping else None,
               'challenge_name': challenge.name if challenge else 'Unknown',
               'instance_id': tracker.instance_id,
               'docker_image': tracker.docker_image,
               'revert_time': tracker.revert_time,
               'remaining_time': tracker.revert_time - int(datetime.utcnow().timestamp())
           })

       return jsonify({
           'success': True,
           'data': containers,
           'total': trackers.total,
           'pages': trackers.pages,
           'page': trackers.page
       })

   @blueprint.route("/api/v1/admin/containers/<int:user_id>", methods=["DELETE"])
   @admins_only
   def admin_delete_container(user_id):
       """Admin force-delete user's container"""
       tracker = DockerChallengeTracker.query.filter_by(
           user_id=user_id
       ).first()

       if not tracker:
           return jsonify({
               'success': False,
               'message': 'No container found for user'
           }), 404

       manager = get_container_manager()

       try:
           manager.delete_container(tracker.instance_id)
           return jsonify({
               'success': True,
               'message': 'Container deleted'
           }), 200
       except Exception as e:
           return jsonify({
               'success': False,
               'message': str(e)
           }), 500
   ```

3. **Admin Template HTML**
   ```html
   {% extends "admin/base.html" %}

   {% block content %}
   <div class="container">
       <h2>Container Management</h2>

       <div class="row mb-3">
           <div class="col-md-12">
               <button id="refresh-btn" class="btn btn-primary">Refresh</button>
               <button id="stop-all-btn" class="btn btn-danger">Stop All Containers</button>
           </div>
       </div>

       <table class="table table-striped" id="containers-table">
           <thead>
               <tr>
                   <th>User</th>
                   <th>Challenge</th>
                   <th>Container ID</th>
                   <th>Image</th>
                   <th>Time Remaining</th>
                   <th>Actions</th>
               </tr>
           </thead>
           <tbody id="containers-tbody">
               <!-- Populated by JavaScript -->
           </tbody>
       </table>

       <nav>
           <ul class="pagination" id="pagination">
               <!-- Populated by JavaScript -->
           </ul>
       </nav>
   </div>

   <script>
   let currentPage = 1;

   function loadContainers(page = 1) {
       fetch(`/api/v1/admin/containers?page=${page}&per_page=50`)
           .then(r => r.json())
           .then(data => {
               const tbody = document.getElementById('containers-tbody');
               tbody.innerHTML = '';

               data.data.forEach(container => {
                   const row = document.createElement('tr');

                   const timeRemaining = Math.max(0, container.remaining_time);
                   const minutes = Math.floor(timeRemaining / 60);
                   const seconds = timeRemaining % 60;

                   row.innerHTML = `
                       <td>${container.username}</td>
                       <td>${container.challenge_name}</td>
                       <td><code>${container.instance_id.substring(0, 12)}</code></td>
                       <td>${container.docker_image}</td>
                       <td>${minutes}m ${seconds}s</td>
                       <td>
                           <button class="btn btn-sm btn-danger" onclick="deleteContainer(${container.user_id})">
                               Stop
                           </button>
                       </td>
                   `;
                   tbody.appendChild(row);
               });

               // Update pagination
               updatePagination(data.page, data.pages);
           });
   }

   function deleteContainer(userId) {
       if (confirm('Stop this container?')) {
           fetch(`/api/v1/admin/containers/${userId}`, {method: 'DELETE'})
               .then(r => r.json())
               .then(data => {
                   alert(data.message);
                   loadContainers(currentPage);
               });
       }
   }

   document.getElementById('refresh-btn').onclick = () => loadContainers(currentPage);

   loadContainers(1);
   setInterval(() => loadContainers(currentPage), 5000); // Auto-refresh every 5s
   </script>
   {% endblock %}
   ```

**Files Created:**
- `CTFd/plugins/docker_challenges/templates/admin_containers.html`

**Files Modified:**
- `CTFd/plugins/docker_challenges/__init__.py` (add admin endpoints)

**Estimated Time**: 6-8 hours

---

## 4. Testing Plan

### 4.1 Unit Tests

**Test Cases:**

1. **Container Manager Selection**
   - Test `get_container_manager()` with `WHALE_ENABLED=false` → Returns DockerAPIManager
   - Test `get_container_manager()` with `WHALE_ENABLED=true` → Returns WhaleAPIManager

2. **WhaleAPIManager Methods**
   - Test `create_container()` → Mock Whale API response
   - Test `delete_container()` → Mock Whale API response
   - Test `extend_container()` → Mock Whale API response
   - Test `get_container_status()` → Mock Whale API response
   - Test API error handling → Verify exceptions raised

3. **Database Integrity**
   - Test container creation → Verify DockerChallengeTracker created
   - Test container creation → Verify DynamicFlagMapping created with encrypted flag
   - Test container deletion → Verify CASCADE delete works
   - Test flag encryption → Verify round-trip encrypt/decrypt

**Files:**
- `CTFd/plugins/docker_challenges/tests/test_container_manager.py`

### 4.2 Integration Tests

**Test Scenarios:**

1. **End-to-End Container Lifecycle**
   - User starts container → Verify UI updates
   - User extends container → Verify time updated
   - User stops container → Verify cleanup
   - Container auto-expires → Verify Whale cleanup

2. **Flag System Integration**
   - Container created → Flag generated and encrypted
   - Submit correct flag → Verify validation works
   - Submit incorrect flag → Verify constant-time comparison
   - Container deleted → Verify flag deleted (CASCADE)

3. **Multi-User Scenarios**
   - User A starts container
   - User B starts different container
   - User A cannot access User B's flag
   - User A stops own container (User B unaffected)

4. **Admin Panel**
   - Admin views all containers
   - Admin stops user's container
   - Verify user UI updates after admin stop

**Environment:**
- Test with Whale plugin installed
- Test with `WHALE_ENABLED=true`
- Use test challenges and test users

### 4.3 Performance Tests

**Metrics:**

1. **Container Creation Latency**
   - Docker API baseline: ~1-2 seconds
   - Whale API target: < 3 seconds
   - Measure: Time from API call to container running

2. **Container Deletion Latency**
   - Docker API baseline: ~500ms
   - Whale API target: < 1 second

3. **Concurrent Container Creation**
   - Simulate 10 users creating containers simultaneously
   - Verify all succeed
   - Verify no race conditions in flag generation

4. **Database Performance**
   - Query time for container lookup (should be < 10ms)
   - Flag validation time (should be < 10ms)

**Tools:**
- `ab` (Apache Bench) for load testing
- `pytest-benchmark` for Python benchmarks
- Database query profiling

---

## 5. Migration Strategy

### 5.1 Gradual Rollout

**Phase 1: Parallel Operation (Week 1)**
- Install Whale alongside current Docker implementation
- Set `WHALE_ENABLED=false` (use Docker API)
- Verify no regressions

**Phase 2: Canary Testing (Week 2)**
- Enable Whale for 10% of challenges (`WHALE_ENABLED=true` for specific challenges)
- Monitor errors, performance, user feedback
- Rollback capability ready

**Phase 3: Full Migration (Week 3)**
- Set `WHALE_ENABLED=true` for all challenges
- Monitor all containers
- Deprecate direct Docker API calls

**Phase 4: Cleanup (Week 4)**
- Remove DockerAPIManager (keep as fallback?)
- Remove old Docker API code
- Update documentation

### 5.2 Rollback Plan

**If Whale fails:**
1. Set `WHALE_ENABLED=false` in environment
2. Restart CTFd
3. System reverts to Docker API
4. All existing containers unaffected (tracked in same database)

**Database:**
- No schema changes (both systems use same tables)
- No data migration needed

---

## 6. Documentation Requirements

**User Documentation:**
- How to start containers
- How to extend containers
- How to stop containers
- What happens when container expires

**Admin Documentation:**
- Whale configuration guide
- Container limits and quotas
- Admin panel usage
- Troubleshooting container issues

**Developer Documentation:**
- Container manager abstraction
- Adding new container backends
- Whale API integration guide
- Testing container functionality

---

## 7. Success Criteria

**Phase 2 Complete When:**

- ✅ Whale plugin installed and configured
- ✅ Container abstraction layer implemented
- ✅ WhaleAPIManager fully functional
- ✅ API endpoints updated to use manager
- ✅ UI supports Start, Stop, Extend operations
- ✅ Admin panel for container management
- ✅ All tests passing (unit + integration)
- ✅ Performance meets targets (< 3s container start)
- ✅ Flag system works with Whale containers
- ✅ Documentation complete

---

## 8. Timeline Estimate

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| 2.1 Whale Setup | Install, configure, test Whale | 2-4 hours |
| 2.2 Abstraction Layer | Create ContainerManager classes | 4-6 hours |
| 2.3 Whale API Implementation | Implement WhaleAPIManager | 6-8 hours |
| 2.4 API Endpoints | Update container endpoints | 3-4 hours |
| 2.5 UI Updates | Add Extend button, update JS | 2-3 hours |
| 2.6 Admin UI | Create admin panel | 6-8 hours |
| Testing | Unit + integration + performance | 8-10 hours |
| Documentation | User + admin + developer docs | 4-6 hours |
| **TOTAL** | | **35-49 hours** |

**Estimated Calendar Time**: 1-2 weeks (full-time) or 2-4 weeks (part-time)

---

## 9. Next Steps

**Immediate Actions:**

1. ✅ Review this roadmap
2. ⏭️ Install Whale plugin (Phase 2.1)
3. ⏭️ Test Whale independently with test challenge
4. ⏭️ Create container_manager.py abstraction layer (Phase 2.2)
5. ⏭️ Implement WhaleAPIManager (Phase 2.3)

**Questions to Resolve:**

- Which Whale fork to use? (frankli0324/ctfd-whale is most active)
- FRP configuration needed? (for reverse proxy)
- Docker Swarm or single-host? (Swarm requires multi-node setup)
- Max containers per user? (default: 1, configurable)
- Container timeout? (default: 1 hour, configurable)

---

## 10. Risk Analysis

**Technical Risks:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Whale API compatibility issues | HIGH | Use abstraction layer, maintain Docker API fallback |
| Performance degradation | MEDIUM | Performance testing before rollout, monitor metrics |
| Database schema conflicts | LOW | Whale uses separate tables, no conflicts expected |
| Flag system integration bugs | HIGH | Extensive testing, gradual rollout |

**Operational Risks:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Whale service downtime | HIGH | Automatic fallback to Docker API |
| Container quota exhaustion | MEDIUM | Set appropriate limits, monitoring alerts |
| Network configuration errors | MEDIUM | Test FRP thoroughly, have rollback plan |
| User confusion (new UI) | LOW | Clear documentation, tooltips in UI |

---

## Conclusion

Phase 2 (Whale Integration) builds on the solid foundation of Phase 1 (Flag System v1.0) by adding production-grade container orchestration. The abstraction layer approach ensures a smooth migration with minimal risk, while maintaining full compatibility with the encrypted flag system.

**Key Benefits:**
- 🐋 Docker Swarm support for scalability
- ⏰ Container lifecycle management (extend/renew)
- 🔧 Admin controls for visibility and management
- 🔒 Network isolation via FRP
- 📊 Better resource management and quotas

**Status**: Ready to begin implementation

---

**Document Version**: 1.0
**Last Updated**: 2025-11-23
**Next Review**: After Phase 2.1 complete
