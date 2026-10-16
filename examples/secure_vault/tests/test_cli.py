"""Independent Unit and Integration Tests for the SecureVault CLI.

Tests CLI subcommands (init, register, login, set, get, list) end-to-end,
verifying argument parsing, stdout/stderr streams, exit codes, and error states.
All tests exercise real CLI and backend execution without mocks.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.auth import UserAuthManager
from src.cli import main


class TestSecureVaultCLIEndToEnd(unittest.TestCase):
    """Tests CLI subcommands via direct entrypoint invocation with stream capture."""

    def setUp(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_dir = str(Path(self.temp_dir.name) / "cli_vault")

    def tearDown(self) -> None:
        UserAuthManager.clear_global_sessions()
        UserAuthManager.clear_global_users()
        self.temp_dir.cleanup()

    def _run_cli(self, args: list) -> tuple:
        """Helper to invoke CLI main() while capturing stdout and stderr."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                exit_code = main(args)
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_cli_init_subcommand(self) -> None:
        """Verify 'init' creates vault directory and reports success."""
        code, out, err = self._run_cli(["init", "--vault-dir", self.vault_dir])
        self.assertEqual(code, 0)
        self.assertIn("Initialized SecureVault storage", out)
        self.assertTrue(os.path.isdir(self.vault_dir))
        self.assertTrue(os.path.isdir(os.path.join(self.vault_dir, "secrets")))

    def test_cli_register_and_duplicate(self) -> None:
        """Verify 'register' creates user, and duplicate registration fails."""
        self._run_cli(["init", "--vault-dir", self.vault_dir])

        # Initial registration
        code, out, err = self._run_cli([
            "register",
            "-u", "cli_alice",
            "-p", "AliceSecurePass789!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        self.assertIn("registered successfully", out)

        # Duplicate registration
        code, out, err = self._run_cli([
            "register",
            "-u", "cli_alice",
            "-p", "AliceSecurePass789!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)
        self.assertIn("already exists", err.lower())

    def test_cli_login_success_and_failure(self) -> None:
        """Verify 'login' outputs session token on valid credentials and errors on invalid."""
        self._run_cli(["init", "--vault-dir", self.vault_dir])
        self._run_cli([
            "register",
            "-u", "cli_bob",
            "-p", "BobSecretPass321!",
            "--vault-dir", self.vault_dir,
        ])

        # Valid login
        code, out, err = self._run_cli([
            "login",
            "-u", "cli_bob",
            "-p", "BobSecretPass321!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        session_id = out.strip()
        self.assertEqual(len(session_id), 48)

        # Invalid login (wrong password)
        code, out, err = self._run_cli([
            "login",
            "-u", "cli_bob",
            "-p", "WrongPassphrase999!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)
        self.assertIn("authentication failed", err.lower())

        # Invalid login (unknown user)
        code, out, err = self._run_cli([
            "login",
            "-u", "unknown_user",
            "-p", "AnyPassphrase123!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)

    def test_cli_full_workflow_end_to_end(self) -> None:
        """Verify complete workflow: init -> register -> login -> set -> list -> get."""
        # 1. Init
        code, _, _ = self._run_cli(["init", "--vault-dir", self.vault_dir])
        self.assertEqual(code, 0)

        # 2. Register
        code, _, _ = self._run_cli([
            "register",
            "-u", "dev_admin",
            "-p", "DevAdminPass555!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)

        # 3. Login
        code, out, _ = self._run_cli([
            "login",
            "-u", "dev_admin",
            "-p", "DevAdminPass555!",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        auth_session = out.strip()

        # 4. Set Secret Alpha
        code, out, _ = self._run_cli([
            "set",
            "-k", "api_key_primary",
            "-v", "sk-live-abcdef1234567890",
            "-t", auth_session,
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        self.assertIn("stored successfully", out)

        # 5. Set Secret Beta
        code, out, _ = self._run_cli([
            "set",
            "-k", "database_pwd",
            "-v", "super_secret_db_password",
            "-t", auth_session,
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)

        # 6. List Secrets
        code, out, _ = self._run_cli([
            "list",
            "-t", auth_session,
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        listed_keys = [line.strip() for line in out.splitlines() if line.strip()]
        self.assertIn("api_key_primary", listed_keys)
        self.assertIn("database_pwd", listed_keys)

        # 7. Get Secret Alpha
        code, out, _ = self._run_cli([
            "get",
            "-k", "api_key_primary",
            "-t", auth_session,
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "sk-live-abcdef1234567890")

        # 8. Get Non-existent Secret
        code, out, err = self._run_cli([
            "get",
            "-k", "missing_key",
            "-t", auth_session,
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)
        self.assertIn("not found", err.lower())

    def test_cli_set_and_get_with_invalid_token(self) -> None:
        """Verify set, get, and list fail when an invalid token is supplied."""
        self._run_cli(["init", "--vault-dir", self.vault_dir])

        code, out, err = self._run_cli([
            "set",
            "-k", "test_key",
            "-v", "test_val",
            "-t", "invalid_bogus_token",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)
        self.assertIn("authentication failed", err.lower())

        code, out, err = self._run_cli([
            "get",
            "-k", "test_key",
            "-t", "invalid_bogus_token",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)

        code, out, err = self._run_cli([
            "list",
            "-t", "invalid_bogus_token",
            "--vault-dir", self.vault_dir,
        ])
        self.assertEqual(code, 1)

    def test_cli_argument_parsing_errors(self) -> None:
        """Verify CLI error handling on missing subcommands or arguments."""
        # No arguments
        code, out, err = self._run_cli([])
        self.assertEqual(code, 1)

        # Missing required flags
        code, out, err = self._run_cli(["register", "-u", "missing_password"])
        self.assertNotEqual(code, 0)

        # Unknown subcommand
        code, out, err = self._run_cli(["unknown_cmd"])
        self.assertNotEqual(code, 0)


class TestSecureVaultCLIProcess(unittest.TestCase):
    """Tests CLI execution via true external subprocess invocation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_dir = str(Path(self.temp_dir.name) / "subproc_vault")
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_subprocess_cli_workflow(self) -> None:
        """Verify full CLI flow executed as independent python subprocesses."""
        env = os.environ.copy()
        env["PYTHONPATH"] = self.repo_root

        # 1. Init
        init_res = subprocess.run(
            [sys.executable, "-m", "src.cli", "init", "--vault-dir", self.vault_dir],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=env,
        )
        self.assertEqual(init_res.returncode, 0)

        # 2. Register
        reg_res = subprocess.run(
            [sys.executable, "-m", "src.cli", "register", "-u", "proc_user", "-p", "ProcPass123!", "--vault-dir", self.vault_dir],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=env,
        )
        self.assertEqual(reg_res.returncode, 0)

        # 3. Login
        login_res = subprocess.run(
            [sys.executable, "-m", "src.cli", "login", "-u", "proc_user", "-p", "ProcPass123!", "--vault-dir", self.vault_dir],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=env,
        )
        self.assertEqual(login_res.returncode, 0)
        auth_tok = login_res.stdout.strip()
        self.assertEqual(len(auth_tok), 48)

        # 4. Set
        set_res = subprocess.run(
            [sys.executable, "-m", "src.cli", "set", "-k", "service_token", "-v", "subproc_secret_value", "-t", auth_tok, "--vault-dir", self.vault_dir],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=env,
        )
        self.assertEqual(set_res.returncode, 0)

        # 5. Get
        get_res = subprocess.run(
            [sys.executable, "-m", "src.cli", "get", "-k", "service_token", "-t", auth_tok, "--vault-dir", self.vault_dir],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
            env=env,
        )
        self.assertEqual(get_res.returncode, 0)
        self.assertEqual(get_res.stdout.strip(), "subproc_secret_value")


if __name__ == "__main__":
    unittest.main()
