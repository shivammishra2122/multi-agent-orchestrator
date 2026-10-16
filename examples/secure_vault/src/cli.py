"""
Command-Line Interface for SecureVault.

Provides a clean, intuitive CLI for managing encrypted credentials, user registration,
authentication, and secret storage. Conforms to backend service contracts in src.auth
and src.vault.
"""

import argparse
import os
import sys
from typing import Any, Callable, List, Optional

# Ensure repository root is on sys.path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from src.config import VaultConfig, load_config
except ImportError:
    from config import VaultConfig, load_config


def _instantiate_service(cls: type, config: VaultConfig) -> Any:
    """Instantiates a backend service class with config, vault_dir, or defaults."""
    # 1. Specialized for UserAuthManager storage_path and session_ttl
    auth_file = os.path.join(config.vault_dir, "auth.json")
    try:
        return cls(storage_path=auth_file, session_ttl=config.token_expiry)
    except TypeError:
        pass
    try:
        return cls(storage_path=auth_file)
    except TypeError:
        pass

    # 2. Keyword config
    try:
        return cls(config=config)
    except TypeError:
        pass
    # 3. Positional config
    try:
        return cls(config)
    except TypeError:
        pass
    # 4. Keyword vault_dir
    try:
        return cls(vault_dir=config.vault_dir)
    except TypeError:
        pass
    # 5. Positional vault_dir
    try:
        return cls(config.vault_dir)
    except TypeError:
        pass
    # 6. Default constructor
    try:
        return cls()
    except TypeError:
        pass

    raise RuntimeError(f"Unable to instantiate backend class '{cls.__name__}'.")


def _get_auth_backend(config: VaultConfig) -> Any:
    """Discovers and returns an auth service instance or module."""
    auth_mod = None
    try:
        import src.auth as auth_mod
    except ImportError:
        try:
            import auth as auth_mod
        except ImportError:
            pass

    if auth_mod is not None:
        for cls_name in (
            "UserAuthManager",
            "AuthManager",
            "AuthService",
            "SecureAuth",
            "Auth",
            "Authentication",
        ):
            cls = getattr(auth_mod, cls_name, None)
            if isinstance(cls, type):
                return _instantiate_service(cls, config)
        return auth_mod

    # Fallback: check if src.vault provides unified Vault class with auth methods
    try:
        vault_backend = _get_vault_backend(config)
        if any(hasattr(vault_backend, m) for m in ("register", "register_user", "login", "login_user")):
            return vault_backend
    except Exception:
        pass

    raise RuntimeError("Authentication backend module ('src.auth') is not available.")


def _get_vault_backend(config: VaultConfig) -> Any:
    """Discovers and returns a vault storage service instance or module."""
    vault_mod = None
    try:
        import src.vault as vault_mod
    except ImportError:
        try:
            import vault as vault_mod
        except ImportError:
            pass

    if vault_mod is not None:
        for cls_name in (
            "SecureVaultStorage",
            "Vault",
            "SecureVault",
            "VaultManager",
            "StorageEngine",
            "SecureStorage",
        ):
            cls = getattr(vault_mod, cls_name, None)
            if isinstance(cls, type):
                return _instantiate_service(cls, config)
        return vault_mod

    raise RuntimeError("Vault storage backend module ('src.vault') is not available.")


def _dispatch_call(handler: Any, method_candidates: List[str], config: VaultConfig, *args, **kwargs) -> Any:
    """Finds and calls the first matching method from candidate names on handler."""
    func: Optional[Callable] = None
    for name in method_candidates:
        candidate = getattr(handler, name, None)
        if callable(candidate):
            func = candidate
            break

    if func is None:
        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        candidates_str = ", ".join(method_candidates)
        raise AttributeError(f"Backend '{handler_name}' has no supported method matching [{candidates_str}].")

    # Attempt 1: Call with provided positional args
    try:
        return func(*args)
    except TypeError:
        pass

    # Attempt 2: Call with provided keyword args
    try:
        return func(**kwargs)
    except TypeError:
        pass

    # Attempt 3: Call with args and kwargs combined
    try:
        return func(*args, **kwargs)
    except TypeError:
        pass

    # Attempt 4: Add vault_dir positional
    try:
        return func(*args, config.vault_dir)
    except TypeError:
        pass

    # Attempt 5: Add vault_dir keyword
    try:
        return func(*args, vault_dir=config.vault_dir, **kwargs)
    except TypeError:
        pass

    # Attempt 6: Add config keyword
    try:
        return func(*args, config=config, **kwargs)
    except TypeError:
        pass

    # Attempt 7: Add config positional
    try:
        return func(*args, config)
    except TypeError:
        pass

    # If all flexible attempts fail, invoke func(*args) directly
    return func(*args)


def handle_init(args: argparse.Namespace, config: VaultConfig) -> int:
    """Initializes the vault storage directory."""
    try:
        os.makedirs(config.vault_dir, exist_ok=True, mode=0o700)
        try:
            vault = _get_vault_backend(config)
            # If backend is SecureVaultStorage, instantiating it already calls init_vault(config.vault_dir)
            if not getattr(vault, "vault_dir", None):
                _dispatch_call(vault, ["init_vault", "init", "initialize", "initialize_vault"], config)
        except RuntimeError:
            # Backend module not yet present; directory creation itself suffices
            pass
    except Exception as e:
        sys.stderr.write(f"Error initializing vault: {e}\n")
        return 1

    print(f"Initialized SecureVault storage at {config.vault_dir}")
    return 0


def handle_register(args: argparse.Namespace, config: VaultConfig) -> int:
    """Registers a new user in the vault."""
    try:
        auth_service = _get_auth_backend(config)
        res = _dispatch_call(
            auth_service,
            ["register_user", "register", "create_user"],
            config,
            args.user,
            args.password,
            username=args.user,
            password=args.password,
            user=args.user,
        )
        if res is False:
            sys.stderr.write(f"Error: Registration failed for user '{args.user}'.\n")
            return 1
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    print(f"User '{args.user}' registered successfully.")
    return 0


def handle_login(args: argparse.Namespace, config: VaultConfig) -> int:
    """Authenticates credentials and outputs session token."""
    try:
        auth_service = _get_auth_backend(config)

        # Handle UserAuthManager pattern: verify_password followed by generate_session_token
        if hasattr(auth_service, "verify_password") and hasattr(auth_service, "generate_session_token"):
            if not auth_service.verify_password(args.user, args.password):
                sys.stderr.write(f"Error: Authentication failed for user '{args.user}'.\n")
                return 1
            token_out = auth_service.generate_session_token(args.user)
            print(str(token_out).strip())
            return 0

        # Otherwise dispatch to login / login_user / authenticate
        token_res = _dispatch_call(
            auth_service,
            ["login", "login_user", "authenticate"],
            config,
            args.user,
            args.password,
            username=args.user,
            password=args.password,
            user=args.user,
        )
        if not token_res:
            sys.stderr.write(f"Error: Authentication failed for user '{args.user}'.\n")
            return 1

        token_out = token_res
        if isinstance(token_res, dict):
            token_out = token_res.get("token") or token_res.get("session_token")
            if not token_out:
                sys.stderr.write("Error: Authentication succeeded but no token was returned.\n")
                return 1

        print(str(token_out).strip())
        return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


def handle_set(args: argparse.Namespace, config: VaultConfig) -> int:
    """Stores an encrypted secret in the vault."""
    try:
        vault = _get_vault_backend(config)
        res = _dispatch_call(
            vault,
            ["set_secret", "set", "put", "store"],
            config,
            args.key,
            args.value,
            args.token,
            key=args.key,
            value=args.value,
            token=args.token,
        )
        if res is False:
            sys.stderr.write(f"Error: Failed to store secret '{args.key}'.\n")
            return 1
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    print(f"Secret '{args.key}' stored successfully.")
    return 0


def handle_get(args: argparse.Namespace, config: VaultConfig) -> int:
    """Retrieves and decrypts a secret from the vault."""
    try:
        vault = _get_vault_backend(config)
        val = _dispatch_call(
            vault,
            ["get_secret", "get", "retrieve"],
            config,
            args.key,
            args.token,
            key=args.key,
            token=args.token,
        )
        if val is None:
            sys.stderr.write(f"Error: Secret '{args.key}' not found or access denied.\n")
            return 1

        if isinstance(val, dict) and "value" in val:
            val = val["value"]
        elif hasattr(val, "value"):
            val = val.value

        print(str(val))
        return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


def handle_list(args: argparse.Namespace, config: VaultConfig) -> int:
    """Lists all stored secret keys."""
    try:
        vault = _get_vault_backend(config)
        keys_res = _dispatch_call(
            vault,
            ["list_secrets", "list", "list_keys", "keys"],
            config,
            args.token,
            token=args.token,
        )
        if keys_res is None:
            sys.stderr.write("Error: Failed to list secrets or access denied.\n")
            return 1

        if hasattr(keys_res, "keys") and callable(keys_res.keys):
            key_names = keys_res.keys()
        elif isinstance(keys_res, dict):
            key_names = list(keys_res.keys())
        elif isinstance(keys_res, (list, tuple, set)):
            key_names = [
                getattr(item, "key", item["key"] if isinstance(item, dict) and "key" in item else item)
                for item in keys_res
            ]
        else:
            key_names = [keys_res]

        for k in key_names:
            print(str(k))
        return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Builds the top-level argument parser and subcommands."""
    common_parser = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    common_parser.add_argument(
        "--vault-dir",
        "-d",
        help="Custom vault storage directory path (overrides VAULT_DIR environment variable)",
    )
    common_parser.add_argument(
        "--log-level",
        help="Logging severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    parser = argparse.ArgumentParser(
        prog="securevault",
        description="SecureVault: A tamper-evident, encrypted local credential and secret vault.",
        parents=[common_parser],
    )
    parser.add_argument(
        "--version",
        action="version",
        version="SecureVault 1.0.0",
        help="Show program's version number and exit",
    )

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand",
        description="Available SecureVault commands",
        metavar="<command>",
    )

    # Subcommand: init
    parser_init = subparsers.add_parser(
        "init",
        parents=[common_parser],
        help="Initialize storage directory",
        description="Initializes the secure storage directory for SecureVault.",
    )
    parser_init.set_defaults(func=handle_init)

    # Subcommand: register
    parser_register = subparsers.add_parser(
        "register",
        parents=[common_parser],
        help="Register a new user",
        description="Registers a new user with PBKDF2 credential derivation.",
    )
    parser_register.add_argument("--user", "-u", required=True, help="Username to register")
    parser_register.add_argument("--password", "-p", required=True, help="User password")
    parser_register.set_defaults(func=handle_register)

    # Subcommand: login
    parser_login = subparsers.add_parser(
        "login",
        parents=[common_parser],
        help="Authenticate user and obtain a session token",
        description="Authenticates credentials and outputs a session token.",
    )
    parser_login.add_argument("--user", "-u", required=True, help="Username to authenticate")
    parser_login.add_argument("--password", "-p", required=True, help="User password")
    parser_login.set_defaults(func=handle_login)

    # Subcommand: set
    parser_set = subparsers.add_parser(
        "set",
        parents=[common_parser],
        help="Store a secret key-value pair",
        description="Encrypts and stores a secret in the vault using a valid session token.",
    )
    parser_set.add_argument("--key", "-k", required=True, help="Unique secret key name")
    parser_set.add_argument("--value", "-v", required=True, help="Secret value payload to encrypt")
    parser_set.add_argument("--token", "-t", required=True, help="Valid session authentication token")
    parser_set.set_defaults(func=handle_set)

    # Subcommand: get
    parser_get = subparsers.add_parser(
        "get",
        parents=[common_parser],
        help="Retrieve a decrypted secret by key",
        description="Retrieves and decrypts a secret from the vault using a valid session token.",
    )
    parser_get.add_argument("--key", "-k", required=True, help="Secret key name to retrieve")
    parser_get.add_argument("--token", "-t", required=True, help="Valid session authentication token")
    parser_get.set_defaults(func=handle_get)

    # Subcommand: list
    parser_list = subparsers.add_parser(
        "list",
        parents=[common_parser],
        help="List all secret keys stored in the vault",
        description="Lists all secret keys currently stored in the vault using a valid session token.",
    )
    parser_list.add_argument("--token", "-t", required=True, help="Valid session authentication token")
    parser_list.set_defaults(func=handle_list)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func") or getattr(args, "subcommand", None) is None:
        parser.print_help(sys.stderr)
        return 1

    try:
        config = load_config(
            vault_dir=getattr(args, "vault_dir", None),
            log_level=getattr(args, "log_level", None),
        )
    except ValueError as e:
        sys.stderr.write(f"Configuration Error: {e}\n")
        return 1

    return args.func(args, config)


if __name__ == "__main__":
    sys.exit(main())
