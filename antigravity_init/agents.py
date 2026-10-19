"""9-Model Subagent Synthesizer & Local/Global Mirroring for Antigravity.

Synthesizes model-locked Superpowers agent definitions from bundled templates,
injects dynamic adversarial review rubrics into quality reviewer agents,
and distributes agent markdown files to local workspace and global agent stores.
"""

from __future__ import annotations

import os
import pathlib
from typing import Sequence

from antigravity_init import TEMPLATES_DIR

AGENT_NAMES: list[str] = [
    "sp-architect-argon",
    "sp-planner-argon",
    "sp-implementer-argon",
    "sp-implementer-sonnet",
    "sp-implementer-flash",
    "sp-spec-reviewer-flash",
    "sp-quality-reviewer-claude",
    "sp-quality-reviewer-argon",
    "sp-quality-reviewer-flash",
]

QUALITY_REVIEWER_NAMES: list[str] = [
    "sp-quality-reviewer-claude",
    "sp-quality-reviewer-argon",
    "sp-quality-reviewer-flash",
]

RUBRIC_INJECTION_HEADER: str = "<!-- ADVERSARIAL-REVIEW-RUBRIC -->"

__all__ = [
    "AGENT_NAMES",
    "QUALITY_REVIEWER_NAMES",
    "RUBRIC_INJECTION_HEADER",
    "get_agent_definitions",
    "write_agents",
]


def _atomic_write_text(dest: pathlib.Path, content: str, encoding: str = "utf-8") -> None:
    """Safely and atomically write content to a file using a temporary sibling file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_file = dest.with_name(f".{dest.name}.tmp.{os.getpid()}")
    try:
        temp_file.write_text(content, encoding=encoding)
        temp_file.replace(dest)
    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


def get_agent_definitions(adversarial_rubric: str = "") -> dict[str, str]:
    """Load agent markdown definitions and dynamically inject adversarial rubric into reviewers.

    Args:
        adversarial_rubric: Compiled adversarial rubric string. If non-empty,
            injected into quality reviewer subagent definitions.

    Returns:
        dict mapping agent name to synthesized markdown content.

    Raises:
        FileNotFoundError: If an agent template file does not exist.
    """
    definitions: dict[str, str] = {}
    clean_rubric = (adversarial_rubric or "").strip()

    for name in AGENT_NAMES:
        template_file = TEMPLATES_DIR / "agents" / f"{name}.md"
        content = template_file.read_text(encoding="utf-8")

        if name in QUALITY_REVIEWER_NAMES and clean_rubric:
            if RUBRIC_INJECTION_HEADER not in content:
                injection = (
                    f"\n\n---\n"
                    f"{RUBRIC_INJECTION_HEADER}\n"
                    f"## Mandatory Adversarial Review Checklist & Taxonomy\n"
                    f"{clean_rubric}\n"
                )
                content = content.rstrip() + injection

        definitions[name] = content

    return definitions


def write_agents(
    target_workspace: pathlib.Path | str,
    adversarial_rubric: str = "",
    mirror_global: bool = True,
    global_dirs: Sequence[pathlib.Path | str] | None = None,
) -> list[pathlib.Path]:
    """Write agent definitions to workspace and optionally mirror to global agent dirs.

    Args:
        target_workspace: Path to repository workspace root (as Path or str).
        adversarial_rubric: Optional compiled adversarial review rubric.
        mirror_global: If True, mirror agent markdown files to global agent stores.
        global_dirs: Optional sequence of global directory paths (as Paths or strs).
            If None, defaults to ~/.gemini/config/agents and ~/.agents/agents.

    Returns:
        List of pathlib.Path objects for written workspace agent files.
    """
    workspace_path = pathlib.Path(target_workspace).resolve()
    workspace_agents_dir = workspace_path / ".agents" / "agents"
    workspace_agents_dir.mkdir(parents=True, exist_ok=True)

    definitions = get_agent_definitions(adversarial_rubric=adversarial_rubric)
    written_paths: list[pathlib.Path] = []

    for name in AGENT_NAMES:
        agent_file = workspace_agents_dir / f"{name}.md"
        _atomic_write_text(agent_file, definitions[name], encoding="utf-8")
        written_paths.append(agent_file)

    if mirror_global:
        if global_dirs is None:
            dest_dirs = [
                (pathlib.Path.home() / ".gemini" / "config" / "agents").resolve(),
                (pathlib.Path.home() / ".agents" / "agents").resolve(),
            ]
        else:
            dest_dirs = [pathlib.Path(d).resolve() for d in global_dirs]

        for dest_dir in dest_dirs:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for name in AGENT_NAMES:
                global_file = dest_dir / f"{name}.md"
                _atomic_write_text(global_file, definitions[name], encoding="utf-8")

    return written_paths
