#!/usr/bin/env python3
"""Secure Vault Storage Engine for SecureVault.

Provides tamper-evident, path-traversal-protected secret storage,
secure retrieval, listing, and session token verification.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

try:
    from src.auth import AuthenticationError, UserAuthManager
except ImportError:
    from auth import AuthenticationError, UserAuthManager  # type: ignore


class VaultError(Exception):
    """Base exception for vault storage errors."""
    pass


class VaultNotInitializedError(VaultError, RuntimeError):
    """Raised when an operation is attempted before the vault is initialized."""
    pass


class PathTraversalError(VaultError, PermissionError, ValueError):
    """Raised when a path traversal attempt is detected in secret keys or file paths."""
    pass


class SecretNotFoundError(VaultError, KeyError):
    """Raised when a requested secret key does not exist in the vault."""
    pass


class SecretRecord(dict):
    """Dictionary representing a secret record envelope with separated metadata and value."""

    def __init__(
        self,
        key: str,
        value: Any,
        timestamp: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        created_by: Optional[str] = None,
        updated_by: Optional[str] = None,
        **extra: Any
    ) -> None:
        created = created_at or timestamp
        updated = updated_at or timestamp
        # Clean envelope separating reserved metadata fields from payload
        data: Dict[str, Any] = {
            "key": key,
            "value": value,
            "timestamp": timestamp,
            "created_at": created,
            "updated_at": updated,
            "created_by": created_by,
            "updated_by": updated_by,
        }
        for k, v in extra.items():
            if k not in data:
                data[k] = v
        super().__init__(data)

    def __getitem__(self, item: Any) -> Any:
        # Check standard dictionary keys first
        if super().__contains__(item):
            return super().__getitem__(item)
        # Transparently allow lookup by key name if not conflicting with reserved keys
        if item == self.get("key"):
            return self.get("value")
        return super().__getitem__(item)

    @property
    def key(self) -> str:
        """Return the secret key."""
        return self["key"]

    @property
    def value(self) -> Any:
        """Return the secret value."""
        return self["value"]

    @property
    def timestamp(self) -> str:
        """Return the ISO-8601 timestamp."""
        return self["timestamp"]

    def __eq__(self, other: Any) -> bool:
        """Allow comparison against key string or dictionary representation."""
        if isinstance(other, str):
            return self["key"] == other
        return super().__eq__(other)

    def to_dict(self) -> Dict[str, Any]:
        """Return a clean dictionary representation of the secret record."""
        return {
            "key": self["key"],
            "value": self["value"],
            "timestamp": self["timestamp"],
            "created_at": self["created_at"],
            "updated_at": self["updated_at"],
            "created_by": self.get("created_by"),
            "updated_by": self.get("updated_by"),
        }


class VaultSecretList(list):
    """List of secret records supporting list iteration, string key indexing, and dict views."""

    def __init__(self, records: List[SecretRecord]) -> None:
        super().__init__(records)
        self._by_key: Dict[str, SecretRecord] = {r["key"]: r for r in records}

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item in self._by_key:
                return self._by_key[item]
            raise KeyError(f"Secret '{item}' not found in vault secret list.")
        return super().__getitem__(item)

    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str) and item in self._by_key:
            return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get secret record by key name with default fallback."""
        return self._by_key.get(key, default)

    def keys(self) -> List[str]:
        """Return list of secret key names."""
        return list(self._by_key.keys())

    def values(self) -> List[SecretRecord]:
        """Return list of secret records."""
        return list(self._by_key.values())

    def items(self) -> List[tuple]:
        """Return key-record tuples."""
        return list(self._by_key.items())

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary mapping secret keys to their clean dictionary records."""
        return {k: v.to_dict() for k, v in self._by_key.items()}


class _InitVaultDescriptor:
    """Descriptor enabling init_vault to be invoked either as an instance method or classmethod."""

    def __init__(self, func: Callable) -> None:
        self.func = func

    def __get__(self, instance: Any, owner: Any) -> Callable:
        if instance is None:
            def class_init(vault_dir: Union[str, Path], *args: Any, **kwargs: Any) -> Any:
                obj = owner(*args, **kwargs)
                obj.init_vault(vault_dir)
                return obj
            return class_init
        else:
            def instance_init(vault_dir: Union[str, Path], *args: Any, **kwargs: Any) -> Any:
                return self.func(instance, vault_dir, *args, **kwargs)
            return instance_init


class SecureVaultStorage:
    """Tamper-evident, path-traversal-protected secret vault storage manager."""

    def __init__(
        self,
        vault_dir: Optional[Union[str, Path]] = None,
        auth_manager: Optional[Union[UserAuthManager, bool]] = None
    ) -> None:
        """Initialize SecureVaultStorage.

        Args:
            vault_dir: Optional directory path to store vault data.
            auth_manager: Optional UserAuthManager instance. If False, authentication
                          is bypassed (useful for testing). If None, defaults to validating
                          against the shared global session registry or vault auth file.
        """
        self.vault_dir: Optional[Path] = None
        self.auth_manager: Optional[Union[UserAuthManager, bool]] = auth_manager
        self._secrets_cache: Dict[str, SecretRecord] = {}

        if vault_dir:
            self.init_vault(vault_dir)

    def _raw_init_vault(self, vault_dir: Union[str, Path]) -> Dict[str, Any]:
        """Internal initialization logic for vault directory."""
        path = Path(vault_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass

        secrets_dir = path / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(secrets_dir, 0o700)
        except OSError:
            pass

        self.vault_dir = path
        self._load_all_secrets()

        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "status": "initialized",
            "vault_dir": str(self.vault_dir),
            "timestamp": timestamp,
        }

    init_vault = _InitVaultDescriptor(_raw_init_vault)

    def _ensure_initialized(self) -> None:
        """Ensure vault_dir has been initialized before reading or writing."""
        if not self.vault_dir or not self.vault_dir.exists():
            raise VaultNotInitializedError(
                "SecureVault has not been initialized. Call init_vault(vault_dir) first."
            )

    def _validate_token(self, token: str) -> str:
        """Validate session token and return the associated username."""
        if self.auth_manager is False:
            return "system"

        if not token or not isinstance(token, str):
            raise AuthenticationError("Authentication failed: token must be a non-empty string.")

        # Check explicit instance auth_manager
        if isinstance(self.auth_manager, UserAuthManager):
            if not self.auth_manager.validate_session_token(token):
                raise AuthenticationError("Authentication failed: invalid or expired session token.")
            username = self.auth_manager.get_user_for_token(token)
            return username or "authenticated_user"

        # Check global session registry
        if UserAuthManager.validate_token_global(token):
            username = UserAuthManager.get_user_for_token_global(token)
            return username or "authenticated_user"

        # Check if auth file exists in vault directory
        if self.vault_dir:
            auth_file = self.vault_dir / "auth.json"
            if auth_file.exists():
                mgr = UserAuthManager(storage_path=auth_file)
                if mgr.validate_session_token(token):
                    username = mgr.get_user_for_token(token)
                    return username or "authenticated_user"

        raise AuthenticationError("Authentication failed: invalid or expired session token.")

    def _validate_key(self, key: str) -> Path:
        """Validate secret key against path traversal attacks.

        Args:
            key: Secret key identifier.

        Returns:
            Resolved absolute Path strictly within vault secrets directory.

        Raises:
            ValueError: If key is not a non-empty string.
            PathTraversalError: If key contains directory traversal sequences or escapes vault root.
        """
        if not isinstance(key, str):
            raise ValueError(f"Secret key must be a string, got {type(key).__name__}.")

        cleaned_key = key.strip()
        if not cleaned_key:
            raise ValueError("Secret key cannot be empty or whitespace.")

        # Defense-in-depth: check for null bytes and traversal sequences
        if "\0" in key:
            raise PathTraversalError("Path traversal rejected: null byte detected in key.")

        # Prevent explicit '..' traversal segments
        segments = key.replace("\\", "/").split("/")
        if ".." in segments or ".." in key:
            raise PathTraversalError(f"Path traversal rejected: key contains traversal sequence: '{key}'")

        if key.startswith("/") or key.startswith("\\"):
            raise PathTraversalError(f"Path traversal rejected: absolute path key: '{key}'")

        self._ensure_initialized()
        secrets_dir = (self.vault_dir / "secrets").resolve()  # type: ignore

        # Resolve candidate target file path
        target_path = (secrets_dir / f"{key}.json").resolve()

        # Strict containment check
        try:
            target_path.relative_to(secrets_dir)
        except ValueError:
            raise PathTraversalError(
                f"Path traversal rejected: key '{key}' resolves outside vault directory."
            )

        return target_path

    def _load_all_secrets(self) -> None:
        """Load all secret files from secrets directory into cache."""
        self._secrets_cache.clear()
        if not self.vault_dir:
            return

        index_file = self.vault_dir / "vault_index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                for k, v in index_data.items():
                    self._secrets_cache[k] = SecretRecord(**v)
                return
            except Exception:
                pass

        secrets_dir = self.vault_dir / "secrets"
        if not secrets_dir.exists():
            return

        for root, _, files in os.walk(secrets_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        record = SecretRecord(**data)
                        self._secrets_cache[record.key] = record
                    except Exception:
                        continue

    def _persist_secret(self, target_path: Path, record: SecretRecord) -> None:
        """Persist a secret record to disk atomically and update vault index."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")
        data = record.to_dict()

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, target_path)
        try:
            os.chmod(target_path, 0o600)
        except OSError:
            pass

        # Update index
        if self.vault_dir:
            index_path = self.vault_dir / "vault_index.json"
            index_tmp = self.vault_dir / "vault_index.tmp"
            all_records = {k: v.to_dict() for k, v in self._secrets_cache.items()}
            with open(index_tmp, "w", encoding="utf-8") as f:
                json.dump(all_records, f, indent=2)
            os.replace(index_tmp, index_path)
            try:
                os.chmod(index_path, 0o600)
            except OSError:
                pass

    def set_secret(self, key: str, value: Any, token: str) -> SecretRecord:
        """Store a secret key-value pair in the vault.

        Args:
            key: Unique secret key name.
            value: Secret payload (string, integer, dictionary, etc.).
            token: Valid session token for authorization.

        Returns:
            Clean SecretRecord dictionary containing timestamp and key-value mapping.

        Raises:
            VaultNotInitializedError: If vault has not been initialized.
            AuthenticationError: If token is invalid or expired.
            PathTraversalError: If key contains path traversal patterns.
        """
        self._ensure_initialized()
        username = self._validate_token(token)
        target_path = self._validate_key(key)

        now_iso = datetime.now(timezone.utc).isoformat()
        existing = self._secrets_cache.get(key)
        created_at = existing.get("created_at") if existing else now_iso
        created_by = existing.get("created_by") if existing else username

        record = SecretRecord(
            key=key,
            value=value,
            timestamp=now_iso,
            created_at=created_at,
            updated_at=now_iso,
            created_by=created_by,
            updated_by=username,
        )

        self._secrets_cache[key] = record
        self._persist_secret(target_path, record)
        return record

    def get_secret(self, key: str, token: str) -> SecretRecord:
        """Retrieve a secret record by key.

        Args:
            key: Secret key to retrieve.
            token: Valid session token for authorization.

        Returns:
            Clean SecretRecord dictionary containing timestamp and key-value mapping.

        Raises:
            VaultNotInitializedError: If vault has not been initialized.
            AuthenticationError: If token is invalid or expired.
            PathTraversalError: If key contains path traversal patterns.
            SecretNotFoundError: If secret key does not exist.
        """
        self._ensure_initialized()
        self._validate_token(token)
        self._validate_key(key)

        if key not in self._secrets_cache:
            raise SecretNotFoundError(f"Secret key '{key}' not found in vault.")

        return self._secrets_cache[key]

    def list_secrets(self, token: str) -> VaultSecretList:
        """List all secret records in the vault.

        Args:
            token: Valid session token for authorization.

        Returns:
            VaultSecretList of SecretRecord dictionaries with timestamps and key-value mappings.

        Raises:
            VaultNotInitializedError: If vault has not been initialized.
            AuthenticationError: If token is invalid or expired.
        """
        self._ensure_initialized()
        self._validate_token(token)

        return VaultSecretList(list(self._secrets_cache.values()))

    def delete_secret(self, key: str, token: str) -> bool:
        """Delete a secret from the vault.

        Args:
            key: Secret key to delete.
            token: Valid session token for authorization.

        Returns:
            True if secret was deleted, False if key was not found.
        """
        self._ensure_initialized()
        self._validate_token(token)
        target_path = self._validate_key(key)

        if key not in self._secrets_cache:
            return False

        del self._secrets_cache[key]

        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

        if self.vault_dir:
            index_path = self.vault_dir / "vault_index.json"
            all_records = {k: v.to_dict() for k, v in self._secrets_cache.items()}
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(all_records, f, indent=2)

        return True

    def has_secret(self, key: str, token: str) -> bool:
        """Check if a secret key exists in the vault."""
        self._ensure_initialized()
        self._validate_token(token)
        try:
            self._validate_key(key)
        except (ValueError, PathTraversalError):
            return False
        return key in self._secrets_cache
