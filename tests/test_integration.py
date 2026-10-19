"""End-to-end integration test suite for Antigravity Project Initialization Helper.

Verifies complete workspace initialization, context isolation, git quarantine,
doctor verification, mode switching, and init.sh shell bootstrap in real Git repositories.
"""

from __future__ import annotations

import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from antigravity_init import agents, fetcher, poison_guard
from antigravity_init.cli import main, run_doctor, run_init

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INIT_SH = REPO_ROOT / "init.sh"


class TestEndToEndIntegration(unittest.TestCase):
    """End-to-end integration test suite for workspace lifecycle."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create shared upstream mock superpowers repository and isolated home."""
        cls.shared_temp_dir = tempfile.TemporaryDirectory()
        cls.base_path = pathlib.Path(cls.shared_temp_dir.name).resolve()

        cls.temp_home = cls.base_path / "home"
        cls.temp_home.mkdir(parents=True, exist_ok=True)

        # Create mock upstream superpowers repository
        cls.mock_upstream = cls.base_path / "mock-superpowers-upstream"
        cls.mock_upstream.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=cls.mock_upstream, check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "config", "user.name", "Test Upstream"],
            cwd=cls.mock_upstream,
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "config", "user.email", "upstream@example.com"],
            cwd=cls.mock_upstream,
            check=True,
            capture_output=True,
            timeout=15,
        )

        skills_dir = cls.mock_upstream / "skills"
        all_skills = [
            "brainstorming",
            "writing-plans",
            "subagent-driven-development",
            "executing-plans",
            "requesting-code-review",
            "systematic-debugging",
        ]
        for skill in all_skills:
            s_path = skills_dir / skill
            s_path.mkdir(parents=True, exist_ok=True)
            content = (
                f"# {skill} Skill\n\n"
                f"Spec: docs/superpowers/specs/{skill}.md and docs/specs/{skill}.md\n"
                f"Plan: docs/superpowers/plans/{skill}.md and docs/plans/{skill}.md\n"
            )
            (s_path / "SKILL.md").write_text(content, encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=cls.mock_upstream, check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "commit", "-m", "Initial mock upstream superpowers"],
            cwd=cls.mock_upstream,
            check=True,
            capture_output=True,
            timeout=15,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared upstream mock repository."""
        cls.shared_temp_dir.cleanup()

    def setUp(self) -> None:
        """Create a fresh temporary git repository workspace for each test."""
        self.ws_dir = tempfile.TemporaryDirectory()
        self.ws = pathlib.Path(self.ws_dir.name).resolve()

        subprocess.run(["git", "init"], cwd=self.ws, check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.ws,
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.ws,
            check=True,
            capture_output=True,
            timeout=15,
        )

        # Create an initial commit so HEAD exists
        (self.ws / "README.md").write_text("# Test Workspace Repository\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.ws, check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "commit", "-m", "Initial workspace commit"],
            cwd=self.ws,
            check=True,
            capture_output=True,
            timeout=15,
        )

        self.isolated_cache = self.temp_home / ".cache" / "antigravity" / "superpowers"

    def tearDown(self) -> None:
        """Clean up workspace."""
        self.ws_dir.cleanup()

    def test_end_to_end_initialization_clean_workspace(self) -> None:
        """Verify full end-to-end workspace initialization, context isolation, and doctor verification."""
        with patch.dict(os.environ, {"HOME": str(self.temp_home)}), \
             patch("antigravity_init.fetcher.DEFAULT_CACHE_DIR", self.isolated_cache), \
             patch("sys.stdout", new_callable=io.StringIO):
            code = main([
                "--workspace", str(self.ws),
                "--superpowers-url", str(self.mock_upstream),
                "--no-web",
                "--no-global-sync",
            ])
        self.assertEqual(code, 0)

        # 1. Verify .git/info/exclude contains all DEFAULT_EXCLUDES under the Ultra header
        exclude_file = self.ws / ".git" / "info" / "exclude"
        self.assertTrue(exclude_file.is_file(), ".git/info/exclude must exist")
        exclude_content = exclude_file.read_text(encoding="utf-8")
        self.assertIn(poison_guard.EXCLUDE_HEADER, exclude_content)
        for pattern in poison_guard.DEFAULT_EXCLUDES:
            self.assertIn(pattern, exclude_content)

        # 2. Verify .agents/rules/ultra-routing.md exists with frontmatter
        rules_file = self.ws / ".agents" / "rules" / "ultra-routing.md"
        self.assertTrue(rules_file.is_file(), "ultra-routing.md must exist")
        rules_content = rules_file.read_text(encoding="utf-8")
        self.assertTrue(rules_content.startswith("---"), "ultra-routing.md must contain frontmatter")
        self.assertIn("QUOTA_MODE", rules_content)

        # 3. Verify .agents/scratch/quota_mode.env contains QUOTA_MODE=balanced
        quota_env = self.ws / ".agents" / "scratch" / "quota_mode.env"
        self.assertTrue(quota_env.is_file(), "quota_mode.env must exist")
        self.assertIn("QUOTA_MODE=balanced", quota_env.read_text(encoding="utf-8"))

        # 4. Verify .agents/scratch/research/adversarial_review.md exists
        rubric_file = self.ws / ".agents" / "scratch" / "research" / "adversarial_review.md"
        self.assertTrue(rubric_file.is_file(), "adversarial_review.md must exist")
        self.assertGreater(rubric_file.stat().st_size, 0)

        # 5. Verify all 9 model-locked subagents exist under .agents/agents/
        for agent_name in agents.AGENT_NAMES:
            agent_path = self.ws / ".agents" / "agents" / f"{agent_name}.md"
            self.assertTrue(agent_path.is_file(), f"Subagent {agent_name}.md must exist")
            agent_text = agent_path.read_text(encoding="utf-8")
            self.assertTrue(agent_text.startswith("---"))
            if agent_name in agents.QUALITY_REVIEWER_NAMES:
                self.assertIn(agents.RUBRIC_INJECTION_HEADER, agent_text)

        # 6. Verify workspace MCP plugin and configuration exist
        plugin_json = self.ws / ".agents" / "plugins" / "workspace-mcp" / "plugin.json"
        mcp_config = self.ws / ".agents" / "plugins" / "workspace-mcp" / "mcp_config.json"
        self.assertTrue(plugin_json.is_file(), "plugin.json must exist")
        self.assertTrue(mcp_config.is_file(), "mcp_config.json must exist")

        # 7. Verify project advisor skill exists
        advisor_skill = self.ws / ".agents" / "skills" / "project-advisor" / "SKILL.md"
        self.assertTrue(advisor_skill.is_file(), "project-advisor SKILL.md must exist")

        # 8. Verify transformed skills under .agents/skills/
        ws_skills = self.ws / ".agents" / "skills"
        for core in fetcher.CORE_SKILLS:
            c_skill = ws_skills / core / "SKILL.md"
            self.assertTrue(c_skill.is_file(), f"Core skill {core} must exist")
            c_text = c_skill.read_text(encoding="utf-8")
            self.assertIn(fetcher.ULTRA_ADAPTER_HEADER, c_text)
            self.assertIn(".agents/scratch/specs/", c_text)
            self.assertIn(".agents/scratch/plans/", c_text)
            self.assertNotIn("docs/superpowers/specs/", c_text)
            self.assertNotIn("docs/specs/", c_text)
            self.assertNotIn("docs/superpowers/plans/", c_text)
            self.assertNotIn("docs/plans/", c_text)

        non_core = ws_skills / "systematic-debugging" / "SKILL.md"
        self.assertTrue(non_core.is_file(), "Non-core skill systematic-debugging must exist")
        non_core_text = non_core.read_text(encoding="utf-8")
        self.assertNotIn(fetcher.ULTRA_ADAPTER_HEADER, non_core_text)
        self.assertIn(".agents/scratch/specs/", non_core_text)
        self.assertIn(".agents/scratch/plans/", non_core_text)

        # 9. Quarantine verification: git status --porcelain shows zero untracked scratch files
        git_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.ws,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        st_lines = git_res.stdout.splitlines()
        scratch_leaks = [line for line in st_lines if ".agents/scratch" in line]
        self.assertEqual(scratch_leaks, [], f"Scratch files leaked into git status: {scratch_leaks}")

        # 10. Doctor verification: run_doctor returns exit code 0
        with patch("sys.stdout", new_callable=io.StringIO):
            doctor_exit = run_doctor(self.ws)
        self.assertEqual(doctor_exit, 0, "run_doctor must return exit code 0 on healthy workspace")

    def test_doctor_detects_leaked_staged_scratch_file(self) -> None:
        """Verify that staging a quarantined scratch file triggers doctor failure with exit code 1."""
        with patch.dict(os.environ, {"HOME": str(self.temp_home)}), \
             patch("antigravity_init.fetcher.DEFAULT_CACHE_DIR", self.isolated_cache), \
             patch("sys.stdout", new_callable=io.StringIO):
            code = main([
                "--workspace", str(self.ws),
                "--superpowers-url", str(self.mock_upstream),
                "--no-web",
                "--no-global-sync",
            ])
        self.assertEqual(code, 0)

        # In initialized workspace, create .agents/scratch/plans/leaked_plan.md and force-stage it
        leaked_plan = self.ws / ".agents" / "scratch" / "plans" / "leaked_plan.md"
        leaked_plan.parent.mkdir(parents=True, exist_ok=True)
        leaked_plan.write_text("# Leaked Implementation Plan\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-f", ".agents/scratch/plans/leaked_plan.md"],
            cwd=self.ws,
            check=True,
            capture_output=True,
            timeout=15,
        )

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            doctor_exit = run_doctor(self.ws)

        self.assertEqual(doctor_exit, 1, "Doctor must return 1 when scratch file is staged")
        output = fake_out.getvalue()
        self.assertIn("leaked_plan.md", output)
        self.assertIn("Leaked staged files matching quarantine", output)

    def test_doctor_detects_missing_subagent(self) -> None:
        """Verify that deleting a subagent definition triggers doctor failure with exit code 1."""
        with patch.dict(os.environ, {"HOME": str(self.temp_home)}), \
             patch("antigravity_init.fetcher.DEFAULT_CACHE_DIR", self.isolated_cache), \
             patch("sys.stdout", new_callable=io.StringIO):
            code = main([
                "--workspace", str(self.ws),
                "--superpowers-url", str(self.mock_upstream),
                "--no-web",
                "--no-global-sync",
            ])
        self.assertEqual(code, 0)

        # Delete one subagent file
        missing_agent = self.ws / ".agents" / "agents" / "sp-architect-argon.md"
        self.assertTrue(missing_agent.is_file(), "Subagent file must exist before deletion")
        missing_agent.unlink()

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            doctor_exit = run_doctor(self.ws)

        self.assertEqual(doctor_exit, 1, "Doctor must return 1 when subagent is missing")
        output = fake_out.getvalue()
        self.assertIn("sp-architect-argon", output)
        self.assertIn("Missing subagent markdown files", output)

    def test_mode_switching_and_idempotence(self) -> None:
        """Verify running init again with --mode low-claude updates quota_mode.env and passes doctor."""
        with patch.dict(os.environ, {"HOME": str(self.temp_home)}), \
             patch("antigravity_init.fetcher.DEFAULT_CACHE_DIR", self.isolated_cache), \
             patch("sys.stdout", new_callable=io.StringIO):
            code1 = main([
                "--workspace", str(self.ws),
                "--superpowers-url", str(self.mock_upstream),
                "--no-web",
                "--no-global-sync",
            ])
            self.assertEqual(code1, 0)

            # Re-run init with low-claude mode
            code2 = main([
                "--workspace", str(self.ws),
                "--superpowers-url", str(self.mock_upstream),
                "--mode", "low-claude",
                "--no-web",
                "--no-global-sync",
            ])
            self.assertEqual(code2, 0)

        quota_env = self.ws / ".agents" / "scratch" / "quota_mode.env"
        self.assertIn("QUOTA_MODE=low-claude", quota_env.read_text(encoding="utf-8"))

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            doctor_exit = run_doctor(self.ws)

        self.assertEqual(doctor_exit, 0, "Doctor must return 0 after mode switch")
        output = fake_out.getvalue()
        self.assertIn("Active quota mode: low-claude", output)

    def test_init_sh_end_to_end(self) -> None:
        """Verify init.sh bootstrap executes end-to-end and passes doctor check."""
        env = os.environ.copy()
        env["HOME"] = str(self.temp_home)

        # Run ./init.sh to initialize workspace
        init_res = subprocess.run(
            [
                str(INIT_SH),
                "--workspace", str(self.ws),
                "--no-web",
                "--no-global-sync",
                "--superpowers-url", str(self.mock_upstream),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=30,
        )
        self.assertEqual(
            init_res.returncode,
            0,
            f"init.sh failed with {init_res.returncode}. Stderr: {init_res.stderr}\nStdout: {init_res.stdout}",
        )
        self.assertIn("Initialization Complete!", init_res.stdout)

        # Run ./init.sh --doctor --workspace <ws>
        doctor_res = subprocess.run(
            [
                str(INIT_SH),
                "--doctor",
                "--workspace", str(self.ws),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=15,
        )
        self.assertEqual(
            doctor_res.returncode,
            0,
            f"init.sh --doctor failed with {doctor_res.returncode}. Stderr: {doctor_res.stderr}\nStdout: {doctor_res.stdout}",
        )
        self.assertIn("Doctor Audit: PASSED", doctor_res.stdout)


if __name__ == "__main__":
    unittest.main()
