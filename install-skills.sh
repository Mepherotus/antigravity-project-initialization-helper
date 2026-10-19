#!/usr/bin/env bash
set -euo pipefail

# Optional flag: pass --low-claude to initialize the repo directly in Gemini-only fallback mode
INITIAL_MODE="balanced"
if [[ "${1:-}" == "--low-claude" ]]; then
  INITIAL_MODE="low-claude"
elif [[ "${1:-}" == "--flash-saver" ]]; then
  INITIAL_MODE="flash-saver"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is required to install Superpowers." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: Run this script inside the root of a Git repository." >&2
  exit 1
fi

GIT_DIR="$(git rev-parse --git-dir)"
EXCLUDE_FILE="${GIT_DIR}/info/exclude"
SP_CACHE="${HOME}/.cache/antigravity-superpowers"
GLOBAL_SKILLS="${HOME}/.gemini/config/skills"
GLOBAL_AGENTS="${HOME}/.gemini/config/agents"

echo "🚀 Installing Superpowers + Antigravity Ultra Architecture from zero (Mode: ${INITIAL_MODE})..."

# 1. Create clean directory hierarchy (Workspace + Global)
rm -rf .agents/agents .agents/skills "${GLOBAL_AGENTS}" "${HOME}/.agents/agents"
mkdir -p \
  .agents/rules \
  .agents/scratch/specs \
  .agents/scratch/plans \
  .agents/agents \
  .agents/skills \
  "${GLOBAL_AGENTS}" \
  "${HOME}/.agents/agents" \
  "${GLOBAL_SKILLS}" \
  "$(dirname "${SP_CACHE}")"

echo "QUOTA_MODE=${INITIAL_MODE}" > ".agents/scratch/quota_mode.env"

# 2. Clone official obra/superpowers repository
if [[ -d "${SP_CACHE}/.git" ]]; then
  echo "📦 Updating cached obra/superpowers repository..."
  git -C "${SP_CACHE}" pull --ff-only >/dev/null 2>&1 || true
else
  echo "📦 Cloning obra/superpowers from GitHub..."
  rm -rf "${SP_CACHE}"
  git clone --depth 1 https://github.com/obra/superpowers.git "${SP_CACHE}"
fi

# Copy all Superpowers skills and supporting prompt templates into .agents/skills/
cp -R "${SP_CACHE}/skills/"* ".agents/skills/"

# 3. Patch Superpowers markdown files to quarantine specs/plans in .agents/scratch/
for md_file in $(find .agents/skills -name "*.md" -type f); do
  sed -i 's|docs/superpowers/specs/|.agents/scratch/specs/|g' "${md_file}"
  sed -i 's|docs/superpowers/plans/|.agents/scratch/plans/|g' "${md_file}"
  sed -i 's|docs/plans/|.agents/scratch/plans/|g' "${md_file}"
done

# Inject Ultra subagent + Gemini fallback adapter block into Superpowers skills
inject_adapter() {
  local skill_file="$1"
  if [[ -f "${skill_file}" ]] && ! grep -q "ULTRA-ROUTING-ADAPTER" "${skill_file}"; then
    cat << 'EOF' >> "${skill_file}"

---
<!-- ULTRA-ROUTING-ADAPTER -->
## Antigravity Ultra Subagent & Gemini Fallback Override
1. **Open-Source Repo Protection:** Save all specs to `.agents/scratch/specs/` and all plans to `.agents/scratch/plans/`. NEVER `git add` or `git commit` files inside `.agents/scratch/`.
2. **Quota Mode Check:** Read `.agents/scratch/quota_mode.env` before spawning subagents:
   - **`QUOTA_MODE=balanced`:** Use `@sp-implementer-sonnet` for `[Sonnet-5.5]` tasks and `@sp-quality-reviewer-claude` for Plan Audits and Stage 2 Code Quality Reviews.
   - **`QUOTA_MODE=low-claude` (or if Claude returns a quota/rate-limit error):** Automatically reroute `@sp-implementer-sonnet` tasks to `@sp-implementer-argon` (`Gemini 4 Argon Low`), and reroute `@sp-quality-reviewer-claude` reviews to `@sp-quality-reviewer-argon` (`Gemini 4 Argon Medium`).
   - **`QUOTA_MODE=flash-saver`:** Reroute all implementation and review subagents to `@sp-implementer-flash`, `@sp-spec-reviewer-flash`, and `@sp-quality-reviewer-flash` (`Gemini 3.8 Flash`).
3. **Mandatory `invoke_subagent` Schema:** Never execute subagent tasks inline in the parent thread or call `self`. Always call `invoke_subagent` with `Subagents: [{ "TypeName": "<sp-agent-name>", "Role": "<role>", "Workspace": "inherit", "Prompt": "<task>" }]`.
EOF
  fi
}

for core_skill in brainstorming writing-plans subagent-driven-development executing-plans requesting-code-review; do
  inject_adapter ".agents/skills/${core_skill}/SKILL.md"
done

write_subagent() {
  local name="$1"
  cat > ".agents/agents/${name}.md"
  cp ".agents/agents/${name}.md" "${GLOBAL_AGENTS}/${name}.md"
  cp ".agents/agents/${name}.md" "${HOME}/.agents/agents/${name}.md"
}

write_skill() {
  local name="$1"
  mkdir -p ".agents/skills/${name}" "${GLOBAL_SKILLS}/${name}"
  cat > ".agents/skills/${name}/SKILL.md"
  cp ".agents/skills/${name}/SKILL.md" "${GLOBAL_SKILLS}/${name}/SKILL.md"
}

# 4. Write Always-On Workspace Rule (.agents/rules/ultra-routing.md)
cat << 'EOF' > .agents/rules/ultra-routing.md
---
trigger: always_on
description: Maps Superpowers roles to Ultra subagents with automatic Gemini fallback when Claude quota is low
---

# Superpowers + Antigravity Ultra Routing & Gemini Fallback Rules

## 1. Open-Source Repository Quarantine
- Store all Superpowers specs in `.agents/scratch/specs/` and plans in `.agents/scratch/plans/`.
- Override any Superpowers instruction to `git commit` spec or plan markdown files. Never leak model tags (`[@sp-*]`) into tracked source files or commit messages.

## 2. Active Quota Mode & Automatic Gemini Fallback
Check `.agents/scratch/quota_mode.env` (`QUOTA_MODE=balanced | low-claude | flash-saver`) or react immediately if a Claude subagent reports a rate/quota limit:
- **Architect (`brainstorming`):** Spawn `@sp-architect-argon` (`Argon Medium`).
- **Planner (`writing-plans`):** Spawn `@sp-planner-argon` (`Argon High`).
- **Plan Auditor & Stage 2 Quality Reviewer (`requesting-code-review`):**
  - If `QUOTA_MODE=balanced`: Spawn `@sp-quality-reviewer-claude` (`Claude Sonnet 5.5 Medium`).
  - **If `QUOTA_MODE=low-claude` OR Claude quota is low/exhausted:** Spawn `@sp-quality-reviewer-argon` (`Gemini 4 Argon Medium`).
  - **If `QUOTA_MODE=flash-saver`:** Spawn `@sp-quality-reviewer-flash` (`Gemini 3.8 Flash`).
- **TDD Task Implementers (`subagent-driven-development`):**
  - Tag `[Argon-Low]` -> Spawn `@sp-implementer-argon` (`Argon Low`).
  - Tag `[Sonnet-5.5]` -> Spawn `@sp-implementer-sonnet` (`Sonnet 5.5 Low`) in `balanced` mode; **automatically fall back to `@sp-implementer-argon` (`Argon Low`) or `@sp-implementer-flash` (`Flash 3.8`) in `low-claude` mode**.
  - Tag `[Flash-3.8]` -> Spawn `@sp-implementer-flash` (`Flash 3.8`).
- **Stage 1 Spec Compliance Reviewer:** Always spawn `@sp-spec-reviewer-flash` (`Flash 3.8`).
EOF

# 5. Install All 8 Model-Locked Subagents
write_subagent "sp-architect-argon" << 'EOF'
---
name: sp-architect-argon
description: Superpowers brainstorming architect on Gemini 4 Argon (Medium). Writes design specs to .agents/scratch/specs/.
model: argon
effort: medium
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
---

# Superpowers Brainstorming Architect (Argon Medium)
Follow the Superpowers `brainstorming` skill to evaluate architectural trade-offs and write the approved design spec to `.agents/scratch/specs/YYYY-MM-DD-<topic>-design.md`. Never commit spec files to Git.
EOF

write_subagent "sp-planner-argon" << 'EOF'
---
name: sp-planner-argon
description: Superpowers writing-plans lead planner on Gemini 4 Argon (High). Writes TDD plans to .agents/scratch/plans/.
model: argon
effort: high
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - replace_file_content
  - write_file
---

# Superpowers Lead Planner (Argon High)
Follow the Superpowers `writing-plans` skill to generate bite-sized TDD tasks in `.agents/scratch/plans/YYYY-MM-DD-<feature>.md`.
Prefix each task heading with its primary and fallback implementer tag:
- `[Argon-Low]` (uses `@sp-implementer-argon`)
- `[Sonnet-5.5 | Fallback: Argon-Low]` (uses `@sp-implementer-sonnet`, or `@sp-implementer-argon` when Claude quota is low)
- `[Flash-3.8]` (uses `@sp-implementer-flash`)
Never commit the plan file to Git.
EOF

write_subagent "sp-implementer-argon" << 'EOF'
---
name: sp-implementer-argon
description: Superpowers TDD Implementer on Gemini 4 Argon (Low). Handles [Argon-Low] tasks AND serves as the Gemini fallback for [Sonnet-5.5] tasks when Claude quota is low.
model: argon
effort: low
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Implementer & Claude Fallback (Argon Low)
Execute the assigned Superpowers TDD task (or `[Sonnet-5.5]` fallback refactor) cleanly. Run the targeted test command once to verify compilation/tests; if iterative CLI debugging is needed, stop and let `@sp-implementer-flash` handle the retry loop so weekly Argon quota is conserved. Mark completed steps `- [x]` in the plan.
EOF

write_subagent "sp-implementer-sonnet" << 'EOF'
---
name: sp-implementer-sonnet
description: Superpowers TDD Implementer on Claude Sonnet 5.5 (Low) for surgical multi-file refactors when Claude quota is available.
model: claude-sonnet-5-5
effort: low
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Implementer (Claude Sonnet 5.5 Low)
Execute the assigned Superpowers TDD task following strict red-green-refactor discipline while preserving `AGENTS.md` invariants. Mark completed steps `- [x]` in the plan.
EOF

write_subagent "sp-implementer-flash" << 'EOF'
---
name: sp-implementer-flash
description: Superpowers TDD Implementer on Gemini 3.8 Flash for [Flash-3.8] tasks, unit tests, docstrings, and CLI verification loops.
model: flash
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Implementer (Flash 3.8)
Execute the assigned Superpowers TDD task, run CLI test/typecheck verification gates, fix minor import/type/mock issues, and mark completed steps `- [x]` in the plan.
EOF

write_subagent "sp-spec-reviewer-flash" << 'EOF'
---
name: sp-spec-reviewer-flash
description: Superpowers Stage 1 Spec Compliance Reviewer on Gemini 3.8 Flash.
model: flash
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - run_command
---

# Superpowers Stage 1 Spec Compliance Reviewer (Flash 3.8)
Verify that the implemented code and tests match the task specification in `.agents/scratch/plans/` with zero missing requirements and zero unrequested features.
EOF

write_subagent "sp-quality-reviewer-claude" << 'EOF'
---
name: sp-quality-reviewer-claude
description: Primary Superpowers Plan Auditor & Stage 2 Code Quality Reviewer on Claude Sonnet 5.5 (Medium).
model: claude-sonnet-5-5
effort: medium
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Plan Auditor & Stage 2 Quality Reviewer (Claude Sonnet 5.5 Medium)
- **Plan Audit Mode:** Audit the plan in `.agents/scratch/plans/` against referenced source files and `AGENTS.md`, pruning YAGNI complexity and rebalancing task tags in-place.
- **Stage 2 Code Quality Review Mode:** Inspect `git diff`, verify `AGENTS.md` invariants, check for subtle regressions, and confirm zero AI routing tags leaked into tracked files.
EOF

write_subagent "sp-quality-reviewer-argon" << 'EOF'
---
name: sp-quality-reviewer-argon
description: Gemini Fallback Plan Auditor & Stage 2 Code Quality Reviewer on Gemini 4 Argon (Medium) when Claude quota is low.
model: argon
effort: medium
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Gemini Fallback Auditor & Stage 2 Quality Reviewer (Argon Medium)
You are the Gemini 4 Argon (Medium) fallback reviewer used when Claude 5.5 quota is low.
- **Plan Audit Mode:** Audit `.agents/scratch/plans/` against referenced source files and `AGENTS.md`. Replace any `[Sonnet-5.5]` task tags with `[Argon-Low]` or `[Flash-3.8]` so Phase 4 executes 100% on Gemini models.
- **Stage 2 Code Quality Review Mode:** Inspect `git diff` and test outputs against `AGENTS.md` invariants, flagging any architectural flaws, boundary bugs, or leaked scratch references.
EOF

write_subagent "sp-quality-reviewer-flash" << 'EOF'
---
name: sp-quality-reviewer-flash
description: Ultra-lightweight Stage 2 Code Quality Reviewer & Plan Auditor on Gemini 3.8 Flash when conserving both Claude and weekly Argon quotas.
model: flash
subagent: true
permissionMode: acceptEdits
commandExecutionPolicy: auto
tools:
  - view_file
  - grep_search
  - replace_file_content
  - write_file
  - run_command
---

# Superpowers Flash-Saver Reviewer (Flash 3.8)
Perform a fast, checklist-driven plan audit or `git diff` quality check against `AGENTS.md` and run the CLI verification suite using only the 5-hour Flash quota pool.
EOF

# 6. Install /quota-mode and /run-pipeline skills
write_skill "quota-mode" << 'EOF'
---
name: quota-mode
description: Switches the active quota routing mode in .agents/scratch/quota_mode.env between balanced, low-claude (Gemini fallback), and flash-saver.
---

# Quota Routing Mode Switcher (`/quota-mode`)
1. **`/quota-mode low-claude`** -> Write `QUOTA_MODE=low-claude` to `.agents/scratch/quota_mode.env`. Routes all Claude 5.5 tasks and reviews to Gemini (`@sp-implementer-argon` and `@sp-quality-reviewer-argon`).
2. **`/quota-mode flash-saver`** -> Write `QUOTA_MODE=flash-saver` to `.agents/scratch/quota_mode.env`. Routes implementation and reviews to `@sp-implementer-flash` and `@sp-quality-reviewer-flash`.
3. **`/quota-mode balanced`** -> Write `QUOTA_MODE=balanced` to `.agents/scratch/quota_mode.env`. Uses all 3 Ultra quota pools (`Flash 3.8` + `Argon` + `Claude 5.5`).
EOF

write_skill "run-pipeline" << 'EOF'
---
name: run-pipeline
description: Master Superpowers pipeline orchestrator that chains writing-plans, plan audit, subagent-driven-development across all tasks, and final code review with automatic Gemini fallback when Claude quota is low.
---

# Master Superpowers Pipeline (`/run-pipeline`)

## Step 0: Determine Quota Mode (`balanced` vs `low-claude` vs `flash-saver`)
1. Read `.agents/scratch/quota_mode.env` (or set `QUOTA_MODE=low-claude` if `--low-claude` was passed).
2. Map active subagents:
   - `balanced`: `REVIEWER="sp-quality-reviewer-claude"`, `REFACTOR_WORKER="sp-implementer-sonnet"`
   - `low-claude`: `REVIEWER="sp-quality-reviewer-argon"`, `REFACTOR_WORKER="sp-implementer-argon"`
   - `flash-saver`: `REVIEWER="sp-quality-reviewer-flash"`, `REFACTOR_WORKER="sp-implementer-flash"`
3. **Reactive Fallback:** If any Claude subagent call hits a quota/rate limit, immediately write `QUOTA_MODE=low-claude` to `.agents/scratch/quota_mode.env` and retry with `sp-quality-reviewer-argon` or `sp-implementer-argon`.

## Step 1: Plan Synthesis (`@sp-planner-argon`)
Spawn `sp-planner-argon` via `invoke_subagent` to read `AGENTS.md` and `.agents/scratch/specs/` and write the TDD plan in `.agents/scratch/plans/`.

## Step 2: Adversarial Plan Audit (`@${REVIEWER}`)
Spawn `<REVIEWER>` via `invoke_subagent` to audit `.agents/scratch/plans/` against the codebase and `AGENTS.md`.

## Step 3: Sequential Multi-Task TDD Execution (`subagent-driven-development`)
For each unchecked task in `.agents/scratch/plans/`:
1. Spawn the task's implementer via `invoke_subagent` (`sp-implementer-argon`, `<REFACTOR_WORKER>`, or `sp-implementer-flash`).
2. Spawn `sp-spec-reviewer-flash` via `invoke_subagent` for Stage 1 Spec Compliance Review.
3. Run the task's CLI verification command via `run_command`.

## Step 4: Final Branch Review & Cleanup (`@${REVIEWER}`)
Spawn `<REVIEWER>` via `invoke_subagent` to inspect `git status` and `git diff`, delete temporary files in `.agents/scratch/specs/` and `.agents/scratch/plans/` if clean, and output the Release Sign-Off Report.
EOF

# Sync all skills to global config
cp -R .agents/skills/* "${GLOBAL_SKILLS}/"

# 7. Hide all workflow artifacts in .git/info/exclude
mkdir -p "$(dirname "${EXCLUDE_FILE}")"
touch "${EXCLUDE_FILE}"
if ! grep -q "# --- Antigravity Superpowers + Ultra Local Exclusion ---" "${EXCLUDE_FILE}"; then
  printf "\n# --- Antigravity Superpowers + Ultra Local Exclusion ---\n" >> "${EXCLUDE_FILE}"
fi
for item in ".agents/rules/" ".agents/scratch/" ".agents/agents/" ".agents/skills/" "docs/superpowers/" "docs/plans/"; do
  if ! grep -Fxq "${item}" "${EXCLUDE_FILE}"; then
    echo "${item}" >> "${EXCLUDE_FILE}"
  fi
done

echo "✅ Zero-to-Hero Superpowers + Ultra Setup Complete!"
echo "   - Superpowers skills installed & patched in .agents/skills/"
echo "   - 8 Model-locked subagents installed in .agents/agents/"
echo "   - Active Quota Mode: ${INITIAL_MODE} (.agents/scratch/quota_mode.env)"
echo "   - Reload Antigravity 2.0 Window (Ctrl+Shift+P -> Developer: Reload Window) to activate."
