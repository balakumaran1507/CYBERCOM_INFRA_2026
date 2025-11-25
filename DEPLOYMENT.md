# CYBERCOM CTF Infrastructure - Deployment Guide

## Quick Start (Fresh Machine)

**Works on: Linux | macOS | WSL | Cloud (AWS/DigitalOcean)**

```bash
# 1. Clone repository
git clone https://github.com/balakumaran1507/CYBERCOM_INFRA_2026.git
cd CYBERCOM_INFRA_2026

# 2. Initialize data directories (REQUIRED before first run)
./init-data-dirs.sh

# 3. Build and start (health checks ensure proper startup order)
docker compose build
docker compose up -d

# 4. Wait for services to be healthy (~30-60 seconds on fresh install)
docker compose ps  # Check all services show "healthy" or "Up"

# 5. Access platform
# Open browser to: http://localhost:8000
```

**IMPORTANT**: On fresh clones, the database needs ~30-60 seconds to initialize.
Docker health checks ensure CTFd doesn't start until the database is ready.

## System Requirements

- **Docker**: 20.10+
- **Docker Compose**: v2+
- **Git**: 2.0+
- **Disk Space**: 10GB+ recommended
- **RAM**: 4GB+ recommended

## Initial Setup

On first run, CTFd will show the setup wizard at `http://localhost:8000`

### Setup Configuration:
1. **Event Name**: CYBERCOM CTF 2026
2. **Mode**: Teams or Users (choose based on competition type)
3. **Admin Account**: Create your credentials
4. **Theme**: cybercom_ui (pre-configured)

## Architecture

### Docker Services:
- **ctfd**: Main CTFd application (port 8000)
- **db**: MariaDB 10.11 (persistent data)
- **cache**: Redis 4 (sessions/cache)
- **nginx**: Reverse proxy (port 80)
- **docker-proxy**: Docker socket proxy for Whale plugin

### Data Persistence:
All data stored in `.data/` directory (gitignored):
- `.data/mysql/` - Database files
- `.data/redis/` - Cache data
- `.data/CTFd/logs/` - Application logs
- `.data/CTFd/uploads/` - File uploads

**IMPORTANT**: The `.data/` directory is gitignored. The `init-data-dirs.sh` script MUST be run before first deployment.

## Plugins

### Pre-installed:
- **Whale**: Dynamic Docker challenge provisioning
- **Phase2**: Intelligence layer (first blood, health monitoring, flag sharing detection)
- **CYBERCOM UI**: Custom Japanese Cyber Minimal theme

### Plugin Status Check:
```bash
docker compose logs ctfd | grep -E "(Whale|PHASE2|Started successfully)"
```

Expected output:
```
[CTFd Whale] Started successfully
[PHASE2] 🎯 Phase 2 Intelligence Layer initialized successfully
```

## Troubleshooting

### Database Init Failure
**Symptom**: `Can't create database 'ctfd'`

**Solution**:
```bash
# Ensure data directories exist
./init-data-dirs.sh

# Restart database
docker compose restart db
docker compose restart ctfd
```

### Whale Plugin Missing
**Symptom**: Container challenges don't work

**Verification**:
```bash
git ls-files CTFd/plugins/whale/__init__.py
```

Should return: `CTFd/plugins/whale/__init__.py`

If empty, the Whale plugin was not properly cloned. This should not happen with commit 426a8f7+.

### Port Conflicts
**Symptom**: `port is already allocated`

**Solution**:
```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :80

# Stop conflicting service or change ports in docker-compose.yml
```

### Redis MISCONF Error
**Symptom**: `MISCONF Redis is configured to save RDB snapshots, but is currently not able to persist on disk`

**Root Cause**: Redis container (UID 999) cannot write to `.data/redis` directory due to permission mismatch.

**Solution**:
```bash
# Stop containers (NOT docker compose down -v)
docker compose down

# Fix permissions - CHOOSE ONE:

# Option A: World-writable (quick fix, works everywhere)
chmod 777 .data/redis .data/mysql

# Option B: Proper ownership (requires sudo, more secure)
sudo chown -R 999:999 .data/redis .data/mysql
chmod 755 .data/redis .data/mysql

# Restart
docker compose up -d
```

**Prevention**: Always run `./init-data-dirs.sh` before first deployment. This script sets correct permissions automatically.

**Verification**:
```bash
docker compose logs cache --tail=20
```

Should NOT show "Permission denied" or "Background saving error".

### Cache Issues
**Solution**:
```bash
docker compose exec cache redis-cli FLUSHALL
docker compose restart ctfd
```

## Maintenance

### View Logs:
```bash
docker compose logs -f ctfd     # CTFd logs
docker compose logs -f db       # Database logs
docker compose logs -f nginx    # Web server logs
```

### Backup Data:
```bash
# Backup database
docker compose exec db mysqldump -uctfd -pctfd ctfd > backup.sql

# Backup uploads
tar -czf uploads_backup.tar.gz .data/CTFd/uploads/
```

### Update Platform:
```bash
git pull
docker compose build
docker compose up -d
```

## Production Deployment

### Security Checklist:
- [ ] Change default database password in `docker-compose.yml`
- [ ] Configure HTTPS with valid SSL certificate
- [ ] Set up firewall rules (allow 80/443, block 8000)
- [ ] Enable CTFd security headers
- [ ] Configure rate limiting
- [ ] Set up automated backups
- [ ] Monitor logs for suspicious activity

### Performance Tuning:
- Increase `max_connections` in MariaDB for large events
- Scale Redis memory limits for high traffic
- Use CDN for static assets
- Enable Gunicorn workers scaling

## Support

### Platform Status:
- Whale: ✅ Vendored in repository
- Phase2: ✅ Fully integrated
- CYBERCOM UI: ✅ Production-ready

### Common URLs:
- Main site: `http://localhost:8000`
- Admin panel: `http://localhost:8000/admin`
- Challenges: `http://localhost:8000/challenges`
- Scoreboard: `http://localhost:8000/scoreboard`

## License

CTFd is licensed under Apache 2.0
CYBERCOM customizations: Proprietary

---

**Version**: 2.0.0
**Last Updated**: 2025-11-25
**Maintainer**: CYBERCOM Security Team
