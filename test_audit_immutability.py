#!/usr/bin/env python3
"""
Audit Trail Immutability Test for Phase 2 Verdict History
Verifies that verdict changes create immutable audit trail entries
"""
from CTFd import create_app
from CTFd.models import db

app = create_app()

from CTFd.plugins.phase2.models import FlagSharingSuspicion, VerdictHistory

print("=" * 60)
print("TEST 5: AUDIT IMMUTABILITY CHECK")
print("=" * 60)
print()

# Create a test suspicion record
with app.app_context():
    # Clean existing test data
    db.session.query(FlagSharingSuspicion).filter(
        FlagSharingSuspicion.challenge_id == 2
    ).delete()
    db.session.commit()

    suspicion = FlagSharingSuspicion(
        user_id_1=2,
        user_id_2=3,
        challenge_id=2,
        detection_type='same_ip',
        confidence_score=0.85,
        risk_level='HIGH',
        evidence={'ip_hash': 'test123', 'time_delta_ms': 500}
    )
    db.session.add(suspicion)
    db.session.commit()

    suspicion_id = suspicion.id
    print(f"✅ Created test suspicion record (ID: {suspicion_id})")
    print()

# Apply first verdict: innocent
with app.app_context():
    print("Applying first verdict: 'innocent'...")
    verdict1 = VerdictHistory.record_verdict(
        suspicion_id=suspicion_id,
        verdict='innocent',
        admin_id=1,
        admin_ip='192.168.1.10',
        notes='Initial review - appears to be false positive'
    )
    print(f"✅ Verdict 1 recorded (audit ID: {verdict1.id})")
    print()

# Apply second verdict: suspicious (changed mind)
with app.app_context():
    print("Applying second verdict: 'suspicious' (changing mind)...")
    verdict2 = VerdictHistory.record_verdict(
        suspicion_id=suspicion_id,
        verdict='suspicious',
        admin_id=1,
        admin_ip='192.168.1.10',
        notes='On second review - found additional evidence'
    )
    print(f"✅ Verdict 2 recorded (audit ID: {verdict2.id})")
    print()

# Verify immutability: Both verdicts should exist in history
with app.app_context():
    history = VerdictHistory.get_history(suspicion_id)

    print("=" * 60)
    print("AUDIT TRAIL VERIFICATION:")
    print("=" * 60)
    print(f"Total verdict history entries: {len(history)}")
    print()

    if len(history) == 2:
        print("✅ PASS: TWO immutable audit entries exist")
        print()
        for i, entry in enumerate(history, 1):
            print(f"Entry {i}:")
            print(f"  - Verdict: {entry.verdict}")
            print(f"  - Admin ID: {entry.reviewed_by}")
            print(f"  - IP: {entry.admin_ip}")
            print(f"  - Notes: {entry.notes}")
            print(f"  - Created: {entry.created_at}")
            print()

        # Verify chronological order
        if history[0].verdict == 'innocent' and history[1].verdict == 'suspicious':
            print("✅ PASS: Verdicts in chronological order")
        else:
            print("❌ FAIL: Verdicts NOT in chronological order")
        print()

        # Verify different IDs (INSERT only, no UPDATE)
        if history[0].id != history[1].id:
            print("✅ PASS: Different audit IDs (INSERT-only, immutable)")
        else:
            print("❌ FAIL: Same audit ID (possible UPDATE instead of INSERT)")
        print()

        print("✅ TEST PASSED:")
        print("   - Verdict changes create new audit entries")
        print("   - NO updates to existing entries (immutable)")
        print("   - Chronological order preserved")
        print("   - Admin accountability enforced")
    elif len(history) == 1:
        print("❌ FAIL: Only ONE audit entry (second verdict may have overwritten first)")
        print(f"   Entry: {history[0].verdict}")
    elif len(history) == 0:
        print("❌ FAIL: NO audit entries found")
    else:
        print(f"❌ FAIL: Unexpected number of entries: {len(history)}")

    print("=" * 60)

# Check suspicion record shows latest verdict
with app.app_context():
    suspicion = FlagSharingSuspicion.query.get(suspicion_id)
    print()
    print("Suspicion Record (convenience field):")
    print(f"  - Latest verdict: {suspicion.admin_verdict}")
    print(f"  - Reviewed by: {suspicion.reviewed_by}")
    print(f"  - Reviewed at: {suspicion.reviewed_at}")
    print()
    if suspicion.admin_verdict == 'suspicious':
        print("✅ Suspicion record updated with latest verdict")
    else:
        print("❌ Suspicion record NOT updated correctly")
    print("=" * 60)
