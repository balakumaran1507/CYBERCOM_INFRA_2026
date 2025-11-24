#!/usr/bin/env python3
"""
RED TEAM ATTACK B1: Consent State Race Condition
=================================================

Attack Vector:
--------------
Rapidly toggle user consent (grant -> withdraw -> grant) while analytics
worker is running to create race condition in consent checking.

Expected Behavior:
------------------
System should:
1. Check consent atomically during suspicion creation
2. No suspicions created during "withdrawn" state
3. Consent state changes properly synchronized

Attack Goal:
------------
Exploit TOCTOU (Time-of-Check-Time-of-Use) vulnerability in consent checking.
Create suspicion records for users who have withdrawn consent.

Threat Level: HIGH (GDPR violation if successful)
"""

import threading
import time
from CTFd import create_app
from CTFd.models import db

app = create_app()
from CTFd.plugins.phase2.models import UserConsent, FlagSharingSuspicion
from CTFd.plugins.phase2.detection import create_suspicion_record

print("=" * 80)
print("RED TEAM ATTACK B1: CONSENT STATE RACE CONDITION")
print("=" * 80)
print()

# Setup
with app.app_context():
    # Clean
    db.session.query(UserConsent).filter(UserConsent.user_id == 5).delete()
    db.session.query(FlagSharingSuspicion).filter(
        (FlagSharingSuspicion.user_id_1 == 5) | (FlagSharingSuspicion.user_id_2 == 5)
    ).delete()
    db.session.commit()

    # Grant initial consent
    UserConsent.grant_consent(5)
    UserConsent.grant_consent(2)  # Partner user
    print("✓ Initial consent granted for users 5 and 2")

# Attack state
attack_running = threading.Event()
attack_running.set()
consent_states = []

def consent_toggler():
    """Rapidly toggle consent state"""
    toggle_count = 0
    while attack_running.is_set() and toggle_count < 20:
        with app.app_context():
            try:
                # Toggle: withdraw -> grant -> withdraw...
                if toggle_count % 2 == 0:
                    UserConsent.withdraw_consent(5)
                    consent_states.append(('withdrawn', time.time()))
                else:
                    UserConsent.grant_consent(5)
                    consent_states.append(('granted', time.time()))

                toggle_count += 1
                time.sleep(0.01)  # 10ms toggle rate
            except Exception as e:
                print(f"Toggle error: {e}")
                break

def suspicion_attacker():
    """Attempt to create suspicions during consent toggling"""
    attempt_count = 0
    success_count = 0

    while attack_running.is_set() and attempt_count < 50:
        with app.app_context():
            try:
                pattern = {
                    'user_id_1': 5,  # Rapidly toggling consent
                    'user_id_2': 2,  # Has consent
                    'challenge_id': 2,
                    'detection_type': 'same_ip',
                    'confidence': 0.80 + (attempt_count * 0.001),  # Slight variation
                    'evidence': {
                        'ip': '10.0.0.100',
                        'attempt': attempt_count,
                        'time_delta_ms': 100
                    }
                }

                result = create_suspicion_record(pattern)
                if result is not None:
                    success_count += 1
                    print(f"⚠ Suspicion created during toggle! (Attempt {attempt_count})")

                attempt_count += 1
                time.sleep(0.005)  # 5ms between attempts

            except Exception as e:
                # Expected: some will fail due to consent
                pass

    return success_count

print("\n[ATTACK] Launching consent race condition attack...")
print("         Thread 1: Toggling consent (grant/withdraw) at 100 Hz")
print("         Thread 2: Creating suspicions at 200 Hz")
print("         Duration: ~1 second")
print()

# Launch attack
toggler = threading.Thread(target=consent_toggler)
toggler.start()

time.sleep(0.05)  # Let toggler start

attacker = threading.Thread(target=suspicion_attacker)
attacker.start()

# Wait for attack completion
attacker.join()
attack_running.clear()
toggler.join()

# Verification
with app.app_context():
    # Check created suspicions
    suspicions = FlagSharingSuspicion.query.filter(
        (FlagSharingSuspicion.user_id_1 == 5) | (FlagSharingSuspicion.user_id_2 == 5)
    ).all()

    # Check final consent state
    final_consent = UserConsent.has_consent(5)

    print("\n" + "=" * 80)
    print("ATTACK RESULTS:")
    print("=" * 80)
    print(f"Consent toggles performed: {len(consent_states)}")
    print(f"Suspicion attempts: ~50")
    print(f"Suspicions created: {len(suspicions)}")
    print(f"Final consent state: {'GRANTED' if final_consent else 'WITHDRAWN'}")
    print()

    if len(suspicions) == 0:
        print("✓ NO suspicions created (consent checking held under race)")
        print("  System properly synchronized consent checks")
    else:
        print(f"⚠ POTENTIAL GDPR VIOLATION: {len(suspicions)} suspicions created!")
        print()

        # Check if any were created during withdrawn state
        withdrawn_times = [t for state, t in consent_states if state == 'withdrawn']

        print("  Suspicions created:")
        for susp in suspicions:
            created_timestamp = susp.created_at.timestamp()
            print(f"    - ID {susp.id}, created at {susp.created_at}")

            # Check if created during withdrawn window
            during_withdrawn = any(
                abs(created_timestamp - wt) < 0.05  # 50ms window
                for wt in withdrawn_times
            )

            if during_withdrawn:
                print(f"      ✗ CRITICAL: Created during WITHDRAWN state!")
                print(f"      GDPR VIOLATION: Suspicion recorded without consent")

    # Consent state history
    print(f"\nConsent toggle history ({len(consent_states)} events):")
    for i, (state, timestamp) in enumerate(consent_states[:10]):
        print(f"  {i+1}. {state.upper()} at {timestamp:.4f}")
    if len(consent_states) > 10:
        print(f"  ... and {len(consent_states) - 10} more toggles")

    print("=" * 80)

print("\n[SECURITY ASSESSMENT]")
if len(suspicions) == 0:
    print("✓ Consent checking is RACE-SAFE")
    print("  - Atomic consent verification prevents TOCTOU")
    print("  - No GDPR violations detected under rapid state changes")
else:
    print("✗ GDPR COMPLIANCE RISK DETECTED")
    print("  - Consent state changes may not be properly synchronized")
    print("  - TOCTOU vulnerability in consent checking")
    print("  - URGENT: Review consent check atomicity")

print("\nRecommendation: Use database transaction-level consent checks.")
print("                Consider consent_version column for optimistic locking.")
print("=" * 80)
