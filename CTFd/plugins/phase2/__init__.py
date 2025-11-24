"""
CYBERCOM Phase 2 - Intelligence Layer
======================================

Production-grade competition integrity and challenge quality intelligence system.

Features:
- First Blood Prestige System (race-safe, prestige-based leaderboard)
- Flag Sharing Detection (intelligence only, admin-reviewed)
- Challenge Health Monitoring (hourly quality snapshots)

Performance:
- <20ms sync overhead on submission flow
- Async workers for heavy analytics
- Redis-backed caching

Author: CYBERCOM Security Team
Version: 2.0.0-MVP
"""

from flask import Blueprint
from CTFd.plugins import register_plugin_assets_directory, register_admin_plugin_menu_bar
from CTFd.api import CTFd_API_v1

# Import Phase 2 components
from .models import db
from .api import phase2_namespace
from .workers import start_phase2_workers
from .hooks import register_phase2_hooks
from .config import Phase2Config


def load(app):
    """
    Plugin load function called by CTFd on startup.

    Responsibilities:
    1. Create database tables
    2. Register API namespace
    3. Start background workers
    4. Register event hooks
    5. Add admin menu items
    """

    # Check if Phase 2 is enabled
    if not Phase2Config.is_enabled():
        print("[PHASE2] ⚠️  Phase 2 is DISABLED (PHASE2_ENABLED=0)")
        return

    print("[PHASE2] 🚀 Initializing CYBERCOM Phase 2 Intelligence Layer...")

    # 1. Create database tables
    try:
        app.db.create_all()
        print("[PHASE2] ✅ Database tables created/verified")
    except Exception as e:
        print(f"[PHASE2] ❌ Database initialization failed: {e}")
        return

    # 2. Register API namespace
    try:
        CTFd_API_v1.add_namespace(phase2_namespace, path='/phase2')
        print("[PHASE2] ✅ API namespace registered (/api/v1/phase2)")
    except Exception as e:
        print(f"[PHASE2] ❌ API registration failed: {e}")
        return

    # 3. Register SQLAlchemy event hooks
    try:
        register_phase2_hooks()
        print("[PHASE2] ✅ SQLAlchemy event hooks registered")
    except Exception as e:
        print(f"[PHASE2] ❌ Event hook registration failed: {e}")
        return

    # 4. Start background workers
    try:
        start_phase2_workers(app)
        print("[PHASE2] ✅ Background workers started")
    except Exception as e:
        # Allow "scheduler already running" to pass through - workers.py handles it
        if "already running" not in str(e).lower():
            print(f"[PHASE2] ❌ Worker startup failed: {e}")
            return
        else:
            print(f"[PHASE2] ℹ️  Worker startup: {e} (continuing with job registration)")

    # 5. Register admin menu item (optional, for future UI)
    # register_admin_plugin_menu_bar(
    #     title="Phase 2 Intel",
    #     route="/admin/phase2",
    #     icon="fa-shield-alt"
    # )

    print("[PHASE2] 🎯 Phase 2 Intelligence Layer initialized successfully")
    print(f"[PHASE2] 📊 Config: First Blood={Phase2Config.FIRST_BLOOD_ENABLED}, "
          f"Health={Phase2Config.HEALTH_ENABLED}, "
          f"Suspicion={Phase2Config.SUSPICION_ENABLED}")
