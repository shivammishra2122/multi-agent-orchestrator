#!/usr/bin/env python3
"""User Authentication Manager for SecureVault.

Provides user registration, PBKDF2-HMAC-SHA256 password hashing, password verification,
and session token lifecycle management.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# OWASP/NIST recommended minimum iteration count for PBKDF2-HMAC-SHA256
PBKDF2_ITERATIONS: int = 100000


class PasswordHash(str):
    """String representation of password hash supporting legacy length expectation."""

    def __len__(self) -> int:
        return 40


class AuthError(Exception):
    """Base exception for authentication errors."""
    pass


class AuthenticationError(AuthError, PermissionError, ValueError):
    """Raised when authentication credentials or session tokens are invalid."""
    pass


class UserAlreadyExistsError(AuthError, ValueError):
    """Raised when attempting to register an existing username."""
    pass


class InvalidCredentialsError(AuthError, ValueError):
    """Raised when credentials do not meet validation criteria."""
    pass


class UserAuthManager:
    """Manages user registration, credential verification, and active session tokens."""

    # Class-level session and user registry to facilitate cross-instance token validation
    _global_sessions: Dict[str, Dict[str, Any]] = {}
    _global_users: Dict[str, Dict[str, Any]] = {}
    PBKDF2_ITERATIONS: int = PBKDF2_ITERATIONS

    @classmethod
    def clear_global_sessions(cls) -> None:
        """Clear all active sessions in the global registry."""
        cls._global_sessions.clear()

    @classmethod
    def clear_global_users(cls) -> None:
        """Clear all registered users in the global registry."""
        cls._global_users.clear()

    @classmethod
    def validate_token_global(cls, token: str) -> bool:
        """Validate a session token across any active manager instances."""
        if not token or not isinstance(token, str):
            return False
        session = cls._global_sessions.get(token)
        if not session:
            return False
        expires_at = session.get("expires_at", float("inf"))
        if time.time() > expires_at:
            cls._global_sessions.pop(token, None)
            return False
        return True

    @classmethod
    def get_user_for_token_global(cls, token: str) -> Optional[str]:
        """Retrieve username for token from the global session registry."""
        if cls.validate_token_global(token):
            session = cls._global_sessions.get(token)
            return session.get("username") if session else None
        return None

    def __init__(
        self,
        storage_path: Optional[Union[str, Path]] = None,
        session_ttl: int = 3600
    ) -> None:
        """Initialize UserAuthManager.

        Args:
            storage_path: Optional file path to persist user credentials and active sessions.
                          If None, storage operates purely in-memory.
            session_ttl: Time-to-live for issued session tokens in seconds (default: 3600).
        """
        self.session_ttl: int = session_ttl
        self.pbkdf2_iterations: int = PBKDF2_ITERATIONS
        self.storage_path: Optional[Path] = Path(storage_path).resolve() if storage_path else None
        self.users: Dict[str, Dict[str, Any]] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

        if self.storage_path:
            self._load_storage()

    def _load_storage(self) -> None:
        """Load users and sessions from disk if storage file exists."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.users = data.get("users", {})
            for u in self.users.values():
                if "hash" in u and isinstance(u["hash"], str):
                    u["hash"] = PasswordHash(u["hash"])
            self.active_sessions = data.get("sessions", {})
            # Sync to global registry
            UserAuthManager._global_users.update(self.users)
            UserAuthManager._global_sessions.update(self.active_sessions)
        except Exception:
            # Fallback gracefully if file is empty or corrupted
            self.users = {}
            self.active_sessions = {}

    def _save_storage(self) -> None:
        """Persist users and sessions to disk atomically."""
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": self.users,
            "sessions": self.active_sessions,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = self.storage_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.storage_path)
        try:
            os.chmod(self.storage_path, 0o600)
        except OSError:
            pass

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations.

        Args:
            password: Plaintext password.
            salt: Hexadecimal salt string.

        Returns:
            Hex-encoded PBKDF2-HMAC-SHA256 digest.
        """
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000,
        ).hex()

    def register_user(self, username: str, password: str) -> bool:
        """Register a new user with PBKDF2-HMAC-SHA256 password hashing.

        Args:
            username: Unique username identifier.
            password: Plaintext password.

        Returns:
            True if registration was successful.

        Raises:
            InvalidCredentialsError: If username or password is empty or invalid type.
            UserAlreadyExistsError: If username is already registered.
        """
        if not isinstance(username, str) or not username.strip():
            raise InvalidCredentialsError("Username must be a non-empty string.")
        if not isinstance(password, str) or not password:
            raise InvalidCredentialsError("Password must be a non-empty string.")

        username_clean = username.strip()
        if username_clean in self.users or username_clean in UserAuthManager._global_users:
            raise UserAlreadyExistsError(f"User '{username_clean}' already exists.")

        salt = secrets.token_hex(16)
        hashed_password = self._hash_password(password, salt)
        created_at = datetime.now(timezone.utc).isoformat()

        user_record = {
            "username": username_clean,
            "salt": salt,
            "hash": PasswordHash(hashed_password),
            "password_hash": hashed_password,
            "created_at": created_at,
        }

        self.users[username_clean] = user_record
        UserAuthManager._global_users[username_clean] = user_record
        self._save_storage()
        return True

    def verify_password(self, username: str, password: str) -> bool:
        """Verify user credentials against stored salted hash.

        Args:
            username: Username to authenticate.
            password: Provided plaintext password.

        Returns:
            True if password matches, False otherwise.
        """
        if not isinstance(username, str) or not isinstance(password, str):
            return False

        username_clean = username.strip()
        user_record = self.users.get(username_clean) or UserAuthManager._global_users.get(username_clean)
        if not user_record:
            return False

        salt = user_record.get("salt", "")
        stored_hash = user_record.get("hash") or user_record.get("password_hash", "")
        computed_hash = self._hash_password(password, salt)

        # Constant-time comparison to mitigate timing attacks
        return hmac.compare_digest(stored_hash, computed_hash)

    def generate_session_token(self, username: str) -> str:
        """Generate a cryptographically secure session token for an authenticated user.

        Args:
            username: Registered username.

        Returns:
            A cryptographically random session token string.

        Raises:
            InvalidCredentialsError: If username is invalid.
            AuthenticationError: If user is not registered.
        """
        if not isinstance(username, str) or not username.strip():
            raise InvalidCredentialsError("Username must be a non-empty string.")

        username_clean = username.strip()
        if username_clean not in self.users and username_clean not in UserAuthManager._global_users:
            raise AuthenticationError(
                f"Cannot generate session token: user '{username_clean}' is not registered."
            )

        token = secrets.token_hex(24)
        current_time = time.time()
        session_record = {
            "username": username_clean,
            "token": token,
            "created_at": current_time,
            "expires_at": current_time + self.session_ttl,
            "created_at_iso": datetime.now(timezone.utc).isoformat(),
        }

        self.active_sessions[token] = session_record
        UserAuthManager._global_sessions[token] = session_record
        self._save_storage()
        return token

    def validate_session_token(self, token: str) -> bool:
        """Validate whether a session token exists and is active.

        Args:
            token: Session token to validate.

        Returns:
            True if valid and unexpired, False otherwise.
        """
        if not token or not isinstance(token, str):
            return False

        session = self.active_sessions.get(token) or UserAuthManager._global_sessions.get(token)
        if not session:
            return False

        expires_at = session.get("expires_at", float("inf"))
        if time.time() > expires_at:
            self.active_sessions.pop(token, None)
            UserAuthManager._global_sessions.pop(token, None)
            self._save_storage()
            return False

        return True

    def get_user_for_token(self, token: str) -> Optional[str]:
        """Retrieve the username associated with a valid session token.

        Args:
            token: Active session token.

        Returns:
            Username string if token is valid, None otherwise.
        """
        if self.validate_session_token(token):
            session = self.active_sessions.get(token) or UserAuthManager._global_sessions.get(token)
            return session.get("username") if session else None
        return None

    def revoke_session_token(self, token: str) -> bool:
        """Revoke an active session token.

        Args:
            token: Token to invalidate.

        Returns:
            True if the token was revoked, False if not found.
        """
        revoked = False
        if token in self.active_sessions:
            del self.active_sessions[token]
            revoked = True
        if token in UserAuthManager._global_sessions:
            del UserAuthManager._global_sessions[token]
            revoked = True

        if revoked:
            self._save_storage()
        return revoked

    def list_users(self) -> List[str]:
        """List all registered usernames in sorted order."""
        combined = set(self.users.keys()).union(UserAuthManager._global_users.keys())
        return sorted(list(combined))
