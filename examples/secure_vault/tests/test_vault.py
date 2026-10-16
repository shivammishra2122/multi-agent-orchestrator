"""Independent Unit and Integration Tests for SecureVaultStorage.

Tests initialization, secret storage, retrieval, updating, listing, deletion,
path traversal attack mitigations, persistence, and authorization.
All tests exercise real filesystem and data-persistence logic without mocks.
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from src.auth import AuthenticationError, UserAuthManager
from src.vault import (
    PathTraversalError,
    SecretNotFoundError,
    SecretRecord,
    SecureVaultStorage,
    VaultNotInitializedError,
    VaultSecretList,
)


class TestSecureVaultStorageInit(unittest.TestCase):
    """Tests vault storage initialization and uninitialized state protection."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "vault"

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_init_creates_directories_and_sets_permissions(self) -> None:
        """Verify initialization creates vault and secrets directories with 0700 mode."""
        vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=False)
        self.assertTrue(self.vault_path.exists())
        secrets_dir = self.vault_path / "secrets"
        self.assertTrue(secrets_dir.exists())

        vault_mode = stat.S_IMODE(os.stat(self.vault_path).st_mode)
        secrets_mode = stat.S_IMODE(os.stat(secrets_dir).st_mode)
        self.assertEqual(vault_mode, 0o700)
        self.assertEqual(secrets_mode, 0o700)

    def test_init_via_classmethod_descriptor(self) -> None:
        """Verify SecureVaultStorage.init_vault(...) classmethod initialization."""
        vault = SecureVaultStorage.init_vault(self.vault_path)
        self.assertIsInstance(vault, SecureVaultStorage)
        self.assertEqual(vault.vault_dir, self.vault_path.resolve())

    def test_uninitialized_vault_raises_error(self) -> None:
        """Verify calling operations on uninitialized storage raises VaultNotInitializedError."""
        uninit_vault = SecureVaultStorage()
        with self.assertRaises(VaultNotInitializedError):
            uninit_vault.set_secret("key1", "val1", "fake_token")
        with self.assertRaises(VaultNotInitializedError):
            uninit_vault.get_secret("key1", "fake_token")
        with self.assertRaises(VaultNotInitializedError):
            uninit_vault.list_secrets("fake_token")
        with self.assertRaises(VaultNotInitializedError):
            uninit_vault.delete_secret("key1", "fake_token")
        with self.assertRaises(VaultNotInitializedError):
            uninit_vault.has_secret("key1", "fake_token")


class TestSecureVaultStorageOperations(unittest.TestCase):
    """Tests secret storage, retrieval, list, update, and deletion."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "vault"

        # Setup real auth manager with registered users
        self.auth_file = self.vault_path / "auth.json"
        self.auth_mgr = UserAuthManager(storage_path=self.auth_file)
        self.auth_mgr.register_user("operator_a", "OperatorPass123!")
        self.auth_mgr.register_user("operator_b", "OperatorPass456!")
        self.tok_a = self.auth_mgr.generate_session_token("operator_a")
        self.tok_b = self.auth_mgr.generate_session_token("operator_b")

        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_set_and_get_secret_success(self) -> None:
        """Verify storing a secret returns SecretRecord and can be retrieved."""
        key_name = "db_connection_uri"
        secret_content = "postgres://user:dbpass@localhost:5432/vault_db"

        record = self.vault.set_secret(key_name, secret_content, self.tok_a)
        self.assertIsInstance(record, SecretRecord)
        self.assertEqual(record.key, key_name)
        self.assertEqual(record.value, secret_content)
        self.assertEqual(record["key"], key_name)
        self.assertEqual(record["value"], secret_content)
        self.assertEqual(record["created_by"], "operator_a")
        self.assertEqual(record["updated_by"], "operator_a")

        # Retrieve secret
        retrieved = self.vault.get_secret(key_name, self.tok_a)
        self.assertEqual(retrieved.key, key_name)
        self.assertEqual(retrieved.value, secret_content)
        self.assertTrue(self.vault.has_secret(key_name, self.tok_a))

    def test_secret_file_permissions_and_storage(self) -> None:
        """Verify secret files on disk have 0600 permissions."""
        key_name = "api_credential"
        self.vault.set_secret(key_name, "super_secret_payload", self.tok_a)

        secret_file = self.vault_path / "secrets" / f"{key_name}.json"
        self.assertTrue(secret_file.exists())
        file_mode = stat.S_IMODE(os.stat(secret_file).st_mode)
        self.assertEqual(file_mode, 0o600)

        # Verify vault index exists and has 0600 mode
        index_file = self.vault_path / "vault_index.json"
        self.assertTrue(index_file.exists())
        index_mode = stat.S_IMODE(os.stat(index_file).st_mode)
        self.assertEqual(index_mode, 0o600)

    def test_update_existing_secret(self) -> None:
        """Verify updating an existing secret updates value and preserves created_at/created_by."""
        key_name = "rotatable_key"
        first_rec = self.vault.set_secret(key_name, "version_1", self.tok_a)
        orig_created_at = first_rec["created_at"]
        self.assertEqual(first_rec["created_by"], "operator_a")

        updated_rec = self.vault.set_secret(key_name, "version_2", self.tok_b)
        self.assertEqual(updated_rec.value, "version_2")
        self.assertEqual(updated_rec["created_at"], orig_created_at)
        self.assertEqual(updated_rec["created_by"], "operator_a")
        self.assertEqual(updated_rec["updated_by"], "operator_b")

    def test_get_nonexistent_secret_raises_error(self) -> None:
        """Verify attempting to retrieve a non-existent secret raises SecretNotFoundError."""
        with self.assertRaises(SecretNotFoundError):
            self.vault.get_secret("non_existent_secret_key", self.tok_a)
        self.assertFalse(self.vault.has_secret("non_existent_secret_key", self.tok_a))

    def test_list_secrets(self) -> None:
        """Verify listing secrets returns VaultSecretList with dict, key, and item views."""
        self.vault.set_secret("key_alpha", "val_alpha", self.tok_a)
        self.vault.set_secret("key_beta", "val_beta", self.tok_a)
        self.vault.set_secret("key_gamma", "val_gamma", self.tok_a)

        secret_list = self.vault.list_secrets(self.tok_a)
        self.assertIsInstance(secret_list, VaultSecretList)
        self.assertEqual(len(secret_list), 3)

        # Test containment and key lookup
        self.assertIn("key_alpha", secret_list)
        self.assertIn("key_beta", secret_list)
        self.assertEqual(secret_list["key_alpha"].value, "val_alpha")
        self.assertEqual(set(secret_list.keys()), {"key_alpha", "key_beta", "key_gamma"})

        # Test to_dict export
        dict_view = secret_list.to_dict()
        self.assertEqual(dict_view["key_alpha"]["value"], "val_alpha")

    def test_delete_secret(self) -> None:
        """Verify deleting a secret removes it from cache and filesystem."""
        key_name = "ephemeral_key"
        self.vault.set_secret(key_name, "delete_me", self.tok_a)
        self.assertTrue(self.vault.has_secret(key_name, self.tok_a))

        deleted = self.vault.delete_secret(key_name, self.tok_a)
        self.assertTrue(deleted)
        self.assertFalse(self.vault.has_secret(key_name, self.tok_a))
        with self.assertRaises(SecretNotFoundError):
            self.vault.get_secret(key_name, self.tok_a)

        # Deleting again returns False
        self.assertFalse(self.vault.delete_secret(key_name, self.tok_a))

    def test_persistence_across_vault_restarts(self) -> None:
        """Verify secrets remain accessible after re-initializing storage from disk."""
        self.vault.set_secret("persisted_secret", "stored_on_disk", self.tok_a)

        # Re-create vault instance from same directory
        reopened_vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)
        rec = reopened_vault.get_secret("persisted_secret", self.tok_a)
        self.assertEqual(rec.value, "stored_on_disk")
        self.assertIn("persisted_secret", reopened_vault.list_secrets(self.tok_a).keys())


class TestSecureVaultStoragePathTraversal(unittest.TestCase):
    """Tests defense against directory traversal and path manipulation attacks."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "vault"
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=False)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_path_traversal_relative_sequences(self) -> None:
        """Verify traversal attack sequences raise PathTraversalError."""
        traversal_attempts = [
            "../../etc/passwd",
            "../outside_vault",
            "foo/../../bar",
            "secrets/../../../root/.ssh/id_rsa",
            "..\\..\\windows\\system32\\cmd.exe",
            "sub/../../../../../../etc/shadow",
        ]
        for bad_key in traversal_attempts:
            with self.subTest(key=bad_key):
                with self.assertRaises(PathTraversalError):
                    self.vault.set_secret(bad_key, "payload", "valid_token")
                with self.assertRaises(PathTraversalError):
                    self.vault.get_secret(bad_key, "valid_token")
                self.assertFalse(self.vault.has_secret(bad_key, "valid_token"))

    def test_path_traversal_absolute_paths(self) -> None:
        """Verify absolute path key attempts raise PathTraversalError."""
        abs_attempts = [
            "/etc/passwd",
            "/var/log/system.log",
            "\\Windows\\System32\\config\\SAM",
        ]
        for bad_key in abs_attempts:
            with self.subTest(key=bad_key):
                with self.assertRaises(PathTraversalError):
                    self.vault.set_secret(bad_key, "payload", "valid_token")
                with self.assertRaises(PathTraversalError):
                    self.vault.get_secret(bad_key, "valid_token")

    def test_null_byte_injection_rejected(self) -> None:
        """Verify null byte injection in key raises PathTraversalError."""
        with self.assertRaises(PathTraversalError):
            self.vault.set_secret("valid_prefix\0/../../etc/passwd", "payload", "valid_token")

    def test_empty_or_invalid_key_types(self) -> None:
        """Verify empty strings or non-string key inputs raise ValueError."""
        with self.assertRaises(ValueError):
            self.vault.set_secret("", "payload", "valid_token")
        with self.assertRaises(ValueError):
            self.vault.set_secret("   ", "payload", "valid_token")
        with self.assertRaises(ValueError):
            self.vault.set_secret(None, "payload", "valid_token")  # type: ignore
        with self.assertRaises(ValueError):
            self.vault.set_secret(12345, "payload", "valid_token")  # type: ignore


class TestSecureVaultStorageAuthentication(unittest.TestCase):
    """Tests access control enforcement for all vault operations."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "vault"
        self.auth_mgr = UserAuthManager()
        self.auth_mgr.register_user("auth_user", "ValidPassphrase123!")
        self.valid_tok = self.auth_mgr.generate_session_token("auth_user")
        self.vault = SecureVaultStorage(vault_dir=self.vault_path, auth_manager=self.auth_mgr)

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def test_operations_with_invalid_token_rejected(self) -> None:
        """Verify invalid or empty session tokens raise AuthenticationError."""
        invalid_tokens = ["", "   ", "invalid_token_hex_9999", None]
        for bad_tok in invalid_tokens:
            with self.subTest(tok=bad_tok):
                with self.assertRaises(AuthenticationError):
                    self.vault.set_secret("key1", "val1", bad_tok)  # type: ignore
                with self.assertRaises(AuthenticationError):
                    self.vault.get_secret("key1", bad_tok)  # type: ignore
                with self.assertRaises(AuthenticationError):
                    self.vault.list_secrets(bad_tok)  # type: ignore
                with self.assertRaises(AuthenticationError):
                    self.vault.delete_secret("key1", bad_tok)  # type: ignore


if __name__ == "__main__":
    unittest.main()
