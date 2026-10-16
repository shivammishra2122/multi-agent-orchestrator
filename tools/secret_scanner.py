#!/usr/bin/env python3
"""
Lightweight Secret and Credential Scanner
Scans source code and configurations for unmasked secrets, private keys, and API tokens.
"""

import os
import re
import sys
from typing import List, Dict, Any

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "High-entropy API/Secret Key", "HIGH"),
    (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "Exposed Private Key Block", "CRITICAL"),
    (r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS Secret Access Key", "CRITICAL"),
    (r"(?i)ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token", "CRITICAL"),
    (r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]", "Hardcoded Plaintext Password", "HIGH"),
]

IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", "venv", ".agents"}
IGNORED_FILES = {"secret_scanner.py", "sast_scanner.py"}

def scan_file(filepath: str) -> List[Dict[str, Any]]:
    findings = []
    basename = os.path.basename(filepath)
    if basename in IGNORED_FILES or filepath.endswith(".md"):
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []

    for idx, line in enumerate(lines, start=1):
        # Ignore comments explaining regex or test patterns
        if "test_mock" in line or "dummy_sample" in line:
            continue
        for pattern, desc, severity in SECRET_PATTERNS:
            match = re.search(pattern, line)
            if match:
                # Mask secret
                matched_str = match.group(0)
                masked = matched_str[:8] + "..." + matched_str[-4:] if len(matched_str) > 12 else "[REDACTED]"
                findings.append({
                    "file": filepath,
                    "line": idx,
                    "severity": severity,
                    "type": desc,
                    "evidence": masked
                })
    return findings

def scan_directory(target_dir: str) -> List[Dict[str, Any]]:
    findings = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            path = os.path.join(root, file)
            findings.extend(scan_file(path))
    return findings

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"=== Secret & Credential Scanner: Target '{target}' ===")
    findings = scan_directory(target) if os.path.isdir(target) else scan_file(target)

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")

    print(f"Secret scan complete. Found {len(findings)} issues.")
    for f in findings:
        print(f"[{f['severity']}] {f['file']}:{f['line']} - {f['type']} (Evidence: {f['evidence']})")

    if critical_count > 0 or high_count > 0:
        print("[!] SECRET SCAN FAILED: Sensitive credentials detected in codebase.")
        sys.exit(1)
    else:
        print("[+] SECRET SCAN PASSED: No unmasked secrets found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
