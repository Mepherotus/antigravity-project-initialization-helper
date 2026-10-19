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
