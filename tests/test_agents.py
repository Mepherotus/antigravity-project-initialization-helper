"""Unit tests for antigravity_init.agents module."""

import pathlib
import tempfile
import unittest
from unittest import mock

from antigravity_init import TEMPLATES_DIR


class TestAgentConstants(unittest.TestCase):
    """Test exported constants in antigravity_init.agents."""

    def test_agent_names_list(self):
        from antigravity_init.agents import AGENT_NAMES

        expected_names = [
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
        self.assertEqual(AGENT_NAMES, expected_names)
        self.assertEqual(len(AGENT_NAMES), 9)
        self.assertEqual(len(set(AGENT_NAMES)), 9, "AGENT_NAMES must not contain duplicates")

    def test_quality_reviewer_names_list(self):
        from antigravity_init.agents import AGENT_NAMES, QUALITY_REVIEWER_NAMES

        expected_reviewers = [
            "sp-quality-reviewer-claude",
            "sp-quality-reviewer-argon",
            "sp-quality-reviewer-flash",
        ]
        self.assertEqual(QUALITY_REVIEWER_NAMES, expected_reviewers)
        self.assertEqual(len(QUALITY_REVIEWER_NAMES), 3)
        for reviewer in QUALITY_REVIEWER_NAMES:
            self.assertIn(
                reviewer,
                AGENT_NAMES,
                f"Reviewer {reviewer} must be present in AGENT_NAMES",
            )

    def test_rubric_injection_header(self):
        from antigravity_init.agents import RUBRIC_INJECTION_HEADER

        self.assertEqual(RUBRIC_INJECTION_HEADER, "<!-- ADVERSARIAL-REVIEW-RUBRIC -->")


class TestGetAgentDefinitions(unittest.TestCase):
    """Test get_agent_definitions loading and rubric injection."""

    def test_get_agent_definitions_returns_all_nine_agents(self):
        from antigravity_init.agents import AGENT_NAMES, get_agent_definitions

        definitions = get_agent_definitions()
        self.assertIsInstance(definitions, dict)
        self.assertEqual(set(definitions.keys()), set(AGENT_NAMES))
        self.assertEqual(len(definitions), 9)

    def test_get_agent_definitions_preserves_frontmatter(self):
        from antigravity_init.agents import AGENT_NAMES, get_agent_definitions

        definitions = get_agent_definitions()
        for name in AGENT_NAMES:
            content = definitions[name]
            self.assertTrue(
                content.startswith("---"),
                f"Agent {name} definition must begin with YAML frontmatter delimiter",
            )
            parts = content.split("---", 2)
            self.assertGreaterEqual(
                len(parts), 3, f"Agent {name} frontmatter must have closing delimiter"
            )
            frontmatter = parts[1]
            self.assertIn(f"name: {name}", frontmatter)
            self.assertIn("subagent: true", frontmatter)
            self.assertIn("model:", frontmatter)
            self.assertIn("tools:", frontmatter)

    def test_get_agent_definitions_without_rubric_has_no_injection(self):
        from antigravity_init.agents import (
            AGENT_NAMES,
            RUBRIC_INJECTION_HEADER,
            get_agent_definitions,
        )

        definitions = get_agent_definitions()
        for name in AGENT_NAMES:
            content = definitions[name]
            self.assertNotIn(
                RUBRIC_INJECTION_HEADER,
                content,
                f"Agent {name} should not contain injection header when rubric is empty",
            )
            self.assertNotIn(
                "Mandatory Adversarial Review Checklist",
                content,
                f"Agent {name} should not contain rubric title when rubric is empty",
            )

    def test_get_agent_definitions_whitespace_rubric_has_no_injection(self):
        from antigravity_init.agents import (
            AGENT_NAMES,
            RUBRIC_INJECTION_HEADER,
            get_agent_definitions,
        )

        definitions = get_agent_definitions("   \n\t  ")
        for name in AGENT_NAMES:
            content = definitions[name]
            self.assertNotIn(
                RUBRIC_INJECTION_HEADER,
                content,
                f"Agent {name} should not contain injection header for whitespace rubric",
            )

    def test_get_agent_definitions_none_rubric_has_no_injection(self):
        from antigravity_init.agents import (
            AGENT_NAMES,
            RUBRIC_INJECTION_HEADER,
            get_agent_definitions,
        )

        definitions = get_agent_definitions(None)  # type: ignore[arg-type]
        for name in AGENT_NAMES:
            content = definitions[name]
            self.assertNotIn(
                RUBRIC_INJECTION_HEADER,
                content,
                f"Agent {name} should not contain injection header for None rubric",
            )

    def test_get_agent_definitions_injects_rubric_only_into_quality_reviewers(self):
        from antigravity_init.agents import (
            AGENT_NAMES,
            QUALITY_REVIEWER_NAMES,
            RUBRIC_INJECTION_HEADER,
            get_agent_definitions,
        )

        test_rubric = "### SOTA Checklist\n- [ ] Check for sycophancy"
        definitions = get_agent_definitions(adversarial_rubric=test_rubric)

        for name in AGENT_NAMES:
            content = definitions[name]
            if name in QUALITY_REVIEWER_NAMES:
                self.assertIn(
                    RUBRIC_INJECTION_HEADER,
                    content,
                    f"Quality reviewer {name} must have injection header",
                )
                self.assertIn(
                    "## Mandatory Adversarial Review Checklist & Taxonomy",
                    content,
                    f"Quality reviewer {name} must have checklist header",
                )
                self.assertIn(
                    test_rubric,
                    content,
                    f"Quality reviewer {name} must contain the injected rubric",
                )
                # Ensure frontmatter is still intact
                self.assertTrue(content.startswith("---"))
                self.assertIn(f"name: {name}", content)
            else:
                self.assertNotIn(
                    RUBRIC_INJECTION_HEADER,
                    content,
                    f"Non-reviewer agent {name} must NOT contain injection header",
                )
                self.assertNotIn(
                    "Mandatory Adversarial Review Checklist",
                    content,
                    f"Non-reviewer agent {name} must NOT contain checklist header",
                )
                self.assertNotIn(
                    test_rubric,
                    content,
                    f"Non-reviewer agent {name} must NOT contain the rubric",
                )

    def test_get_agent_definitions_rubric_injection_idempotence(self):
        from antigravity_init.agents import (
            QUALITY_REVIEWER_NAMES,
            RUBRIC_INJECTION_HEADER,
            get_agent_definitions,
        )

        test_rubric = "### SOTA Checklist\n- [ ] Check for sycophancy"

        # Simulate template already having the header
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_agents_dir = pathlib.Path(tmp_dir) / "agents"
            tmp_agents_dir.mkdir(parents=True)

            # Copy real templates but pre-inject header into one reviewer
            real_agents_dir = TEMPLATES_DIR / "agents"
            for agent_file in real_agents_dir.glob("*.md"):
                content = agent_file.read_text(encoding="utf-8")
                if agent_file.stem == "sp-quality-reviewer-argon":
                    content = (
                        content.rstrip()
                        + f"\n\n---\n{RUBRIC_INJECTION_HEADER}\n"
                        f"## Mandatory Adversarial Review Checklist & Taxonomy\n"
                        f"{test_rubric}\n"
                    )
                (tmp_agents_dir / agent_file.name).write_text(content, encoding="utf-8")

            with mock.patch("antigravity_init.agents.TEMPLATES_DIR", pathlib.Path(tmp_dir)):
                definitions = get_agent_definitions(adversarial_rubric=test_rubric)
                argon_content = definitions["sp-quality-reviewer-argon"]

                # Should appear exactly once, not twice
                count = argon_content.count(RUBRIC_INJECTION_HEADER)
                self.assertEqual(
                    count,
                    1,
                    "Pre-injected template must not have rubric header duplicated",
                )

    def test_get_agent_definitions_missing_template_raises(self):
        from antigravity_init.agents import get_agent_definitions

        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_agents_dir = pathlib.Path(tmp_dir) / "agents"
            empty_agents_dir.mkdir()
            with mock.patch("antigravity_init.agents.TEMPLATES_DIR", pathlib.Path(tmp_dir)):
                with self.assertRaises(FileNotFoundError):
                    get_agent_definitions()


class TestWriteAgents(unittest.TestCase):
    """Test write_agents writing to workspace and mirroring globally."""

    def test_write_agents_workspace_target(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir:
            workspace = pathlib.Path(ws_dir)
            written = write_agents(workspace, mirror_global=False)

            agents_dir = workspace / ".agents" / "agents"
            self.assertTrue(agents_dir.is_dir(), ".agents/agents must exist")
            self.assertEqual(len(written), 9)

            for name in AGENT_NAMES:
                expected_file = agents_dir / f"{name}.md"
                self.assertIn(expected_file, written)
                self.assertTrue(expected_file.is_file())
                content = expected_file.read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", content)

    def test_write_agents_with_adversarial_rubric(self):
        from antigravity_init.agents import (
            QUALITY_REVIEWER_NAMES,
            RUBRIC_INJECTION_HEADER,
            write_agents,
        )

        test_rubric = "## Failure Taxonomy\n- Mock leakage"
        with tempfile.TemporaryDirectory() as ws_dir:
            workspace = pathlib.Path(ws_dir)
            write_agents(workspace, adversarial_rubric=test_rubric, mirror_global=False)

            agents_dir = workspace / ".agents" / "agents"
            for reviewer in QUALITY_REVIEWER_NAMES:
                content = (agents_dir / f"{reviewer}.md").read_text(encoding="utf-8")
                self.assertIn(RUBRIC_INJECTION_HEADER, content)
                self.assertIn(test_rubric, content)

            non_reviewer_content = (agents_dir / "sp-architect-argon.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(RUBRIC_INJECTION_HEADER, non_reviewer_content)
            self.assertNotIn(test_rubric, non_reviewer_content)

    def test_write_agents_mirror_global_with_explicit_dirs(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir, tempfile.TemporaryDirectory() as g1_dir, tempfile.TemporaryDirectory() as g2_dir:
            workspace = pathlib.Path(ws_dir)
            global_1 = pathlib.Path(g1_dir) / "agents"
            global_2 = pathlib.Path(g2_dir) / "agents"

            written = write_agents(
                workspace,
                mirror_global=True,
                global_dirs=[global_1, global_2],
            )

            self.assertEqual(len(written), 9)
            # Verify workspace target
            for name in AGENT_NAMES:
                self.assertTrue((workspace / ".agents" / "agents" / f"{name}.md").is_file())

            # Verify global mirrors
            for name in AGENT_NAMES:
                file_1 = global_1 / f"{name}.md"
                file_2 = global_2 / f"{name}.md"
                self.assertTrue(file_1.is_file(), f"{file_1} must be created")
                self.assertTrue(file_2.is_file(), f"{file_2} must be created")
                self.assertEqual(
                    file_1.read_text(encoding="utf-8"),
                    (workspace / ".agents" / "agents" / f"{name}.md").read_text(
                        encoding="utf-8"
                    ),
                )

    def test_write_agents_mirror_global_false_does_not_touch_global(self):
        from antigravity_init.agents import write_agents

        with tempfile.TemporaryDirectory() as ws_dir, tempfile.TemporaryDirectory() as g_dir:
            workspace = pathlib.Path(ws_dir)
            global_dir = pathlib.Path(g_dir) / "agents"

            write_agents(
                workspace,
                mirror_global=False,
                global_dirs=[global_dir],
            )

            self.assertFalse(
                global_dir.exists(),
                "global_dir must not be created when mirror_global=False",
            )

    def test_write_agents_mirror_global_default_paths(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir, tempfile.TemporaryDirectory() as home_dir:
            workspace = pathlib.Path(ws_dir)
            fake_home = pathlib.Path(home_dir)

            with mock.patch("pathlib.Path.home", return_value=fake_home):
                write_agents(workspace, mirror_global=True)

                dest_gemini = fake_home / ".gemini" / "config" / "agents"
                dest_agents = fake_home / ".agents" / "agents"

                self.assertTrue(dest_gemini.is_dir())
                self.assertTrue(dest_agents.is_dir())

                for name in AGENT_NAMES:
                    self.assertTrue((dest_gemini / f"{name}.md").is_file())
                    self.assertTrue((dest_agents / f"{name}.md").is_file())

    def test_write_agents_idempotent_overwrites(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir:
            workspace = pathlib.Path(ws_dir)
            write_agents(workspace, adversarial_rubric="First run", mirror_global=False)
            # Re-run with updated rubric
            write_agents(workspace, adversarial_rubric="Second run", mirror_global=False)

            for name in AGENT_NAMES:
                target = workspace / ".agents" / "agents" / f"{name}.md"
                self.assertTrue(target.is_file())

            reviewer_content = (
                workspace / ".agents" / "agents" / "sp-quality-reviewer-flash.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Second run", reviewer_content)
            self.assertNotIn("First run", reviewer_content)

    def test_write_agents_accepts_string_workspace_and_resolves_canonical_path(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir:
            # Pass target_workspace as a raw string
            written = write_agents(ws_dir, mirror_global=False)
            self.assertEqual(len(written), 9)

            for path in written:
                self.assertTrue(path.is_absolute())
                self.assertTrue(path.is_file())
                self.assertEqual(path, path.resolve())

    def test_write_agents_accepts_string_global_dirs(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as ws_dir, tempfile.TemporaryDirectory() as g_dir:
            global_dir_str = str(pathlib.Path(g_dir) / "global_str_agents")
            written = write_agents(
                ws_dir,
                mirror_global=True,
                global_dirs=[global_dir_str],
            )
            self.assertEqual(len(written), 9)

            for name in AGENT_NAMES:
                mirrored_file = pathlib.Path(global_dir_str) / f"{name}.md"
                self.assertTrue(mirrored_file.is_file())

    def test_write_agents_creates_deeply_nested_nonexistent_workspace(self):
        from antigravity_init.agents import AGENT_NAMES, write_agents

        with tempfile.TemporaryDirectory() as base_dir:
            deep_workspace = pathlib.Path(base_dir) / "level1" / "level2" / "level3"
            self.assertFalse(deep_workspace.exists())

            written = write_agents(deep_workspace, mirror_global=False)
            self.assertEqual(len(written), 9)
            self.assertTrue(deep_workspace.is_dir())
            self.assertTrue((deep_workspace / ".agents" / "agents").is_dir())

    def test_write_agents_utf8_encoding_preservation(self):
        from antigravity_init.agents import write_agents

        unicode_rubric = "## 🧪 Internationalization Audit\n- 日本語チェック\n- 🛡️ 安全性確認"
        with tempfile.TemporaryDirectory() as ws_dir:
            write_agents(ws_dir, adversarial_rubric=unicode_rubric, mirror_global=False)
            reviewer_file = (
                pathlib.Path(ws_dir)
                / ".agents"
                / "agents"
                / "sp-quality-reviewer-flash.md"
            )
            content = reviewer_file.read_text(encoding="utf-8")
            self.assertIn("🧪 Internationalization Audit", content)
            self.assertIn("日本語チェック", content)
            self.assertIn("🛡️ 安全性確認", content)

    def test_atomic_write_cleans_up_on_failure(self):
        from antigravity_init.agents import _atomic_write_text

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = pathlib.Path(tmp_dir) / "sub" / "fail.md"

            # Mock replace to simulate an unexpected error during atomic rename
            with mock.patch("pathlib.Path.replace", side_effect=OSError("Disk write simulated failure")):
                with self.assertRaises(OSError):
                    _atomic_write_text(target_path, "temporary content")

            # Verify target was not created and no temporary dotfiles leaked
            self.assertFalse(target_path.exists())
            leftover_files = list(target_path.parent.glob(".*"))
            self.assertEqual(leftover_files, [], "No temporary sibling dotfiles should remain after error")


if __name__ == "__main__":
    unittest.main()
