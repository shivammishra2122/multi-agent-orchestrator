"""
Configuration Management for SecureVault.

Provides the VaultConfig dataclass and load_config() function to manage
environment-driven configuration with validation and safe defaults.
"""

from dataclasses import dataclass
import os
from typing import Any, Dict, Optional, Set

DEFAULT_VAULT_DIR: str = os.path.expanduser("~/.securevault")
DEFAULT_TOKEN_EXPIRY: int = 3600
DEFAULT_LOG_LEVEL: str = "INFO"

VALID_LOG_LEVELS: Set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass
class VaultConfig:
    """
    Configuration settings for SecureVault runtime.

    Attributes:
        vault_dir: Absolute path to the secure vault storage directory.
        token_expiry: Lifetime of issued session tokens in seconds (must be positive).
        log_level: Logging severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """

    vault_dir: str = DEFAULT_VAULT_DIR
    token_expiry: int = DEFAULT_TOKEN_EXPIRY
    log_level: str = DEFAULT_LOG_LEVEL

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validates configuration parameters and normalizes paths and strings."""
        # 1. Validate vault_dir
        if not isinstance(self.vault_dir, str):
            raise ValueError(f"Vault directory must be a string, got {type(self.vault_dir).__name__}.")

        stripped_dir = self.vault_dir.strip()
        if not stripped_dir:
            raise ValueError("Vault directory path cannot be empty.")

        self.vault_dir = os.path.abspath(os.path.expanduser(stripped_dir))

        # 2. Validate token_expiry
        if isinstance(self.token_expiry, bool) or not isinstance(self.token_expiry, int):
            try:
                self.token_expiry = int(self.token_expiry)
            except (ValueError, TypeError):
                raise ValueError(f"Token expiry must be a valid integer, got {self.token_expiry!r}.")

        if self.token_expiry <= 0:
            raise ValueError(f"Token expiry must be a positive integer, got {self.token_expiry}.")

        # 3. Validate log_level
        if not isinstance(self.log_level, str):
            raise ValueError(f"Log level must be a string, got {type(self.log_level).__name__}.")

        normalized_level = self.log_level.strip().upper()
        if normalized_level == "WARN":
            normalized_level = "WARNING"

        if normalized_level not in VALID_LOG_LEVELS:
            sorted_levels = ", ".join(sorted(VALID_LOG_LEVELS))
            raise ValueError(f"Invalid log level '{self.log_level}'. Must be one of: {sorted_levels}.")

        self.log_level = normalized_level


def load_config(
    vault_dir: Optional[str] = None,
    token_expiry: Optional[int] = None,
    log_level: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> VaultConfig:
    """
    Loads SecureVault configuration from environment variables and explicit overrides.

    Precedence:
      Explicit parameter > Environment variable > Safe default

    Environment Variables:
      VAULT_DIR: Path to storage directory (default: ~/.securevault)
      VAULT_TOKEN_EXPIRY: Session token expiry in seconds (default: 3600)
      VAULT_LOG_LEVEL: Logging level (default: INFO)

    Args:
        vault_dir: Optional override for vault directory path.
        token_expiry: Optional override for session token expiry in seconds.
        log_level: Optional override for logging severity level.
        env: Optional mapping to simulate environment variables (defaults to os.environ).

    Returns:
        A validated VaultConfig instance.

    Raises:
        ValueError: If any configuration value is invalid.
    """
    source_env = os.environ if env is None else env

    # Resolve vault_dir
    resolved_dir: str
    if vault_dir is not None:
        resolved_dir = vault_dir
    else:
        resolved_dir = source_env.get("VAULT_DIR", DEFAULT_VAULT_DIR)

    # Resolve token_expiry
    resolved_expiry: Any
    if token_expiry is not None:
        try:
            resolved_expiry = int(token_expiry)
        except (ValueError, TypeError):
            raise ValueError(f"Token expiry must be an integer, got {token_expiry!r}.")
    else:
        env_expiry = source_env.get("VAULT_TOKEN_EXPIRY")
        if env_expiry is not None:
            try:
                resolved_expiry = int(env_expiry)
            except (ValueError, TypeError):
                raise ValueError(f"VAULT_TOKEN_EXPIRY environment variable must be an integer, got {env_expiry!r}.")
        else:
            resolved_expiry = DEFAULT_TOKEN_EXPIRY

    # Resolve log_level
    resolved_log_level: str
    if log_level is not None:
        resolved_log_level = log_level
    else:
        resolved_log_level = source_env.get("VAULT_LOG_LEVEL", DEFAULT_LOG_LEVEL)

    return VaultConfig(
        vault_dir=resolved_dir,
        token_expiry=resolved_expiry,
        log_level=resolved_log_level,
    )
