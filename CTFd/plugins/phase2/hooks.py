"""
Phase 2 SQLAlchemy Event Hooks
================================

Event hooks for intercepting database operations.

CRITICAL: These hooks run SYNCHRONOUSLY during db.session.commit()
- Must be FAST (<20ms total overhead)
- Must NOT raise exceptions (would rollback transaction)
- Heavy work should be offloaded to async workers

Hooks:
1. Solves.after_insert - First blood detection
2. Submissions.after_insert - Metadata capture for analytics (future)
"""

from sqlalchemy import event
from CTFd.models import Solves, Submissions, Challenges, db
from CTFd.cache import cache
from .models import FirstBloodPrestige
from .config import Phase2Config
from .utils import calculate_prestige_score, get_signed_cache, set_signed_cache
import datetime


def register_phase2_hooks():
    """
    Register all Phase 2 SQLAlchemy event hooks.

    Called during plugin load().
    """
    print("[PHASE2 HOOKS] Registering SQLAlchemy event hooks...")

    # Hook 1: First Blood Detection (on Solves)
    if Phase2Config.FIRST_BLOOD_ENABLED:
        event.listen(Solves, 'after_insert', on_solve_inserted)
        print("[PHASE2 HOOKS] ✅ Registered first_blood hook (Solves.after_insert)")

    # Hook 2: Metadata Capture (on Submissions) - Placeholder for future
    # if Phase2Config.SUSPICION_ENABLED:
    #     event.listen(Submissions, 'after_insert', on_submission_inserted)
    #     print("[PHASE2 HOOKS] ✅ Registered metadata_capture hook (Submissions.after_insert)")

    print("[PHASE2 HOOKS] Event hooks registered successfully")


def on_solve_inserted(mapper, connection, target):
    """
    SECURITY-HARDENED: First Blood Detection with Advisory Locks

    SQLAlchemy event hook: Fires after a Solve is inserted.

    SECURITY IMPROVEMENTS (2025-11-24):
    ✅ Database advisory locks prevent race conditions
    ✅ Timestamp-based tie-breaking (NOT solve.id)
    ✅ Redis used for optimization ONLY (never authority)
    ✅ UNIQUE constraint on challenge_id enforces atomicity
    ✅ Handles concurrent submissions with <1ms precision

    Performance Budget: ~10-15ms
    - Redis optimization check: ~0.5ms (hint only)
    - Advisory lock acquisition: ~1-2ms
    - Timestamp-based query: ~5-8ms
    - First blood insert: ~2-3ms
    - Redis cache update: ~0.5ms

    Tie-Breaker Rules:
    1. Earliest timestamp wins (microsecond precision)
    2. If exact timestamp match: lowest user_id wins (deterministic)
    3. UNIQUE(challenge_id) constraint prevents duplicates

    Args:
        mapper: SQLAlchemy mapper
        connection: Database connection (use for raw SQL within transaction)
        target: The Solve object being inserted
    """
    if not Phase2Config.FIRST_BLOOD_ENABLED:
        return

    try:
        challenge_id = target.challenge_id
        solve_id = target.id
        user_id = target.user_id
        team_id = target.team_id
        solve_timestamp = target.date if target.date else datetime.datetime.utcnow()

        # SECURITY: HMAC-signed Redis cache (optimization hint ONLY, never authority)
        # This is a performance hint - we ALWAYS verify with database
        redis_key = f'phase2:first_blood_claimed:{challenge_id}'
        cached_hint = get_signed_cache(cache, redis_key)

        # Even if signed cache says "claimed", we still verify with DB
        # Signature prevents cache poisoning attacks

        from sqlalchemy import text

        # STEP 1: Acquire database advisory lock for this challenge
        # This ensures ONLY ONE transaction processes first blood at a time
        # Lock is automatically released at transaction end (COMMIT/ROLLBACK)

        # Try to acquire lock (10 second timeout)
        # MySQL: GET_LOCK returns 1 on success, 0 on timeout, NULL on error
        try:
            lock_result = connection.execute(
                text("SELECT GET_LOCK(:lock_name, 10) AS lock_acquired"),
                {'lock_name': f'phase2_first_blood_{challenge_id}'}
            ).scalar()

            if lock_result != 1:
                print(f"[PHASE2 FIRST BLOOD WARNING] Failed to acquire advisory lock for challenge {challenge_id} (timeout or error)")
                return  # Skip first blood detection on lock failure (graceful degradation)
        except Exception as lock_error:
            # PostgreSQL or SQLite might not support GET_LOCK
            # Fall back to database-level uniqueness enforcement
            print(f"[PHASE2 FIRST BLOOD INFO] Advisory locks not supported, relying on UNIQUE constraint: {lock_error}")
            # Continue without lock - UNIQUE constraint will prevent duplicates

        # STEP 2: Check for existing first blood record (optimization)
        # If first blood already claimed, skip expensive solve timestamp checks
        existing_fb_record = connection.execute(
            text("""
                SELECT id FROM phase2_first_blood_prestige
                WHERE challenge_id = :challenge_id
                LIMIT 1
            """),
            {'challenge_id': challenge_id}
        ).first()

        if existing_fb_record:
            # First blood already recorded in database
            # Update signed cache hint and exit
            set_signed_cache(cache, redis_key, '1', timeout=Phase2Config.FIRST_BLOOD_REDIS_TTL)
            return

        # STEP 3: Timestamp-based authority check
        # Check if ANY solve exists with earlier timestamp
        # Tie-breaker: If timestamps match, lowest user_id wins
        # SECURITY FIX: JOIN with submissions table for timestamp (solves inherits from submissions)
        existing_earlier_solve = connection.execute(
            text("""
                SELECT s.id, s.user_id, sub.date
                FROM solves s
                JOIN submissions sub ON sub.id = s.id
                WHERE s.challenge_id = :challenge_id
                AND (
                    sub.date < :solve_timestamp
                    OR (sub.date = :solve_timestamp AND s.user_id < :user_id)
                )
                ORDER BY sub.date ASC, s.user_id ASC
                LIMIT 1
            """),
            {
                'challenge_id': challenge_id,
                'solve_timestamp': solve_timestamp,
                'user_id': user_id
            }
        ).first()

        if existing_earlier_solve:
            # Not first blood - another solve has earlier timestamp or lower user_id
            # Update signed cache hint to skip future checks
            set_signed_cache(cache, redis_key, '1', timeout=Phase2Config.FIRST_BLOOD_REDIS_TTL)
            return

        # THIS IS FIRST BLOOD! 🩸

        # Get challenge value for prestige calculation
        challenge = connection.execute(
            text("SELECT value FROM challenges WHERE id = :id"),
            {'id': challenge_id}
        ).first()

        challenge_value = challenge[0] if challenge else 100

        # Calculate prestige score
        prestige = calculate_prestige_score(challenge_value)

        # STEP 4: Create first blood record
        # UNIQUE constraint on challenge_id ensures no duplicates
        # If concurrent insert happens, one will succeed, other will fail silently
        try:
            connection.execute(
                text("""
                    INSERT INTO phase2_first_blood_prestige
                    (solve_id, challenge_id, user_id, team_id, prestige_score, timestamp)
                    VALUES (:solve_id, :challenge_id, :user_id, :team_id, :prestige, :timestamp)
                """),
                {
                    'solve_id': solve_id,
                    'challenge_id': challenge_id,
                    'user_id': user_id,
                    'team_id': team_id,
                    'prestige': prestige,
                    'timestamp': solve_timestamp
                }
            )

            # Cache result as HMAC-signed optimization hint (NOT authority)
            set_signed_cache(cache, redis_key, '1', timeout=Phase2Config.FIRST_BLOOD_REDIS_TTL)

            print(f"[PHASE2 FIRST BLOOD] 🩸 Challenge {challenge_id} - "
                  f"User {user_id} Team {team_id} - "
                  f"Prestige {prestige} (timestamp={solve_timestamp})")

        except Exception as insert_error:
            # UNIQUE constraint violation - another transaction won the race
            # This is EXPECTED in high-concurrency scenarios
            if 'unique' in str(insert_error).lower() or 'duplicate' in str(insert_error).lower():
                print(f"[PHASE2 FIRST BLOOD INFO] Concurrent first blood detected for challenge {challenge_id}, another transaction won")
                set_signed_cache(cache, redis_key, '1', timeout=Phase2Config.FIRST_BLOOD_REDIS_TTL)
            else:
                # Unexpected error
                raise

        # Release advisory lock (if acquired)
        try:
            connection.execute(
                text("SELECT RELEASE_LOCK(:lock_name)"),
                {'lock_name': f'phase2_first_blood_{challenge_id}'}
            )
        except:
            pass  # Lock auto-releases on transaction end anyway

    except Exception as e:
        # CRITICAL: Do NOT raise exception (would rollback solve)
        # Log error and continue
        print(f"[PHASE2 FIRST BLOOD ERROR] Failed to record first blood: {e}")
        import traceback
        traceback.print_exc()


def on_submission_inserted(mapper, connection, target):
    """
    SQLAlchemy event hook: Fires after a Submission is inserted.

    Responsibilities:
    1. Capture metadata (user_agent, timing) for analytics
    2. Publish event to Redis for async processing

    Performance Budget: ~2-3ms
    - Redis publish: ~1-2ms
    - Metadata extraction: ~1ms

    FUTURE: Enable when user_agent column is added to Submissions table.

    Args:
        mapper: SQLAlchemy mapper
        connection: Database connection
        target: The Submission object being inserted
    """
    if not Phase2Config.SUSPICION_ENABLED:
        return

    try:
        # Quick metadata capture
        metadata = {
            'submission_id': target.id,
            'user_id': target.user_id,
            'challenge_id': target.challenge_id,
            'ip': target.ip,
            'user_agent': getattr(target, 'user_agent', None),  # If column exists
            'type': target.type,
            'timestamp': target.date.timestamp() if target.date else None
        }

        # Publish to Redis for async analytics worker
        # NOTE: This is fire-and-forget (won't block submission)
        # cache.publish('phase2:submission_event', json.dumps(metadata))

        # For MVP: Analytics worker will query database directly
        # No need to publish events

    except Exception as e:
        # CRITICAL: Do NOT raise exception
        print(f"[PHASE2 METADATA ERROR] Failed to capture submission metadata: {e}")
