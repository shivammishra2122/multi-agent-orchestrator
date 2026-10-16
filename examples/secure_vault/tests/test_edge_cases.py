"""Independent Unit and Integration Tests for Boundary Conditions and Edge Cases.

Tests boundary conditions across UserAuthManager and SecureVaultStorage:
- Empty strings and whitespace variants
- Unicode and multi-byte UTF-8 character sets (emojis, accented, Cyrillic, CJK)
- Very large secret payloads (100KB, 1MB, 5MB)
- Malformed, expired, revoked, and type-invalid session tokens
- Non-string structured secret payloads (dicts, lists, ints, booleans, None)
All tests exercise real application logic without mocks.
"""

import hashlib
import tempfile
import time
import unittest
from pathlib import Path

from src.auth import (
    AuthenticationError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserAuthManager,
)
from src.vault import (
    PathTraversalError,
    SecretNotFoundError,
    SecureVaultStorage,
)


class TestEmptyStringsAndWhitespace(unittest.TestCase):
    """Tests handling of empty, whitespace, and boundary string values."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "edge_vault"
        self.auth_mgr = UserAuthManager()
        self.auth_mgr.register_user("edge_admin", "AdminPass123!")
        self.valid_tok = self.auth_mgr.generate_session_token("edge_admin")
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_auth_empty_and_whitespace_usernames_rejected(self) -> None:
        """Verify auth manager rejects empty or whitespace-only usernames."""
        empty_variants = ["", " ", "   ", "\t", "\n", "\r\n"]
        for empty_val in empty_variants:
            with self.subTest(variant=repr(empty_val)):
                with self.assertRaises(InvalidCredentialsError):
                    self.auth_mgr.register_user(empty_val, "ValidPass123!")
                with self.assertRaises(InvalidCredentialsError):
                    self.auth_mgr.generate_session_token(empty_val)

    def test_auth_empty_password_rejected(self) -> None:
        """Verify empty password string raises InvalidCredentialsError."""
        with self.assertRaises(InvalidCredentialsError):
            self.auth_mgr.register_user("valid_user_empty_pwd", "")

    def test_vault_empty_and_whitespace_keys(self) -> None:
        """Verify storage engine rejects empty or whitespace-only keys."""
        empty_keys = ["", " ", "   ", "\t\t", "\n"]
        for bad_key in empty_keys:
            with self.subTest(key=repr(bad_key)):
                with self.assertRaises(ValueError):
                    self.vault.set_secret(bad_key, "some_value", self.valid_tok)
                with self.assertRaises(ValueError):
                    self.vault.get_secret(bad_key, self.valid_tok)

    def test_vault_empty_string_secret_value(self) -> None:
        """Verify empty string can be stored and retrieved as a valid secret value."""
        self.vault.set_secret("empty_secret", "", self.valid_tok)
        record = self.vault.get_secret("empty_secret", self.valid_tok)
        self.assertEqual(record.value, "")

    def test_vault_whitespace_secret_value_preserved(self) -> None:
        """Verify whitespace secret values are preserved exactly without stripping."""
        whitespace_payload = "   \n\t  preserved  \t\n  "
        self.vault.set_secret("whitespace_secret", whitespace_payload, self.valid_tok)
        record = self.vault.get_secret("whitespace_secret", self.valid_tok)
        self.assertEqual(record.value, whitespace_payload)


class TestUnicodeAndSpecialCharacters(unittest.TestCase):
    """Tests multi-byte UTF-8, international scripts, and emoji handling."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "unicode_vault"
        self.auth_mgr = UserAuthManager()
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_unicode_user_registration_and_authentication(self) -> None:
        """Verify registration and verification with Unicode usernames and passwords."""
        test_accounts = [
            ("ünicode_üser", "P@sswørd_123_🔑"),
            ("тестовый_пользователь", "СложныйПароль!789"),
            ("日本語ユーザー", "セキュリティ_パスワード_456"),
            ("مستخدم_مشفر", "كلمة_المرور_السرية!"),
            ("admin_🚀_vault", "ComplexEmoji🌟✨Pass99!"),
        ]
        for uname, upwd in test_accounts:
            with self.subTest(account=uname):
                reg_ok = self.auth_mgr.register_user(uname, upwd)
                self.assertTrue(reg_ok)
                self.assertTrue(self.auth_mgr.verify_password(uname, upwd))
                self.assertFalse(self.auth_mgr.verify_password(uname, "WrongPassphrase!"))

                sess_tok = self.auth_mgr.generate_session_token(uname)
                self.assertEqual(self.auth_mgr.get_user_for_token(sess_tok), uname)

    def test_unicode_secret_keys_and_values(self) -> None:
        """Verify storing and retrieving Unicode keys and multilingual payloads."""
        self.auth_mgr.register_user("unicode_admin", "Pass12345!")
        auth_tok = self.auth_mgr.generate_session_token("unicode_admin")

        unicode_pairs = [
            ("clé_secrète_api", "Valeur chiffrée avec accents: à, é, î, ô, ü!"),
            ("ключ_шифрования", "Конфиденциальные данные: токен доступа к API."),
            ("認証キー_prod", "日本語の機密データ: データベース接続文字列。"),
            ("مفتاح_سري", "نص سري باللغة العربية مع علامات ترقيم خاصة."),
            ("emoji_key_🔐", "Payload with rocket 🚀, key 🔑, shield 🛡️ and lock 🔒"),
        ]

        for k, v in unicode_pairs:
            with self.subTest(key=k):
                rec = self.vault.set_secret(k, v, auth_tok)
                self.assertEqual(rec.key, k)
                self.assertEqual(rec.value, v)

                fetched = self.vault.get_secret(k, auth_tok)
                self.assertEqual(fetched.value, v)
                self.assertTrue(self.vault.has_secret(k, auth_tok))

        all_keys = self.vault.list_secrets(auth_tok).keys()
        for k, _ in unicode_pairs:
            self.assertIn(k, all_keys)


class TestVeryLargeSecretValues(unittest.TestCase):
    """Tests storing and retrieving large payloads up to 5MB."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "large_payload_vault"
        self.auth_mgr = UserAuthManager()
        self.auth_mgr.register_user("scale_user", "ScalePass123!")
        self.auth_tok = self.auth_mgr.generate_session_token("scale_user")
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_store_and_retrieve_100kb_payload(self) -> None:
        """Verify 100KB payload integrity through set and get."""
        payload_100k = "A" * (100 * 1024)
        expected_digest = hashlib.sha256(payload_100k.encode("utf-8")).hexdigest()

        self.vault.set_secret("blob_100kb", payload_100k, self.auth_tok)
        rec = self.vault.get_secret("blob_100kb", self.auth_tok)
        actual_digest = hashlib.sha256(rec.value.encode("utf-8")).hexdigest()

        self.assertEqual(len(rec.value), len(payload_100k))
        self.assertEqual(actual_digest, expected_digest)

    def test_store_and_retrieve_1mb_payload(self) -> None:
        """Verify 1MB payload integrity and persistent reloading."""
        payload_1mb = ("XYZ123456789\n" * (1024 * 79))[: 1024 * 1024]
        expected_digest = hashlib.sha256(payload_1mb.encode("utf-8")).hexdigest()

        self.vault.set_secret("blob_1mb", payload_1mb, self.auth_tok)

        # Fresh instance reading from disk
        fresh_vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)
        rec = fresh_vault.get_secret("blob_1mb", self.auth_tok)
        actual_digest = hashlib.sha256(rec.value.encode("utf-8")).hexdigest()

        self.assertEqual(len(rec.value), len(payload_1mb))
        self.assertEqual(actual_digest, expected_digest)

    def test_store_and_retrieve_5mb_payload(self) -> None:
        """Verify 5MB payload storage, retrieval, and clean deletion."""
        pattern = "SECURE_VAULT_CHUNK_DATA_BLOCK_0123456789ABCDEF\n"
        repetitions = (5 * 1024 * 1024) // len(pattern) + 1
        payload_5mb = (pattern * repetitions)[: 5 * 1024 * 1024]
        expected_digest = hashlib.sha256(payload_5mb.encode("utf-8")).hexdigest()

        self.vault.set_secret("blob_5mb", payload_5mb, self.auth_tok)
        rec = self.vault.get_secret("blob_5mb", self.auth_tok)
        actual_digest = hashlib.sha256(rec.value.encode("utf-8")).hexdigest()

        self.assertEqual(len(rec.value), 5 * 1024 * 1024)
        self.assertEqual(actual_digest, expected_digest)

        # Verify deletion cleans up 5MB file
        deleted = self.vault.delete_secret("blob_5mb", self.auth_tok)
        self.assertTrue(deleted)
        self.assertFalse(self.vault.has_secret("blob_5mb", self.auth_tok))


class TestInvalidSessionTokensAndAccessControl(unittest.TestCase):
    """Tests rigorous boundary checking on authentication tokens."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "token_vault"
        self.auth_mgr = UserAuthManager(session_ttl=1)
        self.auth_mgr.register_user("token_user", "TokenPass123!")
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_expired_token_rejected_across_operations(self) -> None:
        """Verify expired session token is rejected and raises AuthenticationError."""
        timed_tok = self.auth_mgr.generate_session_token("token_user")
        self.vault.set_secret("active_key", "active_val", timed_tok)

        # Wait past 1-second TTL
        time.sleep(1.2)

        with self.assertRaises(AuthenticationError):
            self.vault.set_secret("new_key", "new_val", timed_tok)
        with self.assertRaises(AuthenticationError):
            self.vault.get_secret("active_key", timed_tok)
        with self.assertRaises(AuthenticationError):
            self.vault.list_secrets(timed_tok)
        with self.assertRaises(AuthenticationError):
            self.vault.delete_secret("active_key", timed_tok)

    def test_revoked_token_rejected(self) -> None:
        """Verify revoked token is immediately rejected across all endpoints."""
        live_tok = self.auth_mgr.generate_session_token("token_user")
        self.vault.set_secret("rev_key", "rev_val", live_tok)

        self.auth_mgr.revoke_session_token(live_tok)

        with self.assertRaises(AuthenticationError):
            self.vault.get_secret("rev_key", live_tok)
        with self.assertRaises(AuthenticationError):
            self.vault.set_secret("rev_key", "updated", live_tok)
        with self.assertRaises(AuthenticationError):
            self.vault.list_secrets(live_tok)

    def test_malformed_and_type_invalid_tokens(self) -> None:
        """Verify non-string and malformed tokens are rejected safely."""
        bad_token_samples = [
            None,
            123456,
            3.14159,
            ["token_in_list"],
            {"token": "dict"},
            True,
            False,
            "",
            "   ",
            "completely_unrecognized_hex_string_1234567890",
        ]
        for bad_tok in bad_token_samples:
            with self.subTest(tok=repr(bad_tok)):
                with self.assertRaises(AuthenticationError):
                    self.vault.set_secret("any_key", "any_val", bad_tok)  # type: ignore


class TestStructuredSecretDataTypes(unittest.TestCase):
    """Tests storing non-string structured values (JSON primitives, arrays, objects)."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "types_vault"
        self.auth_mgr = UserAuthManager()
        self.auth_mgr.register_user("type_user", "TypePass123!")
        self.auth_tok = self.auth_mgr.generate_session_token("type_user")
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_structured_json_payloads(self) -> None:
        """Verify storing dicts, lists, booleans, ints, floats, and None values."""
        test_payloads = {
            "dict_secret": {"host": "127.0.0.1", "port": 5432, "ssl": True, "tags": ["db", "prod"]},
            "list_secret": ["token1", "token2", 42, False, None],
            "integer_secret": 987654321,
            "float_secret": 123.456789,
            "boolean_false_secret": False,
            "boolean_true_secret": True,
            "none_secret": None,
        }

        for key_name, expected_val in test_payloads.items():
            with self.subTest(key=key_name):
                self.vault.set_secret(key_name, expected_val, self.auth_tok)
                rec = self.vault.get_secret(key_name, self.auth_tok)
                self.assertEqual(rec.value, expected_val)


if __name__ == "__main__":
    unittest.main()
