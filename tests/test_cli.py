"""Tests for CLI engine & terminal orchestrator (antigravity_init/cli.py)."""

from __future__ import annotations

import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from antigravity_init import agents, fetcher, poison_guard
from antigravity_init.cli import main, parse_args, run_doctor, run_init


class TestParseArgs(unittest.TestCase):
    """Test parse_args CLI flag parsing and defaults."""

    def test_parse_args_defaults(self) -> None:
        args = parse_args([])
        self.assertEqual(args.mode, "balanced")
        self.assertEqual(args.workspace, pathlib.Path.cwd())
        self.assertFalse(args.interactive)
        self.assertFalse(args.non_interactive)
        self.assertFalse(args.doctor)
        self.assertFalse(args.no_web)
        self.assertEqual(args.superpowers_url, fetcher.DEFAULT_REPO_URL)
        self.assertIsNone(args.research_url)
        self.assertFalse(args.verbose)
        self.assertFalse(args.no_global_sync)

    def test_parse_args_valid_modes(self) -> None:
        for mode in ("balanced", "low-claude", "flash-saver"):
            args = parse_args(["--mode", mode])
            self.assertEqual(args.mode, mode)

    def test_parse_args_invalid_mode_raises(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as ctx:
                parse_args(["--mode", "ultra-warp"])
            self.assertNotEqual(ctx.exception.code, 0)

    def test_parse_args_custom_values_and_flags(self) -> None:
        custom_path = "/tmp/my-project"
        args = parse_args([
            "--mode", "flash-saver",
            "--workspace", custom_path,
            "--interactive",
            "--non-interactive",
            "--doctor",
            "--no-web",
            "--superpowers-url", "https://example.com/custom-superpowers.git",
            "--research-url", "https://example.com/custom-rubric.json",
            "--verbose",
            "--no-global-sync",
        ])
        self.assertEqual(args.mode, "flash-saver")
        self.assertEqual(args.workspace, pathlib.Path(custom_path))
        self.assertTrue(args.interactive)
        self.assertTrue(args.non_interactive)
        self.assertTrue(args.doctor)
        self.assertTrue(args.no_web)
        self.assertEqual(args.superpowers_url, "https://example.com/custom-superpowers.git")
        self.assertEqual(args.research_url, "https://example.com/custom-rubric.json")
        self.assertTrue(args.verbose)
        self.assertTrue(args.no_global_sync)


class TestRunDoctor(unittest.TestCase):
    """Test run_doctor health audit functionality."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self.temp_dir.name).resolve()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _setup_healthy_workspace(self) -> None:
        """Create a fully healthy initialized workspace fixture."""
        # 1. Git exclude setup
        git_dir = self.workspace / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        exclude_file = git_dir / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        exclude_file.write_text("\n".join(poison_guard.DEFAULT_EXCLUDES) + "\n", encoding="utf-8")

        # 2. Quota mode file
        quota_file = self.workspace / ".agents" / "scratch" / "quota_mode.env"
        quota_file.parent.mkdir(parents=True, exist_ok=True)
        quota_file.write_text("QUOTA_MODE=balanced\n", encoding="utf-8")

        # 3. All 9 subagents
        agents_dir = self.workspace / ".agents" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name in agents.AGENT_NAMES:
            (agents_dir / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

        # 4. Workspace MCP scaffolding
        mcp_dir = self.workspace / ".agents" / "plugins" / "workspace-mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        (mcp_dir / "plugin.json").write_text(
            json.dumps({"name": "workspace-mcp", "version": "0.1.0"}, indent=2),
            encoding="utf-8",
        )
        (mcp_dir / "mcp_config.json").write_text(
            json.dumps({"mcpServers": {}}, indent=2),
            encoding="utf-8",
        )

        # 5. Project advisor skill
        advisor_skill = self.workspace / ".agents" / "skills" / "project-advisor" / "SKILL.md"
        advisor_skill.parent.mkdir(parents=True, exist_ok=True)
        advisor_skill.write_text("# Project Advisor Skill\n", encoding="utf-8")

    def test_doctor_healthy_workspace_returns_0(self) -> None:
        self._setup_healthy_workspace()
        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 0)
        output = fake_out.getvalue()
        self.assertIn("pass", output.lower())

    def test_doctor_missing_git_excludes_returns_1(self) -> None:
        self._setup_healthy_workspace()
        # Corrupt git exclude file by making it empty
        exclude_file = self.workspace / ".git" / "info" / "exclude"
        exclude_file.write_text("# Empty exclude\n", encoding="utf-8")

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("quarantine", output.lower())

    def test_doctor_leaked_staged_files_returns_1(self) -> None:
        self._setup_healthy_workspace()
        # Mock poison_guard.check_quarantine_status returning leaked files
        with patch(
            "antigravity_init.poison_guard.check_quarantine_status",
            return_value={
                "is_clean": False,
                "leaked_staged_files": [".agents/scratch/plans/leaked_plan.md"],
                "missing_excludes": [],
            },
        ):
            with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
                code = run_doctor(self.workspace)
            self.assertEqual(code, 1)
            output = fake_out.getvalue()
            self.assertIn("leaked", output.lower())

    def test_doctor_missing_quota_mode_file_returns_1(self) -> None:
        self._setup_healthy_workspace()
        quota_file = self.workspace / ".agents" / "scratch" / "quota_mode.env"
        quota_file.unlink()

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("quota", output.lower())

    def test_doctor_invalid_quota_mode_value_returns_1(self) -> None:
        self._setup_healthy_workspace()
        quota_file = self.workspace / ".agents" / "scratch" / "quota_mode.env"
        quota_file.write_text("QUOTA_MODE=unsupported_mode\n", encoding="utf-8")

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("quota", output.lower())

    def test_doctor_missing_subagent_returns_1(self) -> None:
        self._setup_healthy_workspace()
        # Remove one agent
        target_agent = self.workspace / ".agents" / "agents" / "sp-implementer-argon.md"
        target_agent.unlink()

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("agent", output.lower())

    def test_doctor_missing_mcp_plugin_json_returns_1(self) -> None:
        self._setup_healthy_workspace()
        (self.workspace / ".agents" / "plugins" / "workspace-mcp" / "plugin.json").unlink()

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("mcp", output.lower())

    def test_doctor_corrupted_mcp_config_json_returns_1(self) -> None:
        self._setup_healthy_workspace()
        (self.workspace / ".agents" / "plugins" / "workspace-mcp" / "mcp_config.json").write_text(
            "{ invalid json ...",
            encoding="utf-8",
        )

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("mcp", output.lower())
        self.assertNotIn("Workspace MCP plugin and configuration valid", output)

    def test_doctor_corrupted_plugin_json_returns_1(self) -> None:
        self._setup_healthy_workspace()
        (self.workspace / ".agents" / "plugins" / "workspace-mcp" / "plugin.json").write_text(
            "{ not valid json ...",
            encoding="utf-8",
        )

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("mcp", output.lower())
        self.assertNotIn("Workspace MCP plugin and configuration valid", output)

    def test_doctor_missing_project_advisor_skill_returns_1(self) -> None:
        self._setup_healthy_workspace()
        (self.workspace / ".agents" / "skills" / "project-advisor" / "SKILL.md").unlink()

        with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
            code = run_doctor(self.workspace)
        self.assertEqual(code, 1)
        output = fake_out.getvalue()
        self.assertIn("advisor", output.lower())


class TestRunInit(unittest.TestCase):
    """Test run_init complete orchestration workflow."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self.temp_dir.name).resolve()

        # Create mock upstream superpowers skills directory
        self.mock_superpowers_dir = tempfile.TemporaryDirectory()
        mock_skills = pathlib.Path(self.mock_superpowers_dir.name) / "skills"
        mock_skills.mkdir(parents=True, exist_ok=True)
        for skill in ("brainstorming", "writing-plans", "executing-plans"):
            s_dir = mock_skills / skill
            s_dir.mkdir(parents=True, exist_ok=True)
            (s_dir / "SKILL.md").write_text(f"---\nname: {skill}\n---\n# {skill}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        self.mock_superpowers_dir.cleanup()

    def test_run_init_git_workspace_full_orchestration(self) -> None:
        # Initialize a real git repo
        subprocess.run(["git", "init", str(self.workspace)], capture_output=True, check=True)

        args = parse_args([
            "--workspace", str(self.workspace),
            "--mode", "balanced",
            "--no-web",
            "--no-global-sync",
        ])

        with patch("antigravity_init.fetcher.clone_or_update_superpowers") as mock_clone:
            mock_clone.return_value = pathlib.Path(self.mock_superpowers_dir.name)
            with patch("sys.stdout", new_callable=io.StringIO) as fake_out:
                code = run_init(args)

        self.assertEqual(code, 0)
        output = fake_out.getvalue()
        self.assertIn("complete", output.lower())

        # Verify git excludes
        exclude_file = self.workspace / ".git" / "info" / "exclude"
        self.assertTrue(exclude_file.is_file())
        exclude_content = exclude_file.read_text(encoding="utf-8")
        for excl in poison_guard.DEFAULT_EXCLUDES:
            self.assertIn(excl, exclude_content)

        # Verify routing rules
        rules_file = self.workspace / ".agents" / "rules" / "ultra-routing.md"
        self.assertTrue(rules_file.is_file())

        # Verify quota mode env
        quota_file = self.workspace / ".agents" / "scratch" / "quota_mode.env"
        self.assertTrue(quota_file.is_file())
        self.assertIn("QUOTA_MODE=balanced", quota_file.read_text(encoding="utf-8"))

        # Verify research artifacts
        rubric_file = self.workspace / ".agents" / "scratch" / "research" / "adversarial_review.md"
        self.assertTrue(rubric_file.is_file())

        # Verify 9 subagents
        for name in agents.AGENT_NAMES:
            agent_file = self.workspace / ".agents" / "agents" / f"{name}.md"
            self.assertTrue(agent_file.is_file(), f"Missing agent {name}")

        # Verify skills
        for skill in ("brainstorming", "writing-plans", "executing-plans"):
            skill_file = self.workspace / ".agents" / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_file.is_file(), f"Missing skill {skill}")

        # Verify workspace MCP
        mcp_plugin = self.workspace / ".agents" / "plugins" / "workspace-mcp" / "plugin.json"
        mcp_config = self.workspace / ".agents" / "plugins" / "workspace-mcp" / "mcp_config.json"
        self.assertTrue(mcp_plugin.is_file())
        self.assertTrue(mcp_config.is_file())

        # Verify project advisor skill
        advisor_skill = self.workspace / ".agents" / "skills" / "project-advisor" / "SKILL.md"
        self.assertTrue(advisor_skill.is_file())

        # Now run doctor on the freshly initialized workspace: MUST return 0!
        with patch("sys.stdout", new_callable=io.StringIO):
            doctor_exit = run_doctor(self.workspace)
        self.assertEqual(doctor_exit, 0)

    def test_run_init_non_git_workspace_does_not_crash(self) -> None:
        args = parse_args([
            "--workspace", str(self.workspace),
            "--mode", "low-claude",
            "--no-web",
            "--no-global-sync",
        ])

        with patch("antigravity_init.fetcher.clone_or_update_superpowers") as mock_clone:
            mock_clone.return_value = pathlib.Path(self.mock_superpowers_dir.name)
            with patch("sys.stdout", new_callable=io.StringIO):
                code = run_init(args)

        self.assertEqual(code, 0)
        quota_file = self.workspace / ".agents" / "scratch" / "quota_mode.env"
        self.assertTrue(quota_file.is_file())
        self.assertIn("QUOTA_MODE=low-claude", quota_file.read_text(encoding="utf-8"))

    def test_run_init_interactive_mcp_prompting(self) -> None:
        # Create python marker file
        (self.workspace / "requirements.txt").write_text("numpy\n", encoding="utf-8")

        args = parse_args([
            "--workspace", str(self.workspace),
            "--interactive",
            "--no-web",
            "--no-global-sync",
        ])

        with patch("antigravity_init.fetcher.clone_or_update_superpowers") as mock_clone:
            mock_clone.return_value = pathlib.Path(self.mock_superpowers_dir.name)
            with patch("builtins.input", return_value="y"):
                with patch("sys.stdout", new_callable=io.StringIO):
                    code = run_init(args)

        self.assertEqual(code, 0)
        mcp_config = self.workspace / ".agents" / "plugins" / "workspace-mcp" / "mcp_config.json"
        data = json.loads(mcp_config.read_text(encoding="utf-8"))
        self.assertIn("python-mcp", data["mcpServers"])

    def test_run_init_non_interactive_overrides_interactive(self) -> None:
        (self.workspace / "requirements.txt").write_text("numpy\n", encoding="utf-8")

        args = parse_args([
            "--workspace", str(self.workspace),
            "--interactive",
            "--non-interactive",
            "--no-web",
            "--no-global-sync",
        ])

        with patch("antigravity_init.fetcher.clone_or_update_superpowers") as mock_clone:
            mock_clone.return_value = pathlib.Path(self.mock_superpowers_dir.name)
            with patch("builtins.input", side_effect=AssertionError("Should not prompt in non-interactive")):
                with patch("sys.stdout", new_callable=io.StringIO):
                    code = run_init(args)

    def test_run_init_superpowers_clone_failure_raises(self) -> None:
        args = parse_args([
            "--workspace", str(self.workspace),
            "--no-web",
            "--no-global-sync",
        ])

        with patch("antigravity_init.fetcher.clone_or_update_superpowers", side_effect=RuntimeError("Git clone connection failed")):
            with patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(RuntimeError) as ctx:
                    run_init(args)
            self.assertIn("Git clone connection failed", str(ctx.exception))


class TestMain(unittest.TestCase):
    """Test main entrypoint dispatching and exception handling."""

    def test_main_dispatches_to_doctor(self) -> None:
        with patch("antigravity_init.cli.run_doctor", return_value=0) as mock_doc:
            exit_code = main(["--doctor", "--workspace", "/test/path"])
        self.assertEqual(exit_code, 0)
        mock_doc.assert_called_once_with(pathlib.Path("/test/path"))

    def test_main_dispatches_to_init(self) -> None:
        with patch("antigravity_init.cli.run_init", return_value=0) as mock_init:
            exit_code = main(["--workspace", "/test/path", "--no-web"])
        self.assertEqual(exit_code, 0)
        mock_init.assert_called_once()
        args = mock_init.call_args[0][0]
        self.assertEqual(args.workspace, pathlib.Path("/test/path"))
        self.assertTrue(args.no_web)

    def test_main_argv_none_uses_sys_argv(self) -> None:
        test_argv = ["antigravity-init", "--doctor", "--workspace", "/test/path"]
        with patch.object(sys, "argv", test_argv):
            with patch("antigravity_init.cli.run_doctor", return_value=0) as mock_doc:
                exit_code = main(None)
        self.assertEqual(exit_code, 0)
        mock_doc.assert_called_once_with(pathlib.Path("/test/path"))

    def test_main_handles_exception_without_verbose(self) -> None:
        with patch("antigravity_init.cli.run_init", side_effect=RuntimeError("Simulated init error")):
            with patch("sys.stderr", new_callable=io.StringIO) as fake_err:
                code = main(["--workspace", "/test/path"])
        self.assertEqual(code, 1)
        err_output = fake_err.getvalue()
        self.assertIn("Error: Simulated init error", err_output)

    def test_main_reraises_exception_with_verbose(self) -> None:
        with patch("antigravity_init.cli.run_init", side_effect=RuntimeError("Simulated verbose error")):
            with self.assertRaises(RuntimeError) as ctx:
                main(["--workspace", "/test/path", "--verbose"])
        self.assertIn("Simulated verbose error", str(ctx.exception))

    def test_main_handles_keyboard_interrupt(self) -> None:
        with patch("antigravity_init.cli.run_init", side_effect=KeyboardInterrupt):
            with patch("sys.stderr", new_callable=io.StringIO) as fake_err:
                code = main(["--workspace", "/test/path"])
        self.assertEqual(code, 130)
        self.assertIn("Operation cancelled by user", fake_err.getvalue())

    def test_main_handles_help_flag(self) -> None:
        with patch("sys.stdout", new_callable=io.StringIO):
            code = main(["--help"])
        self.assertEqual(code, 0)

    def test_main_handles_invalid_arguments(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO):
            code = main(["--totally-invalid-cli-flag"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
