# Agent Findings & Code Review Log

## 1. QA Defect Reports & Test Execution Summary

### Test Execution Overview
- **Command**: `python3 -m unittest discover -s tests -v`
- **Total Tests Executed**: 65
- **Execution Time**: ~2.74s
- **QA Suites Status**: **59 / 59 PASSED (100%)**
- **Security Regression Suite Status**: 2 PASSED, 4 FAILED (Awaiting TASK-006 Developer Remediation)

### Suite Breakdown
| Test Suite File | Tests | Passes | Failures | Status | Execution Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tests/test_auth.py` | 23 | 23 | 0 | **PASS** | UserAuthManager: registration, duplicate rejection, salted hashing, password verification, session token issuance/validation/expiry/revocation, file persistence (0600), global session registry |
| `tests/test_vault.py` | 15 | 15 | 0 | **PASS** | SecureVaultStorage: init (0700), uninitialized guard, secret storage/retrieval (0600), updating, listing, deletion, path traversal attack mitigations (`../../`, absolute paths, null bytes) |
| `tests/test_cli.py` | 7 | 7 | 0 | **PASS** | CLI subcommands: `init`, `register`, `login`, `set`, `get`, `list`, full end-to-end workflow, argument validation, and subprocess isolation |
| `tests/test_edge_cases.py` | 14 | 14 | 0 | **PASS** | Boundary conditions: empty/whitespace strings, Unicode/emoji character sets, large payloads (100KB, 1MB, 5MB), invalid/expired/revoked session tokens, structured data types |
| `tests/test_security_regressions.py` | 6 | 2 | 4 | **FAIL** | Security baseline (authored by `security_engineer`): Flags intentional weak SHA-1 hash in `src/auth.py` |

### Reproducible Security Regression Failures (Handoff to Developer for TASK-006)
- **Exact Command**: `python3 -m unittest tests/test_security_regressions.py -v`
- **Failures Detected**:
  1. `test_forbid_weak_hash_algorithms_in_auth`:
     - **Location**: `src/auth.py:150`
     - **Actual**: `hasher = hashlib.sha1()`
     - **Expected**: No usage of `sha1` or `md5`; migrate to `hashlib.pbkdf2_hmac("sha256", ...)`.
  2. `test_pbkdf2_hmac_sha256_mandated_in_auth`:
     - **Actual**: 0 occurrences of `hashlib.pbkdf2_hmac`.
     - **Expected**: Password hashing must use `hashlib.pbkdf2_hmac`.
  3. `test_pbkdf2_minimum_iteration_count`:
     - **Actual**: Iteration count not detected or < 100,000.
     - **Expected**: Iteration count >= 100,000 per NIST/OWASP standards.
  4. `test_runtime_hash_algorithm_not_sha1_or_md5`:
     - **Actual**: Runtime digest matches single-pass salted SHA-1 `63f0767829ce2ad9b4c86e6fba909c313db9a51a`.
     - **Expected**: PBKDF2-HMAC-SHA256 digest output.

### Anti-Mocking Integrity Verification
- All test suites strictly exercise genuine system behavior without tautological stubs or mock bypasses.
- Filesystem I/O, atomic file replacements, directory permission checks (0700/0600), crypto hashing, and subprocess CLI execution are performed against real temporary directories.


---

## 2. Independent Code Review Findings
*Reviewed by: Independent Code Reviewer (`code_reviewer`)*
*Status: CHANGES REQUIRED (Hard Gate Blocker)*

### Priority Findings Summary

| Issue ID | Severity | File & Line | Category | Description | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SEC-001` | **CRITICAL** | `src/auth.py:150` | Cryptography | Single-round SHA-1 hash (`hashlib.sha1`) used for credentials. Fails SAST gate. | Migrate to PBKDF2-HMAC-SHA256 with 100,000+ iterations. |
| `SEC-002` | **HIGH** | `src/vault.py:338` | Security / Architecture | Secrets stored in plaintext JSON without encryption or tamper-evident HMAC. | Implement authenticated PBKDF2/HMAC encryption & tamper detection. |
| `BUG-001` | **HIGH** | `src/vault.py:56` | Correctness | `SecretRecord` key/value collision on reserved metadata names (`timestamp`, `value`). | Separate payload dict from envelope metadata. |
| `BUG-002` | **HIGH** | `src/cli.py:131` | Error Handling | `_dispatch_call` retries 7 times catching generic `TypeError`, masking real bugs. | Standardize backend signatures and call directly without guesswork retries. |
| `SEC-003` | **MEDIUM** | `src/cli.py:418` | Security | Passwords and tokens passed as raw CLI arguments, exposing them in process tables. | Support stdin / environment variables / getpass input. |
| `BUG-003` | **MEDIUM** | `src/config.py:50` | Validation | `isinstance(True, int)` causes `token_expiry=True` to coerce to 1 second. | Explicitly reject `bool` types before integer checks. |
