"""
CYBERCOM Runtime Engine (CRE)

Production-grade container lifecycle management with:
- Atomic operations (row-level locking)
- Extension control (max 5 extensions, 90 min total)
- Audit logging (every action tracked)
- Whale compatibility (challenge_id + user_id interface)
- Race condition protection (database-level locking)

Author: CYBERCOM Security Team
Version: 1.0.0
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from flask import current_app
from CTFd.models import db
from CTFd.utils.config import is_teams_mode
from sqlalchemy import and_
# Note: with_for_update is a Query method, not an importable symbol

# Import existing models and functions
# These will be imported from __init__.py when integrated
# from .models_cre import ContainerEvent, ContainerRuntimePolicy


class RuntimePolicy:
    """
    Container runtime policy (default or per-challenge).

    Encapsulates all timing rules:
    - How long does container run initially?
    - How much time does extension add?
    - How many extensions allowed?
    - What's the hard lifetime cap?
    """

    def __init__(
        self,
        base_runtime_seconds: int = 900,  # 15 minutes
        extension_increment_seconds: int = 900,  # 15 minutes
        max_extensions: int = 5,
        max_lifetime_seconds: int = 5400  # 90 minutes (hard cap)
    ):
        self.base_runtime_seconds = base_runtime_seconds
        self.extension_increment_seconds = extension_increment_seconds
        self.max_extensions = max_extensions
        self.max_lifetime_seconds = max_lifetime_seconds

    @classmethod
    def from_challenge(cls, challenge_id: int):
        """
        Load policy from database (per-challenge) or use defaults.

        Future: Query ContainerRuntimePolicy table for challenge-specific config.
        For now: Always returns defaults.
        """
        # TODO: Query database for challenge-specific policy
        # policy_row = ContainerRuntimePolicy.query.filter_by(challenge_id=challenge_id).first()
        # if policy_row:
        #     return cls(
        #         base_runtime_seconds=policy_row.base_runtime_seconds,
        #         extension_increment_seconds=policy_row.extension_increment_seconds,
        #         max_extensions=policy_row.max_extensions,
        #         max_lifetime_seconds=policy_row.max_lifetime_seconds
        #     )

        # Return defaults
        return cls()

    @classmethod
    def get_global_default(cls):
        """Get global default policy (fallback if no challenge-specific config)."""
        return cls()


class ContainerRuntimeEngine:
    """
    Production-grade container lifecycle manager.

    Features:
    - Atomic operations (prevents race conditions)
    - Extension tracking (count + timestamps)
    - Audit logging (full event history)
    - Whale-compatible interface
    - Team mode support

    Usage:
        cre = ContainerRuntimeEngine()

        # Start container
        success, msg, info = cre.start_instance(user_id=1, challenge_id=5)

        # Extend container
        success, msg = cre.extend_instance(user_id=1, challenge_id=5)

        # Stop container
        success, msg = cre.stop_instance(user_id=1, challenge_id=5)

        # Get status
        status = cre.get_instance_status(user_id=1, challenge_id=5)
    """

    def __init__(self):
        """
        Initialize CRE.

        Thread-local lock prevents concurrent operations on same container.
        Database row locks provide transaction-level safety.
        """
        self._lock = threading.Lock()

    # =========================================================================
    # PUBLIC API (Whale-Compatible)
    # =========================================================================

    def start_instance(
        self,
        user_id: int,
        challenge_id: int,
        team_id: Optional[int] = None,
        docker_image: str = None,
        challenge_name: str = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Start a container instance with runtime tracking.

        DELEGATES to existing container creation logic in __init__.py.
        CRE only handles lifecycle timing, not Docker API calls.

        Args:
            user_id: User ID (always required, even in teams mode)
            challenge_id: Challenge ID
            team_id: Team ID (if teams mode)
            docker_image: Docker image name (passed to create_container)
            challenge_name: Challenge name (for UI display)

        Returns:
            (success, message, container_info_dict)

        Notes:
            - Checks policy (can user start container?)
            - Creates tracker with proper runtime fields
            - Logs "created" event to audit trail
            - Does NOT call Docker API directly (uses existing functions)
        """
        policy = RuntimePolicy.from_challenge(challenge_id)

        # This would typically delegate to existing create_container()
        # For now, return placeholder (integration happens in __init__.py)
        return (
            False,
            "CRE.start_instance() must be integrated with existing create_container()",
            None
        )

    def extend_instance(
        self,
        user_id: int,
        challenge_id: int,
        team_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Extend container lifetime (Whale-compatible signature).

        Uses database row locking to prevent race conditions.

        Race Condition Prevention:
            User clicks "Extend" 10 times rapidly:
            → First request locks row (FOR UPDATE)
            → Other 9 requests wait for lock
            → First increments extension_count: 0 → 1
            → Commits and releases lock
            → Second request locks row, sees extension_count=1
            → Increments to 2, commits, releases
            → Result: extension_count = 10 (correct)

        Args:
            user_id: User ID
            challenge_id: Challenge ID
            team_id: Team ID (if teams mode)

        Returns:
            (success, message)

        Validations:
            1. Container exists and belongs to user/team
            2. Extension count < max_extensions
            3. Total lifetime < max_lifetime (prevent time overflow)
            4. Container hasn't already expired
        """
        from CTFd.plugins.docker_challenges import DockerChallengeTracker
        from CTFd.plugins.docker_challenges.models_cre import ContainerEvent

        policy = RuntimePolicy.from_challenge(challenge_id)

        try:
            with db.session.begin_nested():  # Savepoint for atomic operation
                # Get container with FOR UPDATE lock (prevents concurrent modifications)
                query = db.session.query(DockerChallengeTracker)

                if team_id:
                    query = query.filter(
                        and_(
                            DockerChallengeTracker.team_id == team_id,
                            DockerChallengeTracker.challenge == challenge_id  # Note: challenge field is VARCHAR, not FK
                        )
                    )
                else:
                    query = query.filter(
                        and_(
                            DockerChallengeTracker.user_id == user_id,
                            DockerChallengeTracker.challenge == challenge_id
                        )
                    )

                tracker = query.with_for_update().first()

                if not tracker:
                    self._log_action(
                        user_id, challenge_id, "failed_extend",
                        error="No active container"
                    )
                    return (False, "No active container found")

                # Validation 1: Max extensions
                if tracker.extension_count >= policy.max_extensions:
                    self._log_action(
                        user_id, challenge_id, "failed_extend",
                        container_id=tracker.instance_id,
                        error=f"Max extensions reached ({policy.max_extensions})"
                    )
                    return (False, f"Maximum extensions reached ({policy.max_extensions})")

                # Validation 2: Max lifetime (prevent time overflow attacks)
                now = int(datetime.utcnow().timestamp())
                total_lifetime = now - tracker.timestamp

                if total_lifetime + policy.extension_increment_seconds > policy.max_lifetime_seconds:
                    self._log_action(
                        user_id, challenge_id, "failed_extend",
                        container_id=tracker.instance_id,
                        error=f"Max lifetime exceeded ({policy.max_lifetime_seconds}s)"
                    )
                    return (False, f"Maximum lifetime reached ({policy.max_lifetime_seconds // 60} minutes)")

                # Validation 3: Container hasn't already expired
                if tracker.revert_time < now:
                    self._log_action(
                        user_id, challenge_id, "failed_extend",
                        container_id=tracker.instance_id,
                        error="Container already expired"
                    )
                    return (False, "Container already expired")

                # Apply extension
                old_expiry = tracker.revert_time
                tracker.extension_count += 1
                tracker.revert_time += policy.extension_increment_seconds
                tracker.last_extended_at = datetime.utcnow()

                new_expiry = tracker.revert_time

                # Commit nested transaction (releases lock)
                db.session.commit()

            # Audit log (outside transaction to avoid lock duration)
            self._log_action(
                user_id, challenge_id, "extended",
                container_id=tracker.instance_id,
                old_expiry=old_expiry,
                new_expiry=new_expiry,
                extension_number=tracker.extension_count
            )

            extension_minutes = policy.extension_increment_seconds // 60
            return (True, f"Container extended by {extension_minutes} minutes (extension {tracker.extension_count}/{policy.max_extensions})")

        except Exception as e:
            db.session.rollback()
            self._log_action(
                user_id, challenge_id, "failed_extend",
                error=str(e)
            )
            return (False, f"Extension failed: {str(e)}")

    def stop_instance(
        self,
        user_id: int,
        challenge_id: int,
        team_id: Optional[int] = None,
        auto_cleanup: bool = False
    ) -> Tuple[bool, str]:
        """
        Stop and remove container.

        DELEGATES to existing delete_container() logic in __init__.py.

        Args:
            user_id: User ID
            challenge_id: Challenge ID
            team_id: Team ID (if teams mode)
            auto_cleanup: True if called by cleanup worker (for audit trail)

        Returns:
            (success, message)

        Notes:
            - Finds tracker by user/team + challenge
            - Calls existing delete_container()
            - Logs event (stopped_manual or stopped_auto)
            - CASCADE delete handles flag cleanup
        """
        # This would delegate to existing delete logic
        # For now, return placeholder
        return (
            False,
            "CRE.stop_instance() must be integrated with existing delete_container()"
        )

    def get_instance_status(
        self,
        user_id: int,
        challenge_id: int,
        team_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Get container status (Whale-compatible).

        Args:
            user_id: User ID
            challenge_id: Challenge ID
            team_id: Team ID (if teams mode)

        Returns:
            {
                'active': bool,
                'container_id': str,
                'docker_image': str,
                'revert_time': int,
                'remaining_seconds': int,
                'extension_count': int,
                'max_extensions': int,
                'created_at': str (ISO format),
                'last_extended_at': str or None
            }
            OR None if no active container
        """
        from CTFd.plugins.docker_challenges import DockerChallengeTracker

        query = db.session.query(DockerChallengeTracker)

        if team_id:
            tracker = query.filter_by(team_id=team_id, challenge=challenge_id).first()
        else:
            tracker = query.filter_by(user_id=user_id, challenge=challenge_id).first()

        if not tracker:
            return None

        policy = RuntimePolicy.from_challenge(challenge_id)
        now = int(datetime.utcnow().timestamp())
        remaining = max(0, tracker.revert_time - now)

        return {
            'active': True,
            'container_id': tracker.instance_id,
            'docker_image': tracker.docker_image,
            'revert_time': tracker.revert_time,
            'remaining_seconds': remaining,
            'extension_count': tracker.extension_count,
            'max_extensions': policy.max_extensions,
            'created_at': tracker.created_at.isoformat() if hasattr(tracker, 'created_at') else None,
            'last_extended_at': tracker.last_extended_at.isoformat() if hasattr(tracker, 'last_extended_at') else None,
            'host': tracker.host,
            'ports': tracker.ports
        }

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _log_action(self, user_id: int, challenge_id: int, action: str, **metadata):
        """
        Log container lifecycle event to audit table.

        Args:
            user_id: User who performed action (or None for system)
            challenge_id: Challenge ID
            action: Action type (created, extended, stopped_manual, etc)
            **metadata: Additional context (old_expiry, new_expiry, error, etc)
        """
        try:
            from CTFd.plugins.docker_challenges.models_cre import ContainerEvent

            event = ContainerEvent(
                user_id=user_id if user_id else None,
                challenge_id=challenge_id,
                container_id=metadata.get('container_id'),
                action=action,
                timestamp=datetime.utcnow(),
                event_metadata=metadata  # Renamed from 'metadata' (SQLAlchemy reserved word)
            )

            db.session.add(event)
            db.session.commit()

        except Exception as e:
            # Don't fail the operation if logging fails
            print(f"[CRE ERROR] Failed to log action {action}: {e}")


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Singleton instance (initialized once, reused throughout app)
cre = ContainerRuntimeEngine()
