#!/usr/bin/env python3
"""
RED TEAM ATTACK A2: Distributed Race Condition (100 Threads)
=============================================================

Attack Vector:
--------------
Simulate distributed botnet attack with 100 concurrent solve submissions
to stress-test UNIQUE constraint and advisory lock mechanism.

Expected Behavior:
------------------
System should:
1. Handle 100 concurrent transactions gracefully
2. Only ONE first blood record created
3. Advisory locks OR UNIQUE constraint prevents duplicates
4. No database deadlocks or transaction failures

Attack Goal:
------------
Test if high concurrency can bypass race condition protections.
Identify performance degradation or transaction failures.

Threat Level: HIGH
"""

import threading
import time
import random
from CTFd import create_app
from CTFd.models import db

app = create_app()
from CTFd.models import Solves
import datetime

print("=" * 80)
print("RED TEAM ATTACK A2: DISTRIBUTED RACE CONDITION (100 THREADS)")
print("=" * 80)
print()

# Clean slate
with app.app_context():
    db.session.execute(db.text("DELETE FROM solves WHERE challenge_id = 4"))
    db.session.execute(db.text("DELETE FROM submissions WHERE challenge_id = 4"))
    db.session.execute(db.text("DELETE FROM phase2_first_blood_prestige WHERE challenge_id = 4"))
    db.session.commit()
    print("✓ Cleaned test data for challenge 4")

# Attack configuration
NUM_THREADS = 100
CHALLENGE_ID = 4
results = {'success': 0, 'failed': 0, 'errors': []}
results_lock = threading.Lock()

def attack_thread(thread_id):
    """Simulate attacker submitting solve"""
    # Random micro-delay to simulate network jitter (0-5ms)
    time.sleep(random.uniform(0, 0.005))

    try:
        with app.app_context():
            # Use different user IDs (cycling through available test users)
            # Simulate multiple accounts controlled by attacker
            user_id = 2 + (thread_id % 3)  # Users 2, 3, 4

            solve = Solves(
                user_id=user_id,
                team_id=None,
                challenge_id=CHALLENGE_ID,
                ip=f'10.0.{thread_id // 256}.{thread_id % 256}',  # Distributed IPs
                provided=f'flag{{thread_{thread_id}}}',
                type='correct',
                date=datetime.datetime.utcnow()
            )
            db.session.add(solve)
            db.session.commit()

            with results_lock:
                results['success'] += 1

    except Exception as e:
        with results_lock:
            results['failed'] += 1
            error_msg = str(e)
            # Only store unique errors
            if error_msg not in results['errors']:
                results['errors'].append(error_msg)

print(f"\n[ATTACK] Launching {NUM_THREADS} concurrent solve submissions...")
print(f"         Target: Challenge {CHALLENGE_ID}")
print(f"         Simulating distributed botnet with IP rotation")
print()

# Launch attack
threads = []
start_time = time.time()

for i in range(NUM_THREADS):
    thread = threading.Thread(target=attack_thread, args=(i,))
    threads.append(thread)

# Start all threads nearly simultaneously
for thread in threads:
    thread.start()

# Wait for completion
for thread in threads:
    thread.join()

elapsed = time.time() - start_time

print(f"✓ Attack completed in {elapsed:.3f} seconds")
print(f"  Successful submissions: {results['success']}")
print(f"  Failed submissions: {results['failed']}")
print()

if results['errors']:
    print("Errors encountered:")
    for error in results['errors'][:5]:  # Show first 5 unique errors
        print(f"  - {error[:100]}...")
    if len(results['errors']) > 5:
        print(f"  ... and {len(results['errors']) - 5} more unique errors")
    print()

# Verification
with app.app_context():
    from CTFd.plugins.phase2.models import FirstBloodPrestige

    # Check first blood records
    fb_records = FirstBloodPrestige.query.filter_by(challenge_id=CHALLENGE_ID).all()
    total_solves = db.session.execute(
        db.text("SELECT COUNT(*) FROM solves WHERE challenge_id = :cid"),
        {'cid': CHALLENGE_ID}
    ).scalar()

    print("=" * 80)
    print("ATTACK RESULTS:")
    print("=" * 80)
    print(f"Total solves created: {total_solves}")
    print(f"First blood records: {len(fb_records)}")
    print()

    if len(fb_records) == 0:
        print("✗ CRITICAL: NO first blood records despite solves!")
        print("  System failed under load")
    elif len(fb_records) == 1:
        fb = fb_records[0]
        print("✓ SUCCESS: Only ONE first blood record")
        print(f"  Winner: User ID {fb.user_id}")
        print(f"  Solve ID: {fb.solve_id}")
        print(f"  Prestige: {fb.prestige_score}")
        print()
        print("✓ RACE CONDITION PROTECTION HELD UNDER 100x CONCURRENT LOAD")
    else:
        print(f"✗ CRITICAL VULNERABILITY: {len(fb_records)} FIRST BLOOD RECORDS!")
        print("  UNIQUE constraint BYPASSED under high concurrency")
        print("  RACE CONDITION EXPLOIT SUCCESSFUL")
        print()
        print("  Duplicate records:")
        for fb in fb_records:
            print(f"    - User {fb.user_id}, Solve {fb.solve_id}, Timestamp {fb.timestamp}")

    # Performance analysis
    if elapsed > 10:
        print(f"\n⚠ PERFORMANCE CONCERN: Attack took {elapsed:.1f}s for {NUM_THREADS} threads")
        print("  Advisory lock contention or database bottleneck detected")
    else:
        print(f"\n✓ Performance acceptable: {NUM_THREADS} threads in {elapsed:.3f}s")

    # Database integrity check
    duplicate_solves = db.session.execute(
        db.text("""
            SELECT challenge_id, user_id, COUNT(*) as cnt
            FROM solves
            WHERE challenge_id = :cid
            GROUP BY challenge_id, user_id
            HAVING COUNT(*) > 1
        """),
        {'cid': CHALLENGE_ID}
    ).fetchall()

    if duplicate_solves:
        print(f"\n⚠ DATABASE INTEGRITY ISSUE:")
        print(f"  {len(duplicate_solves)} users have duplicate solves for same challenge")
        print("  UNIQUE(challenge_id, user_id) constraint may be missing or bypassed")
    else:
        print(f"\n✓ Database integrity maintained (no duplicate user solves)")

    print("=" * 80)

print("\n[SECURITY ASSESSMENT]")
if len(fb_records) == 1:
    print("✓ System SURVIVED distributed race condition attack")
    print("  - UNIQUE constraint effective under 100x concurrent load")
    print("  - Transaction isolation prevents duplicate first bloods")
    print("  - Advisory lock warnings acceptable (fallback works)")
else:
    print("✗ System VULNERABLE to distributed race condition")
    print("  - URGENT: Review UNIQUE constraint enforcement")
    print("  - URGENT: Check transaction isolation levels")
    print("  - URGENT: Verify advisory lock implementation")

print("\nRecommendation: Monitor production for advisory lock warnings.")
print("                Consider connection pooling limits to prevent resource exhaustion.")
print("=" * 80)
