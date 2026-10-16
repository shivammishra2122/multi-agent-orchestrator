# Workspace Multi-Agent Software Engineering & Business Team

This workspace is equipped with a complete, cross-functional 11-agent autonomous team:

### Business & Product Strategy
- **Business Strategist (`business_strategist`)**: Evaluates commercial feasibility, revenue models, pricing strategies, market sizing, ROI projections, and Go-To-Market (GTM) launch plans.
- **Lead Product Manager (`product_manager`)**: Ingests high-level business ideas, writes comprehensive PRDs (`PRD.md`), user personas, MoSCoW feature prioritization, and Given-When-Then acceptance criteria.

### Architecture & Engineering
- **Senior Software Architect (`senior_architect`)**: Evaluates requirements, creates system blueprints (`ARCHITECTURE.md`), defines component boundaries, and establishes interface contracts.
- **Project Orchestrator (`project_orchestrator`)**: Requirements intake, DAG task decomposition, file locking, progress tracking, and remediation coordination (`AGENT_PLAN.md`).
- **Backend Developer (`backend_developer`)**: Core business logic, APIs, models, validation, and error handling.
- **Integration Engineer (`integration_engineer`)**: CLI interfaces, configuration loading, CI/CD, and packaging.

### Quality, Security & Certification
- **QA and Test Engineer (`qa_engineer`)**: Independent test design, unit/integration/edge/negative testing. Never edits implementation files.
- **Code Quality & Performance Optimizer (`code_quality_engineer`)**: Algorithmic complexity audits ($O(N^2) \to O(N)$), memory efficiency, clean code refactoring, and benchmarking.
- **Security Engineer (`security_engineer`)**: Defensive reviews, SAST, secret scanning, security regression testing. Hard release blocker on Critical/High flaws.
- **Code Reviewer (`code_reviewer`)**: Read-only objective git diff review against requirements.
- **Release Auditor (`release_auditor`)**: Independent verification of test command outputs, no-mock enforcement, Go/No-Go release certification (`RELEASE_READINESS.md`).

## Operational Tiers:
- **`LEAN`**: Senior Architect + Backend Developer + Code Quality Optimizer (Rapid prototyping, quick tools).
- **`STANDARD`**: Product Manager + Senior Architect + Orchestrator + Backend + Integration + QA + Code Quality + Reviewer (Feature dev, robust apps).
- **`COMMERCIAL`**: Business Strategist + Product Manager + Senior Architect + Backend + QA + Code Quality Optimizer (Revenue generation, business scoping, and product launches).
- **`ENTERPRISE`**: All 11 Agents with full SAST security gates & release certification (Auth, payments, sensitive systems).
- **`CUSTOM`**: Choose any combination of agents for targeted workflows.

Governance rules, skills, and templates are maintained in `.agents/`.
See `README.md` and `DOCUMENTATION.md` for full documentation and usage guides.
