# Security Policy

## 🔒 Overview

CYBERCOM CTF 2026 takes security seriously. This document outlines our security policy, how to report vulnerabilities, and our security practices.

---

## 🛡️ Security Features

CYBERCOM CTF 2026 has been hardened with enterprise-grade security features:

### Phase 2 Security Hardening

- **V-001 Fixed**: GDPR Consent TOCTOU race condition eliminated with atomic transactions and row-level locking
- **V-002 Fixed**: Audit trail immutability enforced at database level with MySQL triggers
- **Red Team Validated**: Comprehensive adversarial testing with 7 attack scenarios
- **Defense-in-Depth**: 4 security layers (application, transaction, constraints, triggers)

### Security Architecture

1. **Database-Level Protections**
   - Immutable audit trails (INSERT-only enforcement)
   - Row-level locking for critical operations
   - Advisory locks for race condition prevention
   - UNIQUE constraints for atomicity

2. **Cryptographic Integrity**
   - HMAC-SHA256 signatures on Redis cache entries
   - SHA256 hashing for PII (IP addresses)
   - Secure random flag generation

3. **GDPR Compliance**
   - Atomic consent verification
   - Zero TOCTOU race windows
   - User consent required for analytics
   - PII sanitization and minimization

4. **Container Security**
   - Docker socket proxy (no direct daemon access)
   - Network isolation for challenge containers
   - Resource limits and quotas
   - Time-based lifecycle management

---

## 🚨 Reporting a Vulnerability

### Critical Rule

**DO NOT** open a public GitHub issue for security vulnerabilities.

### Reporting Process

If you discover a security vulnerability in CYBERCOM CTF 2026:

1. **Email Us**: security@cybercom-ctf.local

2. **Subject Line**: `[SECURITY] Brief Description`

3. **Include in Your Report**:
   - **Vulnerability Type**: (e.g., SQL Injection, XSS, Race Condition)
   - **Affected Component**: (e.g., Phase 2 API, Docker challenges)
   - **Severity**: (Critical, High, Medium, Low)
   - **Steps to Reproduce**: Detailed reproduction steps
   - **Proof of Concept**: Code or screenshots demonstrating the issue
   - **Impact Assessment**: Potential consequences
   - **Suggested Fix**: (Optional) Proposed remediation
   - **Your Contact Info**: For follow-up questions

### What to Expect

- **Initial Response**: Within 48 hours
- **Vulnerability Assessment**: Within 5 business days
- **Fix Timeline**: Based on severity
  - **Critical**: 7 days
  - **High**: 14 days
  - **Medium**: 30 days
  - **Low**: 60 days
- **Disclosure**: Coordinated disclosure after fix deployment

### Recognition

We believe in recognizing security researchers:

- **Hall of Fame**: Listed in our security acknowledgments
- **CVE Assignment**: For significant vulnerabilities
- **Public Credit**: In our security advisory (if desired)
- **Bug Bounty**: (Under consideration for future implementation)

---

## 🔍 Supported Versions

Security updates are provided for the following versions:

| Version | Supported | Status |
|---------|-----------|--------|
| Phase 2 v1.0 (Current) | ✅ Yes | Active support |
| Phase 1.x | ⚠️ Limited | Critical fixes only |
| Phase B/C (Legacy) | ❌ No | End of life |

---

## 🛠️ Security Best Practices for Deployment

### Production Deployment

When deploying CYBERCOM CTF 2026 in production:

#### 1. **Environment Configuration**

```bash
# Use strong, random secrets
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_PASSWORD=$(openssl rand -base64 32)

# Disable debug mode
FLASK_ENV=production
DEBUG=False
```

#### 2. **Database Hardening**

```sql
-- Create dedicated database user with minimal privileges
CREATE USER 'cybercom'@'%' IDENTIFIED BY 'strong_password';
GRANT SELECT, INSERT ON ctfd.* TO 'cybercom'@'%';
GRANT UPDATE ON ctfd.users TO 'cybercom'@'%';
-- DO NOT grant UPDATE on phase2_verdict_history (immutable)

-- Verify triggers are active
SHOW TRIGGERS WHERE `Table` = 'phase2_verdict_history';
```

#### 3. **Network Security**

- Use HTTPS/TLS for all connections
- Configure firewalls to restrict database access
- Isolate challenge containers on separate networks
- Enable Docker socket proxy (never expose raw socket)

#### 4. **Access Control**

- Implement strong password policies
- Enable two-factor authentication (if available)
- Regularly audit admin accounts
- Use least-privilege principle

#### 5. **Monitoring & Logging**

```bash
# Monitor for security violations
docker compose logs ctfd | grep "SECURITY VIOLATION"

# Track failed login attempts
docker compose logs ctfd | grep "Failed login"

# Monitor Phase 2 security events
docker compose logs ctfd | grep "PHASE2.*WARNING"
```

---

## 🔐 Known Security Considerations

### 1. Docker Socket Access

**Risk**: Docker socket proxy provides filtered access to Docker daemon

**Mitigation**:
- Use `tecnativa/docker-socket-proxy` with read-only permissions
- Limit exposed API endpoints (CONTAINERS, IMAGES, NETWORKS only)
- Never expose raw `/var/run/docker.sock`

**Configuration**:
```yaml
docker-proxy:
  environment:
    CONTAINERS: 1
    IMAGES: 1
    NETWORKS: 1
    VOLUMES: 1
    # CRITICAL: Keep these disabled
    ALLOW_RESTARTS: 0
    ALLOW_STOP: 0
    BUILD: 0
    EXEC: 0
```

### 2. Challenge Container Isolation

**Risk**: Challenge containers could potentially attack host or other containers

**Mitigation**:
- Network isolation per container
- Resource limits (CPU, memory)
- No privileged containers
- Time-based auto-cleanup

**Recommended**:
```yaml
# In docker-compose.yml for challenge containers
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

### 3. Dynamic Flag Generation

**Risk**: Predictable flag patterns could be brute-forced

**Mitigation**:
- Use `secrets.token_hex()` for secure randomness
- Minimum 6 characters per `<hex>` placeholder
- Store flags with HMAC verification
- Rate limit submission attempts

### 4. GDPR and Privacy

**Risk**: Collecting user data without proper consent

**Mitigation**:
- Explicit opt-in consent required
- Atomic consent verification (V-001 fix)
- PII sanitization (SHA256 hashing)
- Right to erasure implemented

---

## 🧪 Security Testing

### Red Team Scripts

Validate security hardening with included attack scripts:

```bash
# Run all security tests
./redteam_execute_all.sh

# Test specific vulnerabilities
docker compose exec ctfd python redteam_b1_consent_race.py  # V-001
docker compose exec ctfd python redteam_c1_verdict_tampering.py  # V-002
docker compose exec ctfd python redteam_d1_hmac_forgery.py  # Cache integrity
```

### Manual Security Checks

```bash
# 1. Verify audit trail immutability
docker compose exec db mysql -u root -pctfd ctfd -e \
  "UPDATE phase2_verdict_history SET verdict='TEST' WHERE id=1;"
# Expected: ERROR 1644 (45000): SECURITY VIOLATION

# 2. Check GDPR consent enforcement
docker compose logs ctfd | grep "Skipping suspicion.*no consent"

# 3. Verify Redis HMAC signatures
docker compose exec cache redis-cli GET "phase2:first_blood_claimed:1"
# Should contain HMAC signature

# 4. Test first blood race protection
# Run redteam_a2_distributed_race.py - only 1 first blood should be awarded
```

---

## 📋 Security Checklist for Administrators

Before going live with CYBERCOM CTF 2026:

- [ ] Change all default passwords
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Restrict database access
- [ ] Enable Redis password authentication
- [ ] Run all red team tests
- [ ] Verify audit triggers are active
- [ ] Review admin account list
- [ ] Enable access logging
- [ ] Set up security monitoring
- [ ] Test backup/restore procedures
- [ ] Review GDPR compliance settings
- [ ] Configure rate limiting
- [ ] Test incident response plan

---

## 🔄 Security Update Process

### Applying Security Updates

1. **Backup Database**
   ```bash
   docker compose exec db mysqldump -u root -pctfd ctfd > backup_$(date +%Y%m%d).sql
   ```

2. **Pull Latest Code**
   ```bash
   git fetch upstream
   git merge upstream/master
   ```

3. **Apply Database Migrations**
   ```bash
   docker compose exec ctfd flask db upgrade
   ```

4. **Verify Security Triggers**
   ```bash
   docker compose exec db mysql -u root -pctfd ctfd < create_audit_triggers.sql
   ```

5. **Run Security Tests**
   ```bash
   ./redteam_execute_all.sh
   ```

6. **Restart Services**
   ```bash
   docker compose restart
   ```

---

## 📞 Security Contact

### Primary Contact

- **Email**: security@cybercom-ctf.local
- **Response Time**: Within 48 hours
- **PGP Key**: Available on request

### Emergency Contact

For critical, actively exploited vulnerabilities:

- **Priority Email**: security-urgent@cybercom-ctf.local
- **Response Time**: Within 12 hours

---

## 📚 Security Resources

### Documentation

- [Security Hardening Report](docs/SECURITY_HARDENING_REPORT.md)
- [Backend Hardening Audit](docs/CYBERCOM_BACKEND_HARDENING_AUDIT.md)
- [Red Team Assessment Report](REDTEAM_ASSESSMENT_REPORT.md)
- [Vulnerability Remediation Report](VULNERABILITY_REMEDIATION_COMPLETE.md)

### External Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

## 🙏 Acknowledgments

We thank the following security researchers for responsible disclosure:

- **CYBERCOM Red Team** - Phase 2 security hardening (2025-11-24)
- *Your name could be here - report vulnerabilities responsibly!*

---

## 📄 Legal

### Disclosure Policy

- **Coordinated Disclosure**: We prefer coordinated disclosure with a 90-day window
- **Public Disclosure**: After fix deployment, we will publish a security advisory
- **CVE Assignment**: Significant vulnerabilities will receive CVE identifiers

### Scope

This security policy applies to:

- ✅ CYBERCOM CTF 2026 platform code
- ✅ Phase 2 Intelligence Layer
- ✅ CRE (Container Runtime Extension)
- ✅ Custom plugins and extensions
- ❌ Third-party plugins (report to plugin authors)
- ❌ Deployment-specific configurations (user responsibility)

---

**Last Updated**: November 24, 2025
**Policy Version**: 1.0
**Classification**: Public

---

**CYBERCOM CTF 2026** - *Secure by Design, Hardened by Testing*
