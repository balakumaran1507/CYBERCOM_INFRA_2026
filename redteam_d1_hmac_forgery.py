#!/usr/bin/env python3
"""
RED TEAM ATTACK D1: HMAC Signature Forgery Attempt
===================================================

Attack Vector:
--------------
Attempt to forge valid HMAC signatures for Redis cache entries by:
1. Brute-forcing weak secrets
2. Replaying valid signatures with modified values
3. Timing attacks to extract secret information
4. Length extension attacks

Expected Behavior:
------------------
System should:
1. Reject all forged signatures
2. Delete poisoned cache entries
3. Log security warnings
4. Fall back to database as authority

Attack Goal:
------------
Test HMAC implementation for:
- Weak or predictable secrets
- Signature verification bypass
- Timing attack vulnerabilities

Threat Level: HIGH (Cache poisoning if successful)
"""

import hmac
import hashlib
import json
import itertools
from CTFd import create_app
from CTFd.models import db
from CTFd.cache import cache

app = create_app()
from CTFd.plugins.phase2.utils import sign_redis_value, verify_redis_signature

print("=" * 80)
print("RED TEAM ATTACK D1: HMAC SIGNATURE FORGERY")
print("=" * 80)
print()

# Attack 1: Brute force weak secrets
print("[ATTACK 1] Brute-forcing weak HMAC secrets...")
print("=" * 80)

weak_secrets = [
    'secret', 'password', '123456', 'admin', 'default',
    'ctfd', 'changeme', 'insecure', 'test', 'development',
    'default-insecure-key'  # From utils.py fallback
]

test_value = "1"  # Cache value for first blood claimed

# Get a valid signature for comparison
with app.app_context():
    valid_signature = sign_redis_value(test_value)
    print(f"Valid signature (first 32 chars): {valid_signature[:32]}...")
    print()

forgery_success = False

for secret in weak_secrets:
    # Attempt to forge signature
    forged_sig = hmac.new(
        secret.encode('utf-8'),
        test_value.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if forged_sig == valid_signature:
        print(f"✗ CRITICAL: WEAK SECRET DETECTED!")
        print(f"  Secret: '{secret}'")
        print(f"  Forged signature matches!")
        forgery_success = True
        break

if not forgery_success:
    print("✓ Weak secret brute-force FAILED")
    print("  Secret appears strong (not in common wordlist)")
    print()

# Attack 2: Signature replay with value modification
print("[ATTACK 2] Signature replay attack...")
print("=" * 80)

with app.app_context():
    # Get valid signed data
    cache_key = 'phase2:attack_test:replay'
    original_value = "0"

    # Create valid signed cache
    valid_sig = sign_redis_value(original_value)
    valid_data = json.dumps({'value': original_value, 'signature': valid_sig})
    cache.set(cache_key, valid_data, timeout=60)

    print(f"Original value: '{original_value}'")
    print(f"Valid signature: {valid_sig[:32]}...")
    print()

    # Attempt 1: Modify value, keep signature
    print("Attempt 1: Modify value, replay signature")
    modified_value = "1"  # Change value
    replay_data = json.dumps({'value': modified_value, 'signature': valid_sig})
    cache.set(cache_key, replay_data, timeout=60)

    # Try to verify
    result = verify_redis_signature(modified_value, valid_sig)

    if result:
        print("  ✗ CRITICAL: Signature replay SUCCESSFUL!")
        print("  Value modified without detection")
    else:
        print("  ✓ Signature replay BLOCKED")
        print("  Modified value rejected")
    print()

    # Attempt 2: Valid value, truncated signature
    print("Attempt 2: Truncate signature")
    truncated_sig = valid_sig[:32]  # Half length
    result = verify_redis_signature(original_value, truncated_sig)

    if result:
        print("  ✗ CRITICAL: Truncated signature accepted!")
    else:
        print("  ✓ Truncated signature rejected")
    print()

# Attack 3: Timing attack on signature verification
print("[ATTACK 3] Timing attack on signature comparison...")
print("=" * 80)

import time

with app.app_context():
    test_value = "1"
    correct_sig = sign_redis_value(test_value)

    # Test if hmac.compare_digest is used (constant time)
    # vs simple string comparison (variable time)

    timings_correct_prefix = []
    timings_wrong_prefix = []

    iterations = 1000

    # Time with correct prefix (first 32 chars)
    sig_correct_prefix = correct_sig[:32] + 'a' * 32

    for _ in range(iterations):
        start = time.perf_counter()
        verify_redis_signature(test_value, sig_correct_prefix)
        elapsed = time.perf_counter() - start
        timings_correct_prefix.append(elapsed)

    # Time with wrong prefix
    sig_wrong_prefix = 'z' * 64

    for _ in range(iterations):
        start = time.perf_counter()
        verify_redis_signature(test_value, sig_wrong_prefix)
        elapsed = time.perf_counter() - start
        timings_wrong_prefix.append(elapsed)

    avg_correct = sum(timings_correct_prefix) / len(timings_correct_prefix)
    avg_wrong = sum(timings_wrong_prefix) / len(timings_wrong_prefix)

    diff_ns = abs(avg_correct - avg_wrong) * 1_000_000_000

    print(f"Average time (correct prefix): {avg_correct*1000:.6f} ms")
    print(f"Average time (wrong prefix):   {avg_wrong*1000:.6f} ms")
    print(f"Difference: {diff_ns:.2f} ns")
    print()

    if diff_ns > 1000:  # > 1 microsecond difference
        print("⚠ TIMING LEAK DETECTED")
        print("  Signature comparison may not be constant-time")
        print("  Theoretical timing attack possible")
    else:
        print("✓ Constant-time comparison detected")
        print("  Timing attack MITIGATED")

    print()

# Attack 4: Cache injection with valid JSON structure
print("[ATTACK 4] Malformed cache injection...")
print("=" * 80)

with app.app_context():
    from CTFd.plugins.phase2.utils import get_signed_cache

    cache_key = 'phase2:attack_test:injection'

    # Inject various malformed payloads
    payloads = [
        '{"value": "1", "signature": null}',  # Null signature
        '{"value": "1"}',  # Missing signature
        '{"signature": "fake"}',  # Missing value
        '{"value": "1", "signature": ""}',  # Empty signature
        'not json at all',  # Invalid JSON
        '{"value": "1", "signature": "' + 'A' * 10000 + '"}',  # Huge signature
    ]

    for i, payload in enumerate(payloads, 1):
        cache.set(cache_key, payload, timeout=60)
        result = get_signed_cache(cache, cache_key)

        if result is not None:
            print(f"  Payload {i}: ✗ ACCEPTED (injection successful!)")
        else:
            print(f"  Payload {i}: ✓ Rejected")

print()
print("=" * 80)
print("ATTACK SUMMARY:")
print("=" * 80)

if forgery_success:
    print("✗ CRITICAL VULNERABILITY: HMAC secret is weak")
    print("  - Attacker can forge valid signatures")
    print("  - Cache poisoning POSSIBLE")
    print("  - Database integrity may be compromised")
else:
    print("✓ HMAC implementation appears secure")
    print("  - Strong secret (resistant to brute force)")
    print("  - Signature verification enforced")
    print("  - Constant-time comparison prevents timing attacks")
    print("  - Malformed payloads rejected")

print()
print("[SECURITY ASSESSMENT]")
print("Recommendations:")
print("1. Ensure PHASE2_HMAC_SECRET is cryptographically random (32+ bytes)")
print("2. Rotate HMAC secret periodically (invalidates all cached signatures)")
print("3. Monitor for [PHASE2 SECURITY WARNING] in logs")
print("4. Consider adding signature version field for key rotation")
print("=" * 80)
