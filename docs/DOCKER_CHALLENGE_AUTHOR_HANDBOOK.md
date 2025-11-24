# 🐳 Docker Challenge Author Handbook
## CYBERCOM CTF Platform - Official Guide for Challenge Designers

**Version**: 1.0.0
**Last Updated**: 2025-11-23
**Target Audience**: CTF Challenge Authors
**System**: CTFd + CYBERCOM Runtime Engine (CRE)

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [Quick Start Checklist](#quick-start-checklist)
3. [Docker Image Requirements](#docker-image-requirements)
4. [Port Exposure Rules](#port-exposure-rules)
5. [Flag Injection System](#flag-injection-system)
6. [Security Guidelines](#security-guidelines)
7. [Resource Best Practices](#resource-best-practices)
8. [Common Mistakes & Solutions](#common-mistakes--solutions)
9. [Testing Your Challenge](#testing-your-challenge)
10. [Troubleshooting](#troubleshooting)

---

## 1. Introduction

### What is CYBERCOM?

CYBERCOM is our custom Docker container runtime engine that powers dynamic CTF challenges. It provides:

- **Automatic container lifecycle management** (15-minute base runtime)
- **Container extension system** (up to 5 extensions, 90-minute hard cap)
- **Dynamic flag generation** using customizable templates
- **Automatic cleanup** of expired containers
- **Full audit logging** of all container operations

### How It Works

```
Player requests challenge
    ↓
System generates unique flag
    ↓
Docker container spawned with injected flag
    ↓
Player receives connection details (host:port)
    ↓
Player exploits challenge, retrieves flag
    ↓
Container auto-expires after runtime limit
```

---

## 2. Quick Start Checklist

✅ **Before Submitting Your Challenge**:

- [ ] Docker image has explicit tag (e.g., `myimage:latest`, not just `myimage`)
- [ ] All required ports are explicitly exposed in Dockerfile (`EXPOSE` directive)
- [ ] Image size is reasonable (<500MB preferred, <2GB maximum)
- [ ] Flag is retrievable via environment variable `$FLAG` or file `/flag.txt`
- [ ] Challenge works without requiring privileged mode
- [ ] No hardcoded flags in the image (use dynamic templates instead)
- [ ] Service starts automatically (no manual intervention needed)
- [ ] Container doesn't require persistent storage
- [ ] Tested locally with `docker run -p <port>:<port> <image>`

---

## 3. Docker Image Requirements

### 3.1 Image Naming Convention

✅ **CORRECT**:
```dockerfile
# Always specify a tag
FROM nginx:1.25
FROM ubuntu:22.04
FROM python:3.11-slim
```

❌ **INCORRECT**:
```dockerfile
# No tag specified - will cause container naming issues
FROM nginx
FROM ubuntu
```

**Why**: Untagged images default to `latest`, but CYBERCOM needs explicit tags for container naming.

---

### 3.2 Port Exposure

All ports MUST be explicitly declared in your Dockerfile:

```dockerfile
# Expose the port your service listens on
EXPOSE 80

# Multiple ports supported
EXPOSE 8080
EXPOSE 3306
```

**Port Assignment**:
- CYBERCOM automatically assigns random ports in range `30000-60000`
- Players receive: `hostname:assigned_port`
- Your service should listen on the `EXPOSE`d port inside the container

**Example**:
```dockerfile
FROM nginx:1.25
EXPOSE 80
# Player connects to: cybercom.example.com:45231
# CYBERCOM maps: 45231 (host) → 80 (container)
```

---

### 3.3 Port-less Challenges (Advanced)

If your challenge does NOT need network access (e.g., local exploitation):

```dockerfile
FROM ubuntu:22.04
# No EXPOSE directive
RUN apt-get update && apt-get install -y gcc
COPY vulnerable_binary /usr/local/bin/
```

**Note**: CYBERCOM will log a warning but allow creation:
```
[CYBERCOM WARNING] Image ubuntu:22.04 has no exposed ports - creating port-less container
```

---

## 4. Port Exposure Rules

### 4.1 Supported Scenarios

| Scenario | Supported | Example |
|----------|-----------|---------|
| Single port (HTTP) | ✅ Yes | `EXPOSE 80` |
| Multiple ports | ✅ Yes | `EXPOSE 22 80 443` |
| No ports (offline challenge) | ✅ Yes | No `EXPOSE` |
| Privileged ports (<1024) | ✅ Yes* | `EXPOSE 22` (mapped to high port) |
| Dynamic ports | ❌ No | Port must be known at build time |

*Privileged ports inside container are OK (mapped to unprivileged host ports)

---

### 4.2 Port Configuration Best Practices

```dockerfile
# ✅ GOOD: Standard service port
FROM nginx:1.25
EXPOSE 80

# ✅ GOOD: Custom application port
FROM node:18
EXPOSE 3000
COPY app.js /app/
CMD ["node", "/app/app.js"]

# ✅ GOOD: Multiple services
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y openssh-server nginx
EXPOSE 22 80

# ❌ BAD: No EXPOSE directive for networked service
FROM nginx:1.25
# Missing EXPOSE 80
# Players won't be able to connect!
```

---

## 5. Flag Injection System

### 5.1 How Flags Are Injected

CYBERCOM automatically injects your challenge's flag into containers in TWO ways:

1. **Environment variable**: `$FLAG`
2. **File**: `/flag.txt`

Your challenge can use either or both methods.

---

### 5.2 Flag Templates

Define custom flag formats using templates:

**Available Placeholders**:
- `<hex>` - Random 6-character hex string (e.g., `a3f29c`)
- `<uuid>` - Full UUID v4 (e.g., `f47ac10b-58cc-4372-a567-0e02b2c3d479`)
- `<user_id>` - Player's user ID (e.g., `42`)
- `<team_id>` - Player's team ID (e.g., `7`)

**Examples**:

```python
# Template: "pwn_<hex>_<hex>"
# Generated: CYBERCOM{pwn_a3f29c_7b8def}

# Template: "user_<user_id>_flag_<hex>"
# Generated: CYBERCOM{user_42_flag_3c9a21}

# Template: "sql_<uuid>"
# Generated: CYBERCOM{sql_f47ac10b-58cc-4372-a567-0e02b2c3d479}
```

**Setting Template in Admin Panel**:
1. Go to Challenge Settings
2. Set "Flag Template" field
3. Example: `web_<hex>_challenge_<hex>`

---

### 5.3 Accessing Flags in Your Challenge

#### Method 1: Environment Variable (Recommended)

```dockerfile
FROM nginx:1.25
COPY index.html /usr/share/nginx/html/
EXPOSE 80

# Flag is automatically available as $FLAG
# CYBERCOM injects: ENV FLAG=CYBERCOM{generated_flag}

CMD ["sh", "-c", "echo $FLAG > /usr/share/nginx/html/secret.txt && nginx -g 'daemon off;'"]
```

#### Method 2: File `/flag.txt` (Auto-created)

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3
COPY server.py /app/
EXPOSE 8080

# CYBERCOM automatically creates /flag.txt with flag contents
CMD ["python3", "/app/server.py"]
```

```python
# server.py
with open('/flag.txt', 'r') as f:
    flag = f.read().strip()
    print(f"Flag is: {flag}")
```

#### Method 3: Script Injection (Advanced)

```dockerfile
FROM nginx:1.25
EXPOSE 80
# CYBERCOM automatically runs:
# sh -c "echo \"$FLAG\" > /flag.txt && nginx -g 'daemon off;'"
```

---

### 5.4 Flag Security

🔒 **Flags are encrypted at rest** using AES-256 in the database.

✅ **DO**:
- Use dynamic templates for unique flags per player
- Hide flags in realistic challenge scenarios
- Make flags retrievable only via exploitation

❌ **DON'T**:
- Hardcode flags in Docker images
- Expose flags in environment variables visible via `/proc`
- Store flags in world-readable locations without challenge logic

---

## 6. Security Guidelines

### 6.1 Container Security

```dockerfile
# ✅ GOOD: Run as non-root user
FROM ubuntu:22.04
RUN useradd -m -u 1000 ctfuser
USER ctfuser
WORKDIR /home/ctfuser
```

```dockerfile
# ⚠️ ACCEPTABLE: Root required for service (nginx, sshd)
FROM nginx:1.25
# nginx drops privileges automatically
```

```dockerfile
# ❌ BAD: Unnecessary root escalation
FROM ubuntu:22.04
RUN chmod u+s /bin/bash
# Don't give players unintended root access!
```

---

### 6.2 Forbidden Practices

❌ **NEVER**:
1. Use `--privileged` mode (not supported by CYBERCOM)
2. Mount host filesystems (`-v /:/host`)
3. Expose Docker socket (`/var/run/docker.sock`)
4. Use `NET_ADMIN` or `SYS_ADMIN` capabilities
5. Hardcode admin credentials
6. Include backdoors or unintended exploits

✅ **ALWAYS**:
1. Minimize attack surface (only install needed packages)
2. Use official base images
3. Keep images updated
4. Document intended solution
5. Test challenge in isolated environment

---

### 6.3 Resource Limits

**CPU/Memory**:
- CYBERCOM doesn't enforce strict limits per container
- Design challenges to be lightweight
- Avoid CPU-intensive operations (mining, brute-force)

**Storage**:
- Container filesystems are ephemeral
- No persistent storage between runs
- Players get fresh container each time

**Network**:
- Outbound internet access: Depends on deployment config
- Inbound: Only via assigned ports
- Container-to-container: Isolated

---

## 7. Resource Best Practices

### 7.1 Image Size Optimization

```dockerfile
# ✅ GOOD: Multi-stage builds
FROM golang:1.21 AS builder
WORKDIR /app
COPY . .
RUN go build -o server

FROM alpine:3.18
COPY --from=builder /app/server /usr/local/bin/
EXPOSE 8080
CMD ["server"]
# Final image: ~10MB
```

```dockerfile
# ❌ BAD: Bloated image
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    python3-pip \
    git \
    vim \
    curl
# Unnecessary packages increase size to 800MB+
```

---

### 7.2 Startup Time

```dockerfile
# ✅ GOOD: Fast startup
FROM nginx:1.25-alpine
COPY index.html /usr/share/nginx/html/
EXPOSE 80
# Starts in <1 second
```

```dockerfile
# ❌ BAD: Slow startup
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y build-essential
RUN pip install --upgrade pip setuptools wheel
RUN pip install numpy pandas scikit-learn tensorflow
# Takes 30+ seconds to start
```

**Target**: Container should be ready in <5 seconds

---

### 7.3 Container Lifetime

**Default Runtime**: 15 minutes

**Extensions**: Players can extend 5 times (15 min each)

**Hard Cap**: 90 minutes total

**Design Guidelines**:
- Challenge should be solvable in 5-10 minutes by experienced players
- Provide clear hints to avoid time wastage
- Don't require brute-force operations taking >5 minutes

---

## 8. Common Mistakes & Solutions

### 8.1 "Container won't start"

**Symptom**: Container created but not accessible

**Causes**:
```dockerfile
# ❌ Service not running
FROM nginx:1.25
# CMD missing - nginx doesn't start
```

**Fix**:
```dockerfile
# ✅ Explicit CMD
FROM nginx:1.25
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

### 8.2 "Players can't connect"

**Symptom**: Connection refused/timeout

**Cause**:
```dockerfile
# ❌ Missing EXPOSE
FROM python:3.11
COPY server.py /app/
CMD ["python", "/app/server.py"]  # Listens on port 8080
```

**Fix**:
```dockerfile
# ✅ Add EXPOSE
FROM python:3.11
COPY server.py /app/
EXPOSE 8080  # ← This is required!
CMD ["python", "/app/server.py"]
```

---

### 8.3 "Flag not found"

**Symptom**: Players exploit correctly but can't find flag

**Cause**:
```python
# ❌ Wrong environment variable name
import os
secret = os.environ.get('SECRET_FLAG')  # Wrong name!
```

**Fix**:
```python
# ✅ Use correct name
import os
flag = os.environ.get('FLAG')  # Correct!
# Or read from file:
with open('/flag.txt', 'r') as f:
    flag = f.read().strip()
```

---

### 8.4 "Container crashes immediately"

**Symptom**: Container exits right after starting

**Cause**:
```dockerfile
# ❌ CMD exits immediately
FROM ubuntu:22.04
CMD ["echo", "Hello"]  # Runs and exits
```

**Fix**:
```dockerfile
# ✅ Long-running process
FROM ubuntu:22.04
CMD ["tail", "-f", "/dev/null"]  # Keeps running
# Or better: run actual service
CMD ["python3", "-m", "http.server", "8080"]
```

---

### 8.5 "Port collision errors"

**Symptom**: "Port already in use" in logs

**Explanation**: CYBERCOM handles port allocation automatically. You don't need to worry about this - it's a platform issue, not your challenge.

**If persistent**: Contact admin - might be CYBERCOM port allocation bug.

---

## 9. Testing Your Challenge

### 9.1 Local Testing Checklist

```bash
# 1. Build your image
docker build -t my-challenge:1.0 .

# 2. Test flag injection
docker run -e FLAG="CYBERCOM{test_flag_12345}" -p 8080:80 my-challenge:1.0

# 3. Verify port access
curl http://localhost:8080

# 4. Check flag retrieval
docker exec <container_id> cat /flag.txt
# Should show: CYBERCOM{test_flag_12345}

# 5. Test intended solution
# (Exploit challenge as player would)

# 6. Verify cleanup
docker stop <container_id>
docker rm <container_id>
```

---

### 9.2 CYBERCOM Platform Testing

1. Upload image to platform registry
2. Create challenge in admin panel
3. Set flag template (e.g., `test_<hex>_<hex>`)
4. Test as player:
   - Request container
   - Verify connection details
   - Exploit challenge
   - Submit flag
   - Verify auto-cleanup after 15 minutes

---

## 10. Troubleshooting

### 10.1 Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Image has no exposed ports` | Missing `EXPOSE` directive | Add `EXPOSE <port>` to Dockerfile |
| `Container creation failed` | Invalid Docker image | Check image exists and is accessible |
| `No active container found` | Container expired | Request new container |
| `Maximum extensions reached` | Hit 5-extension limit | Complete challenge or start fresh |

---

### 10.2 Debug Tips

**Check Container Logs**:
```bash
docker logs <container_id>
```

**Inspect Container**:
```bash
docker inspect <container_id>
```

**Test Flag Injection**:
```bash
docker run -it --rm -e FLAG="TEST" my-challenge:1.0 /bin/sh
echo $FLAG  # Should print: TEST
cat /flag.txt  # Should contain: TEST
```

---

## 11. Example Challenges

### 11.1 Simple Web Challenge (Nginx)

**Dockerfile**:
```dockerfile
FROM nginx:1.25-alpine
EXPOSE 80

# Flag will be injected automatically by CYBERCOM
# We just make it accessible via web path
CMD ["sh", "-c", "echo \"$FLAG\" > /usr/share/nginx/html/secret.txt && nginx -g 'daemon off;'"]
```

**Flag Template**: `web_<hex>_easy`

**Solution**: `curl http://host:port/secret.txt`

---

### 11.2 Python API Challenge

**Dockerfile**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY server.py /app/
EXPOSE 8080

# Flag injected as environment variable
CMD ["python3", "server.py"]
```

**server.py**:
```python
from flask import Flask
import os

app = Flask(__name__)
FLAG = os.environ.get('FLAG', 'CYBERCOM{default_flag}')

@app.route('/api/secret')
def secret():
    return {'flag': FLAG}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

**Flag Template**: `api_<uuid>`

**Solution**: `curl http://host:port/api/secret`

---

### 11.3 SSH Challenge

**Dockerfile**:
```dockerfile
FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd

# Create user with password
RUN useradd -m -s /bin/bash ctfuser && \
    echo 'ctfuser:password123' | chpasswd

# Flag will be in /flag.txt (auto-injected)
EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]
```

**Flag Template**: `ssh_<hex>_challenge_<hex>`

**Solution**:
```bash
ssh ctfuser@host -p PORT
# Password: password123
cat /flag.txt
```

---

## 12. Advanced Topics

### 12.1 Multi-Service Challenges

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    nginx \
    mysql-server \
    supervisor

COPY supervisord.conf /etc/supervisor/conf.d/
EXPOSE 80 3306

CMD ["/usr/bin/supervisord"]
```

**Note**: Each service should be non-blocking and managed by supervisor.

---

### 12.2 Build-time vs Runtime Flags

**Build-time** (❌ Don't do this):
```dockerfile
# Flag baked into image - ALL players see same flag!
RUN echo "CYBERCOM{static_flag}" > /flag.txt
```

**Runtime** (✅ Correct):
```dockerfile
# Flag injected at container start - unique per player
# CYBERCOM handles this automatically
CMD ["sh", "-c", "echo $FLAG > /flag.txt && start-service"]
```

---

## 13. Contribution Guidelines

### How to Submit a Challenge

1. Create Dockerfile and test locally
2. Document intended solution
3. Create challenge metadata:
   ```yaml
   name: "SQL Injection Challenge"
   category: "Web"
   difficulty: "Medium"
   points: 100
   flag_template: "sql_<hex>_<hex>"
   description: |
     Find and exploit the SQL injection vulnerability.
     Connection details provided after container start.
   ```
4. Submit via admin panel or contact platform admin

---

## 14. Support & Contact

**Questions?** Contact platform administrators.

**Found a Bug?** Report to: admin@cybercom-ctf.com

**Documentation Updates**: This handbook is versioned. Check for updates regularly.

---

## 15. Appendix

### A. Flag Format

All flags follow format: `CYBERCOM{content}`

**Examples**:
- `CYBERCOM{web_a3f29c_7b8def}`
- `CYBERCOM{user_42_flag_3c9a21}`
- `CYBERCOM{sql_f47ac10b-58cc-4372-a567-0e02b2c3d479}`

### B. Supported Base Images

- `ubuntu:20.04`, `ubuntu:22.04`
- `debian:11`, `debian:12`
- `alpine:3.18`, `alpine:3.19`
- `nginx:1.25`
- `python:3.9`, `python:3.10`, `python:3.11`
- `node:16`, `node:18`, `node:20`
- Any DockerHub public image

### C. Resource Limits

| Resource | Limit |
|----------|-------|
| Image Size | 2GB (soft limit) |
| Memory | No hard limit (be reasonable) |
| CPU | No hard limit (don't mine crypto) |
| Storage | Ephemeral only |
| Network | Isolated, no inter-container |
| Runtime | 15 min base, 90 min hard cap |
| Extensions | 5 max (15 min each) |

---

**Version History**:
- v1.0.0 (2025-11-23): Initial release with CYBERCOM Runtime Engine integration

---

**End of Handbook** 🎯

