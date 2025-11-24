"""
Phase 2 REST API
================

API endpoints for Phase 2 Intelligence Layer.

Endpoints:
- GET /api/v1/phase2/first_blood_leaderboard - First blood prestige leaderboard
- GET /api/v1/phase2/challenge_health - Challenge health status
- GET /api/v1/phase2/challenge_health/<id> - Specific challenge health
- GET /api/v1/phase2/suspicious_activity - Flag sharing suspicions
- PUT /api/v1/phase2/suspicious_activity/<id>/review - Admin review
- GET /api/v1/phase2/status - Phase 2 system status

All endpoints require appropriate permissions (admin-only for sensitive data).
"""

from flask import request
from flask_restx import Namespace, Resource
from CTFd.utils.decorators import admins_only, ratelimit
from CTFd.utils.user import is_admin, get_current_user
from CTFd.utils.config import is_teams_mode
from CTFd.models import db
from .models import FlagSharingSuspicion, ChallengeHealthSnapshot, VerdictHistory
from .config import Phase2Config
from .utils import get_first_blood_leaderboard
import datetime


# Create API namespace
phase2_namespace = Namespace(
    'phase2',
    description='Phase 2 Intelligence Layer API'
)


@phase2_namespace.route('/status')
class Phase2Status(Resource):
    def get(self):
        """
        Get Phase 2 system status and configuration.

        Returns:
            {
                "success": true,
                "data": {
                    "enabled": true,
                    "features": {...},
                    "version": "2.0.0-MVP"
                }
            }
        """
        return {
            'success': True,
            'data': {
                'enabled': Phase2Config.ENABLED,
                'features': Phase2Config.get_feature_status(),
                'version': '2.0.0-MVP'
            }
        }


@phase2_namespace.route('/first_blood_leaderboard')
class FirstBloodLeaderboard(Resource):
    @ratelimit(method="GET", limit=30, interval=60, key_prefix="phase2_fb_leaderboard")
    def get(self):
        """
        Get first blood prestige leaderboard.

        Query Parameters:
            limit (int): Maximum number of entries (default: 100)

        Returns:
            {
                "success": true,
                "data": [
                    {
                        "rank": 1,
                        "user_id": 5,  # or "team_id" in team mode
                        "total_prestige": 1500,
                        "first_bloods": 3
                    },
                    ...
                ]
            }

        Visibility:
        - Admin: Always visible
        - User: Only if configured (future: check CTF end time)
        """
        if not Phase2Config.FIRST_BLOOD_ENABLED:
            return {
                'success': False,
                'message': 'First blood system is disabled'
            }, 404

        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        limit = min(limit, 1000)  # Cap at 1000

        # Check visibility (for now, admin-only in production)
        # Future: Make public after CTF ends
        if not is_admin():
            return {
                'success': False,
                'message': 'First blood leaderboard is admin-only during competition'
            }, 403

        try:
            # Determine team vs individual mode
            team_mode = is_teams_mode()

            # Get leaderboard
            leaderboard = get_first_blood_leaderboard(limit=limit, team_mode=team_mode)

            return {
                'success': True,
                'data': leaderboard,
                'meta': {
                    'team_mode': team_mode,
                    'count': len(leaderboard)
                }
            }

        except Exception as e:
            print(f"[PHASE2 API ERROR] first_blood_leaderboard failed: {e}")
            return {
                'success': False,
                'message': 'Failed to fetch leaderboard'
            }, 500


@phase2_namespace.route('/challenge_health')
class ChallengeHealthList(Resource):
    @admins_only
    @ratelimit(method="GET", limit=60, interval=60, key_prefix="phase2_health_list")
    def get(self):
        """
        Get challenge health status for all challenges (latest snapshots).

        Query Parameters:
            status (str): Filter by status (HEALTHY, UNDERPERFORMING, BROKEN)

        Returns:
            {
                "success": true,
                "data": [
                    {
                        "challenge_id": 1,
                        "solves": 45,
                        "attempts": 120,
                        "solve_rate": 0.375,
                        "health_score": 85,
                        "status": "HEALTHY",
                        "timestamp": "2025-11-23T12:00:00"
                    },
                    ...
                ]
            }
        """
        if not Phase2Config.HEALTH_ENABLED:
            return {
                'success': False,
                'message': 'Challenge health monitoring is disabled'
            }, 404

        try:
            # Get filter parameter
            status_filter = request.args.get('status', None)

            # Get latest snapshot for each challenge
            # Subquery to get max timestamp per challenge
            from sqlalchemy import func
            subquery = db.session.query(
                ChallengeHealthSnapshot.challenge_id,
                func.max(ChallengeHealthSnapshot.timestamp).label('max_timestamp')
            ).group_by(ChallengeHealthSnapshot.challenge_id).subquery()

            # Join to get full records
            query = db.session.query(ChallengeHealthSnapshot).join(
                subquery,
                db.and_(
                    ChallengeHealthSnapshot.challenge_id == subquery.c.challenge_id,
                    ChallengeHealthSnapshot.timestamp == subquery.c.max_timestamp
                )
            )

            # Apply status filter if provided
            if status_filter:
                query = query.filter(ChallengeHealthSnapshot.status == status_filter.upper())

            snapshots = query.all()

            # Serialize
            data = []
            for snapshot in snapshots:
                data.append({
                    'challenge_id': snapshot.challenge_id,
                    'solves': snapshot.solves,
                    'attempts': snapshot.attempts,
                    'solve_rate': snapshot.solve_rate,
                    'health_score': snapshot.health_score,
                    'status': snapshot.status,
                    'timestamp': snapshot.timestamp.isoformat()
                })

            return {
                'success': True,
                'data': data,
                'meta': {
                    'count': len(data),
                    'filter': status_filter
                }
            }

        except Exception as e:
            print(f"[PHASE2 API ERROR] challenge_health failed: {e}")
            return {
                'success': False,
                'message': 'Failed to fetch challenge health'
            }, 500


@phase2_namespace.route('/challenge_health/<int:challenge_id>')
class ChallengeHealthDetail(Resource):
    @admins_only
    @ratelimit(method="GET", limit=100, interval=60, key_prefix="phase2_health_detail")
    def get(self, challenge_id):
        """
        Get health history for a specific challenge.

        Query Parameters:
            limit (int): Number of snapshots to return (default: 24)

        Returns:
            {
                "success": true,
                "data": {
                    "challenge_id": 1,
                    "current": {...},
                    "history": [...]
                }
            }
        """
        if not Phase2Config.HEALTH_ENABLED:
            return {
                'success': False,
                'message': 'Challenge health monitoring is disabled'
            }, 404

        try:
            limit = request.args.get('limit', 24, type=int)
            limit = min(limit, 1000)

            # Get recent snapshots
            snapshots = ChallengeHealthSnapshot.query.filter_by(
                challenge_id=challenge_id
            ).order_by(
                ChallengeHealthSnapshot.timestamp.desc()
            ).limit(limit).all()

            if not snapshots:
                return {
                    'success': False,
                    'message': 'No health data found for this challenge'
                }, 404

            # Serialize
            history = []
            for snapshot in snapshots:
                history.append({
                    'solves': snapshot.solves,
                    'attempts': snapshot.attempts,
                    'solve_rate': snapshot.solve_rate,
                    'health_score': snapshot.health_score,
                    'status': snapshot.status,
                    'timestamp': snapshot.timestamp.isoformat()
                })

            return {
                'success': True,
                'data': {
                    'challenge_id': challenge_id,
                    'current': history[0] if history else None,
                    'history': history
                }
            }

        except Exception as e:
            print(f"[PHASE2 API ERROR] challenge_health/{challenge_id} failed: {e}")
            return {
                'success': False,
                'message': 'Failed to fetch challenge health'
            }, 500


@phase2_namespace.route('/suspicious_activity')
class SuspiciousActivityList(Resource):
    @admins_only
    @ratelimit(method="GET", limit=50, interval=60, key_prefix="phase2_suspicion_list")
    def get(self):
        """
        Get flag sharing suspicions.

        Query Parameters:
            status (str): Filter by admin_verdict (pending, innocent, suspicious, confirmed)
            risk_level (str): Filter by risk_level (LOW, MEDIUM, HIGH)
            limit (int): Number of records (default: 100)

        Returns:
            {
                "success": true,
                "data": [
                    {
                        "id": 1,
                        "user_id_1": 5,
                        "user_id_2": 7,
                        "challenge_id": 3,
                        "detection_type": "same_ip",
                        "confidence_score": 0.85,
                        "risk_level": "HIGH",
                        "evidence": {...},
                        "admin_verdict": null,
                        "created_at": "2025-11-23T12:00:00"
                    },
                    ...
                ]
            }
        """
        if not Phase2Config.SUSPICION_ENABLED:
            return {
                'success': False,
                'message': 'Flag sharing detection is disabled'
            }, 404

        try:
            # Get query parameters
            status_filter = request.args.get('status', None)
            risk_filter = request.args.get('risk_level', None)
            limit = request.args.get('limit', 100, type=int)
            limit = min(limit, 1000)

            # Build query
            query = FlagSharingSuspicion.query

            # Apply filters
            if status_filter:
                if status_filter.lower() == 'pending':
                    query = query.filter(FlagSharingSuspicion.admin_verdict.is_(None))
                else:
                    query = query.filter(FlagSharingSuspicion.admin_verdict == status_filter)

            if risk_filter:
                query = query.filter(FlagSharingSuspicion.risk_level == risk_filter.upper())

            # Order by created_at desc (newest first)
            suspicions = query.order_by(
                FlagSharingSuspicion.created_at.desc()
            ).limit(limit).all()

            # Serialize
            data = []
            for suspicion in suspicions:
                data.append({
                    'id': suspicion.id,
                    'user_id_1': suspicion.user_id_1,
                    'user_id_2': suspicion.user_id_2,
                    'challenge_id': suspicion.challenge_id,
                    'detection_type': suspicion.detection_type,
                    'confidence_score': suspicion.confidence_score,
                    'risk_level': suspicion.risk_level,
                    'evidence': suspicion.evidence,
                    'admin_verdict': suspicion.admin_verdict,
                    'reviewed_at': suspicion.reviewed_at.isoformat() if suspicion.reviewed_at else None,
                    'reviewed_by': suspicion.reviewed_by,
                    'created_at': suspicion.created_at.isoformat()
                })

            return {
                'success': True,
                'data': data,
                'meta': {
                    'count': len(data),
                    'filters': {
                        'status': status_filter,
                        'risk_level': risk_filter
                    }
                }
            }

        except Exception as e:
            print(f"[PHASE2 API ERROR] suspicious_activity failed: {e}")
            return {
                'success': False,
                'message': 'Failed to fetch suspicious activity'
            }, 500


@phase2_namespace.route('/suspicious_activity/<int:suspicion_id>/review')
class SuspiciousActivityReview(Resource):
    @admins_only
    @ratelimit(method="PUT", limit=20, interval=60, key_prefix="phase2_suspicion_review")
    def put(self, suspicion_id):
        """
        Submit admin review verdict for a suspicion.

        Request Body:
            {
                "verdict": "innocent" | "suspicious" | "confirmed"
            }

        Returns:
            {
                "success": true,
                "message": "Verdict recorded"
            }
        """
        if not Phase2Config.SUSPICION_ENABLED:
            return {
                'success': False,
                'message': 'Flag sharing detection is disabled'
            }, 404

        try:
            # Get request data
            data = request.get_json()
            verdict = data.get('verdict')
            notes = data.get('notes', None)  # Optional admin notes

            # Validate verdict
            valid_verdicts = ['innocent', 'suspicious', 'confirmed']
            if verdict not in valid_verdicts:
                return {
                    'success': False,
                    'message': f'Invalid verdict. Must be one of: {valid_verdicts}'
                }, 400

            # Get suspicion record
            suspicion = FlagSharingSuspicion.query.filter_by(id=suspicion_id).first()
            if not suspicion:
                return {
                    'success': False,
                    'message': 'Suspicion not found'
                }, 404

            # Get admin info
            admin_user = get_current_user()
            admin_ip = request.remote_addr

            # SECURITY-HARDENED: Record verdict in IMMUTABLE audit trail
            # This prevents verdict manipulation and provides accountability
            audit_entry = VerdictHistory.record_verdict(
                suspicion_id=suspicion_id,
                verdict=verdict,
                admin_id=admin_user.id,
                admin_ip=admin_ip,
                notes=notes
            )

            # Also update the suspicion record for convenience (but audit trail is authoritative)
            suspicion.admin_verdict = verdict
            suspicion.reviewed_at = datetime.datetime.utcnow()
            suspicion.reviewed_by = admin_user.id

            db.session.commit()

            # SECURITY: Audit logging for admin actions
            print(f"[PHASE2 AUDIT] Suspicion {suspicion_id} reviewed: verdict={verdict} "
                  f"admin_id={admin_user.id} admin_name={admin_user.name} "
                  f"ip={admin_ip} timestamp={datetime.datetime.utcnow().isoformat()} "
                  f"audit_entry_id={audit_entry.id}")

            return {
                'success': True,
                'message': 'Verdict recorded in immutable audit trail',
                'audit': {
                    'reviewed_by': admin_user.id,
                    'reviewed_at': suspicion.reviewed_at.isoformat(),
                    'audit_entry_id': audit_entry.id,
                    'immutable': True
                }
            }

        except Exception as e:
            db.session.rollback()
            print(f"[PHASE2 API ERROR] review suspicion {suspicion_id} failed: {e}")
            return {
                'success': False,
                'message': 'Failed to record verdict'
            }, 500
