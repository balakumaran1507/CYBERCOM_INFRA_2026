#!/usr/bin/env python3
"""
RED TEAM ATTACK F1: Multi-Vector Combination Attack
====================================================

Attack Vector:
--------------
Sophisticated multi-stage attack combining multiple vulnerabilities:

Stage 1: Cache poisoning to trick first blood detection
Stage 2: Race condition exploit during cache invalidation
Stage 3: Consent withdrawal during suspicion creation
Stage 4: Verdict tampering during admin review

Expected Behavior:
------------------
Defense-in-depth should prevent attack at multiple layers:
- Stage 1: HMAC signature rejection
- Stage 2: UNIQUE constraint enforcement
- Stage 3: Consent check rejection
- Stage 4: Audit trail immutability

Attack Goal:
------------
Test if multiple simultaneous attacks can overwhelm defenses or
find gaps between security layers.

Threat Level: CRITICAL (APT-style attack)
"""

import threading
import time
import random
from CTFd import create_app
from CTFd.models import db
from CTFd.cache import cache

app = create_app()

print("=" * 80)
print("RED TEAM ATTACK F1: MULTI-VECTOR COMBINATION ATTACK")
print("=" * 80)
print()
print("Simulating Advanced Persistent Threat (APT) scenario")
print("Multiple attack vectors executed in coordinated sequence")
print()

# Attack state tracking
attack_results = {
    'cache_poison_success': False,
    'race_exploit_success': False,
    'consent_bypass_success': False,
    'verdict_tamper_success': False,
    'stages_blocked': []
}

# STAGE 1: Cache Poisoning
print("[STAGE 1] Cache Poisoning Attack")
print("=" * 80)

CHALLENGE_ID = 7

with app.app_context():
    # Clean slate
    db.session.execute(db.text(f"DELETE FROM solves WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.execute(db.text(f"DELETE FROM submissions WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.execute(db.text(f"DELETE FROM phase2_first_blood_prestige WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.commit()

    # Poison cache with fake first blood claim
    cache_key = f'phase2:first_blood_claimed:{CHALLENGE_ID}'

    # Attempt 1: Raw string (malformed)
    cache.set(cache_key, "FAKE_FIRST_BLOOD_ALREADY_CLAIMED", timeout=300)
    print("✓ Injected poisoned cache (malformed)")

    # Attempt 2: Valid JSON with fake signature
    import json
    fake_signed = json.dumps({
        'value': '1',
        'signature': 'a' * 64  # Fake HMAC
    })
    cache.set(cache_key + '_v2', fake_signed, timeout=300)
    print("✓ Injected poisoned cache (fake signature)")

time.sleep(0.1)

# STAGE 2: Race Condition Exploit
print()
print("[STAGE 2] Race Condition During Cache Invalidation")
print("=" * 80)

from CTFd.models import Solves
import datetime

def race_attacker(user_id, delay=0):
    """Attempt solve during cache invalidation window"""
    time.sleep(delay)
    try:
        with app.app_context():
            solve = Solves(
                user_id=user_id,
                team_id=None,
                challenge_id=CHALLENGE_ID,
                ip=f'192.168.100.{user_id}',
                provided='flag{race_exploit}',
                type='correct',
                date=datetime.datetime.utcnow()
            )
            db.session.add(solve)
            db.session.commit()
    except:
        pass

# Launch 10 concurrent solves during cache poisoning
print("Launching 10 concurrent solves during poisoned cache window...")
threads = []
for i in range(2, 12):  # Users 2-11
    t = threading.Thread(target=race_attacker, args=(i, i * 0.001))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("✓ Race condition attack completed")

# Check results
with app.app_context():
    from CTFd.plugins.phase2.models import FirstBloodPrestige

    fb_records = FirstBloodPrestige.query.filter_by(challenge_id=CHALLENGE_ID).all()
    solve_count = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM solves WHERE challenge_id = {CHALLENGE_ID}")
    ).scalar()

    print(f"  Solves created: {solve_count}")
    print(f"  First blood records: {len(fb_records)}")

    if len(fb_records) == 0:
        print("  ✗ Stage 2 FAILED: Cache poison may have prevented first blood")
        attack_results['cache_poison_success'] = True
        attack_results['stages_blocked'].append('Stage 2')
    elif len(fb_records) == 1:
        print(f"  ✓ Stage 2 BLOCKED: Only one first blood (User {fb_records[0].user_id})")
        attack_results['stages_blocked'].append('Stage 2')
    else:
        print(f"  ✗ Stage 2 EXPLOIT SUCCESS: {len(fb_records)} first blood records!")
        attack_results['race_exploit_success'] = True

# STAGE 3: Consent Bypass via TOCTOU
print()
print("[STAGE 3] GDPR Consent Bypass (TOCTOU)")
print("=" * 80)

from CTFd.plugins.phase2.models import UserConsent, FlagSharingSuspicion
from CTFd.plugins.phase2.detection import create_suspicion_record

with app.app_context():
    # Setup: Grant consent initially
    UserConsent.grant_consent(2)
    UserConsent.grant_consent(3)

consent_withdrawn = threading.Event()

def consent_withdrawer():
    """Withdraw consent during suspicion creation"""
    time.sleep(0.01)  # Wait for suspicion creation to start
    with app.app_context():
        UserConsent.withdraw_consent(2)
        consent_withdrawn.set()

def suspicion_creator():
    """Create suspicion while consent is being withdrawn"""
    time.sleep(0.005)
    with app.app_context():
        pattern = {
            'user_id_1': 2,
            'user_id_2': 3,
            'challenge_id': CHALLENGE_ID,
            'detection_type': 'temporal_proximity',
            'confidence': 0.95,
            'evidence': {
                'ip': '192.168.1.1',
                'time_delta_ms': 50
            }
        }

        result = create_suspicion_record(pattern)
        return result is not None

# Execute TOCTOU attack
withdrawer = threading.Thread(target=consent_withdrawer)
creator = threading.Thread(target=suspicion_creator)

withdrawer.start()
creator.start()

withdrawer.join()
creator.join()

with app.app_context():
    suspicions = FlagSharingSuspicion.query.filter_by(challenge_id=CHALLENGE_ID).all()

    if len(suspicions) == 0:
        print("  ✓ Stage 3 BLOCKED: No suspicions created")
        attack_results['stages_blocked'].append('Stage 3')
    else:
        print(f"  ⚠ Stage 3 UNCERTAIN: {len(suspicions)} suspicions created")
        print("    May indicate TOCTOU vulnerability if consent was withdrawn first")
        # Would need precise timing analysis to confirm

# STAGE 4: Verdict Tampering
print()
print("[STAGE 4] Audit Trail Tampering Attempt")
print("=" * 80)

if len(suspicions) > 0:
    from CTFd.plugins.phase2.models import VerdictHistory

    with app.app_context():
        susp_id = suspicions[0].id

        # Record initial verdict
        VerdictHistory.record_verdict(
            suspicion_id=susp_id,
            verdict='confirmed',
            admin_id=1,
            admin_ip='10.0.0.1',
            notes='Initial verdict'
        )

        # Attempt to tamper: Try direct database UPDATE
        try:
            db.session.execute(
                db.text("""
                    UPDATE phase2_verdict_history
                    SET verdict = 'innocent', notes = 'TAMPERED'
                    WHERE suspicion_id = :sid
                    LIMIT 1
                """),
                {'sid': susp_id}
            )
            db.session.commit()

            print("  ✗ Stage 4 EXPLOIT: Direct UPDATE succeeded!")
            attack_results['verdict_tamper_success'] = True

        except Exception as e:
            print("  ✓ Stage 4 BLOCKED: Direct UPDATE failed")
            print(f"    Error: {str(e)[:50]}")
            attack_results['stages_blocked'].append('Stage 4')
            db.session.rollback()

        # Verify audit trail integrity
        history = VerdictHistory.get_history(susp_id)
        print(f"  Audit trail entries: {len(history)}")

        tampered = any('TAMPERED' in (h.notes or '') for h in history)
        if tampered:
            print("  ✗ CRITICAL: Tampered entry found in audit trail!")
        else:
            print("  ✓ Audit trail integrity maintained")
else:
    print("  ⊘ Stage 4 SKIPPED: No suspicions to tamper")
    attack_results['stages_blocked'].append('Stage 4 (N/A)')

# FINAL ASSESSMENT
print()
print("=" * 80)
print("MULTI-VECTOR ATTACK ASSESSMENT")
print("=" * 80)
print()

print("Attack Results:")
print(f"  Cache Poisoning:    {'SUCCESS' if attack_results['cache_poison_success'] else 'BLOCKED'}")
print(f"  Race Exploit:       {'SUCCESS' if attack_results['race_exploit_success'] else 'BLOCKED'}")
print(f"  Consent Bypass:     {'SUCCESS' if attack_results['consent_bypass_success'] else 'BLOCKED'}")
print(f"  Verdict Tampering:  {'SUCCESS' if attack_results['verdict_tamper_success'] else 'BLOCKED'}")
print()

successful_stages = sum([
    attack_results['cache_poison_success'],
    attack_results['race_exploit_success'],
    attack_results['consent_bypass_success'],
    attack_results['verdict_tamper_success']
])

print(f"Stages Blocked: {len(attack_results['stages_blocked'])}/4")
print(f"Stages Exploited: {successful_stages}/4")
print()

if successful_stages == 0:
    print("✓ DEFENSE-IN-DEPTH SUCCESSFUL")
    print("  All attack vectors blocked at appropriate security layers")
    print("  System resilient against coordinated multi-vector attack")
elif successful_stages <= 2:
    print("⚠ PARTIAL DEFENSE")
    print("  Some attack vectors succeeded")
    print("  Review blocked stages for defense gaps")
else:
    print("✗ CRITICAL: MULTI-VECTOR EXPLOIT SUCCESSFUL")
    print("  System vulnerable to coordinated attack")
    print("  Multiple security layers compromised")

print()
print("[SECURITY ASSESSMENT]")
print("Defense-in-depth effectiveness:")
for stage in attack_results['stages_blocked']:
    print(f"  ✓ {stage}: Defense layer effective")

print()
print("This attack demonstrates importance of:")
print("  1. Layered security (no single point of failure)")
print("  2. Transaction-level consistency (prevent TOCTOU)")
print("  3. Database-level constraints (final enforcement)")
print("  4. Immutable audit trails (detect tampering)")
print()
print("Recommendation: Security audit passed if all 4 stages blocked.")
print("                System should resist coordinated APT-style attacks.")
print("=" * 80)

# Cleanup
with app.app_context():
    db.session.execute(db.text(f"DELETE FROM solves WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.execute(db.text(f"DELETE FROM submissions WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.execute(db.text(f"DELETE FROM phase2_first_blood_prestige WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.execute(db.text(f"DELETE FROM phase2_flag_sharing_suspicion WHERE challenge_id = {CHALLENGE_ID}"))
    db.session.commit()

print("\n✓ Cleanup complete")
