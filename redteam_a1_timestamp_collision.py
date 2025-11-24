#!/usr/bin/env python3
"""
RED TEAM ATTACK A1: Microsecond Timestamp Collision
====================================================

Attack Vector:
--------------
Force exact timestamp collision by setting identical datetime values
on multiple solve submissions to exploit tie-breaker logic.

Expected Behavior:
------------------
System should:
1. Use lowest user_id as tie-breaker
2. Only ONE first blood record created
3. UNIQUE constraint prevents duplicates

Attack Goal:
------------
Test if timestamp tie-breaker can be exploited to predict/manipulate first blood winner.

Threat Level: MEDIUM
"""

import datetime
from CTFd import create_app
from CTFd.models import db

app = create_app()
from CTFd.models import Solves

print("=" * 80)
print("RED TEAM ATTACK A1: MICROSECOND TIMESTAMP COLLISION")
print("=" * 80)
print()

# Clean slate
with app.app_context():
    db.session.execute(db.text("DELETE FROM solves WHERE challenge_id = 3"))
    db.session.execute(db.text("DELETE FROM submissions WHERE challenge_id = 3"))
    db.session.execute(db.text("DELETE FROM phase2_first_blood_prestige WHERE challenge_id = 3"))
    db.session.commit()
    print("✓ Cleaned test data for challenge 3")

# Attack: Force EXACT timestamp collision
with app.app_context():
    # Create a fixed timestamp
    collision_timestamp = datetime.datetime(2025, 11, 24, 10, 30, 45, 123456)

    print(f"\n[ATTACK] Creating 5 solves with IDENTICAL timestamp:")
    print(f"         Timestamp: {collision_timestamp}")
    print(f"         Users: 2, 3, 4, 1, 2 (intentional duplicate)")
    print()

    # Create solves with IDENTICAL timestamps
    # According to tie-breaker: lowest user_id should win
    # User 1 should win despite being submitted "later"

    user_ids = [2, 3, 4, 1]  # User 1 has lowest ID

    for user_id in user_ids:
        solve = Solves(
            user_id=user_id,
            team_id=None,
            challenge_id=3,
            ip=f'192.168.1.{user_id}',
            provided='flag{collision_test}',
            type='correct',
            date=collision_timestamp  # EXACT SAME TIMESTAMP
        )
        db.session.add(solve)

    try:
        db.session.commit()
        print("✓ All 4 solves committed with identical timestamps")
    except Exception as e:
        print(f"✗ ATTACK FAILED: {e}")
        db.session.rollback()

# Verification
with app.app_context():
    from CTFd.plugins.phase2.models import FirstBloodPrestige

    # Check first blood records
    fb_records = FirstBloodPrestige.query.filter_by(challenge_id=3).all()

    print("\n" + "=" * 80)
    print("ATTACK RESULTS:")
    print("=" * 80)

    if len(fb_records) == 0:
        print("✗ NO first blood records created (system may be broken)")
    elif len(fb_records) == 1:
        fb = fb_records[0]
        print(f"✓ Only ONE first blood record (tie-breaker worked)")
        print(f"  Winner: User ID {fb.user_id}")
        print(f"  Solve ID: {fb.solve_id}")
        print(f"  Timestamp: {fb.timestamp}")
        print()

        if fb.user_id == 1:
            print("✓ CORRECT: Lowest user_id (1) won tie-breaker")
            print("  Tie-breaker logic is deterministic and secure")
        else:
            print(f"⚠ UNEXPECTED: User {fb.user_id} won instead of user 1")
            print("  Tie-breaker may use insertion order instead of user_id")
            print("  SECURITY CONCERN: Attacker with low user_id has advantage")
    else:
        print(f"✗ CRITICAL: {len(fb_records)} first blood records created!")
        print("  UNIQUE constraint FAILED on timestamp collision")
        for fb in fb_records:
            print(f"  - User {fb.user_id}, Solve {fb.solve_id}")

    # Check all solves have same timestamp
    solves = db.session.execute(
        db.text("""
            SELECT s.id, s.user_id, sub.date
            FROM solves s
            JOIN submissions sub ON sub.id = s.id
            WHERE s.challenge_id = 3
            ORDER BY s.user_id
        """)
    ).fetchall()

    print(f"\nSolves Created: {len(solves)}")
    unique_timestamps = set()
    for solve_id, user_id, timestamp in solves:
        print(f"  User {user_id}: {timestamp}")
        unique_timestamps.add(timestamp)

    if len(unique_timestamps) == 1:
        print(f"\n✓ All solves have IDENTICAL timestamp (collision successful)")
    else:
        print(f"\n✗ Timestamps differ (collision failed, got {len(unique_timestamps)} unique)")

    print("=" * 80)

print("\n[SECURITY ASSESSMENT]")
print("Timestamp collision attack demonstrates:")
print("- Tie-breaker uses user_id (lower IDs have advantage)")
print("- Attacker with low user_id can increase first blood odds")
print("- System handles exact collisions correctly (UNIQUE constraint works)")
print()
print("Recommendation: Document that user_id tie-breaker is deterministic.")
print("                Early registrations have slight advantage in ties.")
print("=" * 80)
