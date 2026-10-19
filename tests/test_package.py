import pathlib
import unittest
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # pragma: no cover

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestPackageMetadata(unittest.TestCase):
    def test_version(self):
        import antigravity_init
        self.assertEqual(antigravity_init.__version__, "0.1.0")

    def test_pyproject_toml_configuration(self):
        pyproject_path = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.is_file(), "pyproject.toml must exist in repo root")

        content = pyproject_path.read_text(encoding="utf-8")
        data = tomllib.loads(content)

        self.assertIn("project", data)
        project = data["project"]
        self.assertEqual(project.get("version"), "0.1.0")

        # Zero runtime dependencies check
        dependencies = project.get("dependencies", [])
        self.assertEqual(dependencies, [], "Must have zero runtime dependencies")

        # CLI script entrypoint check
        scripts = project.get("scripts", {})
        self.assertEqual(
            scripts.get("antigravity-init"),
            "antigravity_init.cli:main",
            "Project scripts must define antigravity-init = antigravity_init.cli:main",
        )

        # Package-data configuration check
        tool_data = data.get("tool", {}).get("setuptools", {}).get("package-data", {})
        self.assertIn("antigravity_init", tool_data, "package-data must configure antigravity_init")

    def test_package_main_entrypoint(self):
        import antigravity_init.__main__ as pkg_main
        # Ensure main() can be executed cleanly and returns 0 exit code
        self.assertEqual(pkg_main.main(), 0)

    def test_bundled_templates_presence(self):
        import antigravity_init
        templates_dir = antigravity_init.TEMPLATES_DIR
        self.assertTrue(templates_dir.is_dir(), "TEMPLATES_DIR must exist and be a directory")

        expected_templates = [
            "rubrics/adversarial_review.md",
            "rules/ultra-routing.md",
            "skills/project-advisor.md",
            "skills/quota-mode.md",
            "skills/run-pipeline.md",
            "agents/sp-architect-argon.md",
            "agents/sp-planner-argon.md",
            "agents/sp-implementer-argon.md",
            "agents/sp-implementer-sonnet.md",
            "agents/sp-implementer-flash.md",
            "agents/sp-spec-reviewer-flash.md",
            "agents/sp-quality-reviewer-claude.md",
            "agents/sp-quality-reviewer-argon.md",
            "agents/sp-quality-reviewer-flash.md",
        ]

        for rel_path in expected_templates:
            tpl_path = templates_dir / rel_path
            self.assertTrue(tpl_path.is_file(), f"Template {rel_path} must exist at {tpl_path}")
            content = tpl_path.read_text(encoding="utf-8")
            self.assertTrue(len(content.strip()) > 0, f"Template {rel_path} must not be empty")

    def test_adversarial_review_rubric_content(self):
        import antigravity_init
        rubric_path = antigravity_init.TEMPLATES_DIR / "rubrics" / "adversarial_review.md"
        content = rubric_path.read_text(encoding="utf-8")
        self.assertIn("Sycophancy Detection", content)
        self.assertIn("Boundary Bug Catalog", content)
        self.assertIn("Test Mock Leakage", content)
        self.assertIn("Hallucinated Imports", content)
        self.assertIn("Untested Failure Branches & Error Handling", content)

    def test_agent_templates_frontmatter(self):
        import antigravity_init
        agents_dir = antigravity_init.TEMPLATES_DIR / "agents"
        agent_names = [
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
        for name in agent_names:
            agent_file = agents_dir / f"{name}.md"
            content = agent_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"{name}.md must start with YAML frontmatter")
            # Verify YAML frontmatter has opening and closing delimiters
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{name}.md frontmatter must close with '---'")
            frontmatter_body = parts[1]
            self.assertIn(f"name: {name}", frontmatter_body, f"{name}.md must specify its own name")
            self.assertIn("subagent: true", frontmatter_body, f"{name}.md must specify subagent: true")
            self.assertIn("model:", frontmatter_body, f"{name}.md must specify model")
            self.assertIn("tools:", frontmatter_body, f"{name}.md must specify tools")


if __name__ == "__main__":
    unittest.main()
