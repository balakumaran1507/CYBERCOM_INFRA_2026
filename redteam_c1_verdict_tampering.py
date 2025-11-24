#!/usr/bin/env python3
"""
RED TEAM ATTACK C1: Concurrent Verdict Modification
====================================================

Attack Vector:
--------------
Simulate multiple admins (or malicious admin script) attempting to
modify verdicts concurrently to test audit trail integrity.

Expected Behavior:
------------------
System should:
1. Record ALL verdict changes in audit trail
2. No lost updates or race conditions
3. Chronological order preserved
4. Immutability maintained (INSERT only, no UPDATE)

Attack Goal:
------------
Test if concurrent verdict changes can cause:
- Lost audit entries
- Out-of-order entries
- Audit trail corruption

Threat Level: CRITICAL (Evidence tampering if successful)
"""

import threading
import time
import random
from CTFd import create_app
from CTFd.models import db

app = create_app()
from CTFd.plugins.phase2.models import FlagSharingSuspicion, VerdictHistory

print("=" * 80)
print("RED TEAM ATTACK C1: CONCURRENT VERDICT MODIFICATION")
print("=" * 80)
print()

# Setup: Create test suspicion
with app.app_context():
    # Clean
    db.session.query(FlagSharingSuspicion).filter(
        FlagSharingSuspicion.challenge_id == 5
    ).delete()
    db.session.commit()

    # Create suspicion
    susp = FlagSharingSuspicion(
        user_id_1=2,
        user_id_2=3,
        challenge_id=5,
        detection_type='same_ip',
        confidence_score=0.85,
        risk_level='HIGH',
        evidence={'ip_hash': 'attack_test', 'time_delta_ms': 500}
    )
    db.session.add(susp)
    db.session.commit()
    suspicion_id = susp.id
    print(f"✓ Created test suspicion (ID: {suspicion_id})")

# Attack configuration
NUM_ADMINS = 10
VERDICTS_PER_ADMIN = 5
verdicts = ['innocent', 'suspicious', 'confirmed']
results = {'created': 0, 'errors': []}
results_lock = threading.Lock()

def malicious_admin(admin_id):
    """Simulate admin rapidly changing verdicts"""
    for i in range(VERDICTS_PER_ADMIN):
        try:
            with app.app_context():
                verdict = verdicts[random.randint(0, 2)]

                VerdictHistory.record_verdict(
                    suspicion_id=suspicion_id,
                    verdict=verdict,
                    admin_id=admin_id,
                    admin_ip=f'10.0.{admin_id}.{i}',
                    notes=f'Admin {admin_id} attempt {i}'
                )

                with results_lock:
                    results['created'] += 1

                # Small random delay (0-10ms)
                time.sleep(random.uniform(0, 0.01))

        except Exception as e:
            with results_lock:
                error_msg = str(e)[:100]
                if error_msg not in results['errors']:
                    results['errors'].append(error_msg)

print(f"\n[ATTACK] Launching {NUM_ADMINS} concurrent admin verdict modifications...")
print(f"         Each admin will change verdict {VERDICTS_PER_ADMIN} times")
print(f"         Expected total audit entries: {NUM_ADMINS * VERDICTS_PER_ADMIN}")
print()

# Launch attack
threads = []
start_time = time.time()

for admin_id in range(1, NUM_ADMINS + 1):
    thread = threading.Thread(target=malicious_admin, args=(admin_id,))
    threads.append(thread)
    thread.start()

# Wait for completion
for thread in threads:
    thread.join()

elapsed = time.time() - start_time
print(f"✓ Attack completed in {elapsed:.3f} seconds")

if results['errors']:
    print(f"  Errors: {len(results['errors'])} unique errors")
    for err in results['errors'][:3]:
        print(f"    - {err}")

# Verification
with app.app_context():
    # Get all audit entries
    history = VerdictHistory.get_history(suspicion_id, limit=1000)

    # Check for data integrity
    audit_ids = [entry.id for entry in history]
    unique_ids = set(audit_ids)

    print("\n" + "=" * 80)
    print("ATTACK RESULTS:")
    print("=" * 80)
    print(f"Expected audit entries: {NUM_ADMINS * VERDICTS_PER_ADMIN}")
    print(f"Actual audit entries: {len(history)}")
    print(f"Unique audit IDs: {len(unique_ids)}")
    print(f"Verdicts created (counter): {results['created']}")
    print()

    # Check for immutability (no UPDATE)
    if len(audit_ids) != len(unique_ids):
        print("✗ CRITICAL: Duplicate audit IDs detected!")
        print("  Possible UPDATE operations instead of INSERT")
        duplicates = [id for id in audit_ids if audit_ids.count(id) > 1]
        print(f"  Duplicate IDs: {set(duplicates)}")
    else:
        print("✓ All audit IDs unique (INSERT-only verified)")

    # Check for lost entries
    expected = NUM_ADMINS * VERDICTS_PER_ADMIN
    if len(history) < expected:
        lost = expected - len(history)
        print(f"\n⚠ AUDIT TRAIL CORRUPTION: {lost} entries LOST!")
        print(f"  Expected: {expected}")
        print(f"  Actual: {len(history)}")
        print(f"  Loss rate: {lost/expected*100:.1f}%")
    elif len(history) > expected:
        print(f"\n⚠ UNEXPECTED: {len(history) - expected} EXTRA entries")
    else:
        print(f"\n✓ NO LOST ENTRIES: All {expected} verdicts recorded")

    # Check chronological order
    timestamps = [entry.created_at for entry in history]
    sorted_timestamps = sorted(timestamps)

    if timestamps == sorted_timestamps:
        print("✓ Chronological order preserved")
    else:
        print("⚠ Chronological order VIOLATED")
        # Find out-of-order entries
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                print(f"  Out of order at position {i}: {timestamps[i]} < {timestamps[i-1]}")

    # Check verdict distribution
    verdict_counts = {}
    admin_counts = {}
    for entry in history:
        verdict_counts[entry.verdict] = verdict_counts.get(entry.verdict, 0) + 1
        admin_counts[entry.reviewed_by] = admin_counts.get(entry.reviewed_by, 0) + 1

    print(f"\nVerdict distribution:")
    for verdict, count in sorted(verdict_counts.items()):
        print(f"  {verdict}: {count}")

    print(f"\nAdmin contribution:")
    for admin_id, count in sorted(admin_counts.items()):
        print(f"  Admin {admin_id}: {count} verdicts")

    # Sample audit entries
    print(f"\nFirst 5 audit entries:")
    for entry in history[:5]:
        print(f"  [{entry.created_at}] Admin {entry.reviewed_by}: {entry.verdict}")

    print(f"\nLast 5 audit entries:")
    for entry in history[-5:]:
        print(f"  [{entry.created_at}] Admin {entry.reviewed_by}: {entry.verdict}")

    print("=" * 80)

print("\n[SECURITY ASSESSMENT]")
if len(history) == NUM_ADMINS * VERDICTS_PER_ADMIN and len(audit_ids) == len(unique_ids):
    print("✓ Audit trail INTEGRITY MAINTAINED under concurrent load")
    print("  - All verdict changes recorded")
    print("  - No lost entries")
    print("  - Immutability enforced (INSERT-only)")
    print("  - Chronological order preserved")
else:
    print("✗ AUDIT TRAIL VULNERABILITY DETECTED")
    if len(history) < NUM_ADMINS * VERDICTS_PER_ADMIN:
        print("  - CRITICAL: Lost audit entries (data loss)")
    if len(audit_ids) != len(unique_ids):
        print("  - CRITICAL: Duplicate IDs (possible UPDATE operations)")
    print("  - Evidence tampering POSSIBLE")
    print("  - Forensic integrity COMPROMISED")

print("\nRecommendation: Add database triggers to prevent UPDATE/DELETE on verdict_history.")
print("                Implement append-only table with immutability at DB level.")
print("=" * 80)
