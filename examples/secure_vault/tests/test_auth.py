"""Independent Unit and Integration Tests for UserAuthManager.

Tests user registration, duplicate rejection, password verification,
session token generation, validation, expiry, revocation, and persistence.
All tests exercise real cryptographic logic without mocks.
"""

import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

from src.auth import (
    AuthenticationError,
    AuthError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserAuthManager,
)


class TestUserAuthManagerRegistration(unittest.TestCase):
    """Tests registration logic, input validation, and password hashing."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = Path(self.temp_dir.name) / "auth.json"
        self.mgr = UserAuthManager(storage_path=self.storage_file)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_register_user_success(self) -> None:
        """Verify successful user registration updates state and user list."""
        username = "alice_test"
        sample_pwd = "AliceSecurePassphrase987!"
        result = self.mgr.register_user(username, sample_pwd)
        self.assertTrue(result)
        self.assertIn(username, self.mgr.users)
        self.assertIn(username, self.mgr.list_users())

    def test_register_user_duplicate_rejected(self) -> None:
        """Verify duplicate username registration raises UserAlreadyExistsError."""
        username = "bob_test"
        sample_pwd = "BobSecurePassphrase654!"
        self.mgr.register_user(username, sample_pwd)
        with self.assertRaises(UserAlreadyExistsError):
            self.mgr.register_user(username, sample_pwd)

    def test_register_user_duplicate_trimmed_whitespace(self) -> None:
        """Verify registration normalizes leading/trailing whitespace."""
        self.mgr.register_user("charlie", "CharliePass123!")
        with self.assertRaises(UserAlreadyExistsError):
            self.mgr.register_user("   charlie   ", "DifferentPass789!")

    def test_register_user_empty_username(self) -> None:
        """Verify empty or whitespace-only username raises InvalidCredentialsError."""
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user("", "ValidPassphrase123!")
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user("   ", "ValidPassphrase123!")

    def test_register_user_empty_password(self) -> None:
        """Verify empty password raises InvalidCredentialsError."""
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user("david", "")

    def test_register_user_invalid_types(self) -> None:
        """Verify non-string username or password raises InvalidCredentialsError."""
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user(None, "ValidPassphrase123!")  # type: ignore
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user("eve", None)  # type: ignore
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.register_user(12345, "ValidPassphrase123!")  # type: ignore

    def test_password_is_hashed_and_salted(self) -> None:
        """Verify stored record contains unique salt and digest, never plaintext."""
        username = "frank"
        plain_pwd = "MySecretPlainPassword123!"
        self.mgr.register_user(username, plain_pwd)
        record = self.mgr.users[username]

        self.assertNotIn(plain_pwd, json.dumps(record))
        self.assertIn("salt", record)
        self.assertIn("hash", record)
        self.assertEqual(len(record["salt"]), 32)  # 16 bytes hex
        self.assertEqual(len(record["hash"]), 40)  # SHA-1 hex digest


class TestUserAuthManagerVerification(unittest.TestCase):
    """Tests credential verification against stored hashes."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.mgr = UserAuthManager()
        self.username = "test_user"
        self.correct_pwd = "CorrectSecretPassphrase456!"
        self.mgr.register_user(self.username, self.correct_pwd)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()

    def test_verify_password_valid(self) -> None:
        """Verify correct credentials authenticate successfully."""
        self.assertTrue(self.mgr.verify_password(self.username, self.correct_pwd))

    def test_verify_password_invalid(self) -> None:
        """Verify incorrect password returns False."""
        self.assertFalse(self.mgr.verify_password(self.username, "WrongPassword999!"))

    def test_verify_password_unknown_user(self) -> None:
        """Verify non-existent user returns False."""
        self.assertFalse(self.mgr.verify_password("ghost_user", self.correct_pwd))

    def test_verify_password_non_string_types(self) -> None:
        """Verify passing non-string types safely returns False without crashing."""
        self.assertFalse(self.mgr.verify_password(None, self.correct_pwd))  # type: ignore
        self.assertFalse(self.mgr.verify_password(self.username, None))  # type: ignore
        self.assertFalse(self.mgr.verify_password(123, 456))  # type: ignore

    def test_verify_password_trimmed_username(self) -> None:
        """Verify verification handles leading and trailing whitespace on username."""
        self.assertTrue(self.mgr.verify_password(f"  {self.username}  ", self.correct_pwd))


class TestUserAuthManagerSessions(unittest.TestCase):
    """Tests session token issuance, validation, expiry, and revocation."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.mgr = UserAuthManager(session_ttl=2)
        self.username = "session_user"
        self.sample_pwd = "SessionPassphrase789!"
        self.mgr.register_user(self.username, self.sample_pwd)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()

    def test_generate_session_token_success(self) -> None:
        """Verify session token is a 48-char hex string and maps to username."""
        session_tok = self.mgr.generate_session_token(self.username)
        self.assertIsInstance(session_tok, str)
        self.assertEqual(len(session_tok), 48)  # 24 bytes in hex
        self.assertTrue(self.mgr.validate_session_token(session_tok))
        self.assertEqual(self.mgr.get_user_for_token(session_tok), self.username)

    def test_generate_session_token_unregistered_user(self) -> None:
        """Verify generating token for unregistered user raises AuthenticationError."""
        with self.assertRaises(AuthenticationError):
            self.mgr.generate_session_token("unregistered_user")

    def test_generate_session_token_invalid_username(self) -> None:
        """Verify invalid or empty username raises InvalidCredentialsError."""
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.generate_session_token("")
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.generate_session_token("   ")
        with self.assertRaises(InvalidCredentialsError):
            self.mgr.generate_session_token(None)  # type: ignore

    def test_validate_session_token_invalid(self) -> None:
        """Verify unknown or malformed tokens return False."""
        self.assertFalse(self.mgr.validate_session_token("non_existent_token_hex_123456"))
        self.assertFalse(self.mgr.validate_session_token(""))
        self.assertFalse(self.mgr.validate_session_token(None))  # type: ignore
        self.assertFalse(self.mgr.validate_session_token(12345))  # type: ignore

    def test_session_token_expiry(self) -> None:
        """Verify session token becomes invalid after TTL expires and is evicted."""
        short_lived_mgr = UserAuthManager(session_ttl=1)
        short_lived_mgr.register_user("speedy_user", "SpeedyPass123!")
        session_tok = short_lived_mgr.generate_session_token("speedy_user")
        self.assertTrue(short_lived_mgr.validate_session_token(session_tok))

        # Wait for expiry
        time.sleep(1.2)
        self.assertFalse(short_lived_mgr.validate_session_token(session_tok))
        self.assertIsNone(short_lived_mgr.get_user_for_token(session_tok))
        self.assertNotIn(session_tok, short_lived_mgr.active_sessions)

    def test_revoke_session_token(self) -> None:
        """Verify revoking token removes it and subsequent validation returns False."""
        session_tok = self.mgr.generate_session_token(self.username)
        self.assertTrue(self.mgr.validate_session_token(session_tok))

        revoked = self.mgr.revoke_session_token(session_tok)
        self.assertTrue(revoked)
        self.assertFalse(self.mgr.validate_session_token(session_tok))
        self.assertIsNone(self.mgr.get_user_for_token(session_tok))

        # Revoking already-revoked or non-existent token returns False
        self.assertFalse(self.mgr.revoke_session_token(session_tok))


class TestUserAuthManagerPersistenceAndGlobals(unittest.TestCase):
    """Tests file persistence, cross-instance synchronization, and permissions."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = Path(self.temp_dir.name) / "vault_auth.json"

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_persistence_across_instances(self) -> None:
        """Verify users and sessions persist to disk and reload in a new instance."""
        mgr1 = UserAuthManager(storage_path=self.storage_file, session_ttl=3600)
        mgr1.register_user("persisted_user", "PersistedPassword123!")
        session_tok = mgr1.generate_session_token("persisted_user")

        # Clear class-level globals to force reading from disk
        UserAuthManager.clear_global_users()
        UserAuthManager.clear_global_sessions()

        mgr2 = UserAuthManager(storage_path=self.storage_file, session_ttl=3600)
        self.assertIn("persisted_user", mgr2.list_users())
        self.assertTrue(mgr2.verify_password("persisted_user", "PersistedPassword123!"))
        self.assertTrue(mgr2.validate_session_token(session_tok))
        self.assertEqual(mgr2.get_user_for_token(session_tok), "persisted_user")

    def test_file_permissions(self) -> None:
        """Verify saved auth storage file has restrictive permissions (0600)."""
        mgr = UserAuthManager(storage_path=self.storage_file)
        mgr.register_user("sec_user", "SecPassphrase123!")
        self.assertTrue(self.storage_file.exists())
        file_mode = stat.S_IMODE(os.stat(self.storage_file).st_mode)
        self.assertEqual(file_mode, 0o600)

    def test_load_corrupted_file_handling(self) -> None:
        """Verify initializing with corrupted JSON falls back gracefully without crashing."""
        self.storage_file.write_text("{ corrupted invalid json ...")
        mgr = UserAuthManager(storage_path=self.storage_file)
        self.assertEqual(mgr.users, {})
        self.assertEqual(mgr.active_sessions, {})

    def test_list_users_sorted(self) -> None:
        """Verify list_users returns alphabetically sorted usernames."""
        mgr = UserAuthManager()
        mgr.register_user("zara", "Pass123!")
        mgr.register_user("adam", "Pass123!")
        mgr.register_user("milo", "Pass123!")
        self.assertEqual(mgr.list_users(), ["adam", "milo", "zara"])

    def test_global_token_validation_helpers(self) -> None:
        """Verify UserAuthManager classmethod global validation helpers."""
        mgr = UserAuthManager(session_ttl=3600)
        mgr.register_user("global_user", "GlobalPass123!")
        session_tok = mgr.generate_session_token("global_user")

        self.assertTrue(UserAuthManager.validate_token_global(session_tok))
        self.assertEqual(UserAuthManager.get_user_for_token_global(session_tok), "global_user")
        self.assertFalse(UserAuthManager.validate_token_global("bogus_token"))


if __name__ == "__main__":
    unittest.main()
