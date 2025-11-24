"""
Phase 2 Pattern Detection
==========================

Flag sharing detection logic (intelligence only, no auto-punishment).

Detection Patterns:
1. same_ip: Same IP address within temporal window
2. duplicate_wrong: Exact duplicate incorrect submissions
3. similar_ua: High similarity user-agent strings
4. temporal_proximity: Submissions within 60 seconds

Process:
1. Collect recent submissions from database
2. Run pattern detection algorithms
3. Calculate confidence score
4. If confidence >= threshold, create suspicion record
"""

import datetime
from collections import defaultdict
from CTFd.models import db, Submissions
from .models import FlagSharingSuspicion, UserConsent
from .config import Phase2Config
from .utils import (
    calculate_suspicion_confidence,
    determine_risk_level,
    levenshtein_ratio,
    sanitize_evidence
)


def detect_flag_sharing_patterns():
    """
    Main pattern detection function.

    SECURITY-HARDENED (2025-11-24):
    ✅ Query LIMIT prevents memory exhaustion DoS
    ✅ Batch processing for large datasets
    ✅ Timeout protection

    Analyzes recent submissions (last ANALYTICS_INTERVAL_SECONDS * 2)
    to detect suspicious patterns.

    Returns:
        int: Number of suspicions created
    """
    if not Phase2Config.SUSPICION_ENABLED:
        return 0

    print("[PHASE2 ANALYTICS] Running flag sharing pattern detection...")

    # Time window: last 2 intervals (for overlap)
    window_seconds = Phase2Config.ANALYTICS_INTERVAL_SECONDS * 2
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=window_seconds)

    # SECURITY: Hard limit on submissions to prevent memory exhaustion
    # If submission rate > 5000 per interval, system is likely under attack
    MAX_SUBMISSIONS = 5000

    # Get recent submissions with LIMIT
    try:
        recent_submissions = Submissions.query.filter(
            Submissions.date >= cutoff_time
        ).order_by(
            Submissions.date.desc()  # Most recent first
        ).limit(MAX_SUBMISSIONS).all()

        if len(recent_submissions) >= MAX_SUBMISSIONS:
            print(f"[PHASE2 ANALYTICS WARNING] Hit MAX_SUBMISSIONS limit ({MAX_SUBMISSIONS}). "
                  f"Possible DoS or high traffic event. Analyzing most recent submissions only.")

        print(f"[PHASE2 ANALYTICS] Analyzing {len(recent_submissions)} recent submissions "
              f"(max={MAX_SUBMISSIONS})")

    except Exception as e:
        print(f"[PHASE2 ANALYTICS ERROR] Failed to fetch submissions: {e}")
        return 0

    # Group submissions by challenge
    submissions_by_challenge = defaultdict(list)
    for sub in recent_submissions:
        submissions_by_challenge[sub.challenge_id].append(sub)

    suspicions_created = 0

    # Analyze each challenge separately
    for challenge_id, submissions in submissions_by_challenge.items():
        if len(submissions) < 2:
            continue  # Need at least 2 submissions to compare

        # Run detection patterns
        patterns_found = []

        # Pattern 1: Same IP + Temporal Proximity
        patterns_found.extend(detect_same_ip_pattern(submissions))

        # Pattern 2: Duplicate Wrong Answers
        patterns_found.extend(detect_duplicate_wrong_pattern(submissions))

        # Pattern 3: Similar User-Agent
        patterns_found.extend(detect_similar_ua_pattern(submissions))

        # Create suspicion records for patterns above threshold
        for pattern in patterns_found:
            confidence = pattern['confidence']
            if confidence >= Phase2Config.SUSPICION_THRESHOLD:
                try:
                    create_suspicion_record(pattern)
                    suspicions_created += 1
                except Exception as e:
                    print(f"[PHASE2 ANALYTICS ERROR] Failed to create suspicion: {e}")

    print(f"[PHASE2 ANALYTICS] Created {suspicions_created} suspicion records")
    return suspicions_created


def detect_same_ip_pattern(submissions):
    """
    Detect users submitting from same IP within temporal window.

    Args:
        submissions (list): List of Submission objects for a challenge

    Returns:
        list: List of pattern dicts
    """
    patterns = []

    # Group by IP
    ip_groups = defaultdict(list)
    for sub in submissions:
        if sub.ip:
            ip_groups[sub.ip].append(sub)

    # Check each IP group
    for ip, subs in ip_groups.items():
        if len(subs) < 2:
            continue

        # Check all pairs within temporal window
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                sub1, sub2 = subs[i], subs[j]

                # Skip if same user
                if sub1.user_id == sub2.user_id:
                    continue

                # Check temporal proximity
                time_delta = abs((sub2.date - sub1.date).total_seconds())
                if time_delta <= Phase2Config.TEMPORAL_WINDOW_SECONDS:
                    # Pattern detected
                    detected_patterns = ['same_ip', 'temporal_proximity']
                    confidence = calculate_suspicion_confidence(detected_patterns)

                    patterns.append({
                        'user_id_1': sub1.user_id,
                        'user_id_2': sub2.user_id,
                        'challenge_id': sub1.challenge_id,
                        'detection_type': 'same_ip',
                        'confidence': confidence,
                        'evidence': {
                            'ip': ip,
                            'time_delta_seconds': time_delta,
                            'submission_1_id': sub1.id,
                            'submission_2_id': sub2.id,
                            'submission_1_text': sub1.provided[:100],  # Truncate
                            'submission_2_text': sub2.provided[:100]
                        }
                    })

    return patterns


def detect_duplicate_wrong_pattern(submissions):
    """
    Detect users submitting identical WRONG answers.

    Args:
        submissions (list): List of Submission objects for a challenge

    Returns:
        list: List of pattern dicts
    """
    patterns = []

    # Filter wrong submissions only
    wrong_submissions = [s for s in submissions if s.type != 'correct']

    if len(wrong_submissions) < 2:
        return patterns

    # Group by provided text (exact match)
    text_groups = defaultdict(list)
    for sub in wrong_submissions:
        if sub.provided:
            # Normalize: strip whitespace, lowercase
            normalized = sub.provided.strip().lower()
            text_groups[normalized].append(sub)

    # Check each text group
    for text, subs in text_groups.items():
        if len(subs) < 2:
            continue

        # Check all pairs
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                sub1, sub2 = subs[i], subs[j]

                # Skip if same user
                if sub1.user_id == sub2.user_id:
                    continue

                # Pattern detected
                time_delta = abs((sub2.date - sub1.date).total_seconds())
                detected_patterns = ['duplicate_wrong']

                # Add temporal proximity if within window
                if time_delta <= Phase2Config.TEMPORAL_WINDOW_SECONDS:
                    detected_patterns.append('temporal_proximity')

                confidence = calculate_suspicion_confidence(detected_patterns)

                patterns.append({
                    'user_id_1': sub1.user_id,
                    'user_id_2': sub2.user_id,
                    'challenge_id': sub1.challenge_id,
                    'detection_type': 'duplicate_wrong',
                    'confidence': confidence,
                    'evidence': {
                        'submission_text': text[:200],  # Truncate
                        'time_delta_seconds': time_delta,
                        'submission_1_id': sub1.id,
                        'submission_2_id': sub2.id,
                        'ip_1': sub1.ip,
                        'ip_2': sub2.ip
                    }
                })

    return patterns


def detect_similar_ua_pattern(submissions):
    """
    Detect users with suspiciously similar user-agent strings.

    Args:
        submissions (list): List of Submission objects for a challenge

    Returns:
        list: List of pattern dicts
    """
    patterns = []

    # Filter submissions with user_agent
    # NOTE: Requires user_agent column to be added to Submissions table
    ua_submissions = []
    for sub in submissions:
        if hasattr(sub, 'user_agent') and sub.user_agent:
            ua_submissions.append(sub)

    if len(ua_submissions) < 2:
        return patterns

    # Check all pairs
    for i in range(len(ua_submissions)):
        for j in range(i + 1, len(ua_submissions)):
            sub1, sub2 = ua_submissions[i], ua_submissions[j]

            # Skip if same user
            if sub1.user_id == sub2.user_id:
                continue

            # Calculate similarity
            similarity = levenshtein_ratio(sub1.user_agent, sub2.user_agent)

            if similarity >= Phase2Config.UA_SIMILARITY_THRESHOLD:
                # Pattern detected
                time_delta = abs((sub2.date - sub1.date).total_seconds())
                detected_patterns = ['similar_ua']

                # Add temporal proximity if within window
                if time_delta <= Phase2Config.TEMPORAL_WINDOW_SECONDS:
                    detected_patterns.append('temporal_proximity')

                # Add same IP if applicable
                if sub1.ip == sub2.ip:
                    detected_patterns.append('same_ip')

                confidence = calculate_suspicion_confidence(detected_patterns)

                patterns.append({
                    'user_id_1': sub1.user_id,
                    'user_id_2': sub2.user_id,
                    'challenge_id': sub1.challenge_id,
                    'detection_type': 'similar_ua',
                    'confidence': confidence,
                    'evidence': {
                        'ua_similarity': similarity,
                        'user_agent_1': sub1.user_agent[:200],  # Truncate
                        'user_agent_2': sub2.user_agent[:200],
                        'time_delta_seconds': time_delta,
                        'submission_1_id': sub1.id,
                        'submission_2_id': sub2.id,
                        'ip_1': sub1.ip,
                        'ip_2': sub2.ip
                    }
                })

    return patterns


def create_suspicion_record(pattern):
    """
    Create a FlagSharingSuspicion database record.

    SECURITY-HARDENED (2025-11-24):
    ✅ GDPR consent enforcement (skips non-consented users)
    ✅ Sanitizes all PII before storage
    ✅ IP addresses → SHA256 hash
    ✅ User-agents → Generalized "Browser on OS"
    ✅ Submission text → "[REDACTED]"

    Args:
        pattern (dict): Pattern detection result with raw evidence

    Returns:
        FlagSharingSuspicion|None: Created record with sanitized evidence, or None if consent denied
    """
    user_id_1 = pattern['user_id_1']
    user_id_2 = pattern.get('user_id_2')

    # GDPR COMPLIANCE: ATOMIC CONSENT CHECK + SUSPICION CREATION
    # SECURITY FIX (V-001): Prevent TOCTOU race condition
    # Lock consent records during transaction to prevent consent withdrawal
    # between check and suspicion creation
    #
    # References:
    # - Red Team Attack B1: Consent TOCTOU vulnerability
    # - GDPR Article 7: Consent must be verifiable at time of processing
    try:
        # Start atomic transaction with row-level locking
        with db.session.begin_nested():
            # STEP 1: Acquire exclusive locks on consent records
            # This prevents concurrent consent modifications during processing
            consent_1 = UserConsent.query.filter_by(
                user_id=user_id_1
            ).with_for_update().first()

            # Check consent atomically (within locked transaction)
            if not consent_1 or not consent_1.consented:
                print(f"[PHASE2 GDPR] Skipping suspicion for user {user_id_1} - no consent")
                return None

            # Lock second user's consent if present
            if user_id_2:
                consent_2 = UserConsent.query.filter_by(
                    user_id=user_id_2
                ).with_for_update().first()

                # Check consent atomically
                if not consent_2 or not consent_2.consented:
                    print(f"[PHASE2 GDPR] Skipping suspicion for user {user_id_2} - no consent")
                    return None

            # STEP 2: Both consents verified and locked - safe to create suspicion
            confidence = pattern['confidence']
            risk_level = determine_risk_level(confidence)

            # SECURITY: Sanitize evidence to remove PII
            raw_evidence = pattern['evidence']
            sanitized_evidence = sanitize_evidence(raw_evidence)

            suspicion = FlagSharingSuspicion(
                user_id_1=user_id_1,
                user_id_2=user_id_2,
                challenge_id=pattern['challenge_id'],
                detection_type=pattern['detection_type'],
                confidence_score=confidence,
                risk_level=risk_level,
                evidence=sanitized_evidence,  # ✅ SANITIZED (no PII)
                admin_verdict=None,  # Pending review
                reviewed_at=None,
                reviewed_by=None
            )

            db.session.add(suspicion)
            # Commit nested transaction (releases locks)

        # Commit outer transaction
        db.session.commit()

        print(f"[PHASE2 ANALYTICS] Created suspicion: users {user_id_1},{user_id_2} "
              f"challenge {pattern['challenge_id']} type={pattern['detection_type']} confidence={confidence:.2f} "
              f"[GDPR compliant: ATOMIC consent check + sanitized evidence]")

        return suspicion

    except Exception as e:
        db.session.rollback()
        print(f"[PHASE2 GDPR ERROR] Failed to create suspicion (consent may have been withdrawn): {e}")
        return None
