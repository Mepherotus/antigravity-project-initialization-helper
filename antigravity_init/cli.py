"""CLI engine & terminal orchestrator for Antigravity workspaces.

Provides command-line parsing, workspace health audits (--doctor),
and complete project initialization orchestration (run_init).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from antigravity_init import advisor, agents, fetcher, poison_guard, research

VALID_QUOTA_MODES = ("balanced", "low-claude", "flash-saver")

__all__ = [
    "VALID_QUOTA_MODES",
    "parse_args",
    "run_doctor",
    "run_init",
    "main",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for antigravity-init.

    Args:
        argv: Optional list of argument strings (defaults to sys.argv[1:]).

    Returns:
        argparse.Namespace with parsed options.
    """
    parser = argparse.ArgumentParser(
        prog="antigravity-init",
        description="Antigravity Project Initialization Helper & Health Audit Tool",
    )

    parser.add_argument(
        "--mode",
        choices=VALID_QUOTA_MODES,
        default="balanced",
        help="Active quota mode (balanced, low-claude, flash-saver). Default: balanced.",
    )
    parser.add_argument(
        "--workspace",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Path to project workspace root. Default: current directory.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Enable interactive prompts for optional MCP server selection.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Disable interactive prompts (takes precedence over --interactive).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        default=False,
        help="Run health diagnostics and verification on existing workspace without modifying it.",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        default=False,
        help="Disable outbound network requests and use cached/bundled assets.",
    )
    parser.add_argument(
        "--superpowers-url",
        type=str,
        default=fetcher.DEFAULT_REPO_URL,
        help="Upstream Superpowers git repository URL.",
    )
    parser.add_argument(
        "--research-url",
        type=str,
        default=None,
        help="Custom URL for fetching research failure mode taxonomy.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable detailed diagnostic logging output.",
    )
    parser.add_argument(
        "--no-global-sync",
        action="store_true",
        default=False,
        help="Prevent mirroring agents and skills to user's global config directories.",
    )

    return parser.parse_args(argv)


def run_doctor(workspace: pathlib.Path | str) -> int:
    """Audit health and isolation status of an existing workspace.

    Args:
        workspace: Path to project workspace root.

    Returns:
        0 if all audit checks pass, 1 if any check fails.
    """
    target = pathlib.Path(workspace).expanduser().resolve()
    print(f"=== Antigravity Workspace Doctor: {target} ===")

    errors: list[str] = []

    # 1. Quarantine & Git Exclude Check
    print("[1/5] Checking Git Quarantine & Context Isolation...")
    quarantine_status = poison_guard.check_quarantine_status(target)
    if not quarantine_status.get("is_clean", False):
        missing = quarantine_status.get("missing_excludes", [])
        leaked = quarantine_status.get("leaked_staged_files", [])
        if missing:
            errors.append(f"Missing quarantine excludes in .git/info/exclude: {', '.join(missing)}")
        if leaked:
            errors.append(f"Leaked staged files matching quarantine: {', '.join(leaked)}")
    else:
        print("  ✓ Quarantine & git excludes clean")

    # 2. Quota Mode Check
    print("[2/5] Checking Quota Mode Configuration...")
    quota_file = target / ".agents" / "scratch" / "quota_mode.env"
    if not quota_file.is_file():
        errors.append(f"Missing quota mode file: {quota_file}")
    else:
        try:
            content = quota_file.read_text(encoding="utf-8")
            mode_found: str | None = None
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("QUOTA_MODE="):
                    val = stripped.split("=", 1)[1].strip().lower().strip('"\'')
                    if val in VALID_QUOTA_MODES:
                        mode_found = val
                        break
            if not mode_found:
                errors.append(f"Invalid or missing QUOTA_MODE in {quota_file} (expected one of {VALID_QUOTA_MODES})")
            else:
                print(f"  ✓ Active quota mode: {mode_found}")
        except Exception as exc:
            errors.append(f"Failed to read quota mode file {quota_file}: {exc}")

    # 3. Subagents Check
    print("[3/5] Checking 9-Model Subagent Definitions...")
    missing_agents: list[str] = []
    agents_dir = target / ".agents" / "agents"
    for name in agents.AGENT_NAMES:
        agent_file = agents_dir / f"{name}.md"
        if not agent_file.is_file():
            missing_agents.append(name)

    if missing_agents:
        errors.append(f"Missing subagent markdown files in {agents_dir}: {', '.join(missing_agents)}")
    else:
        print(f"  ✓ All {len(agents.AGENT_NAMES)} subagent definitions present")

    # 4. Workspace MCP Scaffolding Check
    print("[4/5] Checking Workspace MCP Scaffolding...")
    mcp_dir = target / ".agents" / "plugins" / "workspace-mcp"
    plugin_json = mcp_dir / "plugin.json"
    mcp_config_json = mcp_dir / "mcp_config.json"
    mcp_clean = True

    if not plugin_json.is_file():
        errors.append(f"Missing MCP plugin descriptor: {plugin_json}")
        mcp_clean = False
    else:
        try:
            json.loads(plugin_json.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid JSON in MCP plugin descriptor {plugin_json}: {exc}")
            mcp_clean = False

    if not mcp_config_json.is_file():
        errors.append(f"Missing MCP config file: {mcp_config_json}")
        mcp_clean = False
    else:
        try:
            json.loads(mcp_config_json.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid JSON in MCP config {mcp_config_json}: {exc}")
            mcp_clean = False

    if mcp_clean:
        print("  ✓ Workspace MCP plugin and configuration valid")

    # 5. Project Advisor Skill Check
    print("[5/5] Checking Project Advisor Skill...")
    advisor_skill = target / ".agents" / "skills" / "project-advisor" / "SKILL.md"
    if not advisor_skill.is_file():
        errors.append(f"Missing project-advisor skill: {advisor_skill}")
    else:
        print("  ✓ Project advisor skill present")

    # Final summary
    if errors:
        print("\nDoctor Audit: FAILED (Errors detected):")
        for err in errors:
            print(f"  ✗ {err}")
        return 1

    print("\nDoctor Audit: PASSED (All checks healthy)")
    return 0


def run_init(args: argparse.Namespace) -> int:
    """Execute complete workspace initialization orchestration.

    Args:
        args: Parsed command-line arguments.

    Returns:
        0 on success.
    """
    workspace = pathlib.Path(args.workspace).expanduser().resolve()
    mirror_global = not getattr(args, "no_global_sync", False)
    is_interactive = bool(args.interactive and not args.non_interactive)

    print(f"=== Initializing Antigravity Workspace: {workspace} ===")
    print(f"  Quota Mode: {args.mode}")
    print(f"  Global Mirroring: {mirror_global}")
    print(f"  Interactive Mode: {is_interactive}")

    # 1. Git Exclusion & Context Poison Guard
    print("\n[Step 1/5] Configuring Git Exclusion & Isolation Guards...")
    try:
        poison_guard.configure_git_exclude(workspace)
        print("  ✓ Configured .git/info/exclude with quarantine rules")
    except (FileNotFoundError, OSError):
        pass

    poison_guard.write_routing_rules(workspace, quota_mode=args.mode)
    print("  ✓ Written .agents/rules/ultra-routing.md")

    poison_guard.write_quota_env(workspace, quota_mode=args.mode)
    print("  ✓ Written .agents/scratch/quota_mode.env")

    # 2. Research & Rubric Compilation
    print("\n[Step 2/5] Fetching Guidelines & Compiling Adversarial Rubric...")
    guidelines = research.fetch_sota_guidelines(url=args.research_url, offline=args.no_web)
    rubric = research.compile_adversarial_rubric(guidelines)
    research.save_research_artifacts(workspace, rubric, guidelines)
    print("  ✓ Compiled and saved adversarial rubric to .agents/scratch/research/")

    # 3. 9-Model Subagent Generation
    print("\n[Step 3/5] Synthesizing 9-Model Subagent Definitions...")
    agents.write_agents(workspace, adversarial_rubric=rubric, mirror_global=mirror_global)
    print(f"  ✓ Deployed {len(agents.AGENT_NAMES)} subagents to .agents/agents/")

    # 4. Superpowers Upstream Skills
    print("\n[Step 4/5] Synchronizing Superpowers Skills...")
    cache_dir = fetcher.clone_or_update_superpowers(repo_url=args.superpowers_url)
    installed_skills = fetcher.install_skills(cache_dir, workspace, global_sync=mirror_global)
    print(f"  ✓ Installed {len(installed_skills)} skills with Ultra adapter transforms")

    # 5. Codebase Inspection & MCP Plugin
    print("\n[Step 5/5] Inspecting Codebase & Scaffolding MCP Servers...")
    inspection = advisor.inspect_codebase(workspace)
    recommended_mcps = inspection.get("recommended_mcps", [])
    confirmed_mcps = advisor.prompt_mcp_selection(recommended_mcps, interactive=is_interactive)
    advisor.generate_workspace_mcp_plugin(workspace, confirmed_mcps)
    print(f"  ✓ Configured workspace MCP plugin ({len(confirmed_mcps)} active servers)")

    advisor.install_project_advisor_skill(workspace, mirror_global=mirror_global)
    print("  ✓ Installed project-advisor skill to .agents/skills/project-advisor/")

    print("\nInitialization Complete! Workspace is ready for Antigravity Ultra.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI runtime entrypoint with exception trapping and robust error reporting.

    Args:
        argv: Optional command-line arguments list.

    Returns:
        Integer exit code (0 for success, non-zero on error or abort).
    """
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception as exc:
        print(f"Error parsing arguments: {exc}", file=sys.stderr)
        return 1

    try:
        if args.doctor:
            return run_doctor(args.workspace)
        return run_init(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        if getattr(args, "verbose", False):
            raise
        print(f"Error: {exc}", file=sys.stderr)
        return 1
