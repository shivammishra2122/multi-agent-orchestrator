#!/usr/bin/env python3
"""Security Regression Test Suite for SecureVault.

Verifies that:
1. Password hashing uses PBKDF2-HMAC-SHA256 with at least 100,000 iterations.
2. Weak cryptographic hash algorithms (SHA-1, MD5) are strictly forbidden in authentication code.
3. Cryptographically strong salts (minimum 16 bytes / 128 bits entropy) are generated.
4. Timing attacks are mitigated via constant-time digest comparison.
"""

import ast
import hashlib
import hmac
import os
import sys
from pathlib import Path
import unittest

# Ensure repo root and src/ are in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from src.auth import UserAuthManager, InvalidCredentialsError
except ImportError:
    from auth import UserAuthManager, InvalidCredentialsError  # type: ignore


class SecurityASTVisitor(ast.NodeVisitor):
    """AST visitor to inspect cryptography usage in source code."""

    def __init__(self):
        self.disallowed_hash_calls = []
        self.pbkdf2_calls = []
        self.iteration_values = []

    def visit_Call(self, node: ast.Call):
        # Detect hashlib.sha1 or hashlib.md5
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                if node.func.attr in ("sha1", "md5", "sha224"):
                    self.disallowed_hash_calls.append({
                        "algorithm": node.func.attr,
                        "line": node.lineno
                    })
                elif node.func.attr == "pbkdf2_hmac":
                    self.pbkdf2_calls.append(node)
                    # Extract iterations argument if present
                    # signature: pbkdf2_hmac(hash_name, password, salt, iterations, dklen=None)
                    if len(node.args) >= 4 and isinstance(node.args[3], ast.Constant):
                        self.iteration_values.append(node.args[3].value)
                    for kw in node.keywords:
                        if kw.arg == "iterations" and isinstance(kw.value, ast.Constant):
                            self.iteration_values.append(kw.value.value)

        self.generic_visit(node)


class TestSecurityRegressions(unittest.TestCase):
    """Automated security regression tests enforcing SecureVault cryptography standards."""

    @classmethod
    def setUpClass(cls):
        cls.auth_py_path = SRC_DIR / "auth.py"
        with open(cls.auth_py_path, "r", encoding="utf-8") as f:
            cls.auth_source = f.read()
        cls.auth_ast = ast.parse(cls.auth_source, filename=str(cls.auth_py_path))

    def test_forbid_weak_hash_algorithms_in_auth(self):
        """Assert that weak hashing algorithms (SHA-1, MD5) are not used anywhere in auth.py."""
        visitor = SecurityASTVisitor()
        visitor.visit(self.auth_ast)
        self.assertEqual(
            visitor.disallowed_hash_calls,
            [],
            f"Vulnerability Detected: Weak hash algorithms found in auth.py: {visitor.disallowed_hash_calls}. "
            f"Migrate to PBKDF2-HMAC-SHA256."
        )

    def test_pbkdf2_hmac_sha256_mandated_in_auth(self):
        """Assert that password hashing uses PBKDF2-HMAC-SHA256."""
        visitor = SecurityASTVisitor()
        visitor.visit(self.auth_ast)
        self.assertGreater(
            len(visitor.pbkdf2_calls),
            0,
            "Security Policy Violation: hashlib.pbkdf2_hmac must be used for password hashing."
        )
        # Check that algorithm specified is 'sha256'
        pbkdf2_node = visitor.pbkdf2_calls[0]
        hash_name = None
        if pbkdf2_node.args and isinstance(pbkdf2_node.args[0], ast.Constant):
            hash_name = str(pbkdf2_node.args[0].value).lower()
        for kw in pbkdf2_node.keywords:
            if kw.arg == "hash_name" and isinstance(kw.value, ast.Constant):
                hash_name = str(kw.value.value).lower()
        if hash_name is not None:
            self.assertEqual(
                hash_name,
                "sha256",
                f"Security Policy Violation: Hash algorithm for PBKDF2 must be 'sha256', got '{hash_name}'."
            )

    def test_pbkdf2_minimum_iteration_count(self):
        """Assert that PBKDF2 uses at least 100,000 iterations per NIST/OWASP recommendations."""
        visitor = SecurityASTVisitor()
        visitor.visit(self.auth_ast)

        auth_mgr = UserAuthManager()
        iterations = getattr(auth_mgr, "pbkdf2_iterations", None) or \
                     getattr(auth_mgr, "PBKDF2_ITERATIONS", None) or \
                     getattr(auth_mgr, "iterations", None)

        if visitor.iteration_values:
            for val in visitor.iteration_values:
                self.assertGreaterEqual(
                    val,
                    100_000,
                    f"PBKDF2 iteration count too low ({val} < 100,000). Insufficient brute-force resistance."
                )
        elif iterations is not None:
            self.assertGreaterEqual(
                iterations,
                100_000,
                f"Configured iterations {iterations} < 100,000."
            )
        else:
            found_const = False
            for node in self.auth_ast.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and "ITER" in target.id.upper():
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                                self.assertGreaterEqual(
                                    node.value.value,
                                    100_000,
                                    f"Iteration constant {target.id} = {node.value.value} < 100,000."
                                )
                                found_const = True
            if not visitor.iteration_values and not found_const and iterations is None:
                self.fail(
                    "Security Policy Violation: Could not detect PBKDF2 iteration count >= 100,000 in auth.py."
                )

    def test_runtime_hash_algorithm_not_sha1_or_md5(self):
        """Assert that runtime password hashing does not produce SHA-1 or MD5 digests."""
        auth_mgr = UserAuthManager()
        salt = "0123456789abcdef"
        password = "SecurePassword123!"  # dummy_sample

        computed_hash = auth_mgr._hash_password(password, salt)

        # Verify not SHA-1 (40 hex characters)
        sha1_candidate = hashlib.sha1(salt.encode("utf-8") + password.encode("utf-8")).hexdigest()
        self.assertNotEqual(
            computed_hash,
            sha1_candidate,
            "Security Regression: Password hash matches single-pass salted SHA-1!"
        )
        # Verify not MD5 (32 hex characters)
        md5_candidate = hashlib.md5(salt.encode("utf-8") + password.encode("utf-8")).hexdigest()
        self.assertNotEqual(
            computed_hash,
            md5_candidate,
            "Security Regression: Password hash matches single-pass salted MD5!"
        )

        # Output must be at least 256 bits (64 hex characters for SHA-256)
        self.assertGreaterEqual(
            len(computed_hash),
            64,
            f"Password digest length ({len(computed_hash)} hex chars) is too short. Expected >= 64 hex chars (SHA-256)."
        )

    def test_salt_randomness_and_length(self):
        """Assert that registered users receive cryptographically secure salts of at least 16 bytes."""
        auth_mgr = UserAuthManager()
        UserAuthManager.clear_global_users()
        auth_mgr.register_user("sec_user_1", "SecretPass!1")
        auth_mgr.register_user("sec_user_2", "SecretPass!2")

        user1 = auth_mgr.users.get("sec_user_1")
        user2 = auth_mgr.users.get("sec_user_2")

        self.assertIsNotNone(user1)
        self.assertIsNotNone(user2)

        salt1 = user1.get("salt")
        salt2 = user2.get("salt")

        # Salts must not be identical (uniqueness)
        self.assertNotEqual(salt1, salt2, "Salts must be unique per user registration.")
        # Salt must be at least 16 bytes (32 hex chars)
        self.assertGreaterEqual(
            len(salt1),
            32,
            f"Salt length ({len(salt1)} chars) provides insufficient entropy. Expected >= 32 hex chars (16 bytes)."
        )

    def test_timing_attack_resistance_in_verify(self):
        """Assert that password verification uses constant-time comparison."""
        self.assertIn(
            "compare_digest",
            self.auth_source,
            "Security Policy Violation: auth.py must use hmac.compare_digest to prevent timing attacks."
        )


if __name__ == "__main__":
    unittest.main()
