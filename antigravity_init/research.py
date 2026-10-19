"""SOTA research synchronizer and adversarial rubric compiler.

Zero-dependency module for fetching and compiling adversarial code review rubrics
and failure mode taxonomies for autonomous Antigravity agents.
"""

import copy
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
import warnings
from typing import Any

from antigravity_init import TEMPLATES_DIR

DEFAULT_CACHE_DIR: pathlib.Path = pathlib.Path.home() / ".cache" / "antigravity-research"
DEFAULT_RESEARCH_URL: str = ""
MAX_RESPONSE_BYTES: int = 5 * 1024 * 1024  # 5 MB safety limit

__all__ = [
    "DEFAULT_CACHE_DIR",
    "DEFAULT_RESEARCH_URL",
    "BUNDLED_TAXONOMY",
    "load_bundled_rubric",
    "validate_guidelines_schema",
    "fetch_sota_guidelines",
    "compile_adversarial_rubric",
    "save_research_artifacts",
]

BUNDLED_TAXONOMY: dict[str, Any] = {
    "version": "1.0.0",
    "description": "State-of-the-art adversarial failure mode taxonomy for autonomous LLM software engineering.",
    "categories": [
        {
            "name": "Sycophancy Detection",
            "description": "LLMs exhibit a strong tendency to validate peer subagents and user propositions uncritically, praising changes while overlooking critical structural defects.",
            "detection_rules": [
                "Uncritical Acceptance Check: Scrutinize edge-case claims and validate assumptions against actual execution.",
                "Rubber-Stamping Detection: Identify positive assertions lacking specific line numbers and verification command output.",
                "Independent Invariant Verification: Independently test or re-derive assertions rather than trusting the implementer's self-assessment.",
            ],
            "adversarial_questions": [
                "Did the review approve the PR without scrutinizing edge-case claims or validating assumptions against actual execution?",
                "Are there positive assertions without citing specific line numbers and verification command output?",
                "Did the reviewer independently verify assertions rather than trusting self-assessments?",
            ],
        },
        {
            "name": "Boundary Bug Catalog",
            "description": "Off-by-one errors, empty collections, path resolution subtleties, and boundary conditions that LLMs frequently miscalculate.",
            "detection_rules": [
                "Empty and Boundary Inputs: Verify empty strings, empty lists, None values, and zero-length buffers are handled gracefully without crashing.",
                "Worktree and Path Edge Cases: Verify path manipulations are safe against symlinks, relative paths, missing parent directories, and git worktrees.",
                "Off-By-One & Range Boundaries: Verify slicing operations, index offsets, and loop boundaries are inclusive/exclusive as specified.",
                "Concurrency & Re-entrancy: Verify shared resources or file writes are safe against race conditions or partial writes.",
            ],
            "adversarial_questions": [
                "Are empty strings, empty lists, None values, or zero-length inputs handled gracefully without crashing?",
                "Are path manipulations safe against symlinks, relative paths, missing parent directories, and git worktrees?",
                "Are slicing operations and loop boundaries strictly adhering to specifications?",
            ],
        },
        {
            "name": "Test Mock Leakage",
            "description": "Mocks that over-simplify behavior, mock the wrong layers, or allow tests to pass while runtime production code is broken.",
            "detection_rules": [
                "Over-Mocked Units: Ensure real runtime behavior is tested and internal units are not mocked excessively.",
                "Mock State Leakage: Ensure mocks and monkeypatches do not persist state across test cases or fail to clean up environment variables.",
                "Tautological Assertions: Verify test assertions check observable system side effects rather than mock return values.",
                "External Dependency Parity: Ensure mocked interfaces accurately mimic standard library or external system behaviors.",
            ],
            "adversarial_questions": [
                "Are tests mocking internal units to the point where real runtime components are never exercised?",
                "Do mocks persist state across test cases or fail to clean up environment variables?",
                "Are test assertions verifying real side effects or merely asserting mock calls?",
            ],
        },
        {
            "name": "Hallucinated Imports & APIs",
            "description": "APIs, modules, or functions that do not exist or are not available in the target runtime environment.",
            "detection_rules": [
                "Zero Third-Party Dependency Rule: Ensure all imports are strictly from the Python standard library unless explicitly allowed.",
                "Python Version Compatibility: Verify APIs are compatible with Python >= 3.9 without undeclared features.",
                "Non-Existent Attribute Calls: Verify all module functions and methods exist in official Python docs.",
                "Shadowed Standard Names: Verify local modules or variables do not shadow standard library modules.",
            ],
            "adversarial_questions": [
                "Are all imports strictly from the Python standard library without implicit dependencies?",
                "Are APIs verified against Python 3.9+ compatibility requirements?",
                "Does any module or variable shadow standard library names?",
            ],
        },
        {
            "name": "Untested Failure Branches & Error Handling",
            "description": "Code that assumes the happy path and fails catastrophically or silently suppresses critical errors.",
            "detection_rules": [
                "Subprocess & IO Error Traps: Properly catch and handle subprocess failures, network disconnects, file permissions, and timeouts.",
                "Silent Exception Swallowing: Eliminate bare except: or except Exception: pass clauses that hide defects.",
                "Idempotence & Recovery: Ensure operations can safely re-run multiple times after partial failure without corrupting state.",
            ],
            "adversarial_questions": [
                "Are subprocess failures, network disconnects, file permissions, and timeouts properly caught and handled?",
                "Are bare except: clauses or silent exception swallowers present?",
                "Can operations be safely re-run multiple times after mid-execution failure without corruption?",
            ],
        },
    ],
}


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


def load_bundled_rubric() -> str:
    """Read and return the bundled adversarial review rubric template.

    Returns:
        The rubric content as a markdown string.

    Raises:
        FileNotFoundError: If the bundled rubric template file does not exist.
    """
    rubric_path = TEMPLATES_DIR / "rubrics" / "adversarial_review.md"
    if not rubric_path.is_file():
        raise FileNotFoundError(f"Bundled rubric template not found: {rubric_path}")
    return rubric_path.read_text(encoding="utf-8")


def validate_guidelines_schema(data: Any) -> bool:
    """Validate whether input data conforms to the SOTA guidelines schema.

    Requirements:
    - Must be a dictionary.
    - Must contain a non-empty 'categories' list.
    - Each category must contain:
        - 'name': non-empty string.
        - 'description': string.
        - 'detection_rules': list.
        - 'adversarial_questions': list.

    Args:
        data: Arbitrary object to validate.

    Returns:
        True if data matches the schema, False otherwise.
    """
    if not isinstance(data, dict):
        return False

    categories = data.get("categories")
    if not isinstance(categories, list) or len(categories) == 0:
        return False

    for cat in categories:
        if not isinstance(cat, dict):
            return False

        name = cat.get("name")
        if not isinstance(name, str) or not name.strip():
            return False

        description = cat.get("description")
        if not isinstance(description, str):
            return False

        detection_rules = cat.get("detection_rules")
        if not isinstance(detection_rules, list):
            return False

        adversarial_questions = cat.get("adversarial_questions")
        if not isinstance(adversarial_questions, list):
            return False

    return True


def _load_cached_or_bundled(cache_file: pathlib.Path) -> dict[str, Any]:
    """Load SOTA guidelines from local cache if valid, otherwise return bundled taxonomy."""
    if cache_file.is_file():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if validate_guidelines_schema(data):
                return data
        except Exception:
            pass
    return copy.deepcopy(BUNDLED_TAXONOMY)


def fetch_sota_guidelines(
    url: str | None = None,
    cache_dir: pathlib.Path | None = None,
    offline: bool = False,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    """Fetch SOTA failure mode guidelines from a remote URL or local cache/bundled taxonomy.

    Args:
        url: Remote URL pointing to a JSON guidelines file.
        cache_dir: Directory where cached guidelines are saved (default: DEFAULT_CACHE_DIR).
        offline: If True, skips network requests and loads from cache or bundled taxonomy.
        timeout_sec: Network request timeout in seconds.

    Returns:
        Structured guidelines taxonomy dictionary.
    """
    effective_cache_dir = cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR
    cache_file = effective_cache_dir / "sota_guidelines.json"

    if offline or not url:
        return _load_cached_or_bundled(cache_file)

    parsed_url = urllib.parse.urlsplit(url)
    if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.netloc:
        warnings.warn(
            f"Unsupported or invalid URL '{url}': only HTTP and HTTPS schemes with a valid host are supported.",
            UserWarning,
        )
        return _load_cached_or_bundled(cache_file)

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "antigravity-project-initialization-helper/research"},
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw_bytes = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw_bytes) > MAX_RESPONSE_BYTES:
                warnings.warn(
                    f"Remote guidelines response exceeded {MAX_RESPONSE_BYTES} bytes limit.",
                    UserWarning,
                )
                return _load_cached_or_bundled(cache_file)
            raw_body = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_body)
        if validate_guidelines_schema(parsed):
            try:
                _atomic_write_text(cache_file, json.dumps(parsed, indent=2))
            except OSError as err:
                warnings.warn(f"Failed to cache SOTA guidelines to {cache_file}: {err}", UserWarning)
            return parsed
        else:
            warnings.warn("Downloaded SOTA guidelines failed schema validation.", UserWarning)
    except Exception as exc:
        warnings.warn(f"Failed to fetch SOTA guidelines from {url}: {exc}", UserWarning)

    return _load_cached_or_bundled(cache_file)


def compile_adversarial_rubric(guidelines_data: dict[str, Any] | None = None) -> str:
    """Compile structured taxonomy data into an adversarial review markdown document.

    If guidelines_data is None or invalid, falls back to load_bundled_rubric().

    Args:
        guidelines_data: Structured guidelines dictionary.

    Returns:
        Formatted markdown rubric string.
    """
    if guidelines_data is None or not validate_guidelines_schema(guidelines_data):
        return load_bundled_rubric()

    sections = [
        "# Adversarial Code Review Rubric & Failure Mode Taxonomy",
        "",
        "This rubric provides an adversarial evaluation checklist grounded in state-of-the-art research on LLM coding failures. Reviewers must rigorously interrogate changes using these categories.",
    ]

    for idx, category in enumerate(guidelines_data.get("categories", []), start=1):
        sections.append("")
        sections.append("---")
        sections.append("")
        name = category.get("name", f"Category {idx}").strip()
        sections.append(f"## {idx}. {name}")
        desc = category.get("description", "").strip()
        if desc:
            sections.append(desc)
        for rule in category.get("detection_rules", []):
            rule_str = str(rule).strip()
            if not rule_str:
                continue
            if rule_str.startswith("**"):
                sections.append(f"- [ ] {rule_str}")
            else:
                sections.append(f"- [ ] **{rule_str}**")
        for q in category.get("adversarial_questions", []):
            q_str = str(q).strip()
            if not q_str:
                continue
            sections.append(f"- [ ] *Interrogation:* {q_str}")

    sections.append("")
    return "\n".join(sections)


def save_research_artifacts(
    target_workspace: pathlib.Path | str,
    rubric_content: str,
    raw_data: dict[str, Any] | None = None,
) -> pathlib.Path:
    """Write research artifacts into target workspace under .agents/scratch/research/.

    Args:
        target_workspace: Root directory of target repository/workspace.
        rubric_content: Adversarial review rubric markdown string.
        raw_data: Optional raw structured guidelines dictionary.

    Returns:
        Path to the written adversarial_review.md file.
    """
    workspace = pathlib.Path(target_workspace)
    research_dir = workspace / ".agents" / "scratch" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)

    rubric_path = research_dir / "adversarial_review.md"
    _atomic_write_text(rubric_path, rubric_content, encoding="utf-8")

    if raw_data is not None:
        raw_json_path = research_dir / "sota_guidelines.json"
        _atomic_write_text(raw_json_path, json.dumps(raw_data, indent=2), encoding="utf-8")

    return rubric_path
