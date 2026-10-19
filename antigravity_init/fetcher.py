"""Upstream Superpowers skill fetcher, path transformer, and adapter injector."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import warnings
from typing import Final

DEFAULT_REPO_URL: Final[str] = "https://github.com/obra/superpowers.git"
DEFAULT_CACHE_DIR: Final[pathlib.Path] = (
    pathlib.Path.home() / ".cache" / "antigravity-superpowers"
)
CORE_SKILLS: Final[list[str]] = [
    "brainstorming",
    "writing-plans",
    "subagent-driven-development",
    "executing-plans",
    "requesting-code-review",
]
ULTRA_ADAPTER_HEADER: Final[str] = "<!-- ULTRA-ROUTING-ADAPTER -->"

ULTRA_ADAPTER_BLOCK: Final[str] = """---
<!-- ULTRA-ROUTING-ADAPTER -->
## Antigravity Ultra Subagent & Gemini Fallback Override
1. **Open-Source Repo Protection:** Save all specs to `.agents/scratch/specs/` and all plans to `.agents/scratch/plans/`. NEVER `git add` or `git commit` files inside `.agents/scratch/`.
2. **Quota Mode Check:** Read `.agents/scratch/quota_mode.env` before spawning subagents:
   - **`QUOTA_MODE=balanced`:** Use `@sp-implementer-sonnet` for `[Sonnet-5.5]` tasks and `@sp-quality-reviewer-claude` for Plan Audits and Stage 2 Code Quality Reviews.
   - **`QUOTA_MODE=low-claude` (or if Claude returns a quota/rate-limit error):** Automatically reroute `@sp-implementer-sonnet` tasks to `@sp-implementer-argon` (`Gemini 4 Argon Low`), and reroute `@sp-quality-reviewer-claude` reviews to `@sp-quality-reviewer-argon` (`Gemini 4 Argon Medium`).
   - **`QUOTA_MODE=flash-saver`:** Reroute all implementation and review subagents to `@sp-implementer-flash`, `@sp-spec-reviewer-flash`, and `@sp-quality-reviewer-flash` (`Gemini 3.8 Flash`).
3. **Mandatory `invoke_subagent` Schema:** Never execute subagent tasks inline in the parent thread or call `self`. Always call `invoke_subagent` with `Subagents: [{ "TypeName": "<sp-agent-name>", "Role": "<role>", "Workspace": "inherit", "Prompt": "<task>" }]`.
"""

_PATH_REPLACEMENTS: Final[list[tuple[str, str]]] = [
    ("docs/superpowers/specs/", ".agents/scratch/specs/"),
    ("docs/specs/", ".agents/scratch/specs/"),
    ("docs/superpowers/plans/", ".agents/scratch/plans/"),
    ("docs/plans/", ".agents/scratch/plans/"),
]

__all__ = [
    "DEFAULT_REPO_URL",
    "DEFAULT_CACHE_DIR",
    "CORE_SKILLS",
    "ULTRA_ADAPTER_HEADER",
    "ULTRA_ADAPTER_BLOCK",
    "clone_or_update_superpowers",
    "transform_skill_markdown",
    "inject_ultra_adapter",
    "install_skills",
]


def clone_or_update_superpowers(
    cache_dir: pathlib.Path | None = None,
    repo_url: str = DEFAULT_REPO_URL,
    force_refresh: bool = False,
) -> pathlib.Path:
    """Clones or updates the upstream Superpowers repository in local cache.

    Falls back cleanly to reusing existing cache if git pull fails or network is down.
    Raises RuntimeError if cloning fails and no local cache is available.
    """
    target_cache = pathlib.Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR

    # If cache exists and is a git repo, attempt pull update
    if target_cache.exists() and (target_cache / ".git").exists():
        try:
            res = subprocess.run(
                ["git", "-C", str(target_cache), "pull"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode != 0:
                warnings.warn(
                    f"Failed to update superpowers cache ({res.stderr.strip()}). "
                    "Reusing existing cache.",
                    RuntimeWarning,
                )
        except Exception as exc:
            warnings.warn(
                f"Failed to update superpowers cache ({exc}). Reusing existing cache.",
                RuntimeWarning,
            )
        return target_cache

    # If cache exists and contains files (non-git cache fixture)
    if target_cache.exists() and any(target_cache.iterdir()):
        warnings.warn(
            "Superpowers cache directory exists but is not a git repository. "
            "Reusing existing cache.",
            RuntimeWarning,
        )
        return target_cache

    # Otherwise clone from upstream repository
    target_cache.parent.mkdir(parents=True, exist_ok=True)
    try:
        res = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_cache)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip()
            raise RuntimeError(
                f"Failed to clone superpowers from {repo_url} and no local cache exists: {err_msg}"
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to clone superpowers from {repo_url} and no local cache exists: {exc}"
        ) from exc

    return target_cache


def transform_skill_markdown(content: str) -> str:
    """Substitutes spec and plan paths into .agents/scratch/ quarantine locations.

    Replaces longer paths before shorter prefixes to prevent partial collisions.
    Leaves unrelated markdown paths, code references, and URLs intact.
    """
    result = content
    for old_path, new_path in _PATH_REPLACEMENTS:
        result = result.replace(old_path, new_path)
    return result


def inject_ultra_adapter(content: str) -> str:
    """Appends Ultra subagent routing and quota mode override block idempotently."""
    if ULTRA_ADAPTER_HEADER in content:
        return content

    if not content:
        return ULTRA_ADAPTER_BLOCK

    if content.endswith("\n\n"):
        return content + ULTRA_ADAPTER_BLOCK
    if content.endswith("\n"):
        return content + "\n" + ULTRA_ADAPTER_BLOCK
    return content + "\n\n" + ULTRA_ADAPTER_BLOCK


def install_skills(
    source_skills_dir: pathlib.Path,
    target_workspace: pathlib.Path,
    global_sync: bool = True,
    global_dir: pathlib.Path | None = None,
) -> list[str]:
    """Installs and transforms Superpowers skills into target workspace.

    Transforms Markdown links to point to `.agents/scratch/` and injects Ultra
    subagent adapter into core skills. Mirrors to global directory if `global_sync=True`.
    Returns sorted list of installed skill names.
    """
    src_path = pathlib.Path(source_skills_dir)
    ws_path = pathlib.Path(target_workspace)
    global_base = (
        pathlib.Path(global_dir)
        if global_dir is not None
        else (pathlib.Path.home() / ".gemini" / "config" / "skills")
    )

    if (src_path / "skills").is_dir():
        skills_src = src_path / "skills"
    else:
        skills_src = src_path

    if not skills_src.exists():
        raise FileNotFoundError(f"Source skills directory not found: {skills_src}")

    installed: list[str] = []

    for entry in sorted(skills_src.iterdir()):
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            skill_name = entry.name
            target_skill_dir = ws_path / ".agents" / "skills" / skill_name
            target_skill_dir.mkdir(parents=True, exist_ok=True)

            for item in entry.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(entry)
                    dest_file = target_skill_dir / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)

                    if item.suffix.lower() == ".md":
                        raw_content = item.read_text(encoding="utf-8")
                        transformed = transform_skill_markdown(raw_content)
                        if skill_name in CORE_SKILLS and rel_path == pathlib.Path("SKILL.md"):
                            transformed = inject_ultra_adapter(transformed)
                        dest_file.write_text(transformed, encoding="utf-8")
                    else:
                        shutil.copy2(item, dest_file)

            if global_sync:
                target_global_dir = global_base / skill_name
                target_global_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(target_skill_dir, target_global_dir, dirs_exist_ok=True)

            installed.append(skill_name)

        elif entry.is_file() and entry.suffix.lower() == ".md":
            skill_name = entry.stem
            target_skill_dir = ws_path / ".agents" / "skills" / skill_name
            target_skill_dir.mkdir(parents=True, exist_ok=True)
            dest_file = target_skill_dir / "SKILL.md"

            raw_content = entry.read_text(encoding="utf-8")
            transformed = transform_skill_markdown(raw_content)
            if skill_name in CORE_SKILLS:
                transformed = inject_ultra_adapter(transformed)
            dest_file.write_text(transformed, encoding="utf-8")

            if global_sync:
                target_global_dir = global_base / skill_name
                target_global_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(target_skill_dir, target_global_dir, dirs_exist_ok=True)

            installed.append(skill_name)

    return sorted(installed)
