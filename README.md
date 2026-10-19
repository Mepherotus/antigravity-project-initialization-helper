# Antigravity Project Initialization Helper

> **Zero-dependency bootstrap engine, context poison guard, and health auditor for autonomous AI agent workspaces powered by Google Antigravity and Superpowers.**

---

## Table of Contents
- [Overview](#overview)
- [Why It Exists](#why-it-exists)
  - [1. Context Poisoning Prevention](#1-context-poisoning-prevention)
  - [2. Antigravity Ultra Routing & Fallback](#2-antigravity-ultra-routing--fallback)
  - [3. SOTA Adversarial Review Rubrics](#3-sota-adversarial-review-rubrics)
  - [4. Zero-Dependency Standard Library Architecture](#4-zero-dependency-standard-library-architecture)
  - [5. Workspace-Scoped MCP Scaffolding](#5-workspace-scoped-mcp-scaffolding)
  - [6. Native `/project-advisor` Skill](#6-native-project-advisor-skill)
- [Architecture & Workspace Layout](#architecture--workspace-layout)
- [Model Routing & Quota Modes](#model-routing--quota-modes)
- [Quickstart Guide](#quickstart-guide)
  - [Bootstrap Options](#bootstrap-options)
  - [CLI Flags Reference](#cli-flags-reference)
- [Workspace Health Doctor](#workspace-health-doctor)
- [The `/project-advisor` Skill](#the-project-advisor-skill)
- [Development & Verification](#development--verification)

---

## Overview

The **Antigravity Project Initialization Helper** configures, hardens, and audits any software repository for autonomous AI software engineering. It bridges [Superpowers](https://github.com/obra/superpowers) methodologies (TDD, brainstorming, plan auditing, subagent-driven development) with Google Antigravity Ultra agent runtimes while ensuring strict context isolation and multi-tier model quota management.

---

## Why It Exists

Autonomous AI coding agents generate extensive scratchpads, speculative execution plans, adversarial reviews, and subagent invocation logs. Without deliberate architecture, these artifacts leak into version control, polluting project history, compromising public repositories, and causing context poisoning in subsequent model invocations.

### 1. Context Poisoning Prevention
- **Git Quarantine Boundary:** Installs strict exclusion patterns directly into local `.git/info/exclude`. Unlike tracked `.gitignore` files, `.git/info/exclude` is never committed to upstream repositories, preventing pollution of team repos and open-source branches.
- **Model Tag Quarantine:** Prevents proprietary model routing markers (`[@sp-*]`) and scratchpads from leaking into tracked source code or git commits.
- **Automated Quarantine Auditing:** Scans the git index (`git diff --cached`) for accidental staging of quarantined paths.

### 2. Antigravity Ultra Routing & Fallback
- Dynamically coordinates heavy reasoning models (Gemini 4 Argon, Claude 3.5 Sonnet) and fast execution models (Gemini 3.8 Flash).
- Supports automatic quota-aware rerouting: when Claude rate limits or quotas are reached, workloads automatically fall back to Gemini 4 Argon or Gemini 3.8 Flash without human intervention.

### 3. SOTA Adversarial Review Rubrics
- Downloads and compiles empirical software failure mode taxonomies into an adversarial code review rubric.
- Injects verification checklists (spec compliance, edge cases, error propagation, concurrency, test flakiness) directly into code reviewer subagent prompts.

### 4. Zero-Dependency Standard Library Architecture
- Runs on any standard Python 3.9+ installation using **only standard library modules** (`urllib.request`, `json`, `subprocess`, `argparse`, `pathlib`).
- Requires no `pip install`, virtual environment creation, or third-party packages.
- Includes a POSIX-compliant bootstrap script (`init.sh`) compatible with `sh`, `bash`, `dash`, and `zsh`.

### 5. Workspace-Scoped MCP Scaffolding
- Inspects repository markers (e.g. `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Dockerfile`, `docker-compose.yml`) to detect development stacks.
- Automatically scaffolds workspace-local Model Context Protocol (MCP) server plugins under `.agents/plugins/workspace-mcp/` without polluting global agent settings.

### 6. Native `/project-advisor` Skill
- Installs an autonomous advisory skill directly into `.agents/skills/project-advisor/`.
- Enables agents to self-diagnose workspace health, inspect active quota policies, audit subagent configurations, and remediate quarantine leaks dynamically.

---

## Architecture & Workspace Layout

```
<workspace-root>/
├── .git/
│   └── info/
│       └── exclude                 # Quarantine boundary (never committed)
├── .agents/
│   ├── rules/
│   │   └── ultra-routing.md        # Antigravity Ultra routing policy & rules
│   ├── scratch/                    # QUARANTINED (never tracked by git)
│   │   ├── quota_mode.env          # Active quota policy (balanced | low-claude | flash-saver)
│   │   ├── specs/                  # Work-in-progress design specifications
│   │   ├── plans/                  # Implementation plans
│   │   └── research/
│   │       ├── adversarial_review.md   # Compiled empirical review rubric
│   │       └── sota_guidelines.json    # Cached raw taxonomy data
│   ├── agents/                     # 9 Model-locked subagent definitions
│   │   ├── sp-architect-argon.md
│   │   ├── sp-planner-argon.md
│   │   ├── sp-implementer-argon.md
│   │   ├── sp-implementer-sonnet.md
│   │   ├── sp-implementer-flash.md
│   │   ├── sp-spec-reviewer-flash.md
│   │   ├── sp-quality-reviewer-claude.md
│   │   ├── sp-quality-reviewer-argon.md
│   │   └── sp-quality-reviewer-flash.md
│   ├── plugins/
│   │   └── workspace-mcp/          # Workspace-scoped MCP server declarations
│   │       ├── plugin.json
│   │       └── mcp_config.json
│   └── skills/                     # Transformed Superpowers & custom skills
│       ├── brainstorming/
│       ├── writing-plans/
│       ├── subagent-driven-development/
│       ├── executing-plans/
│       ├── requesting-code-review/
│       └── project-advisor/        # Workspace health & diagnostic skill
```

---

## Model Routing & Quota Modes

The active quota mode is configured in `.agents/scratch/quota_mode.env`:

| Mode | Role Mapping & Behavior | Best For |
| :--- | :--- | :--- |
| **`balanced`** *(Default)* | - Architect & Planner: Gemini 4 Argon<br>- Implementers: Claude Sonnet 3.5 & Flash<br>- Quality Reviewer: Claude Sonnet 3.5<br>- Spec Reviewer: Flash 3.8 | Standard development with active Claude and Gemini API access. |
| **`low-claude`** | - Quality Reviewer: Gemini 4 Argon Medium<br>- Implementers: Gemini 4 Argon Low / Flash 3.8<br>- Preserves Claude quota while maintaining deep reasoning. | When Claude tier limits are constrained or quota is depleted. |
| **`flash-saver`** | - All implementers and reviewers route to Gemini 3.8 Flash.<br>- High-velocity, ultra-low cost execution. | High-frequency test runs, CI pipelines, and rapid prototyping. |

---

## Quickstart Guide

### Bootstrap Options

#### In-Repository Execution
```bash
# Initialize workspace with default balanced mode
./init.sh

# Or run with explicit options
./init.sh --mode low-claude --no-web
```

#### One-Line Curl Bootstrap
```bash
curl -sSL https://raw.githubusercontent.com/mepherotus/antigravity-project-initialization-helper/main/init.sh | sh
```

#### Direct Python Execution
```bash
python3 -m antigravity_init --workspace /path/to/project --mode balanced
```

---

### CLI Flags Reference

| Flag | Type / Choices | Default | Description |
| :--- | :--- | :--- | :--- |
| `--workspace` | Path | `.` *(cwd)* | Target workspace root directory. |
| `--mode` | `balanced`, `low-claude`, `flash-saver` | `balanced` | Active quota management policy. |
| `--doctor` | Flag | `False` | Run workspace diagnostics and isolation verification without modifying files. |
| `--no-web` | Flag | `False` | Offline mode: skip network downloads and use bundled fallback assets. |
| `--interactive` | Flag | `False` | Prompt interactively for detected MCP server activation. |
| `--non-interactive` | Flag | `False` | Automatically accept detected MCP servers without prompting. |
| `--superpowers-url` | URL / Path | Upstream repo | Superpowers repository URL or local cache source. |
| `--research-url` | URL | None | Custom URL for downloading SOTA research guidelines. |
| `--no-global-sync` | Flag | `False` | Do not mirror generated subagents and skills to `~/.gemini/config/`. |
| `--verbose` | Flag | `False` | Show full stack traces on error. |

---

## Workspace Health Doctor

Run health diagnostics on any workspace at any time to verify that isolation rules and required components are intact:

```bash
./init.sh --doctor --workspace .
```

The Doctor performs a 5-point audit:
1. **Quarantine & Git Excludes:** Verifies `.git/info/exclude` contains all quarantine rules and ensures zero quarantined files are staged in the git index.
2. **Quota Configuration:** Confirms `.agents/scratch/quota_mode.env` exists with a valid `QUOTA_MODE`.
3. **9-Model Subagent Completeness:** Verifies all 9 subagent markdown definitions are present in `.agents/agents/`.
4. **Workspace MCP Scaffolding:** Validates `plugin.json` and `mcp_config.json` exist and parse as valid JSON.
5. **Project Advisor Skill:** Verifies `.agents/skills/project-advisor/SKILL.md` is deployed and readable.

**Exit Codes:**
- `0`: All checks passed; workspace is healthy and quarantined.
- `1`: Diagnostic error detected (details printed to stderr/stdout).

---

## The `/project-advisor` Skill

The initialization helper installs the `project-advisor` skill into `.agents/skills/project-advisor/SKILL.md`. Autonomous agents can activate this skill whenever they start work on a project or encounter unexpected environment issues.

The skill executes a 4-phase verification workflow:
1. **Context Isolation Audit:** Inspects `.git/info/exclude` and checks git porcelain status for leaked files.
2. **Quota Mode Audit:** Determines the active model routing tier from `quota_mode.env`.
3. **Subagent & MCP Audit:** Validates subagent definitions and MCP tool descriptors.
4. **Autonomous Remediation:** Provides actionable commands (`git reset`, re-running `--doctor`) to repair detected drift.

---

## Development & Verification

### Running the Test Suite

The project includes a comprehensive test suite covering unit, CLI, bootstrap, and integration behaviors:

```bash
# Run all tests across all modules
python3 -m unittest discover -s tests -v

# Run specific test suites
python3 -m unittest tests/test_integration.py -v
python3 -m unittest tests/test_cli.py -v
python3 -m unittest tests/test_init_sh.py -v
python3 -m unittest tests/test_poison_guard.py -v
```

### Zero-Dependency Standard

All code in `antigravity_init` strictly uses the Python standard library. When adding new modules or modifying existing code, do not import external third-party packages.
