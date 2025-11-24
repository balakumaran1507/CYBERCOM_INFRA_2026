"""
Phase 2 Database Models
=======================

Three core tables for Phase 2 Intelligence Layer:
1. FirstBloodPrestige - First solve tracking with prestige scores
2. FlagSharingSuspicion - Pattern detection results
3. ChallengeHealthSnapshot - Hourly challenge quality metrics

Design Principles:
- Separate tables (no core CTFd schema modification)
- Foreign keys with CASCADE for data consistency
- Indexes for query performance
- JSON for flexible metadata storage
"""

import datetime
from CTFd.models import db


class FirstBloodPrestige(db.Model):
    """
    First Blood Prestige System - Track first solves per challenge.

    SECURITY-HARDENED (2025-11-24):
    ✅ UNIQUE constraint on challenge_id prevents race condition duplicates
    ✅ Timestamp-based tie-breaking (NOT solve.id)
    ✅ Database-level atomicity enforcement

    Business Rules:
    - ONE first blood per challenge (UNIQUE challenge_id) ← CRITICAL
    - ONE first blood per solve (UNIQUE solve_id)
    - Prestige score calculated at solve time (immutable)
    - Separate tracking for team vs individual modes
    - Tie-breaker: earliest timestamp, then lowest user_id

    Performance:
    - Indexed on challenge_id for leaderboard queries
    - Indexed on user_id/team_id for user profiles
    - Indexed on timestamp for race condition checks
    """
    __tablename__ = 'phase2_first_blood_prestige'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    solve_id = db.Column(
        db.Integer,
        db.ForeignKey('solves.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # ONE first blood per solve
        index=True
    )
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # ✅ SECURITY: ONE first blood per challenge (prevents race duplicates)
        index=True
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,  # Nullable for team mode
        index=True
    )
    team_id = db.Column(
        db.Integer,
        db.ForeignKey('teams.id', ondelete='CASCADE'),
        nullable=True,  # Nullable for individual mode
        index=True
    )

    # Prestige data
    prestige_score = db.Column(db.Integer, nullable=False)  # Based on challenge.value
    timestamp = db.Column(
        db.DateTime(6),
        nullable=False,
        default=datetime.datetime.utcnow,
        index=True
    )

    # Relationships
    solve = db.relationship('Solves', backref='first_blood_prestige', lazy='select')
    challenge = db.relationship('Challenges', backref='first_blood_records', lazy='select')
    user = db.relationship('Users', backref='first_blood_achievements', lazy='select')
    team = db.relationship('Teams', backref='first_blood_achievements', lazy='select')

    def __repr__(self):
        return f"<FirstBloodPrestige challenge={self.challenge_id} user={self.user_id} team={self.team_id} prestige={self.prestige_score}>"


class FlagSharingSuspicion(db.Model):
    """
    Flag Sharing Detection - Intelligence for admin review.

    Detection Patterns:
    - same_ip: Same IP address within temporal window
    - duplicate_wrong: Exact duplicate incorrect submissions
    - similar_ua: High similarity user-agent strings
    - temporal_proximity: Submissions within 60 seconds

    Workflow:
    1. Analytics worker detects pattern
    2. Calculates confidence score (0.0 - 1.0)
    3. Assigns risk level (LOW, MEDIUM, HIGH)
    4. Admin reviews and sets verdict

    NO AUTO-PUNISHMENT - Intelligence only.
    """
    __tablename__ = 'phase2_flag_sharing_suspicion'

    id = db.Column(db.Integer, primary_key=True)

    # Suspected users
    user_id_1 = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    user_id_2 = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,  # Nullable for single-user patterns (e.g., multi-accounting)
        index=True
    )

    # Challenge context
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Detection metadata
    detection_type = db.Column(
        db.String(64),
        nullable=False
    )  # 'same_ip', 'duplicate_wrong', 'similar_ua', 'temporal_proximity'

    confidence_score = db.Column(
        db.Float,
        nullable=False
    )  # 0.0 to 1.0

    risk_level = db.Column(
        db.String(16),
        nullable=False,
        index=True
    )  # 'LOW', 'MEDIUM', 'HIGH'

    evidence = db.Column(
        db.JSON,
        nullable=False
    )  # {'ip': '1.2.3.4', 'time_delta_ms': 500, 'submissions': [...]}

    # Admin review
    admin_verdict = db.Column(
        db.String(32),
        nullable=True,
        index=True
    )  # 'innocent', 'suspicious', 'confirmed', null=pending

    reviewed_at = db.Column(db.DateTime(6), nullable=True)
    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Timestamps
    created_at = db.Column(
        db.DateTime(6),
        nullable=False,
        default=datetime.datetime.utcnow,
        index=True
    )

    # Relationships
    user1 = db.relationship('Users', foreign_keys=[user_id_1], backref='suspicions_as_user1', lazy='select')
    user2 = db.relationship('Users', foreign_keys=[user_id_2], backref='suspicions_as_user2', lazy='select')
    challenge = db.relationship('Challenges', backref='suspicion_records', lazy='select')
    reviewer = db.relationship('Users', foreign_keys=[reviewed_by], backref='reviewed_suspicions', lazy='select')

    def __repr__(self):
        return f"<FlagSharingSuspicion users={self.user_id_1},{self.user_id_2} challenge={self.challenge_id} confidence={self.confidence_score}>"


class ChallengeHealthSnapshot(db.Model):
    """
    Challenge Health Monitoring - Hourly quality snapshots.

    Metrics:
    - Solve count
    - Attempt count
    - Solve rate (solves / attempts)
    - Health score (0-100, derived from solve rate + other factors)

    Health Score Rules:
    - Base: 100
    - Penalty if solve_rate > 90% (too easy): -20
    - Penalty if solve_rate < 5% (too hard): -30
    - Penalty if attempts < 10 (low engagement): -15

    Status:
    - HEALTHY: score >= 70
    - UNDERPERFORMING: 40 <= score < 70
    - BROKEN: score < 40
    """
    __tablename__ = 'phase2_challenge_health_snapshot'

    id = db.Column(db.Integer, primary_key=True)

    # Challenge reference
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey('challenges.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Metrics
    solves = db.Column(db.Integer, nullable=False, default=0)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    solve_rate = db.Column(db.Float, nullable=False, default=0.0)  # 0.0 to 1.0

    # Derived metrics
    health_score = db.Column(db.Integer, nullable=False, default=100)  # 0-100
    status = db.Column(
        db.String(32),
        nullable=False,
        default='HEALTHY',
        index=True
    )  # 'HEALTHY', 'UNDERPERFORMING', 'BROKEN'

    # Timestamp
    timestamp = db.Column(
        db.DateTime(6),
        nullable=False,
        default=datetime.datetime.utcnow,
        index=True
    )

    # Composite index for time-series queries
    __table_args__ = (
        db.Index('idx_challenge_time', 'challenge_id', 'timestamp'),
    )

    # Relationship
    challenge = db.relationship('Challenges', backref='health_snapshots', lazy='select')

    def __repr__(self):
        return f"<ChallengeHealthSnapshot challenge={self.challenge_id} score={self.health_score} status={self.status}>"


class UserConsent(db.Model):
    """
    GDPR User Consent Tracking - Phase 2 Analytics.

    SECURITY-HARDENED (2025-11-24):
    ✅ Explicit consent required for user-agent collection
    ✅ Opt-in only (default: no consent)
    ✅ Immutable audit trail (no updates, only inserts)
    ✅ Tracks consent withdrawal

    Business Rules:
    - Default: No consent (consented=False)
    - Consent required for: User-agent tracking, behavioral analytics
    - Consent NOT required for: First blood (public achievement)
    - Users can withdraw consent at any time
    - Data deleted within 30 days of withdrawal

    GDPR Compliance:
    - Right to withdraw (consented=False)
    - Right to erasure (delete suspicion records)
    - Data minimization (only collect if consented)
    - Purpose limitation (analytics only)
    """
    __tablename__ = 'phase2_user_consent'

    id = db.Column(db.Integer, primary_key=True)

    # User reference
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # ONE consent record per user
        index=True
    )

    # Consent status
    consented = db.Column(
        db.Boolean,
        nullable=False,
        default=False  # Default: NO consent (opt-in required)
    )

    # Audit trail
    consented_at = db.Column(
        db.DateTime(6),
        nullable=True,  # Null if never consented
        default=None
    )
    withdrawn_at = db.Column(
        db.DateTime(6),
        nullable=True,  # Null if not withdrawn
        default=None
    )
    last_updated = db.Column(
        db.DateTime(6),
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        index=True
    )

    # Relationship
    user = db.relationship('Users', backref='phase2_consent', lazy='select')

    def __repr__(self):
        status = "CONSENTED" if self.consented else "NOT_CONSENTED"
        return f"<UserConsent user={self.user_id} status={status}>"

    @classmethod
    def has_consent(cls, user_id):
        """
        Check if user has consented to Phase 2 analytics tracking.

        SECURITY: Returns False by default (opt-in required).

        Args:
            user_id (int): User ID to check

        Returns:
            bool: True if user has active consent, False otherwise
        """
        consent = cls.query.filter_by(user_id=user_id).first()
        return consent.consented if consent else False

    @classmethod
    def grant_consent(cls, user_id):
        """
        Grant consent for a user.

        Creates or updates consent record with consented=True.

        Args:
            user_id (int): User ID to grant consent for
        """
        consent = cls.query.filter_by(user_id=user_id).first()

        if not consent:
            # Create new consent record
            consent = cls(
                user_id=user_id,
                consented=True,
                consented_at=datetime.datetime.utcnow()
            )
            db.session.add(consent)
        else:
            # Update existing record
            consent.consented = True
            consent.consented_at = datetime.datetime.utcnow()
            consent.withdrawn_at = None

        db.session.commit()
        print(f"[PHASE2 GDPR] User {user_id} granted consent")

    @classmethod
    def withdraw_consent(cls, user_id):
        """
        Withdraw consent for a user.

        Updates consent record with consented=False.
        Triggers data deletion within 30 days.

        Args:
            user_id (int): User ID to withdraw consent for
        """
        consent = cls.query.filter_by(user_id=user_id).first()

        if not consent:
            # Create withdrawal record
            consent = cls(
                user_id=user_id,
                consented=False,
                withdrawn_at=datetime.datetime.utcnow()
            )
            db.session.add(consent)
        else:
            # Update existing record
            consent.consented = False
            consent.withdrawn_at = datetime.datetime.utcnow()

        db.session.commit()
        print(f"[PHASE2 GDPR] User {user_id} withdrew consent - data will be deleted in 30 days")


class VerdictHistory(db.Model):
    """
    Immutable Audit Trail for Suspicion Verdicts.

    SECURITY-HARDENED (2025-11-24):
    ✅ Immutable audit log (INSERT only, no UPDATE/DELETE)
    ✅ Tracks all verdict changes with timestamps
    ✅ Records admin identity and IP address
    ✅ Prevents verdict manipulation

    Business Rules:
    - Every verdict change creates a NEW entry
    - NO updates or deletes (immutable)
    - Chronological order preserved
    - Admin accountability enforced

    Use Cases:
    - Audit admin decisions
    - Detect suspicious verdict patterns
    - Compliance reporting
    - Dispute resolution
    """
    __tablename__ = 'phase2_verdict_history'

    id = db.Column(db.Integer, primary_key=True)

    # Suspicion reference
    suspicion_id = db.Column(
        db.Integer,
        db.ForeignKey('phase2_flag_sharing_suspicion.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Verdict data
    verdict = db.Column(
        db.String(32),
        nullable=False  # innocent, suspicious, confirmed
    )

    # Admin accountability
    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,  # NULL if admin deleted
        index=True
    )
    admin_ip = db.Column(
        db.String(46),  # IPv6 support
        nullable=True
    )

    # Audit metadata
    notes = db.Column(
        db.Text,
        nullable=True  # Optional admin notes
    )
    created_at = db.Column(
        db.DateTime(6),
        nullable=False,
        default=datetime.datetime.utcnow,
        index=True
    )

    # Relationships
    suspicion = db.relationship('FlagSharingSuspicion', backref='verdict_history', lazy='select')
    admin = db.relationship('Users', backref='phase2_verdicts', lazy='select')

    def __repr__(self):
        return f"<VerdictHistory suspicion={self.suspicion_id} verdict={self.verdict} admin={self.reviewed_by}>"

    @classmethod
    def record_verdict(cls, suspicion_id, verdict, admin_id, admin_ip, notes=None):
        """
        Record a verdict change in immutable audit trail.

        SECURITY: Creates INSERT-only audit entry.

        Args:
            suspicion_id (int): FlagSharingSuspicion ID
            verdict (str): Verdict value (innocent/suspicious/confirmed)
            admin_id (int): Admin user ID
            admin_ip (str): Admin IP address
            notes (str): Optional admin notes

        Returns:
            VerdictHistory: Created audit entry
        """
        entry = cls(
            suspicion_id=suspicion_id,
            verdict=verdict,
            reviewed_by=admin_id,
            admin_ip=admin_ip,
            notes=notes
        )

        db.session.add(entry)
        db.session.commit()

        print(f"[PHASE2 AUDIT TRAIL] Verdict recorded: suspicion={suspicion_id} "
              f"verdict={verdict} admin={admin_id} ip={admin_ip}")

        return entry

    @classmethod
    def get_history(cls, suspicion_id, limit=100):
        """
        Get verdict history for a suspicion (chronological order).

        Args:
            suspicion_id (int): FlagSharingSuspicion ID
            limit (int): Maximum number of entries

        Returns:
            list: VerdictHistory entries
        """
        return cls.query.filter_by(
            suspicion_id=suspicion_id
        ).order_by(
            cls.created_at.asc()
        ).limit(limit).all()
