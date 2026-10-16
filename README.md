# Reusable Multi-Agent Software Engineering Orchestration System

A production-grade, reusable multi-agent software engineering team configured natively for Google Antigravity. It enables specialized AI agents to collaborate autonomously, safely, and verifiably on software projects with customizable operational tiers.

---

## 1. Specialized Agent Roster (9 Agents)

| Agent Role | Subagent Name | Tool Permissions | Primary File Boundaries | Responsibilities |
| :--- | :--- | :--- | :--- | :--- |
| **Senior Software Architect** | `senior_architect` | Write (`ARCHITECTURE.md`) | `ARCHITECTURE.md`, `docs/adr/*` | System blueprints, component boundaries, interface contracts, tech stack selection, scalability modeling. |
| **Project Orchestrator** | `project_orchestrator` | Subagents + Write | `AGENT_PLAN.md`, `AGENT_PROGRESS.md` | Requirements intake, DAG task decomposition, file ownership enforcement, parallel delegation, remediation loops. |
| **Backend Developer** | `backend_developer` | Write (No subagents) | `src/auth.py`, `src/vault.py`, models | Core business logic, APIs, models, validation, boundary checks. |
| **Integration Engineer** | `integration_engineer` | Write (No subagents) | `src/cli.py`, `src/config.py`, packaging | CLI interfaces, configuration loading, environment parsing, CI/CD automation, packaging. |
| **QA and Test Engineer** | `qa_engineer` | Write (Strictly `tests/`) | `tests/*` (Forbidden from `src/`) | Independent test design, unit/integration/edge/negative tests, anti-mocking verification. |
| **Code Quality & Optimizer** | `code_quality_engineer` | Write (Optimization docs) | `OPTIMIZATION_REPORT.md`, `benchmarks/*` | Algorithmic complexity audits ($O(N^2) \to O(N)$), memory efficiency, clean code refactoring, benchmarking. |
| **Security Engineer** | `security_engineer` | Write (Security files) | `SECURITY_REPORT.md`, regression tests | Defensive reviews, SAST, secret scanning, security regression testing. Hard release blocker on Critical/High flaws. |
| **Code Reviewer** | `code_reviewer` | **Strictly Read-Only** | Entire codebase (Read-only) | Objective git diff review, architectural consistency, maintainability, actionable notes in `AGENT_FINDINGS.md`. |
| **Release Auditor** | `release_auditor` | Write (Audit report only) | `RELEASE_READINESS.md` | Independent verification of actual command outputs, anti-bypass audit (zero mocked/skipped checks), Go/No-Go release certification. |

---

## 2. Flexible Operational Tiers (Pick Which Agents to Use)

Not every project requires intense password hashing or high-grade cryptographic audits. You can select the right tier for each project:

| Profile Tier | Active Agents | Best Suited For | Security & Quality Level |
| :--- | :--- | :--- | :--- |
| **`LEAN`** | Senior Architect, Backend Developer, Code Quality/Optimizer | Quick scripts, prototypes, hackathons, MVPs | Rapid execution. Code quality checks enabled, heavy security blockers disabled. |
| **`STANDARD`** *(Default)* | Senior Architect, Orchestrator, Backend, Integration, QA, Code Quality/Optimizer, Code Reviewer | Web applications, APIs, microservices, CLI utilities | Full automated testing, clean architecture, performance optimization, and diff review. |
| **`ENTERPRISE`** | All 9 Agents (including Security Engineer & Release Auditor) | Auth vaults, payment processors, healthcare, mission-critical systems | Hard security gates (SAST/secrets), regression suites, zero-mock audit, formal Go/No-Go certification. |
| **`CUSTOM`** | Any user-specified combination | Targeted workflows | Exactly the agents you select (e.g. `--agents backend_developer,qa_engineer`). |

---

## 3. How to Deploy in All Your Projects

### A. Existing Projects (1 Command)
```bash
# Standard profile (Default):
python3 scripts/init_team.py /path/to/existing-project

# Lean / Fast Prototype profile:
python3 scripts/init_team.py /path/to/existing-project --profile lean

# Enterprise / Mission-Critical profile:
python3 scripts/init_team.py /path/to/existing-project --profile enterprise

# Custom agent selection:
python3 scripts/init_team.py /path/to/existing-project --agents senior_architect,backend_developer,code_quality_engineer
```
*Preserves 100% of your existing codebase and git history without modification.*

### B. New Project Creation
```bash
python3 scripts/init_team.py /path/to/new-project --new --profile standard
```

---

## 4. Prompt Playbook: Interacting with the Team

Once your project has been initialized, simply open it in Antigravity and prompt the team:

### A. Lean / Rapid Prototype Prompt
> *"Using our Lean team profile (Senior Architect, Developer, Code Quality Engineer), build a prototype CLI tool that does [X]. Ensure the architect defines clean interfaces and the Code Quality Engineer verifies that the code is clean and performant."*

### B. Standard Application Feature Prompt
> *"Using our Standard multi-agent team in AGENTS.md, implement [feature description]. Senior Architect will design the data flow, Backend and Integration will implement in parallel, QA will independently author tests in tests/, and Code Quality Engineer will optimize performance."*

### C. Enterprise High-Security Feature Prompt
> *"Using our Enterprise team profile in AGENTS.md, implement [auth/payment/vault feature]. Execute the full engineering lifecycle: Architect blueprinting, parallel dev, independent QA tests, SAST security scan, remediation loop, and Release Auditor certification."*

### D. Code Quality & Optimization Prompt
> *"Have the Code Quality Engineer run tools/quality_checker.py on src/ and optimize any algorithmic bottlenecks, nested loops, or high-complexity routines."*

---

## 5. Verification & Quality Toolset (`tools/`)

- **`tools/quality_checker.py`**: AST-based code quality, cognitive complexity, type hint coverage, docstring coverage, and algorithmic bottleneck detector ($O(N^2)$ nested loop detector).
- **`tools/sast_scanner.py`**: Static application security testing for injection, path traversal, weak crypto hashes, and unsafe deserialization.
- **`tools/secret_scanner.py`**: High-entropy token, private key, and password leak detector.
- **`tools/release_verifier.py`**: Independent audit runner verifying test suites, security scans, and clean diffs.
