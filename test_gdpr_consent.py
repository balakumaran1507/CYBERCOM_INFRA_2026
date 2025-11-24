#!/usr/bin/env python3
"""
GDPR Consent Enforcement Test for Phase 2 Flag Sharing Detection
Verifies that suspicion records are NOT created without user consent
"""
from CTFd import create_app
from CTFd.models import db

app = create_app()

# Import Phase 2 models AFTER app creation to avoid context issues
from CTFd.plugins.phase2.models import UserConsent, FlagSharingSuspicion
from CTFd.plugins.phase2.detection import create_suspicion_record

print("=" * 60)
print("TEST 4: GDPR CONSENT ENFORCEMENT")
print("=" * 60)
print()

# Setup: Grant consent for user 2, NOT for user 3
with app.app_context():
    # Clean existing consent records
    db.session.query(UserConsent).filter(UserConsent.user_id.in_([2, 3])).delete()
    db.session.commit()

    # Grant consent for user 2 ONLY
    UserConsent.grant_consent(2)
    print("✅ Granted consent for user 2 (racetest1)")
    print("✅ User 3 (racetest2) has NO consent")
    print()

# Test: Try to create suspicion record for users 2 and 3
with app.app_context():
    pattern = {
        'user_id_1': 2,
        'user_id_2': 3,
        'challenge_id': 1,
        'detection_type': 'same_ip',
        'confidence': 0.85,
        'evidence': {
            'ip': '192.168.1.100',
            'user_agent_1': 'Mozilla/5.0 (test)',
            'user_agent_2': 'Mozilla/5.0 (test)',
            'time_delta_ms': 500
        }
    }

    print("Attempting to create suspicion for users 2 and 3...")
    result = create_suspicion_record(pattern)
    print()

    if result is None:
        print("✅ PASS: Suspicion record NOT created (user 3 lacks consent)")
    else:
        print("❌ FAIL: Suspicion record WAS created despite lacking consent!")
        print(f"   Record ID: {result.id}")
    print()

# Test reverse: user_id_1=3 (no consent), user_id_2=2 (consented)
with app.app_context():
    pattern_reverse = {
        'user_id_1': 3,  # No consent
        'user_id_2': 2,  # Has consent        'challenge_id': 1,
        'detection_type': 'same_ip',
        'confidence': 0.75,
        'evidence': {
            'ip': '192.168.1.100',
            'time_delta_ms': 300
        }
    }

    print("Testing reverse scenario (user 3 first, user 2 second)...")
    result_reverse = create_suspicion_record(pattern_reverse)
    print()

    if result_reverse is None:
        print("✅ PASS: Suspicion record NOT created (user 3 lacks consent)")
    else:
        print("❌ FAIL: Suspicion record WAS created despite lacking consent!")
        print(f"   Record ID: {result_reverse.id}")
    print()

# Verify: Grant consent for BOTH users and try again
with app.app_context():
    UserConsent.grant_consent(3)
    print("✅ Granted consent for user 3")
    print()

    pattern_both_consented = {
        'user_id_1': 2,
        'user_id_2': 3,
        'challenge_id': 1,
        'detection_type': 'same_ip',
        'confidence': 0.90,
        'evidence': {
            'ip': '192.168.1.100',
            'time_delta_ms': 200
        }
    }

    print("Testing with BOTH users consented...")
    result_both = create_suspicion_record(pattern_both_consented)
    print()

    if result_both is not None:
        print("✅ PASS: Suspicion record created when BOTH users consented")
        print(f"   Record ID: {result_both.id}")
    else:
        print("❌ FAIL: Suspicion record NOT created even with full consent!")
    print()

# Final verification
with app.app_context():
    suspicion_count = FlagSharingSuspicion.query.filter(
        db.or_(
            db.and_(FlagSharingSuspicion.user_id_1.in_([2, 3]),
                    FlagSharingSuspicion.user_id_2.in_([2, 3])),
            FlagSharingSuspicion.user_id_1.in_([2, 3])
        )
    ).count()

    print("=" * 60)
    print("FINAL RESULTS:")
    print("=" * 60)
    print(f"Total suspicion records created: {suspicion_count}")

    if suspicion_count == 1:
        print("✅ TEST PASSED:")
        print("   - NO records when consent missing")
        print("   - ONE record when both users consented")
        print("   - GDPR compliance verified")
    elif suspicion_count == 0:
        print("❌ TEST FAILED:")
        print("   - No records created even with full consent")
    else:
        print("❌ TEST FAILED:")
        print(f"   - Expected 1 record, got {suspicion_count}")
    print("=" * 60)
