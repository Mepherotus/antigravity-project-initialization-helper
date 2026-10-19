"""Unit tests for antigravity_init.advisor module."""

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from antigravity_init import TEMPLATES_DIR


class TestAdvisorConstants(unittest.TestCase):
    """Test DETECTION_RULES and constant definitions in antigravity_init.advisor."""

    def test_detection_rules_keys(self):
        from antigravity_init.advisor import DETECTION_RULES

        expected_keys = {"python", "node", "rust", "docker", "genai"}
        self.assertEqual(set(DETECTION_RULES.keys()), expected_keys)

    def test_detection_rules_structure(self):
        from antigravity_init.advisor import DETECTION_RULES

        for tech, rule in DETECTION_RULES.items():
            self.assertIn("files", rule, f"Rule '{tech}' must have 'files' list")
            self.assertIsInstance(rule["files"], list)
            self.assertTrue(len(rule["files"]) > 0, f"Rule '{tech}' files list must not be empty")

            self.assertIn("mcp", rule, f"Rule '{tech}' must have 'mcp' dict")
            mcp = rule["mcp"]
            self.assertIn("name", mcp)
            self.assertIn("command", mcp)
            self.assertIn("args", mcp)
            self.assertIn("description", mcp)
            self.assertIsInstance(mcp["args"], list)

    def test_specific_technology_rules(self):
        from antigravity_init.advisor import DETECTION_RULES

        # Python
        python_rule = DETECTION_RULES["python"]
        for marker in ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py"]:
            self.assertIn(marker, python_rule["files"])
        self.assertEqual(python_rule["mcp"]["name"], "python-mcp")
        self.assertEqual(python_rule["mcp"]["command"], "python3")
        self.assertEqual(python_rule["mcp"]["args"], ["-m", "mcp_server_python"])

        # Node
        node_rule = DETECTION_RULES["node"]
        for marker in ["package.json", "tsconfig.json"]:
            self.assertIn(marker, node_rule["files"])
        self.assertEqual(node_rule["mcp"]["name"], "chrome-devtools")
        self.assertEqual(node_rule["mcp"]["command"], "npx")
        self.assertEqual(node_rule["mcp"]["args"], ["-y", "chrome-devtools-mcp"])

        # Rust
        rust_rule = DETECTION_RULES["rust"]
        self.assertIn("Cargo.toml", rust_rule["files"])
        self.assertEqual(rust_rule["mcp"]["name"], "rust-analyzer")
        self.assertEqual(rust_rule["mcp"]["command"], "rust-analyzer")
        self.assertEqual(rust_rule["mcp"]["args"], [])

        # Docker
        docker_rule = DETECTION_RULES["docker"]
        for marker in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]:
            self.assertIn(marker, docker_rule["files"])
        self.assertEqual(docker_rule["mcp"]["name"], "docker-mcp")
        self.assertEqual(docker_rule["mcp"]["command"], "docker-mcp")
        self.assertEqual(docker_rule["mcp"]["args"], [])

        # GenAI
        genai_rule = DETECTION_RULES["genai"]
        for marker in [".gemini", "gemini.json"]:
            self.assertIn(marker, genai_rule["files"])
        self.assertEqual(genai_rule["mcp"]["name"], "gemini-api-docs")
        self.assertEqual(genai_rule["mcp"]["command"], "npx")
        self.assertEqual(genai_rule["mcp"]["args"], ["-y", "@google/gemini-api-docs-mcp"])


class TestInspectCodebase(unittest.TestCase):
    """Test inspect_codebase under various repository setups."""

    def test_empty_directory(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = inspect_codebase(pathlib.Path(tmp_dir))
            self.assertEqual(res["detected_languages"], [])
            self.assertEqual(res["detected_markers"], [])
            self.assertEqual(res["recommended_mcps"], [])

    def test_unrelated_files_directory(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "README.md").write_text("Hello world", encoding="utf-8")
            (tmp_path / "notes.txt").write_text("Notes", encoding="utf-8")
            (tmp_path / "data.csv").write_text("a,b,c\n1,2,3", encoding="utf-8")

            res = inspect_codebase(tmp_path)
            self.assertEqual(res["detected_languages"], [])
            self.assertEqual(res["detected_markers"], [])
            self.assertEqual(res["recommended_mcps"], [])

    def test_nonexistent_directory(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            non_existent = pathlib.Path(tmp_dir) / "does_not_exist"
            res = inspect_codebase(non_existent)
            self.assertEqual(res["detected_languages"], [])
            self.assertEqual(res["detected_markers"], [])
            self.assertEqual(res["recommended_mcps"], [])

    def test_file_path_as_repo_root(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pathlib.Path(tmp_dir) / "some_file.txt"
            file_path.write_text("not a directory", encoding="utf-8")
            res = inspect_codebase(file_path)
            self.assertEqual(res["detected_languages"], [])
            self.assertEqual(res["detected_markers"], [])
            self.assertEqual(res["recommended_mcps"], [])

    def test_string_path_argument(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "requirements.txt").touch()

            res = inspect_codebase(str(tmp_path))
            self.assertIn("python", res["detected_languages"])
            self.assertIn("requirements.txt", res["detected_markers"])
            self.assertEqual(len(res["recommended_mcps"]), 1)
            self.assertEqual(res["recommended_mcps"][0]["name"], "python-mcp")

    def test_detect_python_single_and_multiple_markers(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "pyproject.toml").touch()
            (tmp_path / "setup.py").touch()

            res = inspect_codebase(tmp_path)
            self.assertEqual(res["detected_languages"], ["python"])
            self.assertIn("pyproject.toml", res["detected_markers"])
            self.assertIn("setup.py", res["detected_markers"])
            self.assertEqual(len(res["recommended_mcps"]), 1)
            self.assertEqual(res["recommended_mcps"][0]["name"], "python-mcp")

    def test_detect_node_markers(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "package.json").touch()

            res = inspect_codebase(tmp_path)
            self.assertIn("node", res["detected_languages"])
            self.assertIn("package.json", res["detected_markers"])
            self.assertEqual(res["recommended_mcps"][0]["name"], "chrome-devtools")

    def test_detect_rust_markers(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "Cargo.toml").touch()

            res = inspect_codebase(tmp_path)
            self.assertIn("rust", res["detected_languages"])
            self.assertIn("Cargo.toml", res["detected_markers"])
            self.assertEqual(res["recommended_mcps"][0]["name"], "rust-analyzer")

    def test_detect_docker_markers(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "docker-compose.yaml").touch()

            res = inspect_codebase(tmp_path)
            self.assertIn("docker", res["detected_languages"])
            self.assertIn("docker-compose.yaml", res["detected_markers"])
            self.assertEqual(res["recommended_mcps"][0]["name"], "docker-mcp")

    def test_detect_genai_markers_directory(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / ".gemini").mkdir()

            res = inspect_codebase(tmp_path)
            self.assertIn("genai", res["detected_languages"])
            self.assertIn(".gemini", res["detected_markers"])
            self.assertEqual(res["recommended_mcps"][0]["name"], "gemini-api-docs")

    def test_detect_genai_markers_file(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "gemini.json").touch()

            res = inspect_codebase(tmp_path)
            self.assertIn("genai", res["detected_languages"])
            self.assertIn("gemini.json", res["detected_markers"])
            self.assertEqual(res["recommended_mcps"][0]["name"], "gemini-api-docs")

    def test_detect_multiple_technologies(self):
        from antigravity_init.advisor import inspect_codebase

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "pyproject.toml").touch()
            (tmp_path / "Dockerfile").touch()
            (tmp_path / ".gemini").mkdir()

            res = inspect_codebase(tmp_path)
            self.assertEqual(set(res["detected_languages"]), {"python", "docker", "genai"})
            self.assertIn("pyproject.toml", res["detected_markers"])
            self.assertIn("Dockerfile", res["detected_markers"])
            self.assertIn(".gemini", res["detected_markers"])

            mcp_names = {m["name"] for m in res["recommended_mcps"]}
            self.assertEqual(mcp_names, {"python-mcp", "docker-mcp", "gemini-api-docs"})

    def test_recommended_mcps_are_independent_copies(self):
        from antigravity_init.advisor import inspect_codebase, DETECTION_RULES

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            (tmp_path / "Cargo.toml").touch()

            res = inspect_codebase(tmp_path)
            res["recommended_mcps"][0]["args"].append("--mutated")

            self.assertEqual(DETECTION_RULES["rust"]["mcp"]["args"], [])


class TestGenerateWorkspaceMcpPlugin(unittest.TestCase):
    """Test generate_workspace_mcp_plugin creation of plugin.json and mcp_config.json."""

    def test_generate_with_mcps(self):
        from antigravity_init.advisor import generate_workspace_mcp_plugin

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir)
            confirmed = [
                {
                    "name": "python-mcp",
                    "command": "python3",
                    "args": ["-m", "mcp_server_python"],
                    "description": "Python execution and analysis server",
                },
                {
                    "name": "docker-mcp",
                    "command": "docker-mcp",
                    "args": [],
                    "description": "Docker container inspection server",
                },
            ]

            plugin_path, config_path = generate_workspace_mcp_plugin(workspace, confirmed)

            expected_plugin_dir = workspace / ".agents" / "plugins" / "workspace-mcp"
            self.assertEqual(plugin_path, expected_plugin_dir / "plugin.json")
            self.assertEqual(config_path, expected_plugin_dir / "mcp_config.json")
            self.assertTrue(plugin_path.is_file())
            self.assertTrue(config_path.is_file())

            # Verify plugin.json
            plugin_data = json.loads(plugin_path.read_text(encoding="utf-8"))
            self.assertEqual(plugin_data.get("name"), "workspace-mcp")
            self.assertEqual(
                plugin_data.get("description"),
                "Workspace-scoped MCP servers configured for this project",
            )
            self.assertEqual(plugin_data.get("version"), "0.1.0")

            # Verify mcp_config.json
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("mcpServers", config_data)
            servers = config_data["mcpServers"]
            self.assertEqual(len(servers), 2)
            self.assertEqual(
                servers["python-mcp"],
                {"command": "python3", "args": ["-m", "mcp_server_python"]},
            )
            self.assertEqual(
                servers["docker-mcp"],
                {"command": "docker-mcp", "args": []},
            )

    def test_generate_with_empty_mcps(self):
        from antigravity_init.advisor import generate_workspace_mcp_plugin

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir)
            plugin_path, config_path = generate_workspace_mcp_plugin(workspace, [])

            self.assertTrue(plugin_path.is_file())
            self.assertTrue(config_path.is_file())

            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config_data, {"mcpServers": {}})

    def test_generate_idempotence_and_overwriting(self):
        from antigravity_init.advisor import generate_workspace_mcp_plugin

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir)
            # First call with empty
            generate_workspace_mcp_plugin(workspace, [])

            # Second call with servers
            confirmed = [
                {
                    "name": "rust-analyzer",
                    "command": "rust-analyzer",
                    "args": [],
                    "description": "Rust language server",
                }
            ]
            plugin_path, config_path = generate_workspace_mcp_plugin(workspace, confirmed)

            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("rust-analyzer", config_data["mcpServers"])

    def test_generate_with_string_target_workspace(self):
        from antigravity_init.advisor import generate_workspace_mcp_plugin

        with tempfile.TemporaryDirectory() as tmp_dir:
            plugin_path, config_path = generate_workspace_mcp_plugin(str(tmp_dir), [])
            self.assertTrue(plugin_path.is_file())
            self.assertTrue(config_path.is_file())


class TestInstallProjectAdvisorSkill(unittest.TestCase):
    """Test install_project_advisor_skill deployment and global mirroring."""

    def test_install_workspace_only(self):
        from antigravity_init.advisor import install_project_advisor_skill

        with tempfile.TemporaryDirectory() as tmp_ws:
            ws_path = pathlib.Path(tmp_ws)
            skill_path = install_project_advisor_skill(ws_path, mirror_global=False)

            expected_path = ws_path / ".agents" / "skills" / "project-advisor" / "SKILL.md"
            self.assertEqual(skill_path, expected_path)
            self.assertTrue(skill_path.is_file())

            content = skill_path.read_text(encoding="utf-8")
            self.assertIn("name: project-advisor", content)
            self.assertIn("Antigravity Project Advisor", content)

    def test_install_with_global_mirroring_custom_dir(self):
        from antigravity_init.advisor import install_project_advisor_skill

        with tempfile.TemporaryDirectory() as tmp_ws, tempfile.TemporaryDirectory() as tmp_global:
            ws_path = pathlib.Path(tmp_ws)
            global_dir = pathlib.Path(tmp_global) / "gemini" / "skills"

            skill_path = install_project_advisor_skill(
                ws_path, mirror_global=True, global_dir=global_dir
            )

            self.assertTrue(skill_path.is_file())
            global_skill = global_dir / "project-advisor" / "SKILL.md"
            self.assertTrue(global_skill.is_file())

            ws_content = skill_path.read_text(encoding="utf-8")
            global_content = global_skill.read_text(encoding="utf-8")
            self.assertEqual(ws_content, global_content)

    def test_install_with_default_global_mirroring(self):
        from antigravity_init.advisor import install_project_advisor_skill

        with tempfile.TemporaryDirectory() as tmp_ws, tempfile.TemporaryDirectory() as fake_home:
            ws_path = pathlib.Path(tmp_ws)
            fake_home_path = pathlib.Path(fake_home)

            with mock.patch("pathlib.Path.home", return_value=fake_home_path):
                skill_path = install_project_advisor_skill(ws_path, mirror_global=True)

                self.assertTrue(skill_path.is_file())
                default_global = fake_home_path / ".gemini" / "config" / "skills" / "project-advisor" / "SKILL.md"
                self.assertTrue(default_global.is_file())

    def test_install_missing_template_raises_error(self):
        from antigravity_init.advisor import install_project_advisor_skill

        with tempfile.TemporaryDirectory() as tmp_ws, tempfile.TemporaryDirectory() as fake_templates:
            ws_path = pathlib.Path(tmp_ws)
            with mock.patch("antigravity_init.advisor.TEMPLATES_DIR", pathlib.Path(fake_templates)):
                with self.assertRaises(FileNotFoundError):
                    install_project_advisor_skill(ws_path)

    def test_install_with_string_paths(self):
        from antigravity_init.advisor import install_project_advisor_skill

        with tempfile.TemporaryDirectory() as tmp_ws, tempfile.TemporaryDirectory() as tmp_global:
            skill_path = install_project_advisor_skill(
                str(tmp_ws), mirror_global=True, global_dir=str(tmp_global)
            )
            self.assertTrue(skill_path.is_file())
            self.assertTrue(pathlib.Path(tmp_global, "project-advisor", "SKILL.md").is_file())


class TestPromptMcpSelection(unittest.TestCase):
    """Test prompt_mcp_selection interactive and non-interactive handling."""

    def setUp(self):
        self.recommendations = [
            {
                "name": "python-mcp",
                "command": "python3",
                "args": ["-m", "mcp_server_python"],
                "description": "Python execution and analysis server",
            },
            {
                "name": "docker-mcp",
                "command": "docker-mcp",
                "args": [],
                "description": "Docker container inspection server",
            },
        ]

    def test_empty_recommendations(self):
        from antigravity_init.advisor import prompt_mcp_selection

        self.assertEqual(prompt_mcp_selection([], interactive=False), [])
        self.assertEqual(prompt_mcp_selection([], interactive=True), [])

    def test_non_interactive_returns_empty(self):
        from antigravity_init.advisor import prompt_mcp_selection

        result = prompt_mcp_selection(self.recommendations, interactive=False)
        self.assertEqual(result, [])

    def test_interactive_confirm_all(self):
        from antigravity_init.advisor import prompt_mcp_selection

        prompts = []

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return "y"

        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=fake_input
        )
        self.assertEqual(len(confirmed), 2)
        self.assertEqual(confirmed[0]["name"], "python-mcp")
        self.assertEqual(confirmed[1]["name"], "docker-mcp")
        self.assertEqual(len(prompts), 2)
        self.assertIn("python-mcp", prompts[0])
        self.assertIn("docker-mcp", prompts[1])

    def test_interactive_default_enter_key_is_yes(self):
        from antigravity_init.advisor import prompt_mcp_selection

        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=lambda _: ""
        )
        self.assertEqual(len(confirmed), 2)

    def test_interactive_reject_all(self):
        from antigravity_init.advisor import prompt_mcp_selection

        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=lambda _: "n"
        )
        self.assertEqual(confirmed, [])

    def test_interactive_mixed_responses(self):
        from antigravity_init.advisor import prompt_mcp_selection

        answers = ["yes", "no"]
        confirmed = prompt_mcp_selection(
            self.recommendations,
            interactive=True,
            input_func=lambda _: answers.pop(0),
        )
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["name"], "python-mcp")

    def test_interactive_fallback_to_builtin_input(self):
        from antigravity_init.advisor import prompt_mcp_selection

        with mock.patch("builtins.input", side_effect=["y", "n"]):
            confirmed = prompt_mcp_selection(self.recommendations, interactive=True)
            self.assertEqual(len(confirmed), 1)
            self.assertEqual(confirmed[0]["name"], "python-mcp")

    def test_interactive_whitespace_inputs(self):
        from antigravity_init.advisor import prompt_mcp_selection

        inputs = ["   ", "  no  "]
        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=lambda _: inputs.pop(0)
        )
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["name"], "python-mcp")

    def test_interactive_keyboard_interrupt_aborts_gracefully(self):
        from antigravity_init.advisor import prompt_mcp_selection

        calls = 0

        def fake_input(_: str) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                return "y"
            raise KeyboardInterrupt()

        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=fake_input
        )
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["name"], "python-mcp")

    def test_interactive_eof_error_aborts_gracefully(self):
        from antigravity_init.advisor import prompt_mcp_selection

        def fake_input(_: str) -> str:
            raise EOFError()

        confirmed = prompt_mcp_selection(
            self.recommendations, interactive=True, input_func=fake_input
        )
        self.assertEqual(confirmed, [])


class TestAtomicWriteText(unittest.TestCase):
    """Test internal _atomic_write_text helper."""

    def test_atomic_write_success(self):
        from antigravity_init.advisor import _atomic_write_text

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = pathlib.Path(tmp_dir) / "sub" / "file.txt"
            _atomic_write_text(target, "hello atomic world")
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), "hello atomic world")

    def test_atomic_write_accepts_string_path(self):
        from antigravity_init.advisor import _atomic_write_text

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = str(pathlib.Path(tmp_dir) / "string_path.txt")
            _atomic_write_text(target, "string test")
            self.assertEqual(pathlib.Path(target).read_text(encoding="utf-8"), "string test")

    def test_atomic_write_cleanup_on_failure(self):
        from antigravity_init.advisor import _atomic_write_text

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = pathlib.Path(tmp_dir) / "failure_target.txt"

            with mock.patch("pathlib.Path.replace", side_effect=OSError("Disk full")):
                with self.assertRaises(OSError):
                    _atomic_write_text(target, "will fail")

            self.assertFalse(target.exists())
            sibling_files = list(pathlib.Path(tmp_dir).iterdir())
            self.assertEqual(sibling_files, [])


if __name__ == "__main__":
    unittest.main()
