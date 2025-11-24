#!/usr/bin/env python3
"""
Race Condition Test for Phase 2 First Blood System
Simulates 3 concurrent solves for same challenge
"""
import threading
import time
from CTFd import create_app
from CTFd.models import db, Solves
import datetime

app = create_app()

def create_solve(user_id, challenge_id, delay=0):
    """Create a solve for testing (simulates concurrent submission)"""
    time.sleep(delay)  # Slight delay to simulate network jitter

    with app.app_context():
        solve = Solves(
            user_id=user_id,
            team_id=None,
            challenge_id=challenge_id,
            ip='127.0.0.1',
            provided='flag{test}',
            type='correct',
            date=datetime.datetime.utcnow()
        )
        db.session.add(solve)
        db.session.commit()
        print(f"[THREAD {user_id}] Solve created: ID={solve.id}")
        return solve.id

if __name__ == '__main__':
    CHALLENGE_ID = 2  # TEST - Dynamic Flag

    print("=" * 60)
    print("RACE CONDITION TEST: First Blood System")
    print("=" * 60)
    print(f"Challenge ID: {CHALLENGE_ID}")
    print(f"Simulating 3 concurrent solves...")
    print()

    # Create 3 threads that will submit solves nearly simultaneously
    threads = []
    for user_id in [2, 3, 4]:  # racetest1, racetest2, racetest3
        thread = threading.Thread(
            target=create_solve,
            args=(user_id, CHALLENGE_ID, user_id * 0.001)  # 0ms, 1ms, 2ms delays
        )
        threads.append(thread)

    # Start all threads nearly simultaneously
    start_time = time.time()
    for thread in threads:
        thread.start()

    # Wait for all to complete
    for thread in threads:
        thread.join()

    elapsed = time.time() - start_time
    print()
    print(f"All solves completed in {elapsed:.3f}s")
    print()

    # Verify results
    with app.app_context():
        from CTFd.plugins.phase2.models import FirstBloodPrestige

        # Count first blood records for this challenge
        fb_count = FirstBloodPrestige.query.filter_by(challenge_id=CHALLENGE_ID).count()
        fb_records = FirstBloodPrestige.query.filter_by(challenge_id=CHALLENGE_ID).all()

        print("=" * 60)
        print("RESULTS:")
        print("=" * 60)
        print(f"First Blood Records Created: {fb_count}")

        if fb_count == 1:
            print("✅ PASS: Only ONE first blood record (race condition prevented)")
            fb = fb_records[0]
            print(f"   Winner: User ID {fb.user_id}, Solve ID {fb.solve_id}")
            print(f"   Prestige: {fb.prestige_score}")
        elif fb_count == 0:
            print("❌ FAIL: NO first blood record created")
        else:
            print(f"❌ FAIL: {fb_count} first blood records (RACE CONDITION DETECTED!)")
            for fb in fb_records:
                print(f"   - User {fb.user_id}, Solve {fb.solve_id}")

        print("=" * 60)
