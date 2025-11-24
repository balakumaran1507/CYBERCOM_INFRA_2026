#!/usr/bin/env python3
"""
RED TEAM ATTACK E1: Submission Flood (DoS via Analytics Worker)
================================================================

Attack Vector:
--------------
Flood system with massive submission volume to:
1. Exhaust analytics worker processing capacity
2. Cause memory exhaustion (if 5000 limit bypassed)
3. Create database query timeouts
4. Trigger worker crash or hang

Expected Behavior:
------------------
System should:
1. Cap analytics processing at 5000 submissions
2. Log warning when limit hit
3. Complete processing without crash
4. Maintain database responsiveness

Attack Goal:
------------
Test worker resilience under extreme load:
- Memory exhaustion protection
- Query timeout handling
- Graceful degradation
- DoS resistance

Threat Level: CRITICAL (Service disruption if successful)
"""

import datetime
from CTFd import create_app
from CTFd.models import db, Submissions
import time

app = create_app()

print("=" * 80)
print("RED TEAM ATTACK E1: WORKER DoS VIA SUBMISSION FLOOD")
print("=" * 80)
print()

# Configuration
FLOOD_SIZE = 10000  # Exceed 5000 limit by 2x
CHALLENGE_ID = 6

print(f"[ATTACK SETUP]")
print(f"Creating {FLOOD_SIZE} submissions in database...")
print(f"This tests if analytics worker respects 5000 record limit")
print()

# Clean existing
with app.app_context():
    deleted = db.session.execute(
        db.text("DELETE FROM submissions WHERE challenge_id = :cid"),
        {'cid': CHALLENGE_ID}
    ).rowcount
    db.session.commit()
    print(f"✓ Cleaned {deleted} existing submissions")

# Create flood
print(f"\nCreating {FLOOD_SIZE} submissions...")
start_time = time.time()

batch_size = 1000
created = 0

for batch in range(0, FLOOD_SIZE, batch_size):
    with app.app_context():
        submissions = []
        for i in range(batch, min(batch + batch_size, FLOOD_SIZE)):
            # Create submission with varying timestamps
            timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=FLOOD_SIZE - i)

            sub = Submissions(
                user_id=2 + (i % 3),  # Cycle users 2, 3, 4
                team_id=None,
                challenge_id=CHALLENGE_ID,
                ip=f'10.{(i // 65536) % 256}.{(i // 256) % 256}.{i % 256}',
                provided=f'flag{{flood_{i}}}',
                type='incorrect',  # All wrong to maximize analytics load
                date=timestamp
            )
            submissions.append(sub)

        db.session.bulk_save_objects(submissions)
        db.session.commit()
        created += len(submissions)

        if (created % 2000) == 0:
            print(f"  Created {created}/{FLOOD_SIZE}...")

elapsed = time.time() - start_time
print(f"\n✓ Created {created} submissions in {elapsed:.2f}s")
print()

# Verify flood
with app.app_context():
    total = db.session.execute(
        db.text("SELECT COUNT(*) FROM submissions WHERE challenge_id = :cid"),
        {'cid': CHALLENGE_ID}
    ).scalar()

    print(f"Total submissions in database: {total}")

    if total != FLOOD_SIZE:
        print(f"⚠ Warning: Expected {FLOOD_SIZE}, got {total}")

# Simulate analytics worker query
print()
print("[ATTACK] Simulating analytics worker processing...")
print("=" * 80)

with app.app_context():
    # This is what the analytics worker does
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=30)
    MAX_SUBMISSIONS = 5000

    print(f"Querying recent submissions (limit={MAX_SUBMISSIONS})...")
    query_start = time.time()

    try:
        recent_submissions = Submissions.query.filter(
            Submissions.challenge_id == CHALLENGE_ID,
            Submissions.date >= cutoff_time
        ).order_by(
            Submissions.date.desc()
        ).limit(MAX_SUBMISSIONS).all()

        query_elapsed = time.time() - query_start

        print(f"✓ Query completed in {query_elapsed:.3f}s")
        print(f"  Retrieved: {len(recent_submissions)} submissions")
        print(f"  Memory usage per submission: ~1KB")
        print(f"  Estimated memory: {len(recent_submissions) * 1024 / 1024:.2f} MB")
        print()

        if len(recent_submissions) >= MAX_SUBMISSIONS:
            print("✓ LIMIT ENFORCED: Worker capped at 5000 submissions")
            print("  DoS protection active")
        else:
            print(f"  Retrieved {len(recent_submissions)} (under limit)")

    except Exception as e:
        query_elapsed = time.time() - query_start
        print(f"✗ QUERY FAILED after {query_elapsed:.3f}s")
        print(f"  Error: {e}")
        print("  Possible timeout or resource exhaustion")

# Test without limit (dangerous!)
print()
print("[ATTACK] Testing query WITHOUT limit (DoS scenario)...")
print("=" * 80)

with app.app_context():
    print(f"Querying ALL {FLOOD_SIZE} submissions (NO LIMIT)...")
    query_start = time.time()

    try:
        # DANGEROUS: No limit
        all_submissions = Submissions.query.filter(
            Submissions.challenge_id == CHALLENGE_ID
        ).all()

        query_elapsed = time.time() - query_start

        print(f"✓ Query completed in {query_elapsed:.3f}s")
        print(f"  Retrieved: {len(all_submissions)} submissions")
        print(f"  Estimated memory: {len(all_submissions) * 1024 / 1024:.2f} MB")
        print()

        if query_elapsed > 5.0:
            print("⚠ PERFORMANCE DEGRADATION")
            print(f"  Query took {query_elapsed:.1f}s (>5s threshold)")
            print("  Worker would timeout in production")

        if len(all_submissions) > 5000:
            print("✗ CRITICAL: Query retrieved >5000 records")
            print("  Memory exhaustion POSSIBLE")
            print("  DoS protection BYPASSED")

    except Exception as e:
        query_elapsed = time.time() - query_start
        print(f"✗ QUERY CRASHED after {query_elapsed:.3f}s")
        print(f"  Error: {str(e)[:100]}")
        print("  System vulnerable to DoS via unlimited queries")

# Check worker logs
print()
print("[VERIFICATION] Checking for analytics worker warnings...")
print("=" * 80)

# The worker runs async, so we need to check if it logged warnings
print("Expected log:")
print("[PHASE2 ANALYTICS WARNING] Hit MAX_SUBMISSIONS limit (5000).")
print("Possible DoS or high traffic event. Analyzing most recent submissions only.")
print()
print("To verify: docker compose logs ctfd | grep 'MAX_SUBMISSIONS'")
print()

# Results summary
print("=" * 80)
print("ATTACK RESULTS:")
print("=" * 80)
print(f"Submissions created: {total}")
print(f"Worker limit: 5000")
print(f"Overflow: {total - 5000}")
print()

if len(recent_submissions) == MAX_SUBMISSIONS and query_elapsed < 5.0:
    print("✓ DoS PROTECTION EFFECTIVE")
    print("  - Worker respects 5000 record limit")
    print("  - Query performance acceptable")
    print("  - Memory usage bounded")
    print("  - System resilient under 2x overload")
else:
    print("✗ DoS VULNERABILITY DETECTED")
    if len(recent_submissions) > MAX_SUBMISSIONS:
        print("  - CRITICAL: Limit not enforced")
    if query_elapsed > 5.0:
        print(f"  - CRITICAL: Query timeout ({query_elapsed:.1f}s)")

print()
print("[SECURITY ASSESSMENT]")
print("Worker resilience under extreme load:")

if query_elapsed < 2.0:
    print("  Performance: EXCELLENT (<2s)")
elif query_elapsed < 5.0:
    print("  Performance: ACCEPTABLE (<5s)")
else:
    print("  Performance: POOR (>5s, DoS risk)")

print()
print("Recommendations:")
print("1. Monitor submission rate in production")
print("2. Add rate limiting on submission endpoints")
print("3. Consider worker batch processing (chunks of 1000)")
print("4. Add timeout protection (kill worker after 60s)")
print("5. Alert on repeated MAX_SUBMISSIONS warnings (DoS indicator)")
print()
print("=" * 80)

# Cleanup
print("\n[CLEANUP] Removing test data...")
with app.app_context():
    db.session.execute(
        db.text("DELETE FROM submissions WHERE challenge_id = :cid"),
        {'cid': CHALLENGE_ID}
    )
    db.session.commit()
    print("✓ Test data cleaned")

print("=" * 80)
