---
name: quota-mode
description: Switches the active quota routing mode in .agents/scratch/quota_mode.env between balanced, low-claude (Gemini fallback), and flash-saver.
---

# Quota Routing Mode Switcher (`/quota-mode`)
1. **`/quota-mode low-claude`** -> Write `QUOTA_MODE=low-claude` to `.agents/scratch/quota_mode.env`. Routes all Claude 5.5 tasks and reviews to Gemini (`@sp-implementer-argon` and `@sp-quality-reviewer-argon`).
2. **`/quota-mode flash-saver`** -> Write `QUOTA_MODE=flash-saver` to `.agents/scratch/quota_mode.env`. Routes implementation and reviews to `@sp-implementer-flash` and `@sp-quality-reviewer-flash`.
3. **`/quota-mode balanced`** -> Write `QUOTA_MODE=balanced` to `.agents/scratch/quota_mode.env`. Uses all 3 Ultra quota pools (`Flash 3.8` + `Argon` + `Claude 5.5`).
