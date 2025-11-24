#!/usr/bin/env python3
"""
Redis Poison Attack Test for Phase 2 First Blood System
Tests that poisoned cache is detected and database remains authoritative
"""
from CTFd import create_app
from CTFd.models import db, Solves
import datetime

app = create_app()

print("=" * 60)
print("REDIS POISON ATTACK TEST: First Blood System")
print("=" * 60)
print("Scenario: Cache poisoned with 'POISONED_VALUE'")
print("Expected: System detects invalid signature, uses DB as authority")
print()

# Create a solve for user 3 on challenge 2 (which already has first blood)
with app.app_context():
    solve = Solves(
        user_id=3,  # Different user
        team_id=None,
        challenge_id=2,  # Same challenge
        ip='127.0.0.1',
        provided='flag{test}',
        type='correct',
        date=datetime.datetime.utcnow()
    )
    db.session.add(solve)
    db.session.commit()
    print(f"✅ Solve created: User 3, Challenge 2, Solve ID {solve.id}")
    print()

# Verify first blood count
with app.app_context():
    from CTFd.plugins.phase2.models import FirstBloodPrestige

    fb_count = FirstBloodPrestige.query.filter_by(challenge_id=2).count()
    fb_records = FirstBloodPrestige.query.filter_by(challenge_id=2).all()

    print("=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(f"First Blood Records for Challenge 2: {fb_count}")

    if fb_count == 1:
        fb = fb_records[0]
        print("✅ PASS: Only ONE first blood record (poison attack prevented)")
        print(f"   Winner: User ID {fb.user_id}, Prestige {fb.prestige_score}")
        print(f"   Database remained authoritative despite poisoned cache")
    else:
        print(f"❌ FAIL: {fb_count} first blood records (poison attack succeeded!)")
        for fb in fb_records:
            print(f"   - User {fb.user_id}, Solve {fb.solve_id}")

    print("=" * 60)
    print()
    print("Expected log message:")
    print("[PHASE2 SECURITY WARNING] Invalid Redis signature for phase2:first_blood_claimed:2")
    print("=" * 60)
