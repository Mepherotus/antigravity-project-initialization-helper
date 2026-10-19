"""Codebase inspector and workspace-scoped MCP plugin generator."""

import copy
import json
import os
import pathlib
from typing import Any, Callable

from antigravity_init import TEMPLATES_DIR

DETECTION_RULES: dict[str, dict[str, Any]] = {
    "python": {
        "files": ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py"],
        "mcp": {
            "name": "python-mcp",
            "command": "python3",
            "args": ["-m", "mcp_server_python"],
            "description": "Python execution and analysis server",
        },
    },
    "node": {
        "files": ["package.json", "tsconfig.json"],
        "mcp": {
            "name": "chrome-devtools",
            "command": "npx",
            "args": ["-y", "chrome-devtools-mcp"],
            "description": "Chrome DevTools browser debugging server",
        },
    },
    "rust": {
        "files": ["Cargo.toml"],
        "mcp": {
            "name": "rust-analyzer",
            "command": "rust-analyzer",
            "args": [],
            "description": "Rust language server",
        },
    },
    "docker": {
        "files": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        "mcp": {
            "name": "docker-mcp",
            "command": "docker-mcp",
            "args": [],
            "description": "Docker container inspection server",
        },
    },
    "genai": {
        "files": [".gemini", "gemini.json"],
        "mcp": {
            "name": "gemini-api-docs",
            "command": "npx",
            "args": ["-y", "@google/gemini-api-docs-mcp"],
            "description": "Gemini API documentation search server",
        },
    },
}

__all__ = [
    "DETECTION_RULES",
    "inspect_codebase",
    "generate_workspace_mcp_plugin",
    "install_project_advisor_skill",
    "prompt_mcp_selection",
]


def _atomic_write_text(dest: pathlib.Path | str, content: str, encoding: str = "utf-8") -> None:
    """Safely and atomically write content to a file using a temporary sibling file."""
    dest_path = pathlib.Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = dest_path.with_name(f".{dest_path.name}.tmp.{os.getpid()}")
    try:
        temp_file.write_text(content, encoding=encoding)
        temp_file.replace(dest_path)
    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


def inspect_codebase(repo_root: pathlib.Path | str) -> dict[str, Any]:
    """Inspect repository root for marker files and recommend relevant MCP servers.

    Args:
        repo_root: Root path of the repository to inspect.

    Returns:
        dict containing 'detected_languages', 'detected_markers', and 'recommended_mcps'.
    """
    root = pathlib.Path(repo_root)
    if not root.is_dir():
        return {
            "detected_languages": [],
            "detected_markers": [],
            "recommended_mcps": [],
        }

    detected_languages: list[str] = []
    detected_markers: list[str] = []
    recommended_mcps: list[dict[str, Any]] = []

    for tech, rule in DETECTION_RULES.items():
        found_markers: list[str] = []
        for marker in rule["files"]:
            target_path = root / marker
            if target_path.exists():
                found_markers.append(marker)

        if found_markers:
            detected_languages.append(tech)
            detected_markers.extend(found_markers)
            recommended_mcps.append(copy.deepcopy(rule["mcp"]))

    return {
        "detected_languages": detected_languages,
        "detected_markers": detected_markers,
        "recommended_mcps": recommended_mcps,
    }


def generate_workspace_mcp_plugin(
    target_workspace: pathlib.Path | str,
    confirmed_mcps: list[dict[str, Any]],
) -> tuple[pathlib.Path, pathlib.Path]:
    """Generate workspace-scoped MCP plugin configuration files.

    Args:
        target_workspace: Path to the target workspace root.
        confirmed_mcps: List of confirmed MCP configurations.

    Returns:
        Tuple of paths: (plugin_json_path, mcp_config_json_path).
    """
    workspace = pathlib.Path(target_workspace)
    plugin_dir = workspace / ".agents" / "plugins" / "workspace-mcp"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    plugin_json_path = plugin_dir / "plugin.json"
    mcp_config_json_path = plugin_dir / "mcp_config.json"

    plugin_payload = {
        "name": "workspace-mcp",
        "description": "Workspace-scoped MCP servers configured for this project",
        "version": "0.1.0",
    }

    servers_payload: dict[str, dict[str, Any]] = {}
    for mcp in confirmed_mcps:
        servers_payload[mcp["name"]] = {
            "command": mcp["command"],
            "args": list(mcp.get("args", [])),
        }

    mcp_config_payload = {
        "mcpServers": servers_payload,
    }

    _atomic_write_text(
        plugin_json_path,
        json.dumps(plugin_payload, indent=2) + "\n",
    )
    _atomic_write_text(
        mcp_config_json_path,
        json.dumps(mcp_config_payload, indent=2) + "\n",
    )

    return (plugin_json_path, mcp_config_json_path)


def install_project_advisor_skill(
    target_workspace: pathlib.Path | str,
    mirror_global: bool = True,
    global_dir: pathlib.Path | str | None = None,
) -> pathlib.Path:
    """Deploy the project-advisor skill to the target workspace and optionally mirror globally.

    Args:
        target_workspace: Path to target workspace root.
        mirror_global: Whether to mirror SKILL.md into global skills directory.
        global_dir: Optional custom global skills directory.

    Returns:
        Workspace pathlib.Path pointing to deployed SKILL.md.

    Raises:
        FileNotFoundError: If the bundled project-advisor template cannot be found.
    """
    template_path = TEMPLATES_DIR / "skills" / "project-advisor.md"
    if not template_path.is_file():
        raise FileNotFoundError(f"Project advisor skill template not found at {template_path}")

    content = template_path.read_text(encoding="utf-8")

    workspace = pathlib.Path(target_workspace)
    ws_skill_path = workspace / ".agents" / "skills" / "project-advisor" / "SKILL.md"
    _atomic_write_text(ws_skill_path, content)

    if mirror_global:
        if global_dir is None:
            global_skills_dir = pathlib.Path.home() / ".gemini" / "config" / "skills"
        else:
            global_skills_dir = pathlib.Path(global_dir)

        global_skill_path = global_skills_dir / "project-advisor" / "SKILL.md"
        _atomic_write_text(global_skill_path, content)

    return ws_skill_path


def prompt_mcp_selection(
    recommendations: list[dict[str, Any]],
    interactive: bool = False,
    input_func: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """Prompt user interactively to confirm recommended MCP servers.

    Args:
        recommendations: Recommended MCP server configurations.
        interactive: Boolean flag indicating if interactive selection is enabled.
        input_func: Optional input callable for dependency injection in tests.

    Returns:
        List of confirmed MCP server configuration dictionaries.
    """
    if not recommendations or not interactive:
        return []

    ask = input_func if input_func is not None else input
    confirmed: list[dict[str, Any]] = []

    for rec in recommendations:
        name = rec.get("name", "")
        desc = rec.get("description", "")
        prompt_str = f"Enable MCP server '{name}' ({desc})? [Y/n]: "
        try:
            response = ask(prompt_str)
        except (EOFError, KeyboardInterrupt):
            break

        if response.strip().lower() in ("", "y", "yes"):
            confirmed.append(copy.deepcopy(rec))

    return confirmed
