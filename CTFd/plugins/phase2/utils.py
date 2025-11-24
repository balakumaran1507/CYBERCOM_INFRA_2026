"""
Phase 2 Utilities
=================

Helper functions for:
- Prestige score calculation
- Challenge health scoring
- Confidence calculations
- Data cleanup
- Redis cache integrity (HMAC signing)
"""

import datetime
import hmac
import hashlib
import os
from CTFd.models import db, Challenges, Solves, Submissions
from .models import FirstBloodPrestige, FlagSharingSuspicion, ChallengeHealthSnapshot
from .config import Phase2Config


# ============================================================================
# PII SANITIZATION (GDPR Compliance)
# ============================================================================

def hash_ip(ip_address):
    """
    Hash IP address for privacy-preserving storage.

    SECURITY: One-way SHA256 hash prevents IP recovery while allowing
    duplicate IP detection (same IP = same hash).

    Args:
        ip_address (str): IP address to hash

    Returns:
        str: First 16 chars of SHA256 hex hash

    Example:
        >>> hash_ip("192.168.1.1")
        "c775e7b757ede63..."
    """
    if not ip_address:
        return None

    hashed = hashlib.sha256(ip_address.encode('utf-8')).hexdigest()
    return hashed[:16]  # Truncate for readability


def generalize_user_agent(user_agent):
    """
    Generalize user-agent string to browser family + OS family only.

    PRIVACY: Removes identifying information while retaining analytics value.
    Reduces: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
    To: "Chrome on Windows"

    Args:
        user_agent (str): Raw user-agent string

    Returns:
        str: Generalized "Browser on OS" string

    Example:
        >>> generalize_user_agent("Mozilla/5.0 ... Chrome/119.0")
        "Chrome on Windows"
    """
    if not user_agent:
        return "Unknown"

    ua_lower = user_agent.lower()

    # Extract browser family
    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    elif 'edg' in ua_lower:
        browser = 'Edge'
    elif 'opera' in ua_lower or 'opr' in ua_lower:
        browser = 'Opera'
    elif 'msie' in ua_lower or 'trident' in ua_lower:
        browser = 'Internet Explorer'
    else:
        browser = 'Unknown Browser'

    # Extract OS family
    if 'windows' in ua_lower:
        os_family = 'Windows'
    elif 'mac' in ua_lower and 'iphone' not in ua_lower and 'ipad' not in ua_lower:
        os_family = 'macOS'
    elif 'linux' in ua_lower and 'android' not in ua_lower:
        os_family = 'Linux'
    elif 'android' in ua_lower:
        os_family = 'Android'
    elif 'iphone' in ua_lower or 'ipad' in ua_lower:
        os_family = 'iOS'
    else:
        os_family = 'Unknown OS'

    return f"{browser} on {os_family}"


def sanitize_evidence(evidence):
    """
    Sanitize evidence dictionary to remove/hash PII.

    SECURITY: Ensures all evidence stored in suspicion records is GDPR-compliant.

    Transformations:
    - IP addresses → SHA256 hash (first 16 chars)
    - User-agents → Generalized "Browser on OS"
    - Submission text → "[REDACTED]"

    Args:
        evidence (dict): Raw evidence with PII

    Returns:
        dict: Sanitized evidence without PII

    Example:
        >>> sanitize_evidence({'ip': '1.2.3.4', 'submission_text': 'flag{test}'})
        {'ip_hash': 'a3b2c1d4...', 'submission_text': '[REDACTED]'}
    """
    sanitized = {}

    for key, value in evidence.items():
        # Hash IP addresses
        if 'ip' in key.lower() and value and key not in ['ip_hash', 'ip_1_hash', 'ip_2_hash']:
            hash_key = key + '_hash' if not key.endswith('_hash') else key
            sanitized[hash_key] = hash_ip(value)

        # Generalize user-agents
        elif 'user_agent' in key.lower() and value:
            gen_key = key.replace('user_agent', 'browser_os')
            sanitized[gen_key] = generalize_user_agent(value)

        # Redact submission text
        elif 'submission' in key.lower() and 'text' in key.lower():
            sanitized[key] = '[REDACTED]'

        # Keep all other fields as-is (IDs, timestamps, confidence, etc.)
        else:
            sanitized[key] = value

    return sanitized


# ============================================================================
# REDIS CACHE INTEGRITY (HMAC Signing)
# ============================================================================

def get_hmac_secret():
    """
    Get HMAC secret key for Redis cache integrity signatures.

    SECURITY: Uses environment variable or falls back to CTFd SECRET_KEY.
    Changing this key will invalidate all existing cache signatures.

    Returns:
        bytes: Secret key for HMAC signing
    """
    from flask import current_app

    # Try Phase 2 specific secret first
    secret = os.environ.get('PHASE2_HMAC_SECRET')

    if not secret:
        # Fall back to CTFd's SECRET_KEY
        secret = current_app.config.get('SECRET_KEY', 'default-insecure-key')

    # Handle both string and bytes types (SECRET_KEY can be either)
    if isinstance(secret, bytes):
        return secret
    return secret.encode('utf-8')


def sign_redis_value(value):
    """
    Create HMAC signature for Redis cached value.

    SECURITY: Prevents cache poisoning by authenticating cached data.
    Uses SHA256 HMAC with Phase 2 secret key.

    Args:
        value (str): Value to sign (should be string representation)

    Returns:
        str: Hex-encoded HMAC signature

    Example:
        >>> signature = sign_redis_value("first_blood_claimed")
        >>> "a3f5b2c1d4e6f7..."
    """
    secret = get_hmac_secret()
    signature = hmac.new(
        secret,
        value.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_redis_signature(value, signature):
    """
    Verify HMAC signature for Redis cached value.

    SECURITY: Returns False if signature invalid or missing.
    Constant-time comparison prevents timing attacks.

    Args:
        value (str): Cached value to verify
        signature (str): HMAC signature to check

    Returns:
        bool: True if signature valid, False otherwise

    Example:
        >>> if verify_redis_signature("first_blood_claimed", cached_sig):
        ...     # Trust cached value
    """
    if not signature:
        return False

    expected_signature = sign_redis_value(value)

    # Constant-time comparison prevents timing attacks
    return hmac.compare_digest(expected_signature, signature)


def set_signed_cache(cache, key, value, timeout=None):
    """
    Set Redis cache value with HMAC signature for integrity.

    SECURITY: Stores value with signature in JSON format.
    Format: {"value": "...", "signature": "..."}

    Args:
        cache: Flask-Caching cache instance
        key (str): Cache key
        value (str): Value to cache
        timeout (int): TTL in seconds

    Example:
        >>> set_signed_cache(cache, 'phase2:fb:123', '1', timeout=3600)
    """
    import json

    signature = sign_redis_value(value)
    signed_data = json.dumps({
        'value': value,
        'signature': signature
    })

    cache.set(key, signed_data, timeout=timeout)


def get_signed_cache(cache, key):
    """
    Get Redis cache value and verify HMAC signature.

    SECURITY: Returns None if signature invalid or missing.
    Protects against cache poisoning attacks.

    Args:
        cache: Flask-Caching cache instance
        key (str): Cache key

    Returns:
        str|None: Cached value if signature valid, None otherwise

    Example:
        >>> value = get_signed_cache(cache, 'phase2:fb:123')
        >>> if value:
        ...     # Signature verified, trust value
    """
    import json

    cached_data = cache.get(key)

    if not cached_data:
        return None

    try:
        # Parse signed data
        data = json.loads(cached_data)
        value = data.get('value')
        signature = data.get('signature')

        # Verify signature
        if verify_redis_signature(value, signature):
            return value
        else:
            # Signature invalid - cache poisoning attempt or key rotation
            print(f"[PHASE2 SECURITY WARNING] Invalid Redis signature for key: {key}")
            cache.delete(key)  # Remove poisoned cache entry
            return None

    except (json.JSONDecodeError, KeyError, TypeError):
        # Malformed cache data
        print(f"[PHASE2 SECURITY WARNING] Malformed Redis data for key: {key}")
        cache.delete(key)
        return None


def calculate_prestige_score(challenge_value):
    """
    Calculate prestige score for first blood.

    MVP Formula: prestige = challenge_value * 1.5

    Future enhancements could consider:
    - Dynamic difficulty adjustments
    - Solve count at time of first blood
    - Challenge category weighting

    Args:
        challenge_value (int): Challenge point value

    Returns:
        int: Prestige score (rounded)
    """
    if not challenge_value or challenge_value <= 0:
        challenge_value = 100  # Default for dynamic challenges

    prestige = challenge_value * 1.5
    return int(prestige)


def calculate_challenge_health(challenge_id):
    """
    Calculate health score for a challenge.

    Health Score Rules:
    - Base: 100
    - Penalty if solve_rate > 90% (too easy): -20
    - Penalty if solve_rate < 5% (too hard): -30
    - Penalty if attempts < 10 (low engagement): -15

    Status:
    - HEALTHY: score >= 70
    - UNDERPERFORMING: 40 <= score < 70
    - BROKEN: score < 40

    Args:
        challenge_id (int): Challenge ID

    Returns:
        dict: {
            'solves': int,
            'attempts': int,
            'solve_rate': float,
            'health_score': int,
            'status': str
        }
    """
    # Count solves
    solves = Solves.query.filter_by(challenge_id=challenge_id).count()

    # Count attempts (all submissions: correct + incorrect)
    attempts = Submissions.query.filter_by(challenge_id=challenge_id).count()

    # Calculate solve rate
    solve_rate = (solves / attempts) if attempts > 0 else 0.0

    # Base health score
    health_score = 100

    # Apply penalties
    if solve_rate > 0.90:
        health_score -= 20  # Too easy
    elif solve_rate < 0.05 and attempts >= 10:
        health_score -= 30  # Too hard (but only if people tried)

    if attempts < 10:
        health_score -= 15  # Low engagement

    # Ensure score stays in bounds
    health_score = max(0, min(100, health_score))

    # Determine status
    if health_score >= 70:
        status = 'HEALTHY'
    elif health_score >= 40:
        status = 'UNDERPERFORMING'
    else:
        status = 'BROKEN'

    return {
        'solves': solves,
        'attempts': attempts,
        'solve_rate': solve_rate,
        'health_score': health_score,
        'status': status
    }


def calculate_suspicion_confidence(patterns):
    """
    Calculate confidence score for flag sharing suspicion.

    Weights (from config):
    - same_ip: 0.4
    - duplicate_wrong: 0.3
    - similar_ua: 0.2
    - temporal_proximity: 0.1

    Args:
        patterns (list): List of detected pattern types

    Returns:
        float: Confidence score (0.0 to 1.0)
    """
    score = 0.0

    if 'same_ip' in patterns:
        score += Phase2Config.WEIGHT_SAME_IP
    if 'duplicate_wrong' in patterns:
        score += Phase2Config.WEIGHT_DUPLICATE_WRONG
    if 'similar_ua' in patterns:
        score += Phase2Config.WEIGHT_SIMILAR_UA
    if 'temporal_proximity' in patterns:
        score += Phase2Config.WEIGHT_TEMPORAL_PROXIMITY

    # Cap at 1.0
    return min(score, 1.0)


def determine_risk_level(confidence):
    """
    Determine risk level based on confidence score.

    Thresholds:
    - HIGH: >= 0.75
    - MEDIUM: >= 0.5
    - LOW: < 0.5

    Args:
        confidence (float): Confidence score (0.0 to 1.0)

    Returns:
        str: 'HIGH', 'MEDIUM', or 'LOW'
    """
    if confidence >= 0.75:
        return 'HIGH'
    elif confidence >= 0.5:
        return 'MEDIUM'
    else:
        return 'LOW'


def levenshtein_ratio(s1, s2):
    """
    Calculate Levenshtein similarity ratio between two strings.

    Returns:
        float: Similarity ratio (0.0 to 1.0, 1.0 = identical)
    """
    if not s1 or not s2:
        return 0.0

    # Simple implementation for MVP
    # For production, consider python-Levenshtein package
    s1, s2 = s1.lower(), s2.lower()

    # Quick check for exact match
    if s1 == s2:
        return 1.0

    # Calculate Levenshtein distance
    len1, len2 = len(s1), len(s2)
    if len1 > len2:
        s1, s2 = s2, s1
        len1, len2 = len2, len1

    current_row = range(len1 + 1)
    for i in range(1, len2 + 1):
        previous_row, current_row = current_row, [i] + [0] * len1
        for j in range(1, len1 + 1):
            add, delete, change = previous_row[j] + 1, current_row[j - 1] + 1, previous_row[j - 1]
            if s1[j - 1] != s2[i - 1]:
                change += 1
            current_row[j] = min(add, delete, change)

    distance = current_row[len1]
    max_len = max(len(s1), len(s2))

    # Convert to similarity ratio
    ratio = 1.0 - (distance / max_len) if max_len > 0 else 0.0
    return ratio


def cleanup_old_data():
    """
    Clean up Phase 2 data older than retention period.

    Deletes:
    - Suspicion records older than RETENTION_DAYS
    - Health snapshots older than RETENTION_DAYS
    - First blood records are kept forever (prestige is permanent)

    Returns:
        dict: {'suspicions_deleted': int, 'health_deleted': int}
    """
    retention_days = Phase2Config.RETENTION_DAYS
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)

    try:
        # Delete old suspicions
        suspicions_deleted = FlagSharingSuspicion.query.filter(
            FlagSharingSuspicion.created_at < cutoff_date
        ).delete()

        # Delete old health snapshots
        health_deleted = ChallengeHealthSnapshot.query.filter(
            ChallengeHealthSnapshot.timestamp < cutoff_date
        ).delete()

        db.session.commit()

        print(f"[PHASE2 CLEANUP] Deleted {suspicions_deleted} old suspicions, {health_deleted} old health snapshots")

        return {
            'suspicions_deleted': suspicions_deleted,
            'health_deleted': health_deleted
        }

    except Exception as e:
        db.session.rollback()
        print(f"[PHASE2 CLEANUP ERROR] {e}")
        return {'suspicions_deleted': 0, 'health_deleted': 0}


def get_first_blood_leaderboard(limit=100, team_mode=False):
    """
    Get first blood leaderboard.

    Args:
        limit (int): Maximum number of entries
        team_mode (bool): True for team leaderboard, False for individual

    Returns:
        list: [{'rank': 1, 'user_id': 5, 'total_prestige': 1500, 'first_bloods': 3}, ...]
    """
    try:
        if team_mode:
            # Team leaderboard
            results = db.session.query(
                FirstBloodPrestige.team_id,
                db.func.sum(FirstBloodPrestige.prestige_score).label('total_prestige'),
                db.func.count(FirstBloodPrestige.id).label('first_bloods')
            ).filter(
                FirstBloodPrestige.team_id.isnot(None)
            ).group_by(
                FirstBloodPrestige.team_id
            ).order_by(
                db.func.sum(FirstBloodPrestige.prestige_score).desc()
            ).limit(limit).all()

            leaderboard = []
            for rank, (team_id, total_prestige, first_bloods) in enumerate(results, start=1):
                leaderboard.append({
                    'rank': rank,
                    'team_id': team_id,
                    'total_prestige': int(total_prestige or 0),
                    'first_bloods': int(first_bloods or 0)
                })

        else:
            # Individual leaderboard
            results = db.session.query(
                FirstBloodPrestige.user_id,
                db.func.sum(FirstBloodPrestige.prestige_score).label('total_prestige'),
                db.func.count(FirstBloodPrestige.id).label('first_bloods')
            ).filter(
                FirstBloodPrestige.user_id.isnot(None)
            ).group_by(
                FirstBloodPrestige.user_id
            ).order_by(
                db.func.sum(FirstBloodPrestige.prestige_score).desc()
            ).limit(limit).all()

            leaderboard = []
            for rank, (user_id, total_prestige, first_bloods) in enumerate(results, start=1):
                leaderboard.append({
                    'rank': rank,
                    'user_id': user_id,
                    'total_prestige': int(total_prestige or 0),
                    'first_bloods': int(first_bloods or 0)
                })

        return leaderboard

    except Exception as e:
        print(f"[PHASE2 ERROR] get_first_blood_leaderboard failed: {e}")
        return []
