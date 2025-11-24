"""
CYBERCOM CTF - Flag Encryption Utilities
Production-grade cryptographic operations for dynamic flag storage.

Security Properties:
- Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
- Encrypted at rest, decrypted only during validation
- Constant-time comparison to prevent timing attacks
- Key rotation support via encryption_key_id

Author: CYBERCOM Security Team
Version: 1.0.0
"""

import os
import hmac
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from typing import Tuple


class FlagCrypto:
    """
    Handles all cryptographic operations for dynamic flag system.

    Uses Fernet (symmetric encryption) which provides:
    - AES-128 encryption in CBC mode
    - HMAC-SHA256 for authentication
    - Timestamp verification (prevents replay attacks)
    """

    def __init__(self):
        """
        Initialize encryption with key from environment.
        Falls back to generating a new key if none exists (development only).
        """
        self.key = self._load_or_generate_key()
        self.fernet = Fernet(self.key)

    def _load_or_generate_key(self) -> bytes:
        """
        Load encryption key from environment or generate new one.

        PRODUCTION: Set FLAG_ENCRYPTION_KEY environment variable
        DEVELOPMENT: Auto-generates key (stored in instance/flag_key.secret)

        Returns:
            bytes: Fernet encryption key
        """
        # Try environment variable first (production)
        key_b64 = os.environ.get('FLAG_ENCRYPTION_KEY')

        if key_b64:
            try:
                return key_b64.encode('utf-8')
            except Exception as e:
                print(f"[CRYPTO ERROR] Invalid FLAG_ENCRYPTION_KEY: {e}")
                raise

        # Development fallback: load from file or generate
        key_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../instance/flag_key.secret'
        )

        # Try to load existing key
        if os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    return f.read().strip()
            except Exception as e:
                print(f"[CRYPTO ERROR] Failed to load key from {key_file}: {e}")

        # Generate new key and save it
        print("[CRYPTO WARNING] Generating new encryption key - DEVELOPMENT MODE ONLY")
        new_key = Fernet.generate_key()

        try:
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(new_key)
            os.chmod(key_file, 0o600)  # Owner read/write only
            print(f"[CRYPTO] Saved new key to {key_file}")
        except Exception as e:
            print(f"[CRYPTO ERROR] Failed to save key: {e}")

        return new_key

    def encrypt_flag(self, plaintext_flag: str) -> str:
        """
        Encrypt a flag for storage in database.

        Args:
            plaintext_flag: The flag to encrypt (e.g., "CYBERCOM{test_abc123}")

        Returns:
            str: Base64-encoded encrypted flag

        Example:
            >>> crypto = FlagCrypto()
            >>> encrypted = crypto.encrypt_flag("CYBERCOM{test_abc123}")
            >>> print(encrypted)
            'gAAAAABh...'
        """
        if not plaintext_flag:
            raise ValueError("Cannot encrypt empty flag")

        try:
            # Encrypt and return as UTF-8 string (base64-encoded)
            encrypted_bytes = self.fernet.encrypt(plaintext_flag.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"[CRYPTO ERROR] Encryption failed: {e}")
            raise

    def decrypt_flag(self, encrypted_flag: str) -> str:
        """
        Decrypt a flag from database storage.

        Args:
            encrypted_flag: Base64-encoded encrypted flag from database

        Returns:
            str: Decrypted plaintext flag

        Raises:
            InvalidToken: If decryption fails (wrong key, corrupted data, expired)

        Example:
            >>> crypto = FlagCrypto()
            >>> decrypted = crypto.decrypt_flag("gAAAAABh...")
            >>> print(decrypted)
            'CYBERCOM{test_abc123}'
        """
        if not encrypted_flag:
            raise ValueError("Cannot decrypt empty string")

        try:
            # Decrypt and return as UTF-8 string
            decrypted_bytes = self.fernet.decrypt(encrypted_flag.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            print("[CRYPTO ERROR] Invalid token - decryption failed (wrong key or corrupted data)")
            raise
        except Exception as e:
            print(f"[CRYPTO ERROR] Decryption failed: {e}")
            raise

    def constant_time_compare(self, submission: str, expected_flag: str) -> bool:
        """
        Compare submitted flag with expected flag using constant-time comparison.

        Prevents timing attacks by ensuring comparison takes the same time
        regardless of where strings differ.

        Args:
            submission: User's submitted flag
            expected_flag: The correct flag (decrypted)

        Returns:
            bool: True if flags match, False otherwise

        Security:
            Uses hmac.compare_digest() which is cryptographically secure against
            timing attacks. Standard string comparison (==) leaks information
            through execution time.

        Example:
            >>> crypto = FlagCrypto()
            >>> crypto.constant_time_compare("CYBERCOM{test}", "CYBERCOM{test}")
            True
            >>> crypto.constant_time_compare("CYBERCOM{wrong}", "CYBERCOM{test}")
            False
        """
        if not submission or not expected_flag:
            return False

        try:
            # Normalize to UTF-8 bytes for comparison
            submission_bytes = submission.encode('utf-8')
            expected_bytes = expected_flag.encode('utf-8')

            # Constant-time comparison (prevents timing attacks)
            return hmac.compare_digest(submission_bytes, expected_bytes)
        except Exception as e:
            print(f"[CRYPTO ERROR] Comparison failed: {e}")
            return False

    def redact_flag_for_logging(self, flag: str) -> str:
        """
        Redact flag for safe logging (shows only prefix + suffix).

        Args:
            flag: Full flag to redact

        Returns:
            str: Redacted flag safe for logs

        Example:
            >>> crypto = FlagCrypto()
            >>> crypto.redact_flag_for_logging("CYBERCOM{test_abc123_xyz789}")
            'CYBERCOM{test_...xyz789}'
        """
        if not flag or len(flag) < 20:
            return "[REDACTED]"

        # Show prefix (up to opening brace) + first 5 chars + ... + last 6 chars
        try:
            if '{' in flag and '}' in flag:
                prefix = flag.split('{')[0] + '{'
                content = flag.split('{')[1].split('}')[0]

                if len(content) > 15:
                    redacted_content = content[:5] + '...' + content[-6:]
                else:
                    redacted_content = content[:3] + '...' + content[-3:]

                return f"{prefix}{redacted_content}}}"
            else:
                return flag[:8] + '...' + flag[-6:]
        except:
            return "[REDACTED]"


# Global instance for easy import
flag_crypto = FlagCrypto()


# Convenience functions for direct import
def encrypt_flag(plaintext: str) -> str:
    """Encrypt a flag - convenience wrapper."""
    return flag_crypto.encrypt_flag(plaintext)


def decrypt_flag(encrypted: str) -> str:
    """Decrypt a flag - convenience wrapper."""
    return flag_crypto.decrypt_flag(encrypted)


def constant_time_compare(submission: str, expected: str) -> bool:
    """Constant-time flag comparison - convenience wrapper."""
    return flag_crypto.constant_time_compare(submission, expected)


def redact_flag(flag: str) -> str:
    """Redact flag for logging - convenience wrapper."""
    return flag_crypto.redact_flag_for_logging(flag)


# Self-test on import (development mode)
if __name__ == "__main__":
    print("[CRYPTO TEST] Testing flag encryption utilities...")

    test_flag = "CYBERCOM{test_flag_abc123_xyz789}"

    # Test encryption
    encrypted = encrypt_flag(test_flag)
    print(f"Encrypted: {encrypted[:50]}...")

    # Test decryption
    decrypted = decrypt_flag(encrypted)
    assert decrypted == test_flag, "Decryption failed!"
    print(f"Decrypted: {decrypted}")

    # Test constant-time comparison
    assert constant_time_compare(test_flag, decrypted), "Comparison failed!"
    assert not constant_time_compare("WRONG", decrypted), "Comparison should fail!"
    print("Constant-time comparison: PASS")

    # Test redaction
    redacted = redact_flag(test_flag)
    print(f"Redacted for logs: {redacted}")

    print("[CRYPTO TEST] ✅ All tests passed!")
