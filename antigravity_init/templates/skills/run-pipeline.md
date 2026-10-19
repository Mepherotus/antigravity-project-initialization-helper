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
