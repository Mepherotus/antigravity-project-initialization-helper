"""Unit tests for the project-advisor skill markdown template."""

import pathlib
import unittest

from antigravity_init import TEMPLATES_DIR


class TestProjectAdvisorSkillTemplate(unittest.TestCase):
    """Test the bundled project-advisor skill markdown runbook."""

    @classmethod
    def setUpClass(cls):
        cls.template_path = TEMPLATES_DIR / "skills" / "project-advisor.md"
        if not cls.template_path.is_file():
            raise FileNotFoundError(f"Template not found at {cls.template_path}")
        cls.raw_content = cls.template_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter using standard library
        parts = cls.raw_content.split("---", 2)
        if len(parts) < 3 or not cls.raw_content.startswith("---"):
            cls.frontmatter = {}
            cls.body = cls.raw_content
        else:
            frontmatter_dict: dict[str, str] = {}
            for line in parts[1].strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter_dict[key.strip()] = val.strip()
            cls.frontmatter = frontmatter_dict
            cls.body = parts[2]

    def test_template_file_exists(self):
        """Assert template exists in templates/skills/."""
        self.assertTrue(self.template_path.is_file())

    def test_frontmatter_validity_and_keys(self):
        """Assert frontmatter contains name: project-advisor and non-empty description."""
        self.assertIsInstance(self.frontmatter, dict, "Frontmatter must parse as a dictionary")
        self.assertEqual(self.frontmatter.get("name"), "project-advisor")
        description = self.frontmatter.get("description")
        self.assertIsInstance(description, str)
        self.assertTrue(len(description.strip()) > 0, "Description must be non-empty")

    def test_phase_1_context_isolation_audit(self):
        """Assert Phase 1 details view_file, .git/info/exclude, worktree handling, all 7 excludes, run_command, git status --porcelain, and @sp- leaks."""
        body = self.body
        self.assertIn("Phase 1: Context Isolation", body)
        self.assertIn("view_file", body)
        self.assertIn(".git/info/exclude", body)
        # Worktree resolution instructions
        self.assertIn("worktree", body.lower())

        # All 7 mandatory quarantine exclude entries
        required_excludes = [
            ".agents/scratch/",
            ".agents/rules/",
            ".agents/agents/",
            ".agents/skills/",
            ".agents/plugins/",
            "docs/superpowers/",
            "docs/plans/",
        ]
        for entry in required_excludes:
            self.assertIn(entry, body, f"Phase 1 must require exclusion entry: {entry}")

        # Git status and leak checks
        self.assertIn("run_command", body)
        self.assertIn("git status --porcelain", body)
        self.assertIn("@sp-", body, "Phase 1 must instruct checking for @sp- leak tags")
        self.assertIn("[@sp-", body, "Phase 1 must instruct checking for [@sp- leak tags")

    def test_phase_2_active_quota_mode_audit(self):
        """Assert Phase 2 details view_file, quota_mode.env, and the 3 valid modes with routing details."""
        body = self.body
        self.assertIn("Phase 2: Active Quota Mode Audit", body)
        self.assertIn("view_file", body)
        self.assertIn(".agents/scratch/quota_mode.env", body)

        for mode in ["balanced", "low-claude", "flash-saver"]:
            self.assertIn(mode, body, f"Phase 2 must document '{mode}' quota mode")

    def test_phase_3_subagent_and_mcp_freshness_audit(self):
        """Assert Phase 3 details all 9 subagent files, workspace-mcp plugin and mcp_config.json, JSON validation, and mcpServers."""
        body = self.body
        self.assertIn("Phase 3: Subagent & MCP Freshness Audit", body)
        self.assertIn(".agents/agents/", body)

        expected_agents = [
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
        for agent in expected_agents:
            self.assertIn(agent, body, f"Phase 3 must audit subagent: {agent}")

        self.assertIn(".agents/plugins/workspace-mcp/plugin.json", body)
        self.assertIn(".agents/plugins/workspace-mcp/mcp_config.json", body)
        self.assertIn("mcpServers", body)

    def test_phase_4_remediation_and_doctor_mode(self):
        """Assert Phase 4 details remediation commands: git reset, antigravity-init --doctor, restoring excludes/agents/quota."""
        body = self.body
        self.assertIn("Phase 4: Remediation Actions", body)
        self.assertIn("git reset HEAD .agents/scratch/", body)
        self.assertTrue(
            "antigravity-init --doctor" in body or "python3 -m antigravity_init --doctor" in body,
            "Phase 4 must specify running doctor mode via 'antigravity-init --doctor' or 'python3 -m antigravity_init --doctor'",
        )
        self.assertIn(".git/info/exclude", body)
        self.assertIn("quota_mode.env", body)


if __name__ == "__main__":
    unittest.main()
