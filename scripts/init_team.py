#!/usr/bin/env python3
"""
Multi-Agent Software Engineering Team Scaffolding & Setup Utility

Installs the multi-agent orchestration configuration into any project directory.
Supports flexible operational tiers:
  --profile lean        : Rapid prototyping (Architect, Developer, Quality/Optimizer)
  --profile standard    : Full software apps (Product Manager, Architect, Orchestrator, Backend, Integration, QA, Quality, Reviewer)
  --profile commercial  : Business & Monetization (Business Strategist, Product Manager, Architect, Dev, QA, Optimizer)
  --profile enterprise  : Mission-critical enterprise (All 11 agents with SAST Security & Release Auditor)
  --agents AGENT1,AGENT2: Modular custom selection
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent

PROFILES = {
    "lean": {
        "description": "Rapid prototyping & fast iteration (no heavy security blockers)",
        "agents": ["senior_architect", "backend_developer", "code_quality_engineer"],
        "artifacts": ["AGENT_PLAN.md", "AGENT_PROGRESS.md", "OPTIMIZATION_REPORT.md"],
        "tools": ["quality_checker.py"]
    },
    "standard": {
        "description": "Standard software applications (PRD, automated QA, code review & optimization)",
        "agents": ["product_manager", "senior_architect", "project_orchestrator", "backend_developer", "integration_engineer", "qa_engineer", "code_quality_engineer", "code_reviewer"],
        "artifacts": ["PRD.md", "AGENT_PLAN.md", "AGENT_PROGRESS.md", "AGENT_FINDINGS.md", "OPTIMIZATION_REPORT.md"],
        "tools": ["quality_checker.py"]
    },
    "commercial": {
        "description": "Product launch & revenue generation (Business Case, PRD, Architecture, Implementation)",
        "agents": ["business_strategist", "product_manager", "senior_architect", "backend_developer", "qa_engineer", "code_quality_engineer"],
        "artifacts": ["BUSINESS_CASE.md", "PRD.md", "AGENT_PLAN.md", "AGENT_PROGRESS.md", "OPTIMIZATION_REPORT.md"],
        "tools": ["quality_checker.py"]
    },
    "enterprise": {
        "description": "Mission-critical, security-audited commercial enterprise software (all 11 agents)",
        "agents": ["business_strategist", "product_manager", "senior_architect", "project_orchestrator", "backend_developer", "integration_engineer", "qa_engineer", "code_quality_engineer", "code_reviewer", "security_engineer", "release_auditor"],
        "artifacts": ["BUSINESS_CASE.md", "PRD.md", "AGENT_PLAN.md", "AGENT_PROGRESS.md", "AGENT_FINDINGS.md", "SECURITY_REPORT.md", "RELEASE_READINESS.md", "OPTIMIZATION_REPORT.md"],
        "tools": ["sast_scanner.py", "secret_scanner.py", "release_verifier.py", "quality_checker.py"]
    }
}


def setup_project(target_dir: Path, is_new: bool = False, profile_name: str = "standard", custom_agents: list = None):
    target_dir = target_dir.resolve()
    selected_profile = PROFILES.get(profile_name, PROFILES["standard"])

    if custom_agents:
        active_agents = custom_agents
        profile_label = f"Custom ({', '.join(active_agents)})"
    else:
        active_agents = selected_profile["agents"]
        profile_label = f"{profile_name.upper()} ({selected_profile['description']})"

    print(f"[*] Configuring Multi-Agent Software Engineering Team")
    print(f"    Target Directory: {target_dir}")
    print(f"    Selected Tier   : {profile_label}")

    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize git if not already a repo
    git_dir = target_dir / ".git"
    if not git_dir.exists():
        print("  -> Initializing git repository...")
        os.system(f"git -C '{target_dir}' init -q")

    # 2. Copy .agents/ directory
    agents_src = SOURCE_ROOT / ".agents"
    agents_dst = target_dir / ".agents"
    print(f"  -> Installing .agents/ configuration bundle...")
    if agents_dst.exists():
        shutil.rmtree(agents_dst)
    shutil.copytree(agents_src, agents_dst)

    # Filter agent definitions to active agents
    agent_defs_dir = agents_dst / "agent_definitions"
    if agent_defs_dir.exists():
        for f in agent_defs_dir.glob("*.json"):
            agent_key = f.stem
            if agent_key not in active_agents:
                f.unlink()

    # 3. Generate tailored AGENTS.md
    print(f"  -> Generating customized AGENTS.md for tier '{profile_name}'...")
    agents_md_dst = target_dir / "AGENTS.md"
    generate_agents_md(agents_md_dst, profile_name, active_agents)

    # 4. Copy tools
    tools_src = SOURCE_ROOT / "tools"
    tools_dst = target_dir / "tools"
    tools_dst.mkdir(exist_ok=True)
    required_tools = selected_profile["tools"] if not custom_agents else ["quality_checker.py", "sast_scanner.py", "secret_scanner.py", "release_verifier.py"]
    for t in required_tools:
        src_tool = tools_src / t
        if src_tool.exists():
            shutil.copy2(src_tool, tools_dst / t)
    print(f"  -> Installed {len(required_tools)} verification & audit tools in tools/")

    # 5. Initialize shared artifacts
    templates_dir = agents_dst / "templates"
    required_artifacts = selected_profile["artifacts"] if not custom_agents else ["AGENT_PLAN.md", "AGENT_PROGRESS.md"]
    for art_name in required_artifacts:
        art_path = target_dir / art_name
        tmpl_file = templates_dir / f"{art_name.replace('.md', '.template.md')}"
        if not art_path.exists():
            if tmpl_file.exists():
                shutil.copy2(tmpl_file, art_path)
            else:
                art_path.write_text(f"# {art_name}\n\nInitialized for tier {profile_label}.\n")
            print(f"  -> Initialized artifact: {art_name}")

    # 6. If new project requested, scaffold skeleton
    if is_new:
        src_dir = target_dir / "src"
        tests_dir = target_dir / "tests"
        src_dir.mkdir(exist_ok=True)
        tests_dir.mkdir(exist_ok=True)
        (src_dir / "__init__.py").touch()
        (tests_dir / "__init__.py").touch()
        print("  -> Created src/ and tests/ directory skeleton.")

    print("\n[+] SUCCESS! Multi-Agent Team successfully configured.")
    print("="*65)
    print("ACTIVE AGENTS IN THIS WORKSPACE:")
    for a in active_agents:
        print(f"  • {a}")
    print("\nHOW TO RUN IN ANTIGRAVITY:")
    print("1. Open Antigravity in this project folder.")
    print("2. In chat, specify your task:")
    print(f"   'Using our multi-agent team ({profile_name} profile), implement [feature]'")
    print("="*65)


def generate_agents_md(target_path: Path, profile_name: str, active_agents: list):
    content = f"""# Multi-Agent Software Engineering Team Configuration

**Active Profile**: `{profile_name.upper()}`  
This workspace is equipped with a specialized multi-agent engineering team configured for this project.

## Active Team Roster

"""
    descriptions = {
        "business_strategist": "- **Business Strategist & Monetization Lead (`business_strategist`)**: Evaluates commercial feasibility, revenue models, pricing strategies, market sizing, ROI projections, and Go-To-Market (GTM) launch plans.",
        "product_manager": "- **Lead Product Manager (`product_manager`)**: Ingests high-level business ideas, writes comprehensive PRDs, user stories, MoSCoW feature prioritization, and Given-When-Then acceptance criteria.",
        "senior_architect": "- **Senior Software Architect (`senior_architect`)**: Evaluates requirements, creates system blueprints, defines component boundaries, and establishes interface contracts.",
        "project_orchestrator": "- **Project Orchestrator (`project_orchestrator`)**: Requirements intake, DAG task decomposition, file locking, progress tracking, and workflow coordination.",
        "backend_developer": "- **Backend Developer (`backend_developer`)**: Core business logic, APIs, models, validation, and error handling.",
        "integration_engineer": "- **Integration Engineer (`integration_engineer`)**: CLI interfaces, configuration loading, CI/CD, and packaging.",
        "qa_engineer": "- **QA and Test Engineer (`qa_engineer`)**: Independent test design, unit/integration/edge/negative testing. Never edits implementation files.",
        "code_quality_engineer": "- **Code Quality & Performance Optimizer (`code_quality_engineer`)**: Algorithmic complexity audits ($O(N^2) \\to O(N)$), memory efficiency, clean code refactoring, and benchmarking.",
        "security_engineer": "- **Security Engineer (`security_engineer`)**: Defensive reviews, SAST, secret scanning, security regression testing. Hard release blocker on Critical/High flaws.",
        "code_reviewer": "- **Code Reviewer (`code_reviewer`)**: Read-only objective git diff review against requirements.",
        "release_auditor": "- **Release Auditor (`release_auditor`)**: Independent verification of test command outputs, no-mock enforcement, Go/No-Go release certification."
    }

    for a in active_agents:
        if a in descriptions:
            content += descriptions[a] + "\n"

    content += """
## Governance & Safety Rules
- **File Ownership**: Each task assigns mutually exclusive file ownership. Concurrent workers never edit the same files.
- **Code Optimization**: All code is inspected by the Code Quality Engineer to ensure high performance and clean structure.
- **Progress Tracking**: The team communicates state through `AGENT_PLAN.md` and `AGENT_PROGRESS.md`.
"""
    target_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Team Scaffolding Utility")
    parser.add_argument("target_dir", type=str, help="Target project directory path")
    parser.add_argument("--profile", choices=["lean", "standard", "commercial", "enterprise"], default="standard",
                        help="Team profile tier (default: standard)")
    parser.add_argument("--agents", type=str, default=None,
                        help="Custom comma-separated list of agents to enable (overrides profile)")
    parser.add_argument("--new", action="store_true", help="Scaffold a new project skeleton (src/, tests/)")
    args = parser.parse_args()

    custom_list = [a.strip() for a in args.agents.split(",")] if args.agents else None
    target_path = Path(args.target_dir)
    setup_project(target_path, is_new=args.new, profile_name=args.profile, custom_agents=custom_list)

if __name__ == "__main__":
    main()
