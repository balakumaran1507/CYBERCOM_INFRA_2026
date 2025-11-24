# CYBERCOM CTF 2026 Platform

**Custom CTF Infrastructure based on CTFd**
Repository: https://github.com/balakumaran1507/CYBERCOM_CTF_2026.git

---

## 🎯 Project Overview

CYBERCOM CTF 2026 is a customized Capture The Flag platform built on CTFd, extended with dynamic Docker-based challenge infrastructure. This platform allows per-team/user isolated challenge instances with future support for dynamic flag generation.

### Key Differentiators from Stock CTFd

- ✅ **Dynamic Docker Challenges** - Per-team/user container spawning
- ✅ **Secure Docker Access** - Using docker-socket-proxy instead of direct socket mount
- ✅ **Instance Isolation** - Each team gets their own isolated environment
- 🔄 **Dynamic Flags** - (Phase C - Planned)
- 🔄 **Custom Admin Panel** - Enhanced container management (Phase D - Planned)
- 🔄 **CYBERCOM Branding** - Complete UI overhaul (Phase D - Planned)

---

## 📊 Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      CYBERCOM CTF 2026                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────┐    ┌──────────────┐    ┌────────────────┐ │
│  │   nginx    │───▶│     CTFd     │───▶│  MariaDB 10.11 │ │
│  │ (Port 80)  │    │  (Port 8000) │    │   (Internal)   │ │
│  └────────────┘    └──────┬───────┘    └────────────────┘ │
│                           │                                 │
│                           ├──────────▶┌────────────────┐   │
│                           │           │  Redis Cache   │   │
│                           │           │   (Internal)   │   │
│                           │           └────────────────┘   │
│                           │                                 │
│                           │           ┌────────────────┐   │
│                           └──────────▶│ Docker Proxy   │   │
│                                       │ (Port 2375)    │   │
│                                       └───────┬────────┘   │
│                                               │             │
│                                               ▼             │
│                                       ┌────────────────┐   │
│                                       │ Docker Engine  │   │
│                                       │  (Challenge    │   │
│                                       │  Containers)   │   │
│                                       └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Docker Network Topology

```
ctfd_default (bridge network)
├── nginx:80
├── ctfd:8000
├── docker-proxy:2375
└── (CTFd spawned challenge containers)

ctfd_internal (internal network)
├── db:3306
└── cache:6379
```

### Security Architecture

**Docker Socket Proxy (tecnativa/docker-socket-proxy)**
- **Purpose:** Provides secure, filtered access to Docker API
- **Permissions:** Limited to read-only operations (IMAGES, CONTAINERS, NETWORKS, VOLUMES, INFO, VERSION, EVENTS, PING)
- **Why:** Prevents CTFd from having full Docker daemon control
- **Blocked:** Container start/stop/restart, builds, commits, swarm operations

---

## 🚀 Phase B: Dynamic Docker Challenges (COMPLETED)

### What Was Implemented

#### 1. **CTFd-Docker-Challenges Plugin**
   - **Location:** `CTFd/plugins/docker_challenges/`
   - **Challenge Type:** `docker` (registered in CHALLENGE_CLASSES)
   - **Features:**
     - Per-team/user container spawning
     - Automatic container cleanup (5min revert timer, 2hr stale removal)
     - Container termination on challenge solve
     - Admin management interface

#### 2. **Docker Integration**
   - **Method:** Via docker-socket-proxy (secure)
   - **Connection:** `docker-proxy:2375` (HTTP, no TLS required)
   - **Access Control:** Read-only Docker API permissions

#### 3. **Admin Interfaces**
   - `/admin/docker_config` - Configure Docker connection and select available images
   - `/admin/docker_status` - View and manage active containers

#### 4. **API Endpoints**
   - `/api/v1/docker` - Get available Docker images (Admin only)
   - `/api/v1/container` - Start/stop/revert containers (Authenticated users)
   - `/api/v1/docker_status` - Get user's active containers
   - `/api/v1/nuke` - Kill all containers (Admin only)

### Files Modified/Added

```
Modified:
├── docker-compose.yml          (Docker socket mount)
├── requirements.in             (Added Flask-WTF==1.0.1)

Added:
└── CTFd/plugins/docker_challenges/
    ├── __init__.py             (708 lines - plugin core logic)
    ├── config.json             (Admin menu configuration)
    ├── requirements.txt        (flask_wtf dependency)
    ├── assets/
    │   ├── create.html         (Admin: Create docker challenge)
    │   ├── create.js
    │   ├── update.html         (Admin: Update docker challenge)
    │   ├── update.js
    │   ├── view.html           (User: View and interact with challenge)
    │   └── view.js
    └── templates/
        ├── docker_config.html       (Docker API configuration page)
        └── admin_docker_status.html (Container management dashboard)
```

### Database Schema

**New Tables Created:**

1. **`docker_config`** (Stores Docker API connection settings)
   ```sql
   - id (primary key)
   - hostname (Docker host:port)
   - tls_enabled (boolean)
   - ca_cert, client_cert, client_key (TLS certificates - optional)
   - repositories (comma-separated list of allowed images)
   ```

2. **`docker_challenge_tracker`** (Tracks active containers)
   ```sql
   - id (primary key)
   - team_id / user_id (ownership)
   - docker_image (image being run)
   - timestamp (creation time)
   - revert_time (when container can be reset)
   - instance_id (Docker container ID)
   - ports (exposed port mappings)
   - host (Docker host IP)
   - challenge (challenge name)
   ```

---

## ⚙️ Configuration

### Known Working Configuration

**Docker Connection Settings** (Configured in `/admin/docker_config`):

| Setting | Value | Notes |
|---------|-------|-------|
| **Hostname** | `docker-proxy:2375` | Via secure Docker socket proxy |
| **TLS Enabled** | `No` | Proxy is on internal network |
| **Repositories** | Auto-detected | Select from available images |

### Docker Proxy Settings

The `docker-proxy` container is configured with these environment variables:

```bash
IMAGES=1          # Allow listing/pulling images
NETWORKS=1        # Allow network operations
VOLUMES=1         # Allow volume operations
CONTAINERS=1      # Allow container list/create
INFO=1            # Allow Docker info queries
VERSION=1         # Allow version queries
EVENTS=1          # Allow event streaming
PING=1            # Allow health checks

# Security: Disabled operations
ALLOW_RESTARTS=0  # No container restarts
ALLOW_STOP=0      # No container stops (CTFd uses DELETE instead)
ALLOW_START=0     # No container starts (create already starts)
BUILD=0           # No image builds
COMMIT=0          # No container commits
EXEC=0            # No exec into containers
SWARM=0           # No swarm operations
```

---

## 🛠️ Setup Instructions

### Prerequisites

- Docker & Docker Compose
- Git
- Python 3.11+
- 4GB+ RAM
- Network access for container spawning

### Quick Start (From Scratch)

1. **Clone Repository**
   ```bash
   git clone https://github.com/balakumaran1507/CYBERCOM_CTF_2026.git
   cd CYBERCOM_CTF_2026
   ```

2. **Start Docker Socket Proxy**
   ```bash
   docker run -d \
     --name docker-proxy \
     --restart=always \
     -v /var/run/docker.sock:/var/run/docker.sock:ro \
     -e IMAGES=1 \
     -e NETWORKS=1 \
     -e VOLUMES=1 \
     -e CONTAINERS=1 \
     -e INFO=1 \
     -e VERSION=1 \
     -e EVENTS=1 \
     -e PING=1 \
     -p 2375:2375 \
     --network ctfd_default \
     tecnativa/docker-socket-proxy
   ```

3. **Build and Start CTFd**
   ```bash
   docker compose build
   docker compose up -d
   ```

4. **Wait for Initialization**
   ```bash
   docker compose logs -f ctfd
   # Wait for "Starting CTFd" and "Booting worker"
   ```

5. **Access Platform**
   - CTFd: http://localhost:8000
   - Admin Setup: Follow first-run wizard

6. **Configure Docker Integration**
   - Login as admin
   - Navigate to: Admin → Docker Config
   - Set hostname: `docker-proxy:2375`
   - Set TLS: `No`
   - Click Submit
   - Verify repositories appear

### Verification Checklist

- [ ] CTFd loads at http://localhost:8000
- [ ] Admin panel accessible
- [ ] Docker Config shows available images
- [ ] Docker Status page loads (empty initially)
- [ ] Can create standard (non-docker) challenges
- [ ] Plugin listed in `docker compose logs ctfd | grep "Loaded module.*docker_challenges"`

---

## 🎮 Using Docker Challenges

### For Administrators

#### 1. Prepare Challenge Images

```bash
# Example: Build a vulnerable web app
cd /path/to/challenge
docker build -t myctf/vuln-app:latest .

# Or pull existing image
docker pull nginx:alpine
docker tag nginx:alpine testchallenge:latest
```

#### 2. Create Docker Challenge

1. Admin → Challenges → Create
2. Type: **docker**
3. Configure:
   - Name: "Web Exploitation 101"
   - Category: "Web"
   - Value: 500
   - Docker Image: `myctf/vuln-app:latest` (from dropdown)
   - Description: Challenge instructions
4. Add flag (static for now - Phase C will add dynamic flags)
5. Click Create

#### 3. Monitor Containers

- Admin → Docker Status
  - View all active containers
  - See team/user ownership
  - Kill specific containers
  - Nuke all containers (emergency)

### For Participants

1. Navigate to Challenges
2. Click on a docker challenge
3. Click "Start Instance"
4. Wait for container to spawn (~5-30 seconds)
5. Connection info displayed:
   - Host: `<docker_host_ip>`
   - Ports: `<exposed_ports>`
6. Access the challenge via provided connection
7. Submit flag when found
8. Container auto-deleted on correct submission

### Container Lifecycle

```
Start Instance
     ↓
Container Created (unique name: {image}_{md5(team)[:10]})
     ↓
Random Ports Assigned (30000-60000 range)
     ↓
5 Minutes - Revert Available
     ↓
2 Hours - Auto-Cleanup if Stale
     ↓
Solve - Immediate Deletion
```

### Dynamic Flag Injection (Phase C)

**Flag Generation:**
- Each container instance receives a unique flag generated from a custom template
- Template format: `CYBERCOM{<template>}` where `<hex>` placeholders are replaced with 6-character secure random hex
- Example: `injects_<hex>_hurts_yk_<hex>` → `CYBERCOM{injects_4fa2c1_hurts_yk_b92ed0}`

**Flag Injection Methods:**
1. **Environment Variable:** `FLAG=CYBERCOM{...}` accessible via `$FLAG` in container
2. **File Persistence:** Flag written to `/flag.txt` inside container

**Flag Access Pattern:**
- Containers are accessible at: `http://localhost:<random_port>`
- Port range: 30000-60000 (randomly assigned per instance)
- Each team/user gets isolated container with unique flag

**Container Runtime:**
- Current implementation optimized for nginx-based challenges
- Flag injection: `echo "$FLAG" > /flag.txt && nginx -g 'daemon off;'`
- For non-nginx images, adjust the startup command in `create_container()` function

---

## 🔧 Troubleshooting

### Docker Connectivity Issues

**Symptom:** "ERROR: Failed to Connect to Docker" in Docker Config

**Solutions:**
1. Verify docker-proxy is running:
   ```bash
   docker ps | grep docker-proxy
   ```

2. Check docker-proxy is on ctfd_default network:
   ```bash
   docker network inspect ctfd_default | grep docker-proxy
   ```

3. Test connectivity from CTFd container:
   ```bash
   docker exec ctfd-ctfd-1 curl -s http://docker-proxy:2375/images/json
   ```

4. Check docker-proxy logs:
   ```bash
   docker logs docker-proxy
   ```

### Container Won't Start

**Symptom:** "Container already running" or port conflicts

**Solutions:**
1. Check for stale containers:
   ```bash
   docker ps -a | grep ctfd
   ```

2. Clean up manually:
   ```bash
   docker rm -f $(docker ps -a | grep "_" | awk '{print $1}')
   ```

3. Use admin nuke button in Docker Status page

### Plugin Not Loading

**Symptom:** No "docker" challenge type available

**Solutions:**
1. Check plugin files exist:
   ```bash
   ls -la CTFd/plugins/docker_challenges/
   ```

2. Verify plugin loaded in logs:
   ```bash
   docker compose logs ctfd | grep docker_challenges
   ```

3. Rebuild container:
   ```bash
   docker compose down
   docker compose build ctfd
   docker compose up -d
   ```

### Dynamic Flags Not Working

**Symptom:** Generated flags always show `CYBERCOM{default_<hex>}` instead of custom template

**Root Cause:**
- Challenge lookup was querying by `docker_image` instead of `challenge_id`
- Multiple challenges can use the same Docker image
- This caused wrong template to be selected (first match in database)

**Fixed in Phase C Stabilization:**
- Frontend now passes `challenge_id` parameter
- Backend queries by `challenge_id` instead of `docker_image`
- Each challenge gets its own correct template

**Verification:**
```bash
# Check CTFd logs for dynamic flag generation
docker compose logs ctfd | grep "FLAG GEN"

# Expected output:
# [FLAG GEN] Input template: 'testing_<hex>templates<hex>'
# [FLAG GEN] Generated flag: 'CYBERCOM{testing_4fa2c1_templates_b92ed0}'
```

**Debug Dynamic Flags:**
```bash
# View all flag mappings in database
docker exec ctfd-db-1 mysql -u ctfd -pctfd ctfd -e \
  "SELECT id, user_id, challenge_id, generated_flag, is_active FROM dynamic_flag_mapping;"

# Check challenge templates
docker exec ctfd-db-1 mysql -u ctfd -pctfd ctfd -e \
  "SELECT id, docker_image, flag_template FROM docker_challenge;"
```

---

## 📈 Roadmap

### ✅ Phase B: Instance Spawning (COMPLETED)
- [x] Docker-challenges plugin installation
- [x] Docker socket proxy integration
- [x] Per-team/user container isolation
- [x] Admin management interfaces
- [x] Auto-cleanup mechanisms

### ✅ Phase C: Dynamic Flags (COMPLETED)
- [x] Generate unique flag per instance with custom templates
- [x] Store instance-to-flag mapping in database
- [x] Validate flags based on active container
- [x] Flag regeneration on instance restart/revert
- [x] Custom flag format: `CYBERCOM{<template>}` with `<hex>` placeholders
- [x] **STABILIZED**: Fixed challenge_id lookup bug (was querying by image name)
- [x] Comprehensive logging for debugging

### 🔄 Phase D: CYBERCOM Branding
- [ ] Custom theme development
- [ ] Logo and color scheme
- [ ] Enhanced admin dashboard
- [ ] Custom challenge UI
- [ ] Branded emails and notifications

### 🔄 Phase E: Advanced Features
- [ ] Multi-node Docker Swarm support
- [ ] Challenge templates library
- [ ] Automated difficulty scoring
- [ ] Challenge analytics dashboard
- [ ] Integration with external scoring systems

---

## 🔒 Security Considerations

### Current Security Measures

1. **Docker Socket Proxy**
   - Prevents full Docker daemon access
   - Read-only operations only
   - No exec, no builds, no swarm

2. **Network Isolation**
   - Internal network for database/cache
   - Challenge containers on default bridge
   - No direct database access from challenges

3. **Container Limitations**
   - Random port assignment (reduces conflicts)
   - Time-based auto-cleanup (resource management)
   - One container per team/user (prevents abuse)

### Recommended Hardening (Production)

- [ ] Enable TLS for Docker proxy
- [ ] Implement rate limiting on container creation
- [ ] Resource quotas per container (CPU/Memory limits)
- [ ] Network policies to isolate challenge containers
- [ ] Regular security audits of challenge images
- [ ] Implement container scanning (Trivy/Clair)
- [ ] Enable SELinux/AppArmor policies
- [ ] Regular backup of CTFd database

---

## 📚 Technical Reference

### Dependencies

- **CTFd:** 3.7.x (base framework)
- **Flask:** 2.1.3
- **Flask-WTF:** 1.0.1 (plugin requirement)
- **Docker:** 20.10+ (host requirement)
- **Docker Socket Proxy:** tecnativa/docker-socket-proxy:latest
- **MariaDB:** 10.11
- **Redis:** 4.x
- **nginx:** stable

### Plugin Architecture

The `docker_challenges` plugin extends CTFd using:

1. **Challenge Type Registration**
   ```python
   CHALLENGE_CLASSES['docker'] = DockerChallengeType
   ```

2. **Database Models**
   - `DockerConfig` - Connection settings
   - `DockerChallengeTracker` - Active containers
   - `DockerChallenge` - Challenge type (extends Challenges)

3. **API Namespaces**
   - `docker_namespace` - Image management
   - `container_namespace` - Container lifecycle
   - `active_docker_namespace` - User status
   - `kill_container` - Admin cleanup

4. **Admin Routes**
   - `/admin/docker_config` - Configuration
   - `/admin/docker_status` - Management dashboard

### Git History

```
main (current)
├── e20fc133 PHASE B COMPLETE - Instance Spawning Plugin Installed
├── 3e3b1375 PRE-PLUGIN STABLE STATE
├── 8b63f26e STABLE BASELINE - CYBERCOM CTF Infrastructure
└── 253fc1a7 Clearly mark required fields with an asterisk
```

**Rollback Commands:**
```bash
# To before plugin
git reset --hard 3e3b1375

# To baseline
git reset --hard 8b63f26e
```

---

## 👥 Contributors

- **Balakumaran** - Lead Engineer & Platform Architect
- **Claude (Anthropic)** - Development Assistant & Documentation

---

## 📄 License

This project is based on CTFd, which is licensed under the Apache License 2.0.
CYBERCOM customizations: Proprietary (2026)

---

## 🔗 Resources

- **CTFd Documentation:** https://docs.ctfd.io
- **Docker Socket Proxy:** https://github.com/Tecnativa/docker-socket-proxy
- **Project Repository:** https://github.com/balakumaran1507/CYBERCOM_CTF_2026.git
- **Original CTFd:** https://github.com/CTFd/CTFd

---

**Last Updated:** November 21, 2025
**Platform Version:** CYBERCOM CTF 2026 - Phase B Complete
**Status:** ✅ Production Ready for Instance Spawning
