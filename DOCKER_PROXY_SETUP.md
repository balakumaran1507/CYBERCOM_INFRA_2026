# Docker Socket Proxy Setup Guide

**CYBERCOM CTF 2026 - Secure Docker Integration**

---

## Why Docker Socket Proxy?

Direct Docker socket mounting (`/var/run/docker.sock`) gives containers **full Docker daemon control**, which is a major security risk. The Docker socket proxy provides:

- ✅ **Filtered API Access** - Only allowed operations can be performed
- ✅ **No Root-Level Control** - Cannot manipulate host system
- ✅ **Audit Trail** - All requests logged
- ✅ **Defense in Depth** - Additional security layer

---

## Current Configuration

### Docker Proxy Container

**Image:** `tecnativa/docker-socket-proxy:latest`

**Permissions Granted:**
```bash
IMAGES=1          # List and inspect Docker images
NETWORKS=1        # Manage Docker networks
VOLUMES=1         # Manage Docker volumes
CONTAINERS=1      # Create and list containers
INFO=1            # Query Docker system info
VERSION=1         # Query Docker version
EVENTS=1          # Subscribe to Docker events
PING=1            # Health check endpoint
```

**Permissions Denied:**
```bash
ALLOW_RESTARTS=0  # Cannot restart containers
ALLOW_STOP=0      # Cannot stop containers
ALLOW_START=0     # Cannot start stopped containers
BUILD=0           # Cannot build images
COMMIT=0          # Cannot commit containers
EXEC=0            # Cannot exec into containers
POST=0            # No POST to sensitive endpoints
SWARM=0           # No Docker Swarm operations
```

### Network Configuration

**Proxy Network:** `ctfd_default` (bridge)
**Exposed Port:** `2375` (HTTP)
**TLS:** Disabled (internal network only)

### CTFd Connection Settings

- **Hostname:** `docker-proxy:2375`
- **Protocol:** HTTP
- **TLS:** No
- **Authentication:** None (protected by network isolation)

---

## Setup Commands

### Option 1: Standalone Proxy (Recommended)

```bash
# Create the CTFd network first (if doesn't exist)
docker network create ctfd_default

# Start the Docker socket proxy
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
  -e ALLOW_RESTARTS=0 \
  -e ALLOW_STOP=0 \
  -e ALLOW_START=0 \
  -e BUILD=0 \
  -e COMMIT=0 \
  -e EXEC=0 \
  -e SWARM=0 \
  -e POST=0 \
  -e LOG_LEVEL=info \
  -p 2375:2375 \
  --network ctfd_default \
  tecnativa/docker-socket-proxy
```

### Option 2: Docker Compose Integration

Add to your `docker-compose.yml`:

```yaml
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy
    container_name: docker-proxy
    restart: always
    environment:
      - IMAGES=1
      - NETWORKS=1
      - VOLUMES=1
      - CONTAINERS=1
      - INFO=1
      - VERSION=1
      - EVENTS=1
      - PING=1
      - ALLOW_RESTARTS=0
      - ALLOW_STOP=0
      - ALLOW_START=0
      - BUILD=0
      - COMMIT=0
      - EXEC=0
      - SWARM=0
      - POST=0
      - LOG_LEVEL=info
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - "2375:2375"
    networks:
      - default

  ctfd:
    # ... existing CTFd configuration ...
    depends_on:
      - docker-proxy
    networks:
      - default
```

---

## Verification

### 1. Check Proxy is Running

```bash
docker ps | grep docker-proxy
```

Expected output:
```
docker-proxy   tecnativa/docker-socket-proxy   0.0.0.0:2375->2375/tcp
```

### 2. Test Proxy Connectivity

```bash
# List images (should work)
curl http://localhost:2375/images/json

# Try to build (should fail/not respond)
curl -X POST http://localhost:2375/build
```

### 3. Verify Network Access

```bash
# From CTFd container
docker exec ctfd-ctfd-1 curl -s http://docker-proxy:2375/version
```

Expected: JSON response with Docker version

### 4. Test from CTFd Admin Panel

1. Login to CTFd admin
2. Navigate to: Admin → Docker Config
3. Set hostname: `docker-proxy:2375`
4. Click Submit
5. Should see list of available Docker images

---

## Troubleshooting

### Proxy Not Starting

**Check logs:**
```bash
docker logs docker-proxy
```

**Common issues:**
- Docker socket permission denied
  → Ensure `/var/run/docker.sock` is readable
- Port 2375 already in use
  → Change port or stop conflicting service

### CTFd Can't Connect

**Verify network:**
```bash
docker network inspect ctfd_default | grep -A 10 docker-proxy
```

**Test manually:**
```bash
docker exec ctfd-ctfd-1 ping -c 3 docker-proxy
docker exec ctfd-ctfd-1 curl -v http://docker-proxy:2375/_ping
```

### Permission Denied Errors

**Symptom:** Cannot create containers

**Check:** Ensure `CONTAINERS=1` is set
```bash
docker inspect docker-proxy --format '{{json .Config.Env}}' | grep CONTAINERS
```

---

## Security Best Practices

### Production Recommendations

1. **Enable TLS:**
   ```bash
   -e HAPROXY_SERVER_SSL_VERIFY=required
   -e HAPROXY_SSL_CERT=/path/to/cert.pem
   ```

2. **Restrict Network Access:**
   - Don't expose port 2375 to host (remove `-p 2375:2375`)
   - Keep proxy on internal Docker network only

3. **Monitor Access:**
   ```bash
   docker logs -f docker-proxy
   ```

4. **Regular Updates:**
   ```bash
   docker pull tecnativa/docker-socket-proxy:latest
   docker stop docker-proxy
   docker rm docker-proxy
   # Re-run create command
   ```

### Development vs Production

| Setting | Development | Production |
|---------|-------------|------------|
| TLS | Disabled | **Required** |
| Port Expose | Yes (2375) | **No** |
| LOG_LEVEL | info | warning/error |
| Network | ctfd_default | Dedicated internal |
| EXEC | Disabled | **Disabled** |
| BUILD | Disabled | **Disabled** |

---

## Maintenance

### Updating the Proxy

```bash
# Pull latest image
docker pull tecnativa/docker-socket-proxy:latest

# Recreate container
docker stop docker-proxy
docker rm docker-proxy

# Use same run command from setup
docker run -d --name docker-proxy ...
```

### Checking Proxy Health

```bash
# Health endpoint
curl http://localhost:2375/_ping

# Expected response: "OK"
```

### Log Management

```bash
# View recent logs
docker logs --tail 100 docker-proxy

# Follow logs in real-time
docker logs -f docker-proxy

# Clear old logs (requires restart)
docker compose restart docker-proxy
```

---

## Advanced Configuration

### Custom Permissions

Need to allow more operations? Modify environment variables:

```bash
# Allow container stop (use with caution)
-e ALLOW_STOP=1

# Allow container exec (security risk)
-e EXEC=1
```

**⚠️ Warning:** Enabling additional permissions weakens security.

### Multiple CTFd Instances

Run separate proxies for isolation:

```bash
# Proxy 1 (for CTFd instance 1)
docker run -d --name docker-proxy-ctf1 \
  --network ctfd1_default \
  -p 2375:2375 \
  tecnativa/docker-socket-proxy

# Proxy 2 (for CTFd instance 2)
docker run -d --name docker-proxy-ctf2 \
  --network ctfd2_default \
  -p 2376:2375 \
  tecnativa/docker-socket-proxy
```

---

## Reference Links

- **Docker Socket Proxy GitHub:** https://github.com/Tecnativa/docker-socket-proxy
- **Docker API Documentation:** https://docs.docker.com/engine/api/
- **HAProxy Documentation:** https://www.haproxy.org/

---

**Last Updated:** November 21, 2025
**CYBERCOM CTF 2026 - Phase B**
