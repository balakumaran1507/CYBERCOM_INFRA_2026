"""
CYBERCOM Runtime Engine - Enhanced Data Models

Extends DockerChallengeTracker with lifecycle tracking fields.
Adds ContainerEvent for comprehensive audit logging.

Author: CYBERCOM Security Team
Version: 1.0.0 (CRE)
"""

from CTFd.models import db
from datetime import datetime


# ============================================================================
# ENHANCED DOCKER CHALLENGE TRACKER
# ============================================================================
#
# These fields will be ADDED to existing DockerChallengeTracker model.
# See migration SQL for ALTER TABLE statements.
#
# NEW FIELDS:
# - extension_count: INT DEFAULT 0 NOT NULL
#   Tracks how many times container was extended (max 5)
#
# - created_at: DATETIME NOT NULL
#   Precise creation timestamp (better than unix timestamp)
#
# - last_extended_at: DATETIME NULL
#   When was last extension applied (for rate limiting)
#
# FIXED FIELDS (migration required):
# - user_id: Change from VARCHAR(64) to INT (foreign key to users.id)
# - team_id: Change from VARCHAR(64) to INT (foreign key to teams.id)
#
# ============================================================================


class ContainerEvent(db.Model):
    """
    Audit log for all container lifecycle events.

    Provides:
    - Full audit trail (who did what when)
    - Debugging capability (trace race conditions)
    - Compliance logging (enterprise requirement)
    - Metrics foundation (analytics, monitoring)

    Event Types:
    - created: Container started
    - extended: Lifetime extended
    - stopped_manual: User clicked stop
    - stopped_auto: Cleanup worker expired container
    - failed_create: Container creation error
    - failed_extend: Extension error (max reached, expired, etc)
    - failed_cleanup: Cleanup worker error

    Usage:
        event = ContainerEvent(
            user_id=1,
            challenge_id=5,
            container_id="abc123",
            action="extended",
            metadata={"old_expiry": 1234, "new_expiry": 5678, "extension_number": 2}
        )
        db.session.add(event)
        db.session.commit()
    """
    __tablename__ = "container_events"

    id = db.Column(db.Integer, primary_key=True)

    # Who performed the action
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),  # SET NULL instead of CASCADE (preserve audit)
        nullable=True,  # NULL if system action (cleanup worker)
        index=True
    )

    # Which challenge
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='SET NULL'),  # SET NULL instead of CASCADE
        nullable=True,
        index=True
    )

    # Which container (may not exist if creation failed)
    container_id = db.Column(
        db.String(128),
        nullable=True,
        index=True
    )

    # What happened
    action = db.Column(
        db.String(50),
        nullable=False,
        index=True,
        comment="Action type: created, extended, stopped_manual, stopped_auto, failed_*"
    )

    # When it happened
    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    # Additional context (flexible JSON field)
    # Note: Cannot use 'metadata' as name (reserved by SQLAlchemy)
    event_metadata = db.Column(
        db.JSON,
        nullable=True,
        comment="Context data: {old_expiry, new_expiry, extension_number, error, etc}"
    )

    # Composite index for common queries
    __table_args__ = (
        db.Index('idx_container_events_user_time', 'user_id', 'timestamp'),
        db.Index('idx_container_events_challenge_time', 'challenge_id', 'timestamp'),
        db.Index('idx_container_events_container_time', 'container_id', 'timestamp'),
        db.Index('idx_container_events_action_time', 'action', 'timestamp'),
    )

    def __repr__(self):
        return f"<ContainerEvent user={self.user_id} action={self.action} time={self.timestamp}>"


# ============================================================================
# CONFIGURATION MODEL (Optional - for per-challenge policies)
# ============================================================================

class ContainerRuntimePolicy(db.Model):
    """
    Per-challenge runtime configuration (optional - uses defaults if not set).

    Allows admins to customize:
    - Base runtime (default 15 min)
    - Extension increment (default 15 min)
    - Max extensions (default 5)
    - Max total lifetime (default 90 min)

    Example:
        Easy RCE challenge: 5 min base, 0 extensions (quick solve)
        Complex pwn challenge: 30 min base, 10 extensions (need time)
    """
    __tablename__ = "container_runtime_policies"

    id = db.Column(db.Integer, primary_key=True)

    # Which challenge (NULL = global default)
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='CASCADE'),
        unique=True,
        nullable=True,
        index=True
    )

    # Runtime configuration (seconds)
    base_runtime_seconds = db.Column(
        db.Integer,
        default=900,  # 15 minutes
        nullable=False
    )

    extension_increment_seconds = db.Column(
        db.Integer,
        default=900,  # 15 minutes
        nullable=False
    )

    max_extensions = db.Column(
        db.Integer,
        default=5,
        nullable=False
    )

    max_lifetime_seconds = db.Column(
        db.Integer,
        default=5400,  # 90 minutes
        nullable=False
    )

    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RuntimePolicy challenge={self.challenge_id} base={self.base_runtime_seconds}s>"
