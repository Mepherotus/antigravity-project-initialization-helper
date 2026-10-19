---
name: project-advisor
description: Antigravity-native workspace health auditor and advisor runbook. Use when running /project-advisor to audit quarantine boundaries, quota modes, subagent freshness, and MCP configurations.
---

# Antigravity Project Advisor (`/project-advisor`)

Use this runbook to conduct a zero-dependency diagnostic health and safety audit of the active workspace. Execute each phase sequentially using native Antigravity tools (`view_file`, `run_command`).

---

## Phase 1: Context Isolation & Quarantine Audit
Audit `.git/info/exclude` to guarantee internal scratch plans, specs, instructions, and rules are isolated from Git history and never leak upstream.

1. **Resolve Git Directory and Inspect Exclusions:**
   - Determine the Git directory path:
     - In standard repositories, inspect `.git/info/exclude`.
     - In Git worktree environments, `.git` is a worktree file containing `gitdir: <path>`. Resolve the linked gitdir directory and inspect `<gitdir>/info/exclude`.
   - Use `view_file` on the resolved `.git/info/exclude` file.
   - Verify that all 7 required quarantine exclusion entries are present:
     - `.agents/scratch/`
     - `.agents/rules/`
     - `.agents/agents/`
     - `.agents/skills/`
     - `.agents/plugins/`
     - `docs/superpowers/`
     - `docs/plans/`

2. **Check Staged and Untracked Leaks:**
   - Use `run_command` to execute `git status --porcelain`.
   - Verify that no quarantined files under `.agents/scratch/`, `.agents/rules/`, `.agents/agents/`, or internal plan directories are staged (`A`, `M`, or `AM`).
   - Confirm that no staged files or commit messages contain leaked model routing tags:
     - `@sp-`
     - `[@sp-` (e.g., `[@sp-implementer-flash]`, `[@sp-quality-reviewer-claude]`)

---

## Phase 2: Active Quota Mode Audit
Audit the current model routing configuration to guarantee rate-limit stability and appropriate model tier allocation.

1. **Read Active Policy:**
   - Use `view_file` to read `.agents/scratch/quota_mode.env`.
   - Validate that `QUOTA_MODE` is set to one of the 3 supported modes:
     - `balanced`
     - `low-claude`
     - `flash-saver`

2. **Validate Routing Consistency:**
   - In `balanced` mode: Claude Sonnet 3.7 / 5.5 is enabled for refactoring, complex tasks, and Stage 2 code reviews; Gemini 3.8 Flash handles mechanical tasks.
   - In `low-claude` mode: Gemini 4 Argon is used as high-reasoning fallback for Claude Sonnet when Anthropic quota is limited.
   - In `flash-saver` mode: Gemini 3.8 Flash handles all subagent assignments for maximum quota preservation and rapid iterations.

---

## Phase 3: Subagent & MCP Freshness Audit
Verify that all model-locked subagents and workspace-scoped plugins exist, are uncorrupted, and match canonical architecture.

1. **Verify 9 Model-Locked Subagents:**
   - Use `view_file` or directory listing to verify `.agents/agents/` contains all 9 canonical subagent definitions:
     - `sp-architect-argon.md` (`sp-architect-argon`)
     - `sp-planner-argon.md` (`sp-planner-argon`)
     - `sp-implementer-argon.md` (`sp-implementer-argon`)
     - `sp-implementer-sonnet.md` (`sp-implementer-sonnet`)
     - `sp-implementer-flash.md` (`sp-implementer-flash`)
     - `sp-spec-reviewer-flash.md` (`sp-spec-reviewer-flash`)
     - `sp-quality-reviewer-claude.md` (`sp-quality-reviewer-claude`)
     - `sp-quality-reviewer-argon.md` (`sp-quality-reviewer-argon`)
     - `sp-quality-reviewer-flash.md` (`sp-quality-reviewer-flash`)

2. **Verify Workspace MCP Scaffolding:**
   - Inspect `.agents/plugins/workspace-mcp/plugin.json` and `.agents/plugins/workspace-mcp/mcp_config.json`.
   - Confirm both files contain valid JSON syntax.
   - Verify that `.agents/plugins/workspace-mcp/mcp_config.json` declares workspace-scoped `mcpServers` tailored to detected tech stacks (e.g., Python, Node/TypeScript, Docker, Rust, GenAI).

---

## Phase 4: Remediation Actions & Doctor Mode
If any audit phase detects missing configurations, drift, errors, or context leaks, execute the following remediation actions immediately:

1. **Unstage Leaked Scratch Files:**
   - If scratch artifacts or quarantined files are staged in the git index, immediately use `run_command` to execute:
     ```bash
     git reset HEAD .agents/scratch/
     ```
   - If other internal files were staged, unstage them using `run_command` with `git reset HEAD <path>`.

2. **Run Doctor Mode:**
   - Execute the automated health check and diagnostic tool via `run_command`:
     ```bash
     antigravity-init --doctor
     ```
     (or run `python3 -m antigravity_init --doctor`).
   - Doctor mode will verify git exclude rules, quarantine integrity, subagents, and quota configuration.

3. **Restore Missing Excludes:**
   - Append missing quarantine entries directly to `.git/info/exclude` (or the worktree's info exclude file):
     ```
     .agents/scratch/
     .agents/rules/
     .agents/agents/
     .agents/skills/
     .agents/plugins/
     docs/superpowers/
     docs/plans/
     ```

4. **Restore Subagents and Workspace Scaffolding:**
   - Re-run `antigravity-init` to regenerate any missing or modified agent markdown definitions in `.agents/agents/` and workspace MCP configs.

5. **Update Quota Mode:**
   - Set or reset `.agents/scratch/quota_mode.env` with the desired mode, e.g.:
     ```
     QUOTA_MODE=balanced
     ```
