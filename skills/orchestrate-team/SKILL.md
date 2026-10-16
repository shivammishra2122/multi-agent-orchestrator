---
name: orchestrate-team
description: Coordinates the specialized 11-agent software engineering & business team (Business Strategist, Product Manager, Senior Architect, Orchestrator, Backend, Integration, QA, Optimizer, Security, Reviewer, Auditor) to plan, build, optimize, audit, and certify software projects.
---

# Multi-Agent Team Orchestration Runbook

Use this skill when orchestrating multi-agent software engineering workflows in this repository.

## Execution Sequence

1. **Phase 1: Commercial & Product Scoping (Optional Tier)**
   - Business Strategist evaluates market sizing, monetization models, and unit economics (`BUSINESS_CASE.md`).
   - Product Manager drafts user personas, MoSCoW feature scope, and acceptance criteria (`PRD.md`).

2. **Phase 2: Architecture Blueprinting**
   - Senior Architect defines system blueprints, interface contracts, and component boundaries (`ARCHITECTURE.md`).

3. **Phase 3: DAG Decomposition & Exclusive File Locking**
   - Project Orchestrator breaks the blueprint into tasks with exclusive file locks in `AGENT_PLAN.md`.

4. **Phase 4: Parallel Implementation**
   - Backend Developer and Integration Engineer implement modules concurrently on disjoint files.

5. **Phase 5: Code Quality & Performance Optimization**
   - Code Quality Engineer runs `python3 tools/quality_checker.py src/` to eliminate quadratic loops and improve maintainability.

6. **Phase 6: Independent QA Testing**
   - QA Engineer writes unit, integration, and edge-case tests in `tests/` with zero mocks.

7. **Phase 7: Security SAST & Diff Review**
   - Security Engineer runs `tools/sast_scanner.py` and `tools/secret_scanner.py`.
   - Code Reviewer performs read-only diff inspection.

8. **Phase 8: Remediation Loop (Max 3 Retries)**
   - If tests fail or High/Critical security flaws appear, tasks route back to the developer for targeted remediation.

9. **Phase 9: Independent Release Audit**
   - Release Auditor executes `python3 tools/release_verifier.py` and signs `RELEASE_READINESS.md` (**GO / NO-GO**).

10. **Phase 10: Human Approval Gate**
    - The team presents final deliverables for operator sign-off.
