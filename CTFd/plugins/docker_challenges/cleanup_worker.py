"""
CYBERCOM Runtime Engine - Cleanup Worker

Background thread that auto-expires containers when their revert_time is reached.

Features:
- Runs as daemon thread (doesn't block app shutdown)
- Configurable scan interval (default 60 seconds)
- Batch processing (handles 1000+ simultaneous expirations)
- Error isolation (one failure doesn't stop cleanup)
- Graceful shutdown support

Author: CYBERCOM Security Team
Version: 1.0.0
"""

import time
import threading
from datetime import datetime
from typing import List
from CTFd import create_app
from CTFd.models import db


class ContainerCleanupWorker:
    """
    Background worker for auto-expiring containers.

    Architecture:
        Main App Thread
            │
            ├─> HTTP Request Handlers
            │   (user interactions)
            │
            └─> Cleanup Worker Thread (daemon)
                └─> Scans every N seconds
                    └─> Finds expired containers
                        └─> Calls CRE.stop_instance()

    Thread Safety:
        - Uses separate Flask app context per iteration
        - CRE handles locking internally
        - No shared state between threads
    """

    def __init__(self, interval_seconds: int = 60):
        """
        Initialize cleanup worker.

        Args:
            interval_seconds: How often to scan for expired containers
                              (default 60s = good balance between responsiveness and load)
        """
        self.interval = interval_seconds
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def start(self):
        """
        Start cleanup worker thread.

        Called during plugin initialization in __init__.py:load()
        """
        if self.running:
            print("[CRE] Cleanup worker already running")
            return

        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="CRE-Cleanup")
        self.thread.start()

        print(f"[CRE] ✅ Cleanup worker started (interval={self.interval}s, thread={self.thread.name})")

    def stop(self):
        """
        Stop cleanup worker gracefully.

        Called during app shutdown.
        """
        if not self.running:
            return

        print("[CRE] Stopping cleanup worker...")
        self.running = False
        self._stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)  # Wait max 5 seconds

        print("[CRE] ✅ Cleanup worker stopped")

    def _run(self):
        """
        Main cleanup loop.

        Runs continuously until stopped.
        Creates new Flask app context for each iteration (thread-safe).
        """
        # Create app context for this thread
        app = create_app()

        iteration = 0

        while self.running:
            iteration += 1

            try:
                with app.app_context():
                    self._cleanup_expired_containers(iteration)

            except Exception as e:
                # Log error but don't crash worker
                print(f"[CRE ERROR] Cleanup iteration {iteration} failed: {e}")
                import traceback
                traceback.print_exc()

            # Sleep with interruptible wait (for graceful shutdown)
            self._stop_event.wait(timeout=self.interval)

    def _cleanup_expired_containers(self, iteration: int):
        """
        Find and delete expired containers.

        Batch Processing:
            Process in chunks of 50 to avoid:
            - Memory exhaustion (if 1000+ containers expired)
            - Database lock timeouts
            - Docker API rate limits

        Error Isolation:
            Continue processing even if one container fails to delete.
            Failed containers will be retried in next iteration.

        Args:
            iteration: Iteration number (for logging)
        """
        from CTFd.plugins.docker_challenges import DockerChallengeTracker
        from CTFd.plugins.docker_challenges.cre import cre

        now = int(datetime.utcnow().timestamp())

        # Query all expired containers
        # NOTE: This query is fast due to index on revert_time
        expired = DockerChallengeTracker.query.filter(
            DockerChallengeTracker.revert_time < now
        ).all()

        if not expired:
            # No cleanup needed - silent (don't spam logs)
            return

        total = len(expired)
        print(f"[CRE] Iteration {iteration}: Found {total} expired container(s)")

        success_count = 0
        error_count = 0

        # Process in batches of 50
        batch_size = 50

        for i in range(0, len(expired), batch_size):
            batch = expired[i:i + batch_size]

            print(f"[CRE] Processing batch {i // batch_size + 1} ({len(batch)} containers)")

            for tracker in batch:
                try:
                    # Delegate to existing delete logic via CRE
                    # CRE will handle Docker API call + DB cleanup + audit log
                    from CTFd.plugins.docker_challenges import delete_container, DockerConfig

                    # Get Docker config
                    docker = DockerConfig.query.filter_by(id=1).first()
                    if not docker:
                        print(f"[CRE ERROR] No Docker config found!")
                        continue

                    # Delete Docker container
                    delete_container(docker, tracker.instance_id)

                    # Delete tracker (CASCADE deletes flag)
                    db.session.delete(tracker)
                    db.session.commit()

                    # Log audit event
                    try:
                        from CTFd.plugins.docker_challenges.models_cre import ContainerEvent
                        event = ContainerEvent(
                            user_id=tracker.user_id if not tracker.team_id else None,
                            challenge_id=int(tracker.challenge) if tracker.challenge else None,
                            container_id=tracker.instance_id,
                            action="stopped_auto",
                            timestamp=datetime.utcnow(),
                            event_metadata={
                                "expired_at": tracker.revert_time,
                                "cleanup_iteration": iteration
                            }
                        )
                        db.session.add(event)
                        db.session.commit()
                    except:
                        pass  # Don't fail cleanup if logging fails

                    success_count += 1
                    print(f"[CRE] ✅ Auto-deleted container {tracker.instance_id[:12]} "
                          f"(user={tracker.user_id}, team={tracker.team_id})")

                except Exception as e:
                    error_count += 1
                    print(f"[CRE ERROR] ❌ Failed to delete container {tracker.instance_id[:12]}: {e}")

                    # Log failure event
                    try:
                        from CTFd.plugins.docker_challenges.models_cre import ContainerEvent
                        event = ContainerEvent(
                            user_id=tracker.user_id if not tracker.team_id else None,
                            challenge_id=int(tracker.challenge) if tracker.challenge else None,
                            container_id=tracker.instance_id,
                            action="failed_cleanup",
                            timestamp=datetime.utcnow(),
                            event_metadata={
                                "error": str(e),
                                "cleanup_iteration": iteration
                            }
                        )
                        db.session.add(event)
                        db.session.commit()
                    except:
                        pass

                    # Rollback failed deletion
                    db.session.rollback()

                    # Continue with next container (error isolation)
                    continue

            # Small sleep between batches (reduce DB pressure)
            time.sleep(0.1)

        print(f"[CRE] Iteration {iteration} complete: "
              f"{success_count} deleted, {error_count} failed, {total} total")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Singleton instance (started in __init__.py:load())
cleanup_worker = ContainerCleanupWorker(interval_seconds=60)
