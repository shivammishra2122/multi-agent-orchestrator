# Multi-Agent Team Governance & Safety Rules

This document establishes immutable operational constraints for all agents collaborating in this workspace.

## 1. Role Boundaries & Least Privilege Permissions

| Agent Role | Allowed Write Scope | Disallowed Write Scope | Primary Artifact Owned |
| :--- | :--- | :--- | :--- |
| **Project Orchestrator** | `AGENT_PLAN.md`, `AGENT_PROGRESS.md` | Source code (`src/`), Tests (`tests/`) | `AGENT_PLAN.md`, `AGENT_PROGRESS.md` |
| **Backend Developer** | `src/auth.py`, `src/vault.py`, `src/models/` | `tests/`, CLI files, Audit reports | Handoff notes in `AGENT_PROGRESS.md` |
| **Integration Engineer** | `src/cli.py`, `src/config.py`, `scripts/` | Core backend logic, `tests/` | CLI usage documentation |
| **QA and Test Engineer** | `tests/` | Implementation code (`src/`), Reports | `AGENT_FINDINGS.md` (Test section) |
| **Security Engineer** | `tests/test_security_*.py`, `SECURITY_REPORT.md` | Implementation code (`src/`), Core tests | `SECURITY_REPORT.md` |
| **Code Reviewer** | *None* (Strictly Read-Only) | All project files | Review findings in `AGENT_FINDINGS.md` |
| **Release Auditor** | `RELEASE_READINESS.md` | Implementation code (`src/`), Tests | `RELEASE_READINESS.md` |

## 2. File Ownership & Concurrency Protection
1. **Exclusive File Ownership**: When parallel agents are dispatched, every agent is assigned a disjoint set of files. Under no circumstances may two agents edit the same file concurrently.
2. **Git Worktrees / Branches**: For risky, long-running, or experimental tasks, agents must operate on isolated git branches (`feature/*`, `qa/*`, `security/*`).
3. **No Overwrite Guarantee**: Agents must inspect existing file content before modifying and preserve unrelated user code, comments, and conventions.

## 3. Test & Verification Integrity
1. **Separation of QA and Implementation**: QA engineers must NEVER modify application source code to make tests pass. Bugs must be reported back to the Orchestrator for developer remediation.
2. **Anti-Mocking Rule**: Tests must validate actual execution behavior against live data or state machines. Tautological assertions (testing mocks against mocks) are strictly rejected.
3. **Audit Verification**: A check or test cannot be marked as passed unless the execution command ran, exited with code 0, and the actual stdout/stderr was inspected.

## 4. Security Triage & Gatekeeping
1. **Severity Classification**:
   - `CRITICAL`: Immediate remote execution, unauthenticated data exfiltration, secret leakage.
   - `HIGH`: Broken authorization, path traversal, SQL/command injection.
   - `MEDIUM`: Rate limiting gaps, missing input boundary validation, verbose error disclosures.
   - `LOW`: Informational, style, or defense-in-depth suggestions.
2. **Hard Security Gate**: Any unresolved `CRITICAL` or `HIGH` security finding automatically blocks release approval (`RELEASE_READINESS.md: NO-GO`).

## 5. Remediation Loop & Retry Policy
1. When QA or Security reports failures, the Orchestrator initiates a remediation cycle.
2. **Retry Limit**: Maximum 3 remediation attempts per task. If unresolved after 3 attempts, the task is marked `BLOCKED`, and execution pauses for human architectural review.
3. **Regression Test Requirement**: Every remediated security defect or critical bug must be accompanied by an automated regression test in `tests/test_security_regressions.py` or the relevant QA test module.
