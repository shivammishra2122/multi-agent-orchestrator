---
name: orchestrate-team
description: Coordinates the specialized multi-agent software engineering team (Backend, Integration, QA, Security, Code Reviewer, Release Auditor) to implement, test, audit, and deliver software features safely.
---

# Multi-Agent Team Orchestration Runbook

Use this skill when orchestrating multi-agent software engineering workflows in this repository.

## Procedure Overview

1. **Phase 1: Planning & DAG Generation**
   - Decompose user requirements into distinct tasks.
   - Assign exclusive file boundaries to prevent merge collisions.
   - Initialize `AGENT_PLAN.md` and `AGENT_PROGRESS.md`.

2. **Phase 2: Parallel Implementation**
   - Identify tasks with no unmet dependencies.
   - Invoke Developer and Integration subagents simultaneously:
     - Set `Workspace: "inherit"` (or `"branch"` if branch isolation is required).
     - Specify task objectives, owned files, and acceptance criteria.
   - Collect completions and verify changes touch only owned files.

3. **Phase 3: Independent QA & Test Execution**
   - Task the `qa_engineer` to author test files in `tests/` covering functional behavior, edge cases, negative paths, and boundary values.
   - Run the test suite:
     ```bash
     python3 -m unittest discover -s tests -v
     ```
   - If tests fail, log findings in `AGENT_FINDINGS.md` and trigger the remediation loop.

4. **Phase 4: Security Analysis & Code Review**
   - Dispatch `security_engineer` to run SAST and secret scans:
     ```bash
     python3 tools/sast_scanner.py src/
     python3 tools/secret_scanner.py .
     ```
   - Dispatch `code_reviewer` (read-only) to inspect the diff:
     ```bash
     git diff
     ```
   - Document any security issues in `SECURITY_REPORT.md` and review feedback in `AGENT_FINDINGS.md`.

5. **Phase 5: Remediation Loop (Max 3 Retries)**
   - If QA failures or High/Critical security issues exist:
     - Check retry count. If count >= 3, halt and report blocker.
     - Dispatch `backend_developer` with exact defect details.
     - Re-run affected tests, then full test suite.
     - Security re-scan.

6. **Phase 6: Release Readiness Audit**
   - Task `release_auditor` to verify all acceptance criteria and execute verification suite.
   - Verify zero skipped/mocked critical tests.
   - Generate and sign `RELEASE_READINESS.md`.

7. **Phase 7: Human Approval**
   - Present final release summary to the user and wait for deployment instruction.
