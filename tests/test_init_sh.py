"""Tests for init.sh POSIX bootstrap script."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INIT_SH = REPO_ROOT / "init.sh"


class TestInitSh(unittest.TestCase):
    """Test suite for init.sh bootstrap script."""

    def test_init_sh_exists_and_executable(self) -> None:
        """Verify init.sh exists and is executable."""
        self.assertTrue(INIT_SH.is_file(), f"init.sh not found at {INIT_SH}")
        self.assertTrue(
            os.access(INIT_SH, os.X_OK),
            f"init.sh at {INIT_SH} is not marked executable",
        )

    def test_init_sh_help(self) -> None:
        """sh init.sh --help returns exit code 0 and prints usage help."""
        proc = subprocess.run(
            ["sh", str(INIT_SH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Expected exit code 0, got {proc.returncode}. Stderr: {proc.stderr}",
        )
        self.assertIn("usage:", proc.stdout.lower())
        self.assertIn("antigravity-init", proc.stdout)

    def test_init_sh_direct_execution(self) -> None:
        """./init.sh --help runs directly via shebang and exits with 0."""
        proc = subprocess.run(
            [str(INIT_SH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Expected exit code 0, got {proc.returncode}. Stderr: {proc.stderr}",
        )
        self.assertIn("antigravity-init", proc.stdout)

    def test_init_sh_python_version_check_failure(self) -> None:
        """Failure when Python version < 3.9 exits with code 1 and error on stderr."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bin = pathlib.Path(tmp_dir)
            shim_python = temp_bin / "python3"
            # Create a shim python3 that fails version check
            shim_python.write_text(
                "#!/bin/sh\n"
                "# Simulates Python < 3.9 by failing the version check\n"
                "exit 1\n"
            )
            shim_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{temp_bin}:{env.get('PATH', '')}"

            sh_path = shutil.which("sh") or "/bin/sh"
            proc = subprocess.run(
                [sh_path, str(INIT_SH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("3.9", proc.stderr)
            self.assertTrue(
                "python" in proc.stderr.lower() or "version" in proc.stderr.lower()
            )

    def test_init_sh_missing_git(self) -> None:
        """Failure when git is missing exits with code 1 and error on stderr."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bin = pathlib.Path(tmp_dir)
            # Link python3 and dirname into temp_bin, but omit git
            os.symlink(sys.executable, temp_bin / "python3")
            dirname_path = shutil.which("dirname")
            if dirname_path:
                os.symlink(dirname_path, temp_bin / "dirname")

            env = os.environ.copy()
            env["PATH"] = str(temp_bin)

            sh_path = shutil.which("sh") or "/bin/sh"
            proc = subprocess.run(
                [sh_path, str(INIT_SH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("git", proc.stderr.lower())

    def test_init_sh_missing_python3(self) -> None:
        """Failure when python3 is missing exits with code 1 and error on stderr."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bin = pathlib.Path(tmp_dir)
            # Link git and dirname into temp_bin, but omit python3
            git_path = shutil.which("git")
            self.assertIsNotNone(git_path, "Host system must have git installed")
            assert git_path is not None
            os.symlink(git_path, temp_bin / "git")
            dirname_path = shutil.which("dirname")
            if dirname_path:
                os.symlink(dirname_path, temp_bin / "dirname")

            env = os.environ.copy()
            env["PATH"] = str(temp_bin)

            sh_path = shutil.which("sh") or "/bin/sh"
            proc = subprocess.run(
                [sh_path, str(INIT_SH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("python3", proc.stderr.lower())

    def test_init_sh_argument_forwarding(self) -> None:
        """Proper forwarding of all arguments (\"$@\") to python3 -m antigravity_init."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proc = subprocess.run(
                ["sh", str(INIT_SH), "--doctor", "--workspace", tmp_dir],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            # Doctor mode exits with 1 on uninitialized workspace
            self.assertEqual(proc.returncode, 1)
            # Check output reflects both --doctor and --workspace forwarding
            self.assertIn("Antigravity Workspace Doctor", proc.stdout)
            self.assertIn(tmp_dir, proc.stdout)

    def test_init_sh_invoked_from_different_cwd(self) -> None:
        """init.sh successfully resolves SCRIPT_DIR when executed from a different working directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proc = subprocess.run(
                ["sh", str(INIT_SH), "--help"],
                capture_output=True,
                text=True,
                cwd=tmp_dir,
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("antigravity-init", proc.stdout)

    def test_init_sh_arguments_with_spaces(self) -> None:
        """Arguments containing spaces are preserved and not split across word boundaries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            space_dir = pathlib.Path(tmp_dir) / "workspace with spaces in name"
            space_dir.mkdir(parents=True)
            proc = subprocess.run(
                ["sh", str(INIT_SH), "--doctor", "--workspace", str(space_dir)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn(str(space_dir), proc.stdout)

    def test_init_sh_executed_from_path_with_spaces(self) -> None:
        """init.sh successfully resolves SCRIPT_DIR when located in a path containing spaces."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            space_dir = pathlib.Path(tmp_dir) / "project path with spaces"
            space_dir.mkdir(parents=True)
            copied_init = space_dir / "init.sh"
            shutil.copy2(INIT_SH, copied_init)
            # Symlink antigravity_init package so python3 -m antigravity_init resolves locally
            (space_dir / "antigravity_init").symlink_to(
                REPO_ROOT / "antigravity_init",
                target_is_directory=True,
            )

            proc = subprocess.run(
                ["sh", str(copied_init), "--help"],
                capture_output=True,
                text=True,
                cwd=str(space_dir),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("antigravity-init", proc.stdout)

    def test_init_sh_prepends_to_existing_pythonpath(self) -> None:
        """init.sh prepends SCRIPT_DIR to an already set PYTHONPATH."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bin = pathlib.Path(tmp_dir)
            shim_python = temp_bin / "python3"
            shim_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "    exit 0\n"
                "fi\n"
                "echo \"PYTHONPATH=${PYTHONPATH:-}\"\n"
                "exit 0\n"
            )
            shim_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{temp_bin}:{env.get('PATH', '')}"
            env["PYTHONPATH"] = "/custom/existing/path"

            proc = subprocess.run(
                ["sh", str(INIT_SH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0)
            expected = f"PYTHONPATH={REPO_ROOT}:/custom/existing/path"
            self.assertEqual(proc.stdout.strip(), expected)

    def test_init_sh_sets_pythonpath_when_unset(self) -> None:
        """init.sh sets PYTHONPATH to SCRIPT_DIR when initially unset."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_bin = pathlib.Path(tmp_dir)
            shim_python = temp_bin / "python3"
            shim_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "    exit 0\n"
                "fi\n"
                "echo \"PYTHONPATH=${PYTHONPATH:-}\"\n"
                "exit 0\n"
            )
            shim_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{temp_bin}:{env.get('PATH', '')}"
            env.pop("PYTHONPATH", None)

            proc = subprocess.run(
                ["sh", str(INIT_SH)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0)
            expected = f"PYTHONPATH={REPO_ROOT}"
            self.assertEqual(proc.stdout.strip(), expected)

    def test_init_sh_cdpath_environment_robustness(self) -> None:
        """Exported CDPATH in environment does not corrupt SCRIPT_DIR resolution."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = os.environ.copy()
            env["CDPATH"] = tmp_dir
            proc = subprocess.run(
                ["sh", str(INIT_SH), "--help"],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(REPO_ROOT),
                timeout=10,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("antigravity-init", proc.stdout)

    def test_init_sh_propagates_non_zero_exit_codes(self) -> None:
        """exec python3 forwards non-zero exit codes (such as exit code 2 on invalid arguments)."""
        proc = subprocess.run(
            ["sh", str(INIT_SH), "--non-existent-unrecognized-flag"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unrecognized arguments", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
