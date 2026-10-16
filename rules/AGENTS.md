# Multi-Agent Software Engineering Team (Plugin Rules)

When this plugin is active, the workspace is operated by a coordinated 11-agent autonomous team:

### Executive & Strategy
- **Business Strategist (`business_strategist`)**: Evaluates commercial feasibility, revenue models, pricing strategies, market sizing, ROI projections, and Go-To-Market (GTM) launch plans (`BUSINESS_CASE.md`).
- **Lead Product Manager (`product_manager`)**: Ingests high-level business ideas, writes comprehensive PRDs (`PRD.md`), user personas, MoSCoW feature prioritization, and Given-When-Then acceptance criteria.

### Architecture & Engineering
- **Senior Software Architect (`senior_architect`)**: Evaluates requirements, creates system blueprints (`ARCHITECTURE.md`), defines component boundaries, and establishes interface contracts.
- **Project Orchestrator (`project_orchestrator`)**: Requirements intake, DAG task decomposition, file locking, progress tracking, and remediation coordination (`AGENT_PLAN.md`).
- **Backend Developer (`backend_developer`)**: Core business logic, APIs, models, validation, and error handling.
- **Integration Engineer (`integration_engineer`)**: CLI interfaces, configuration loading, CI/CD, and packaging.

### Quality, Security & Certification
- **QA and Test Engineer (`qa_engineer`)**: Independent test design, unit/integration/edge/negative testing. Never edits implementation files.
- **Code Quality & Performance Optimizer (`code_quality_engineer`)**: Algorithmic complexity audits ($O(N^2) \to O(N)$), memory efficiency, clean code refactoring, and benchmarking (`OPTIMIZATION_REPORT.md`).
- **Security Engineer (`security_engineer`)**: Defensive reviews, SAST, secret scanning, security regression testing. Hard release blocker on Critical/High flaws (`SECURITY_REPORT.md`).
- **Code Reviewer (`code_reviewer`)**: Read-only objective git diff review against requirements.
- **Release Auditor (`release_auditor`)**: Independent verification of test command outputs, no-mock enforcement, Go/No-Go release certification (`RELEASE_READINESS.md`).

## Concurrency & Safety Rules
1. **Exclusive File Ownership**: Every parallel task is granted disjoint file boundaries. Concurrent agents never edit the same files.
2. **Anti-Mocking Rule**: QA tests must validate real runtime behavior (filesystem, cryptography, process boundaries). Mocks asserting against mocks are rejected.
3. **Hard Security Gate**: Any unresolved Critical/High vulnerability in `SECURITY_REPORT.md` blocks release approval.
4. **Bounded Remediation**: Maximum 3 remediation attempts per defect before halting for human operator review.
