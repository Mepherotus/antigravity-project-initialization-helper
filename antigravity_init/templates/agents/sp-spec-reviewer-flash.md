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
