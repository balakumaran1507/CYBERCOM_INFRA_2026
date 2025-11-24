#!/usr/bin/env python3
"""
CYBERCOM CTF - Flag Encryption Migration Script

This script migrates existing plaintext flags to encrypted storage.
Must be run AFTER adding encrypted_flag column, BEFORE dropping generated_flag.

Usage:
    cd /home/kali/CTF/CTFd
    python3 migrations/encrypt_existing_flags.py

Author: CYBERCOM Security Team
Version: 1.0.0
"""

import sys
import os

# Add CTFd to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from CTFd import create_app
from CTFd.models import db


def migrate_flags():
    """Encrypt all existing plaintext flags."""

    print("=" * 70)
    print("CYBERCOM CTF - Flag Encryption Migration")
    print("=" * 70)
    print()

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Import after app context is created
        from CTFd.plugins.docker_challenges import DynamicFlagMapping
        from CTFd.plugins.docker_challenges.crypto_utils import encrypt_flag
        # Count total flags
        total_flags = DynamicFlagMapping.query.count()
        print(f"📊 Total flags in database: {total_flags}")

        # Use raw SQL to get flags needing encryption
        # (the model doesn't have generated_flag anymore, but the DB does)
        result = db.session.execute(
            db.text("SELECT id, generated_flag FROM dynamic_flag_mapping WHERE encrypted_flag IS NULL")
        )
        unencrypted_flags = result.fetchall()

        unencrypted_count = len(unencrypted_flags)
        print(f"🔓 Flags needing encryption: {unencrypted_count}")

        if unencrypted_count == 0:
            print("✅ All flags already encrypted! Nothing to do.")
            return True

        # Confirm migration
        print()
        print(f"⚠️  About to encrypt {unencrypted_count} flags...")
        print("This operation will:")
        print("  1. Read each plaintext flag from 'generated_flag' column")
        print("  2. Encrypt using Fernet (AES-128-CBC + HMAC-SHA256)")
        print("  3. Store encrypted value in 'encrypted_flag' column")
        print()

        response = input("Proceed with encryption? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("❌ Migration cancelled by user.")
            return False

        print()
        print("🔐 Encrypting flags...")

        # Encrypt each flag
        encrypted_count = 0
        skipped_count = 0
        error_count = 0

        for row in unencrypted_flags:
            flag_id = row[0]
            plaintext = row[1]

            try:
                # Check if plaintext flag exists
                if not plaintext:
                    print(f"⚠️  Skipping flag_mapping.id={flag_id} - no plaintext flag")
                    skipped_count += 1
                    continue

                # Encrypt the plaintext flag
                encrypted = encrypt_flag(plaintext)

                # Store encrypted flag using raw SQL
                db.session.execute(
                    db.text(
                        "UPDATE dynamic_flag_mapping "
                        "SET encrypted_flag = :encrypted, encryption_key_id = 1 "
                        "WHERE id = :flag_id"
                    ),
                    {"encrypted": encrypted, "flag_id": flag_id}
                )

                encrypted_count += 1

                # Show progress every 10 flags
                if encrypted_count % 10 == 0:
                    print(f"  Encrypted {encrypted_count}/{unencrypted_count} flags...")

            except Exception as e:
                print(f"❌ Error encrypting flag_mapping.id={flag_id}: {e}")
                error_count += 1

        # Commit all changes
        if encrypted_count > 0:
            try:
                db.session.commit()
                print()
                print(f"✅ Successfully encrypted {encrypted_count} flags")

                if skipped_count > 0:
                    print(f"⚠️  Skipped {skipped_count} flags (no plaintext)")

                if error_count > 0:
                    print(f"❌ Failed to encrypt {error_count} flags")
                    return False

                # Verify encryption
                print()
                print("🔍 Verifying encryption...")
                result = db.session.execute(
                    db.text("SELECT COUNT(*) FROM dynamic_flag_mapping WHERE encrypted_flag IS NULL")
                )
                remaining = result.scalar()

                if remaining == 0:
                    print("✅ All flags successfully encrypted!")
                    print()
                    print("=" * 70)
                    print("NEXT STEPS:")
                    print("=" * 70)
                    print("1. Run the SQL migration STEP 3 to enforce NOT NULL")
                    print("2. Run the SQL migration STEP 4 to drop old columns")
                    print("3. Verify final schema with STEP 5")
                    print()
                    return True
                else:
                    print(f"⚠️  WARNING: {remaining} flags still unencrypted")
                    return False

            except Exception as e:
                print(f"❌ Database commit failed: {e}")
                db.session.rollback()
                return False
        else:
            print("⚠️  No flags were encrypted")
            return False


if __name__ == "__main__":
    success = migrate_flags()
    sys.exit(0 if success else 1)
