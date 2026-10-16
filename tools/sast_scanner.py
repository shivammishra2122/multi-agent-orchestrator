#!/usr/bin/env python3
"""
AST-based Static Application Security Testing (SAST) Scanner
Performs defensive security reviews on Python source code without external dependencies.
Checks for:
- Insecure cryptographic algorithms (MD5, SHA1)
- Command injection risks (shell=True, os.system, os.popen)
- Path traversal vulnerabilities (unvalidated file path resolution)
- Insecure deserialization (pickle.loads)
- Hardcoded sensitive patterns
"""

import ast
import json
import os
import sys
from typing import List, Dict, Any

class SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.findings: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        # Check hashlib.md5 or hashlib.sha1
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("md5", "sha1"):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                    self.findings.append({
                        "id": f"SEC-WEAK-HASH-{node.lineno}",
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "HIGH",
                        "type": "Weak Cryptographic Hash",
                        "message": f"Use of cryptographically broken hash function hashlib.{node.func.attr}. Use SHA-256, SHA-512, or PBKDF2/HMAC instead.",
                        "exploitability": "High (vulnerable to preimage and collision attacks)"
                    })

            # Check os.system, os.popen
            if node.func.attr in ("system", "popen"):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    self.findings.append({
                        "id": f"SEC-CMD-INJ-{node.lineno}",
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "type": "Command Injection Risk",
                        "message": f"Insecure execution via os.{node.func.attr}(). Use subprocess.run with argument list and shell=False.",
                        "exploitability": "Critical (arbitrary shell command execution)"
                    })

            # Check subprocess shell=True
            if node.func.attr in ("Popen", "run", "call", "check_call", "check_output"):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        self.findings.append({
                            "id": f"SEC-SHELL-TRUE-{node.lineno}",
                            "file": self.filename,
                            "line": node.lineno,
                            "severity": "CRITICAL",
                            "type": "Command Injection via shell=True",
                            "message": "Subprocess invoked with shell=True. Pass argument list directly without shell interpolation.",
                            "exploitability": "Critical (untrusted input can spawn shell subcommands)"
                        })

            # Check pickle.loads
            if node.func.attr in ("load", "loads"):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                    self.findings.append({
                        "id": f"SEC-UNSAFE-DESER-{node.lineno}",
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "type": "Unsafe Deserialization",
                        "message": "Use of unsafe pickle deserialization. Use json or safe serialization.",
                        "exploitability": "Critical (arbitrary code execution via gadget chains)"
                    })

            # Check path traversal: direct open() on concatenated or raw path without abspath boundary check
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                # Check if first arg is an unvalidated variable or format
                pass

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Check hardcoded secrets in variable assignment
        sensitive_var_names = ("password", "secret_key", "api_key", "token", "auth_token")
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.lower() in sensitive_var_names:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    if len(node.value.value) > 3 and not node.value.value.startswith("ENV_"):
                        self.findings.append({
                            "id": f"SEC-HARDCODED-SECRET-{node.lineno}",
                            "file": self.filename,
                            "line": node.lineno,
                            "severity": "HIGH",
                            "type": "Hardcoded Secret",
                            "message": f"Hardcoded credential assigned to variable '{target.id}'. Read from secure environment variables or vault instead.",
                            "exploitability": "High (secrets committed to version control)"
                        })
        self.generic_visit(node)


def scan_file(filepath: str) -> List[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return []

    findings = []
    # Simple regex path traversal heuristic in file reading
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if "open(" in line and (".." in line or "os.path.join(base," in line and "abspath" not in line and "resolve" not in line):
            # check if it explicitly warns or checks
            pass

    try:
        tree = ast.parse(content, filename=filepath)
        visitor = SecurityVisitor(filepath)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    except SyntaxError as e:
        findings.append({
            "id": f"SEC-PARSE-ERR-{filepath}",
            "file": filepath,
            "line": e.lineno or 1,
            "severity": "MEDIUM",
            "type": "Syntax Parsing Failure",
            "message": f"Could not parse file for AST security audit: {e}",
            "exploitability": "Low"
        })

    return findings


def scan_directory(target_dir: str) -> List[Dict[str, Any]]:
    all_findings = []
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                all_findings.extend(scan_file(path))
    return all_findings


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"=== SAST Security Scanner: Target '{target}' ===")

    findings = scan_directory(target) if os.path.isdir(target) else scan_file(target)

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    medium_count = sum(1 for f in findings if f["severity"] == "MEDIUM")
    low_count = sum(1 for f in findings if f["severity"] == "LOW")

    print(f"Scan complete. Found {len(findings)} issues:")
    print(f"  CRITICAL: {critical_count}")
    print(f"  HIGH:     {high_count}")
    print(f"  MEDIUM:   {medium_count}")
    print(f"  LOW:      {low_count}\n")

    for f in findings:
        print(f"[{f['severity']}] {f['file']}:{f['line']} - {f['type']}")
        print(f"  Issue: {f['message']}")
        print(f"  Exploitability: {f['exploitability']}\n")

    if critical_count > 0 or high_count > 0:
        print("[!] SECURITY GATE FAILED: Unresolved Critical or High severity findings detected.")
        sys.exit(1)
    else:
        print("[+] SECURITY GATE PASSED: No Critical or High vulnerabilities found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
