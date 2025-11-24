"""
Phase 2 Configuration
=====================

Feature flags and configuration for Phase 2 Intelligence Layer.

All settings can be controlled via environment variables or CTFd config.
"""

import os
from CTFd.utils.config import get_config


class Phase2Config:
    """
    Phase 2 feature flags and configuration.

    Environment Variables:
    - PHASE2_ENABLED: Master switch (default: 1)
    - PHASE2_FIRST_BLOOD_ENABLED: Enable first blood detection (default: 1)
    - PHASE2_HEALTH_ENABLED: Enable challenge health monitoring (default: 1)
    - PHASE2_SUSPICION_ENABLED: Enable flag sharing detection (default: 1)
    - PHASE2_SUSPICION_THRESHOLD: Confidence threshold for alerts (default: 0.75)
    - PHASE2_RETENTION_DAYS: Data retention in days (default: 90)
    - PHASE2_HEALTH_INTERVAL_HOURS: Health check frequency (default: 1)
    """

    # Master switch
    ENABLED = os.environ.get('PHASE2_ENABLED', '1') == '1'

    # Pillar-specific switches
    FIRST_BLOOD_ENABLED = os.environ.get('PHASE2_FIRST_BLOOD_ENABLED', '1') == '1'
    HEALTH_ENABLED = os.environ.get('PHASE2_HEALTH_ENABLED', '1') == '1'
    SUSPICION_ENABLED = os.environ.get('PHASE2_SUSPICION_ENABLED', '1') == '1'

    # Thresholds
    SUSPICION_THRESHOLD = float(os.environ.get('PHASE2_SUSPICION_THRESHOLD', '0.75'))
    # GDPR COMPLIANCE: Reduced retention from 90 to 30 days (2025-11-24)
    RETENTION_DAYS = int(os.environ.get('PHASE2_RETENTION_DAYS', '30'))

    # Worker intervals
    HEALTH_INTERVAL_HOURS = int(os.environ.get('PHASE2_HEALTH_INTERVAL_HOURS', '1'))
    ANALYTICS_INTERVAL_SECONDS = int(os.environ.get('PHASE2_ANALYTICS_INTERVAL_SECONDS', '30'))

    # Performance tuning
    FIRST_BLOOD_REDIS_TTL = 86400  # 24 hours cache for "first blood claimed" flags
    ANALYTICS_BATCH_SIZE = 100  # Process submissions in batches

    # Pattern detection weights (for confidence scoring)
    WEIGHT_SAME_IP = 0.4
    WEIGHT_DUPLICATE_WRONG = 0.3
    WEIGHT_SIMILAR_UA = 0.2
    WEIGHT_TEMPORAL_PROXIMITY = 0.1

    # Temporal window for flag sharing detection (seconds)
    TEMPORAL_WINDOW_SECONDS = 60

    # User-agent similarity threshold (Levenshtein ratio)
    UA_SIMILARITY_THRESHOLD = 0.95

    @classmethod
    def is_enabled(cls):
        """Check if Phase 2 is enabled."""
        return cls.ENABLED

    @classmethod
    def get_feature_status(cls):
        """Get status of all features."""
        return {
            'enabled': cls.ENABLED,
            'first_blood': cls.FIRST_BLOOD_ENABLED,
            'health': cls.HEALTH_ENABLED,
            'suspicion': cls.SUSPICION_ENABLED,
            'suspicion_threshold': cls.SUSPICION_THRESHOLD,
            'retention_days': cls.RETENTION_DAYS
        }
