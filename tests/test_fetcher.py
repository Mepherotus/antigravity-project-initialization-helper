"""Tests for upstream skill fetcher, transformer, and ultra adapter injection."""

import os
import pathlib
import subprocess
import tempfile
import unittest
import warnings
from unittest.mock import MagicMock, patch

from antigravity_init.fetcher import (
    CORE_SKILLS,
    DEFAULT_CACHE_DIR,
    DEFAULT_REPO_URL,
    ULTRA_ADAPTER_BLOCK,
    ULTRA_ADAPTER_HEADER,
    clone_or_update_superpowers,
    inject_ultra_adapter,
    install_skills,
    transform_skill_markdown,
)


class TestTransformSkillMarkdown(unittest.TestCase):
    """Test path quarantine transformations in skill markdown files."""

    def test_transform_spec_paths(self):
        sample = (
            "Store your design spec in `docs/superpowers/specs/feature-design.md`.\n"
            "Earlier versions used `docs/specs/feature-design.md`."
        )
        expected = (
            "Store your design spec in `.agents/scratch/specs/feature-design.md`.\n"
            "Earlier versions used `.agents/scratch/specs/feature-design.md`."
        )
        self.assertEqual(transform_skill_markdown(sample), expected)

    def test_transform_plan_paths(self):
        sample = (
            "Create implementation plan in `docs/superpowers/plans/2026-10-19-feature.md`.\n"
            "Also refer to `docs/plans/2026-10-19-feature.md`."
        )
        expected = (
            "Create implementation plan in `.agents/scratch/plans/2026-10-19-feature.md`.\n"
            "Also refer to `.agents/scratch/plans/2026-10-19-feature.md`."
        )
        self.assertEqual(transform_skill_markdown(sample), expected)

    def test_transform_order_precedence(self):
        # docs/superpowers/specs/ must not be corrupted by matching docs/specs/
        sample = "Path: docs/superpowers/specs/test.md and docs/specs/test.md"
        result = transform_skill_markdown(sample)
        self.assertEqual(
            result,
            "Path: .agents/scratch/specs/test.md and .agents/scratch/specs/test.md",
        )

        sample_plan = "Path: docs/superpowers/plans/test.md and docs/plans/test.md"
        result_plan = transform_skill_markdown(sample_plan)
        self.assertEqual(
            result_plan,
            "Path: .agents/scratch/plans/test.md and .agents/scratch/plans/test.md",
        )

    def test_unrelated_paths_and_urls_not_mutated(self):
        sample = (
            "Repository: https://github.com/obra/superpowers.git\n"
            "See https://example.com/docs/api/v1 for details.\n"
            "Code is in src/core/planner.py and tests/test_plan.py.\n"
            "Other doc: docs/architecture/overview.md or specs/design.md."
        )
        self.assertEqual(transform_skill_markdown(sample), sample)


class TestInjectUltraAdapter(unittest.TestCase):
    """Test ultra routing adapter injection and idempotence."""

    def test_inject_into_clean_content(self):
        content = "# Brainstorming Skill\n\nInstructions on brainstorming.\n"
        result = inject_ultra_adapter(content)

        self.assertIn(ULTRA_ADAPTER_HEADER, result)
        self.assertIn("## Antigravity Ultra Subagent & Gemini Fallback Override", result)
        self.assertIn("QUOTA_MODE=balanced", result)
        self.assertTrue(result.startswith("# Brainstorming Skill"))

    def test_inject_idempotence(self):
        content = "# Writing Plans Skill\nStep-by-step TDD planning.\n"
        once = inject_ultra_adapter(content)
        twice = inject_ultra_adapter(once)
        thrice = inject_ultra_adapter(twice)

        self.assertEqual(once, twice)
        self.assertEqual(twice, thrice)
        self.assertEqual(twice.count(ULTRA_ADAPTER_HEADER), 1)

    def test_inject_empty_content(self):
        result = inject_ultra_adapter("")
        self.assertIn(ULTRA_ADAPTER_HEADER, result)

    def test_inject_already_containing_header(self):
        content = f"Existing file\n{ULTRA_ADAPTER_HEADER}\nCustom content"
        self.assertEqual(inject_ultra_adapter(content), content)

    def test_inject_double_newline(self):
        content = "# Title\n\nContent ends with two newlines.\n\n"
        result = inject_ultra_adapter(content)
        self.assertEqual(result, content + ULTRA_ADAPTER_BLOCK)


class TestCloneOrUpdateSuperpowers(unittest.TestCase):
    """Test git clone/pull handling and offline cache reuse."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = pathlib.Path(self.temp_dir.name) / "superpowers-cache"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_clone_when_cache_does_not_exist(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = clone_or_update_superpowers(cache_dir=self.cache_dir)
        self.assertEqual(res, self.cache_dir)
        mock_run.assert_called_once_with(
            ["git", "clone", "--depth", "1", DEFAULT_REPO_URL, str(self.cache_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_clone_failure_raises_runtime_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout="",
            stderr="fatal: could not resolve host: github.com",
        )

        with self.assertRaises(RuntimeError) as ctx:
            clone_or_update_superpowers(cache_dir=self.cache_dir)
        self.assertIn("Failed to clone superpowers from", str(ctx.exception))
        self.assertIn("no local cache exists", str(ctx.exception))

    @patch("subprocess.run")
    def test_clone_subprocess_exception_raises_runtime_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git clone", timeout=30)

        with self.assertRaises(RuntimeError) as ctx:
            clone_or_update_superpowers(cache_dir=self.cache_dir)
        self.assertIn("Failed to clone superpowers from", str(ctx.exception))
        self.assertIn("no local cache exists", str(ctx.exception))

    @patch("subprocess.run")
    def test_pull_when_cache_exists_and_is_git_repo(self, mock_run):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / ".git").mkdir(parents=True, exist_ok=True)
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.", stderr="")

        res = clone_or_update_superpowers(cache_dir=self.cache_dir)
        self.assertEqual(res, self.cache_dir)
        mock_run.assert_called_once_with(
            ["git", "-C", str(self.cache_dir), "pull"],
            capture_output=True,
            text=True,
            timeout=15,
        )

    @patch("subprocess.run")
    def test_pull_failure_warns_and_reuses_existing_cache(self, mock_run):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / ".git").mkdir(parents=True, exist_ok=True)
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="fatal: unable to access network",
        )

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            res = clone_or_update_superpowers(cache_dir=self.cache_dir)

            self.assertEqual(res, self.cache_dir)
            self.assertTrue(len(caught_warnings) >= 1)
            self.assertTrue(any(
                "Failed to update superpowers cache" in str(w.message)
                for w in caught_warnings
            ))

    @patch("subprocess.run")
    def test_pull_timeout_warns_and_reuses_existing_cache(self, mock_run):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / ".git").mkdir(parents=True, exist_ok=True)
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git pull", timeout=15)

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            res = clone_or_update_superpowers(cache_dir=self.cache_dir)

            self.assertEqual(res, self.cache_dir)
            self.assertTrue(len(caught_warnings) >= 1)
            self.assertTrue(any(
                "Failed to update superpowers cache" in str(w.message)
                for w in caught_warnings
            ))

    def test_clone_non_git_existing_cache_warns_and_reuses(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "offline_note.txt").write_text("offline copy", encoding="utf-8")

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            res = clone_or_update_superpowers(cache_dir=self.cache_dir)

            self.assertEqual(res, self.cache_dir)
            self.assertTrue(len(caught_warnings) >= 1)
            self.assertTrue(any(
                "not a git repository" in str(w.message)
                for w in caught_warnings
            ))


class TestInstallSkills(unittest.TestCase):
    """Test skill directory copying, path transformation, ultra injection, and mirroring."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp_dir.name)
        self.source_dir = self.base / "source_repo"
        self.target_ws = self.base / "target_workspace"
        self.global_dir = self.base / "global_skills"

        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.target_ws.mkdir(parents=True, exist_ok=True)
        self.global_dir.mkdir(parents=True, exist_ok=True)

        # Create mock skills in source (with nested skills/ directory)
        skills_root = self.source_dir / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)

        # Core skill: brainstorming
        brainstorming_dir = skills_root / "brainstorming"
        brainstorming_dir.mkdir(parents=True, exist_ok=True)
        (brainstorming_dir / "SKILL.md").write_text(
            "# Brainstorming\nSave specs to `docs/superpowers/specs/idea.md`.\n",
            encoding="utf-8",
        )
        (brainstorming_dir / "helper.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")

        # Core skill: writing-plans
        plans_dir = skills_root / "writing-plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "SKILL.md").write_text(
            "# Writing Plans\nSave plans to `docs/plans/plan.md`.\n",
            encoding="utf-8",
        )

        # Non-core skill: systematic-debugging
        debug_dir = skills_root / "systematic-debugging"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "SKILL.md").write_text(
            "# Debugging\nInspect docs/superpowers/specs/spec.md\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_install_skills_copies_and_transforms_correctly(self):
        installed = install_skills(
            source_skills_dir=self.source_dir,
            target_workspace=self.target_ws,
            global_sync=True,
            global_dir=self.global_dir,
        )

        self.assertEqual(installed, ["brainstorming", "systematic-debugging", "writing-plans"])

        ws_skills = self.target_ws / ".agents" / "skills"
        self.assertTrue((ws_skills / "brainstorming" / "SKILL.md").exists())
        self.assertTrue((ws_skills / "brainstorming" / "helper.sh").exists())
        self.assertTrue((ws_skills / "writing-plans" / "SKILL.md").exists())
        self.assertTrue((ws_skills / "systematic-debugging" / "SKILL.md").exists())

        # Check transformed paths in brainstorming
        brainstorm_content = (ws_skills / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/specs/idea.md", brainstorm_content)
        self.assertNotIn("docs/superpowers/specs/", brainstorm_content)
        # Core skill must have ultra adapter injected
        self.assertIn(ULTRA_ADAPTER_HEADER, brainstorm_content)
        self.assertIn("QUOTA_MODE=balanced", brainstorm_content)

        # Check helper file untouched
        helper_content = (ws_skills / "brainstorming" / "helper.sh").read_text(encoding="utf-8")
        self.assertEqual(helper_content, "#!/bin/sh\necho hi\n")

        # Check writing-plans
        plans_content = (ws_skills / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/plans/plan.md", plans_content)
        self.assertNotIn("docs/plans/", plans_content)
        self.assertIn(ULTRA_ADAPTER_HEADER, plans_content)

        # Non-core skill must have transformed paths, but NOT ultra adapter
        debug_content = (
            ws_skills / "systematic-debugging" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/specs/spec.md", debug_content)
        self.assertNotIn(ULTRA_ADAPTER_HEADER, debug_content)

        # Check global mirror
        self.assertTrue((self.global_dir / "brainstorming" / "SKILL.md").exists())
        self.assertTrue((self.global_dir / "writing-plans" / "SKILL.md").exists())
        self.assertTrue((self.global_dir / "systematic-debugging" / "SKILL.md").exists())
        global_brainstorm = (
            self.global_dir / "brainstorming" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(global_brainstorm, brainstorm_content)

    def test_install_skills_without_global_sync(self):
        install_skills(
            source_skills_dir=self.source_dir,
            target_workspace=self.target_ws,
            global_sync=False,
            global_dir=self.global_dir,
        )

        ws_skills = self.target_ws / ".agents" / "skills"
        self.assertTrue((ws_skills / "brainstorming" / "SKILL.md").exists())
        # Global dir must remain empty
        self.assertEqual(list(self.global_dir.iterdir()), [])

    def test_install_skills_flat_source_directory(self):
        # When source_skills_dir directly contains the skills (no nested "skills" folder)
        flat_source = self.base / "flat_source"
        flat_source.mkdir(parents=True, exist_ok=True)
        sample_dir = flat_source / "brainstorming"
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / "SKILL.md").write_text("# Direct Brainstorming\n", encoding="utf-8")

        installed = install_skills(
            source_skills_dir=flat_source,
            target_workspace=self.target_ws,
            global_sync=False,
        )

        self.assertEqual(installed, ["brainstorming"])
        ws_file = self.target_ws / ".agents" / "skills" / "brainstorming" / "SKILL.md"
        self.assertTrue(ws_file.exists())
        self.assertIn(ULTRA_ADAPTER_HEADER, ws_file.read_text(encoding="utf-8"))

    def test_install_skills_nonexistent_source_raises_filenotfound(self):
        nonexistent = self.base / "does_not_exist"
        with self.assertRaises(FileNotFoundError):
            install_skills(
                source_skills_dir=nonexistent,
                target_workspace=self.target_ws,
                global_sync=False,
            )

    def test_install_skills_nested_directories_and_binary_files(self):
        nested_skill = self.source_dir / "skills" / "complex-skill"
        nested_sub = nested_skill / "nested" / "deep"
        nested_sub.mkdir(parents=True, exist_ok=True)

        # Markdown at root
        (nested_skill / "SKILL.md").write_text("# Complex Skill\n", encoding="utf-8")
        # Nested markdown (should be transformed, but NO ultra adapter)
        (nested_sub / "reference.md").write_text(
            "See `docs/superpowers/specs/spec.md`",
            encoding="utf-8",
        )
        # Nested file that happens to be named SKILL.md in a subfolder (must NOT receive adapter)
        (nested_sub / "SKILL.md").write_text(
            "Nested template `docs/plans/plan.md`",
            encoding="utf-8",
        )
        # Binary file with arbitrary bytes
        binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\xff\xfe\x01\x02\x03"
        binary_file = nested_sub / "logo.png"
        binary_file.write_bytes(binary_data)

        install_skills(
            source_skills_dir=self.source_dir,
            target_workspace=self.target_ws,
            global_sync=False,
        )

        ws_complex = self.target_ws / ".agents" / "skills" / "complex-skill"
        self.assertTrue((ws_complex / "nested" / "deep" / "reference.md").exists())
        self.assertTrue((ws_complex / "nested" / "deep" / "logo.png").exists())

        # Verify binary file copied identically without corruption
        self.assertEqual(
            (ws_complex / "nested" / "deep" / "logo.png").read_bytes(),
            binary_data,
        )

        # Verify nested markdown transformed
        nested_ref = (ws_complex / "nested" / "deep" / "reference.md").read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/specs/spec.md", nested_ref)
        self.assertNotIn(ULTRA_ADAPTER_HEADER, nested_ref)

        # Verify nested SKILL.md in subfolder did NOT receive adapter
        nested_inner_skill = (
            ws_complex / "nested" / "deep" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/plans/plan.md", nested_inner_skill)
        self.assertNotIn(ULTRA_ADAPTER_HEADER, nested_inner_skill)

    def test_install_skills_skips_hidden_files(self):
        hidden_dir = self.source_dir / "skills" / ".git"
        hidden_dir.mkdir(parents=True, exist_ok=True)
        (hidden_dir / "config").write_text("hidden", encoding="utf-8")

        hidden_file = self.source_dir / "skills" / ".DS_Store"
        hidden_file.write_text("hidden", encoding="utf-8")

        installed = install_skills(
            source_skills_dir=self.source_dir,
            target_workspace=self.target_ws,
            global_sync=False,
        )

        self.assertNotIn(".git", installed)
        self.assertNotIn(".DS_Store", installed)
        ws_skills = self.target_ws / ".agents" / "skills"
        self.assertFalse((ws_skills / ".git").exists())
        self.assertFalse((ws_skills / ".DS_Store").exists())

    def test_install_skills_single_markdown_file_skills(self):
        # When source directory contains standalone .md skill files directly
        flat_md_source = self.base / "flat_md_source"
        flat_md_source.mkdir(parents=True, exist_ok=True)
        (flat_md_source / "brainstorming.md").write_text(
            "# Standalone Brainstorming\nSee `docs/superpowers/specs/idea.md`\n",
            encoding="utf-8",
        )
        (flat_md_source / "custom-tool.md").write_text(
            "# Custom Tool\nSee `docs/plans/tool.md`\n",
            encoding="utf-8",
        )

        installed = install_skills(
            source_skills_dir=flat_md_source,
            target_workspace=self.target_ws,
            global_sync=True,
            global_dir=self.global_dir,
        )

        self.assertEqual(installed, ["brainstorming", "custom-tool"])

        # Check workspace output
        ws_brainstorm = (
            self.target_ws / ".agents" / "skills" / "brainstorming" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/specs/idea.md", ws_brainstorm)
        self.assertIn(ULTRA_ADAPTER_HEADER, ws_brainstorm)

        ws_custom = (
            self.target_ws / ".agents" / "skills" / "custom-tool" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn(".agents/scratch/plans/tool.md", ws_custom)
        self.assertNotIn(ULTRA_ADAPTER_HEADER, ws_custom)

        # Check global mirror
        global_brainstorm = (
            self.global_dir / "brainstorming" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(global_brainstorm, ws_brainstorm)


if __name__ == "__main__":
    unittest.main()
