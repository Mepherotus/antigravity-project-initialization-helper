"""Git exclusion and context poison guard for Antigravity workspaces.

Enforces zero context poisoning and quarantine of open-source repositories
by ensuring local agent artifacts, scratch files, and planning documents
are excluded in .git/info/exclude without polluting tracked repository files.
"""

from __future__ import annotations

import pathlib
import subprocess
from typing import Any

from antigravity_init import TEMPLATES_DIR

DEFAULT_EXCLUDES: list[str] = [
    ".agents/scratch/",
    ".agents/rules/",
    ".agents/agents/",
    ".agents/skills/",
    ".agents/plugins/",
    "docs/superpowers/",
    "docs/plans/",
]

EXCLUDE_HEADER = "# --- Antigravity Superpowers + Ultra Local Exclusion ---"

__all__ = [
    "DEFAULT_EXCLUDES",
    "EXCLUDE_HEADER",
    "resolve_git_dir",
    "configure_git_exclude",
    "write_routing_rules",
    "write_quota_env",
    "check_quarantine_status",
]


def resolve_git_dir(repo_root: pathlib.Path) -> pathlib.Path:
    """Resolve the git directory for a repository root, supporting worktrees.

    Args:
        repo_root: Path to repository workspace root.

    Returns:
        Path to resolved .git directory.

    Raises:
        FileNotFoundError: If .git directory or worktree file does not exist or is invalid.
    """
    root = pathlib.Path(repo_root).resolve()
    git_path = root / ".git"

    if git_path.is_dir():
        return git_path.resolve()

    if git_path.is_file():
        raw_lines = [
            line.strip()
            for line in git_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not raw_lines:
            raise FileNotFoundError(
                f"Invalid git worktree file at {git_path}: empty or comment-only file"
            )

        target = ""
        prefix = "gitdir:"
        for line in raw_lines:
            if line.startswith(prefix):
                target = line[len(prefix):].strip()
                break
        if not target:
            target = raw_lines[0]

        if not target:
            raise FileNotFoundError(
                f"Invalid git worktree file at {git_path}: missing gitdir target"
            )

        target_path = pathlib.Path(target)
        if not target_path.is_absolute():
            return (root / target_path).resolve()
        return target_path.resolve()

    raise FileNotFoundError(f"No .git directory or worktree file found at {root}")


def configure_git_exclude(
    repo_root: pathlib.Path, extra_entries: list[str] | None = None
) -> list[str]:
    """Configure local .git/info/exclude with quarantine rules idempotently.

    Args:
        repo_root: Path to repository workspace root.
        extra_entries: Optional list of additional patterns to exclude.

    Returns:
        List of newly added entries (empty if all were already present).
    """
    git_dir = resolve_git_dir(repo_root)
    exclude_file = git_dir / "info" / "exclude"
    exclude_file.parent.mkdir(parents=True, exist_ok=True)

    existing_text = ""
    existing_entries: set[str] = set()
    if exclude_file.is_file():
        existing_text = exclude_file.read_text(encoding="utf-8")
        for line in existing_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                existing_entries.add(stripped)

    cleaned_extras = [e.strip() for e in (extra_entries or []) if e and e.strip()]
    target_entries = DEFAULT_EXCLUDES + cleaned_extras
    new_entries: list[str] = []
    for entry in target_entries:
        if (
            entry not in existing_entries
            and entry.rstrip("/") not in existing_entries
            and entry not in new_entries
        ):
            new_entries.append(entry)

    if not new_entries:
        return []

    lines_to_append: list[str] = []
    if existing_text and not existing_text.endswith("\n"):
        lines_to_append.append("\n")

    if EXCLUDE_HEADER not in existing_text:
        lines_to_append.append(f"{EXCLUDE_HEADER}\n")

    for entry in new_entries:
        lines_to_append.append(f"{entry}\n")

    with open(exclude_file, "a", encoding="utf-8") as f:
        f.writelines(lines_to_append)

    return new_entries


def write_routing_rules(
    repo_root: pathlib.Path, quota_mode: str = "balanced"
) -> pathlib.Path:
    """Deploy workspace routing rules from bundled template.

    Args:
        repo_root: Path to repository workspace root.
        quota_mode: Active quota mode (balanced, low-claude, flash-saver).

    Returns:
        Path to created rule file.
    """
    target_file = pathlib.Path(repo_root) / ".agents" / "rules" / "ultra-routing.md"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    template_file = TEMPLATES_DIR / "rules" / "ultra-routing.md"
    content = template_file.read_text(encoding="utf-8")

    if quota_mode != "balanced":
        annotation = f"\n<!-- Active Quota Mode Override: {quota_mode} -->\n"
        if annotation not in content:
            content = content.rstrip() + annotation

    target_file.write_text(content, encoding="utf-8")
    return target_file


def write_quota_env(
    repo_root: pathlib.Path, quota_mode: str = "balanced"
) -> pathlib.Path:
    """Deploy or update active quota policy in .agents/scratch/quota_mode.env.

    Args:
        repo_root: Path to repository workspace root.
        quota_mode: Active quota mode name.

    Returns:
        Path to created quota_mode.env file.
    """
    target_file = pathlib.Path(repo_root) / ".agents" / "scratch" / "quota_mode.env"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(f"QUOTA_MODE={quota_mode}\n", encoding="utf-8")
    return target_file


def _is_quarantined_path(path_str: str) -> bool:
    """Check whether a relative file path matches quarantine exclusions or model tags."""
    normalized = path_str.strip().strip('"').replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for pattern in DEFAULT_EXCLUDES:
        clean = pattern.rstrip("/")
        if (
            normalized == clean
            or normalized.startswith(f"{clean}/")
            or normalized.startswith(pattern)
        ):
            return True
    if "[@sp-" in normalized or "@sp-" in normalized:
        return True
    return False


def check_quarantine_status(repo_root: pathlib.Path) -> dict[str, Any]:
    """Audit quarantine status and staged git files for potential leaks.

    Args:
        repo_root: Path to repository workspace root.

    Returns:
        Dictionary containing:
            - is_clean (bool): True if no leaks and no missing excludes.
            - leaked_staged_files (list[str]): List of staged files matching quarantine.
            - missing_excludes (list[str]): List of DEFAULT_EXCLUDES not present in git exclude.
    """
    root = pathlib.Path(repo_root).resolve()

    # 1. Audit missing git excludes
    missing_excludes: list[str] = []
    is_git_repo = False
    try:
        git_dir = resolve_git_dir(root)
        is_git_repo = True
        exclude_file = git_dir / "info" / "exclude"
        if exclude_file.is_file():
            existing_lines = {
                line.strip()
                for line in exclude_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
            missing_excludes = [
                entry
                for entry in DEFAULT_EXCLUDES
                if entry not in existing_lines and entry.rstrip("/") not in existing_lines
            ]
        else:
            missing_excludes = list(DEFAULT_EXCLUDES)
    except (FileNotFoundError, OSError):
        missing_excludes = list(DEFAULT_EXCLUDES)

    # 2. Audit staged files via git diff --cached --name-only
    leaked_staged_files: list[str] = []
    if is_git_repo:
        try:
            res = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    staged = line.strip().strip('"')
                    if not staged:
                        continue
                    if _is_quarantined_path(staged):
                        if staged not in leaked_staged_files:
                            leaked_staged_files.append(staged)

            # Check for model leak tags in staged content
            tag_res = subprocess.run(
                ["git", "diff", "--cached", "-S@sp-", "--name-only"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if tag_res.returncode == 0:
                for line in tag_res.stdout.splitlines():
                    staged = line.strip().strip('"')
                    if staged and staged not in leaked_staged_files:
                        leaked_staged_files.append(staged)
        except (OSError, subprocess.SubprocessError):
            # Git is unavailable, timed out, or not installed
            pass

    is_clean = len(leaked_staged_files) == 0 and len(missing_excludes) == 0

    return {
        "is_clean": is_clean,
        "leaked_staged_files": leaked_staged_files,
        "missing_excludes": missing_excludes,
    }
