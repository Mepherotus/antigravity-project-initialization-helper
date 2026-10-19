import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

from antigravity_init.poison_guard import (
    DEFAULT_EXCLUDES,
    check_quarantine_status,
    configure_git_exclude,
    resolve_git_dir,
    write_quota_env,
    write_routing_rules,
)


class TestPoisonGuard(unittest.TestCase):
    def test_default_excludes_contents(self):
        expected = [
            ".agents/scratch/",
            ".agents/rules/",
            ".agents/agents/",
            ".agents/skills/",
            ".agents/plugins/",
            "docs/superpowers/",
            "docs/plans/",
        ]
        self.assertEqual(DEFAULT_EXCLUDES, expected)

    def test_resolve_git_dir_direct(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            git_dir.mkdir()

            resolved = resolve_git_dir(repo_root)
            self.assertEqual(resolved, git_dir.resolve())

    def test_resolve_git_dir_worktree_relative(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            main_git = base / "main_repo" / ".git" / "worktrees" / "wt1"
            main_git.mkdir(parents=True)

            wt_dir = base / "worktree_dir"
            wt_dir.mkdir()
            git_file = wt_dir / ".git"
            # Relative path from wt_dir to main_git
            rel_path = "../main_repo/.git/worktrees/wt1"
            git_file.write_text(f"gitdir: {rel_path}\n", encoding="utf-8")

            resolved = resolve_git_dir(wt_dir)
            self.assertEqual(resolved, main_git.resolve())

    def test_resolve_git_dir_worktree_absolute(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            target_git = base / "common_git"
            target_git.mkdir()

            wt_dir = base / "worktree_dir"
            wt_dir.mkdir()
            git_file = wt_dir / ".git"
            git_file.write_text(f"gitdir: {target_git.resolve()}\n", encoding="utf-8")

            resolved = resolve_git_dir(wt_dir)
            self.assertEqual(resolved, target_git.resolve())

    def test_resolve_git_dir_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            with self.assertRaises(FileNotFoundError) as ctx:
                resolve_git_dir(repo_root)
            self.assertIn("No .git directory or worktree file found", str(ctx.exception))

    def test_configure_git_exclude_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            git_dir.mkdir()

            added = configure_git_exclude(repo_root)
            self.assertEqual(added, DEFAULT_EXCLUDES)

            exclude_file = git_dir / "info" / "exclude"
            self.assertTrue(exclude_file.is_file())
            content = exclude_file.read_text(encoding="utf-8")
            self.assertIn("# --- Antigravity Superpowers + Ultra Local Exclusion ---", content)
            for entry in DEFAULT_EXCLUDES:
                self.assertIn(entry, content)

    def test_configure_git_exclude_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            git_dir.mkdir()

            first_added = configure_git_exclude(repo_root)
            self.assertEqual(first_added, DEFAULT_EXCLUDES)

            second_added = configure_git_exclude(repo_root)
            self.assertEqual(second_added, [])

            exclude_file = git_dir / "info" / "exclude"
            content = exclude_file.read_text(encoding="utf-8")
            # Header should only appear once
            self.assertEqual(content.count("# --- Antigravity Superpowers + Ultra Local Exclusion ---"), 1)

    def test_configure_git_exclude_with_extra_entries_and_existing_content(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            info_dir = git_dir / "info"
            info_dir.mkdir(parents=True)
            exclude_file = info_dir / "exclude"
            # Pre-populate with existing entries and no trailing newline
            exclude_file.write_text("# existing user exclude\n*.pyc", encoding="utf-8")

            extra = [".env.local", "custom/scratch/"]
            added = configure_git_exclude(repo_root, extra_entries=extra)
            self.assertEqual(added, DEFAULT_EXCLUDES + extra)

            content = exclude_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# existing user exclude\n*.pyc\n"))
            self.assertIn("# --- Antigravity Superpowers + Ultra Local Exclusion ---", content)
            self.assertIn(".env.local", content)
            self.assertIn("custom/scratch/", content)

    def test_write_routing_rules_default(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            rule_path = write_routing_rules(repo_root)
            expected_path = repo_root / ".agents" / "rules" / "ultra-routing.md"
            self.assertEqual(rule_path, expected_path)
            self.assertTrue(rule_path.is_file())
            content = rule_path.read_text(encoding="utf-8")
            self.assertIn("Superpowers + Antigravity Ultra Routing", content)
            self.assertIn("QUOTA_MODE=balanced", content)

    def test_write_routing_rules_custom_quota(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            rule_path = write_routing_rules(repo_root, quota_mode="low-claude")
            self.assertTrue(rule_path.is_file())
            content = rule_path.read_text(encoding="utf-8")
            self.assertIn("low-claude", content)

    def test_write_quota_env(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            quota_file = write_quota_env(repo_root, quota_mode="flash-saver")
            expected_file = repo_root / ".agents" / "scratch" / "quota_mode.env"
            self.assertEqual(quota_file, expected_file)
            self.assertTrue(quota_file.is_file())
            content = quota_file.read_text(encoding="utf-8")
            self.assertEqual(content, "QUOTA_MODE=flash-saver\n")

    def test_check_quarantine_status_non_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            status = check_quarantine_status(repo_root)
            self.assertFalse(status["is_clean"])
            self.assertEqual(status["leaked_staged_files"], [])
            self.assertEqual(status["missing_excludes"], DEFAULT_EXCLUDES)

    def test_check_quarantine_status_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            configure_git_exclude(repo_root)

            # Stage a legitimate source file
            (repo_root / "hello.py").write_text("print('hello')", encoding="utf-8")
            subprocess.run(["git", "add", "hello.py"], cwd=repo_root, check=True, capture_output=True)

            status = check_quarantine_status(repo_root)
            self.assertTrue(status["is_clean"])
            self.assertEqual(status["leaked_staged_files"], [])
            self.assertEqual(status["missing_excludes"], [])

    def test_check_quarantine_status_leaked_staged_files(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            configure_git_exclude(repo_root)

            # Force stage quarantined path
            scratch_file = repo_root / ".agents" / "scratch" / "secret.env"
            scratch_file.parent.mkdir(parents=True, exist_ok=True)
            scratch_file.write_text("SECRET=123", encoding="utf-8")
            subprocess.run(["git", "add", "-f", str(scratch_file)], cwd=repo_root, check=True, capture_output=True)

            # Force stage file containing model leak tag
            leaked_file = repo_root / "notes.txt"
            leaked_file.write_text("Created by [@sp-implementer-flash]", encoding="utf-8")
            subprocess.run(["git", "add", "-f", str(leaked_file)], cwd=repo_root, check=True, capture_output=True)

            status = check_quarantine_status(repo_root)
            self.assertFalse(status["is_clean"])
            self.assertIn(".agents/scratch/secret.env", status["leaked_staged_files"])
            self.assertIn("notes.txt", status["leaked_staged_files"])

    def test_check_quarantine_status_missing_excludes(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            # Do not configure excludes

            status = check_quarantine_status(repo_root)
            self.assertFalse(status["is_clean"])
            self.assertEqual(status["missing_excludes"], DEFAULT_EXCLUDES)

    def test_check_quarantine_status_git_failure_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            git_dir.mkdir()
            configure_git_exclude(repo_root)

            # Mock subprocess.run to simulate git failure / not installed
            with mock.patch("subprocess.run", side_effect=OSError("git not found")):
                status = check_quarantine_status(repo_root)
                self.assertEqual(status["leaked_staged_files"], [])
                self.assertTrue(status["is_clean"])

    def test_resolve_git_dir_empty_worktree_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_file = repo_root / ".git"
            git_file.write_text("   \n\n", encoding="utf-8")
            with self.assertRaises(FileNotFoundError) as ctx:
                resolve_git_dir(repo_root)
            self.assertIn("Invalid git worktree file", str(ctx.exception))

    def test_resolve_git_dir_worktree_multiline_and_comments(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            main_git = base / "main_repo" / ".git" / "worktrees" / "wt2"
            main_git.mkdir(parents=True)

            wt_dir = base / "worktree_dir"
            wt_dir.mkdir()
            git_file = wt_dir / ".git"
            git_file.write_text(
                "# worktree metadata header\n\ngitdir: ../main_repo/.git/worktrees/wt2\n# trailing comment",
                encoding="utf-8",
            )
            resolved = resolve_git_dir(wt_dir)
            self.assertEqual(resolved, main_git.resolve())

    def test_configure_git_exclude_slash_variation_and_extra_entries_cleaning(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            git_dir = repo_root / ".git"
            info_dir = git_dir / "info"
            info_dir.mkdir(parents=True)
            exclude_file = info_dir / "exclude"
            # Pre-populate with one entry without trailing slash
            exclude_file.write_text(".agents/scratch\n", encoding="utf-8")

            # .agents/scratch/ should not be added again since .agents/scratch is present
            extra = ["  custom/scratch/  ", ""]
            added = configure_git_exclude(repo_root, extra_entries=extra)
            self.assertNotIn(".agents/scratch/", added)
            self.assertIn("custom/scratch/", added)

    def test_check_quarantine_status_handles_timeout_and_unbracketed_tags(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = pathlib.Path(td)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            configure_git_exclude(repo_root)

            # Test timeout handling
            with mock.patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=10),
            ):
                status = check_quarantine_status(repo_root)
                self.assertEqual(status["leaked_staged_files"], [])
                self.assertTrue(status["is_clean"])

            # Test unbracketed model leak detection (@sp-implementer-flash)
            unbracketed = repo_root / "leak.txt"
            unbracketed.write_text("Created by @sp-implementer-flash", encoding="utf-8")
            subprocess.run(["git", "add", "leak.txt"], cwd=repo_root, check=True, capture_output=True)

            status = check_quarantine_status(repo_root)
            self.assertFalse(status["is_clean"])
            self.assertIn("leak.txt", status["leaked_staged_files"])


if __name__ == "__main__":
    unittest.main()
