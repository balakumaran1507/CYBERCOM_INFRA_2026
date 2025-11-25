"""
Phase 2 Background Workers
===========================

APScheduler-based background workers for async processing.

Workers:
1. Challenge Health Worker - Hourly snapshots
2. Analytics Worker - Flag sharing pattern detection
3. Cleanup Worker - Old data retention

Performance: All workers run async, NO impact on submission flow.
"""

from flask_apscheduler import APScheduler
from CTFd import create_app
from CTFd.models import db, Challenges
from .models import ChallengeHealthSnapshot
from .config import Phase2Config
from .utils import calculate_challenge_health, cleanup_old_data
from .detection import detect_flag_sharing_patterns

# Global scheduler instance
phase2_scheduler = APScheduler()


def start_phase2_workers(app):
    """
    Start Phase 2 background workers using APScheduler.

    Called during plugin load().

    Workers:
    - challenge_health: Every HEALTH_INTERVAL_HOURS hours
    - analytics: Every ANALYTICS_INTERVAL_SECONDS seconds
    - cleanup: Daily at 3:00 AM UTC

    Args:
        app: Flask app instance
    """
    print("[PHASE2 WORKERS] Starting background workers...")

    # Initialize scheduler
    phase2_scheduler.init_app(app)

    # Guard against scheduler already running (e.g., from Whale plugin or plugin reload)
    try:
        if not phase2_scheduler.running:
            phase2_scheduler.start()
            print("[PHASE2 WORKERS] ✅ Scheduler started")
        else:
            print("[PHASE2 WORKERS] ℹ️  Scheduler already running, reusing existing instance")
    except Exception as e:
        # Scheduler may already be running globally even if this instance reports not running
        if "already running" in str(e).lower():
            print(f"[PHASE2 WORKERS] ℹ️  Scheduler already active globally, proceeding with job registration")
        else:
            raise  # Re-raise if it's a different error

    # Worker 1: Challenge Health Monitoring
    if Phase2Config.HEALTH_ENABLED:
        phase2_scheduler.add_job(
            id='phase2-challenge-health',
            func=challenge_health_worker,
            trigger='interval',
            hours=Phase2Config.HEALTH_INTERVAL_HOURS,
            max_instances=1,  # Prevent concurrent runs
            coalesce=True,  # Skip missed runs if worker takes too long
            replace_existing=True
        )
        print(f"[PHASE2 WORKERS] ✅ Challenge Health Worker (interval={Phase2Config.HEALTH_INTERVAL_HOURS}h)")

    # Worker 2: Analytics / Flag Sharing Detection
    if Phase2Config.SUSPICION_ENABLED:
        phase2_scheduler.add_job(
            id='phase2-analytics',
            func=analytics_worker,
            trigger='interval',
            seconds=Phase2Config.ANALYTICS_INTERVAL_SECONDS,
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        print(f"[PHASE2 WORKERS] ✅ Analytics Worker (interval={Phase2Config.ANALYTICS_INTERVAL_SECONDS}s)")

    # Worker 3: Data Cleanup (daily at 3 AM UTC)
    phase2_scheduler.add_job(
        id='phase2-cleanup',
        func=cleanup_worker,
        trigger='cron',
        hour=3,
        minute=0,
        max_instances=1,
        replace_existing=True
    )
    print("[PHASE2 WORKERS] ✅ Cleanup Worker (daily 3:00 AM UTC)")

    print("[PHASE2 WORKERS] All workers started successfully")


def challenge_health_worker():
    """
    Challenge Health Monitoring Worker.

    Runs every HEALTH_INTERVAL_HOURS hours.

    Process:
    1. Get all visible challenges
    2. Calculate health metrics for each
    3. Create health snapshot records

    Performance: ~100-500ms per challenge (async, no user impact)
    """
    if not Phase2Config.HEALTH_ENABLED:
        return

    print("[PHASE2 HEALTH] Starting health monitoring...")

    # Create app context for database access
    app = create_app()

    with app.app_context():
        try:
            # Get all visible challenges
            challenges = Challenges.query.filter(
                Challenges.state != 'hidden'
            ).all()

            print(f"[PHASE2 HEALTH] Analyzing {len(challenges)} challenges")

            snapshots_created = 0

            for challenge in challenges:
                try:
                    # Calculate health metrics
                    health = calculate_challenge_health(challenge.id)

                    # Create snapshot
                    snapshot = ChallengeHealthSnapshot(
                        challenge_id=challenge.id,
                        solves=health['solves'],
                        attempts=health['attempts'],
                        solve_rate=health['solve_rate'],
                        health_score=health['health_score'],
                        status=health['status']
                    )

                    db.session.add(snapshot)
                    snapshots_created += 1

                    # Log unhealthy challenges
                    if health['status'] != 'HEALTHY':
                        print(f"[PHASE2 HEALTH] ⚠️  Challenge {challenge.id} ({challenge.name}): "
                              f"{health['status']} (score={health['health_score']})")

                except Exception as e:
                    print(f"[PHASE2 HEALTH ERROR] Failed to process challenge {challenge.id}: {e}")
                    continue

            # Commit all snapshots
            db.session.commit()

            print(f"[PHASE2 HEALTH] ✅ Created {snapshots_created} health snapshots")

        except Exception as e:
            db.session.rollback()
            print(f"[PHASE2 HEALTH ERROR] Health monitoring failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # CRITICAL: Clean up database connections to prevent leak
            db.session.remove()
            db.engine.dispose()


def analytics_worker():
    """
    Analytics Worker - Flag Sharing Pattern Detection.

    Runs every ANALYTICS_INTERVAL_SECONDS seconds.

    Process:
    1. Fetch recent submissions (last 2 intervals)
    2. Run pattern detection algorithms
    3. Create suspicion records for patterns above threshold

    Performance: ~100-2000ms depending on submission volume (async)
    """
    if not Phase2Config.SUSPICION_ENABLED:
        return

    print("[PHASE2 ANALYTICS] Starting analytics worker...")

    # Create app context for database access
    app = create_app()

    with app.app_context():
        try:
            # Run pattern detection
            suspicions_created = detect_flag_sharing_patterns()

            print(f"[PHASE2 ANALYTICS] ✅ Completed (suspicions={suspicions_created})")

        except Exception as e:
            print(f"[PHASE2 ANALYTICS ERROR] Analytics worker failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # CRITICAL: Clean up database connections to prevent leak
            db.session.remove()
            db.engine.dispose()


def cleanup_worker():
    """
    Cleanup Worker - Data Retention.

    Runs daily at 3:00 AM UTC.

    Process:
    1. Delete suspicion records older than RETENTION_DAYS
    2. Delete health snapshots older than RETENTION_DAYS
    3. First blood records are kept forever (prestige is permanent)

    Performance: ~100-1000ms depending on data volume
    """
    print("[PHASE2 CLEANUP] Starting cleanup worker...")

    # Create app context for database access
    app = create_app()

    with app.app_context():
        try:
            # Run cleanup
            result = cleanup_old_data()

            print(f"[PHASE2 CLEANUP] ✅ Deleted {result['suspicions_deleted']} suspicions, "
                  f"{result['health_deleted']} health snapshots")

        except Exception as e:
            print(f"[PHASE2 CLEANUP ERROR] Cleanup worker failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # CRITICAL: Clean up database connections to prevent leak
            db.session.remove()
            db.engine.dispose()
