import copy
import json
import pathlib
import tempfile
import unittest
import urllib.error
import warnings
from unittest import mock

from antigravity_init.research import (
    BUNDLED_TAXONOMY,
    DEFAULT_CACHE_DIR,
    DEFAULT_RESEARCH_URL,
    compile_adversarial_rubric,
    fetch_sota_guidelines,
    load_bundled_rubric,
    save_research_artifacts,
    validate_guidelines_schema,
)


class TestResearchModule(unittest.TestCase):
    def test_module_constants(self):
        """Test module constants exist and match expected types and defaults."""
        self.assertIsInstance(DEFAULT_CACHE_DIR, pathlib.Path)
        self.assertEqual(DEFAULT_CACHE_DIR.name, "antigravity-research")
        self.assertIsInstance(DEFAULT_RESEARCH_URL, str)
        self.assertEqual(DEFAULT_RESEARCH_URL, "")

    def test_bundled_taxonomy_structure(self):
        """Test BUNDLED_TAXONOMY passes schema validation and includes the 5 core categories."""
        self.assertTrue(validate_guidelines_schema(BUNDLED_TAXONOMY))
        categories = BUNDLED_TAXONOMY.get("categories", [])
        self.assertGreaterEqual(len(categories), 5)
        
        cat_names = [cat["name"] for cat in categories]
        self.assertTrue(any("Sycophancy" in name for name in cat_names))
        self.assertTrue(any("Boundary Bug" in name for name in cat_names))
        self.assertTrue(any("Test Mock Leakage" in name for name in cat_names))
        self.assertTrue(any("Hallucinated Import" in name for name in cat_names))
        self.assertTrue(any("Untested Failure" in name for name in cat_names))


class TestLoadBundledRubric(unittest.TestCase):
    def test_load_bundled_rubric_success(self):
        """load_bundled_rubric returns non-empty markdown containing core criteria."""
        content = load_bundled_rubric()
        self.assertIsInstance(content, str)
        self.assertTrue(len(content.strip()) > 0)
        self.assertIn("# Adversarial Code Review Rubric & Failure Mode Taxonomy", content)
        self.assertIn("Sycophancy Detection", content)
        self.assertIn("Boundary Bug Catalog", content)
        self.assertIn("Test Mock Leakage", content)
        self.assertIn("Hallucinated Imports", content)
        self.assertIn("Untested Failure Branches", content)

    def test_load_bundled_rubric_missing_template_raises(self):
        """load_bundled_rubric raises FileNotFoundError if template does not exist."""
        with mock.patch("antigravity_init.research.TEMPLATES_DIR", pathlib.Path("/nonexistent/templates")):
            with self.assertRaises(FileNotFoundError):
                load_bundled_rubric()


class TestValidateGuidelinesSchema(unittest.TestCase):
    def setUp(self):
        self.valid_data = {
            "version": "1.0",
            "categories": [
                {
                    "name": "Cat 1",
                    "description": "Description 1",
                    "detection_rules": ["Rule 1", "Rule 2"],
                    "adversarial_questions": ["Question 1?"],
                }
            ],
        }

    def test_valid_schema(self):
        self.assertTrue(validate_guidelines_schema(self.valid_data))
        self.assertTrue(validate_guidelines_schema(BUNDLED_TAXONOMY))

    def test_non_dict_inputs(self):
        self.assertFalse(validate_guidelines_schema(None))
        self.assertFalse(validate_guidelines_schema("string"))
        self.assertFalse(validate_guidelines_schema([1, 2, 3]))
        self.assertFalse(validate_guidelines_schema(123))

    def test_missing_or_invalid_categories_key(self):
        self.assertFalse(validate_guidelines_schema({}))
        self.assertFalse(validate_guidelines_schema({"categories": "not a list"}))
        self.assertFalse(validate_guidelines_schema({"categories": []}))

    def test_invalid_category_items(self):
        self.assertFalse(validate_guidelines_schema({"categories": ["not a dict"]}))
        
        # Missing name
        invalid_cat1 = {
            "categories": [
                {
                    "description": "Desc",
                    "detection_rules": [],
                    "adversarial_questions": [],
                }
            ]
        }
        self.assertFalse(validate_guidelines_schema(invalid_cat1))

        # Blank or non-string name
        invalid_cat1_name = {
            "categories": [
                {
                    "name": "   ",
                    "description": "Desc",
                    "detection_rules": [],
                    "adversarial_questions": [],
                }
            ]
        }
        self.assertFalse(validate_guidelines_schema(invalid_cat1_name))

        # Missing description
        invalid_cat2 = {
            "categories": [
                {
                    "name": "Cat",
                    "detection_rules": [],
                    "adversarial_questions": [],
                }
            ]
        }
        self.assertFalse(validate_guidelines_schema(invalid_cat2))

        # Missing or non-list detection_rules
        invalid_cat3 = {
            "categories": [
                {
                    "name": "Cat",
                    "description": "Desc",
                    "detection_rules": "invalid",
                    "adversarial_questions": [],
                }
            ]
        }
        self.assertFalse(validate_guidelines_schema(invalid_cat3))

        # Missing or non-list adversarial_questions
        invalid_cat4 = {
            "categories": [
                {
                    "name": "Cat",
                    "description": "Desc",
                    "detection_rules": [],
                    "adversarial_questions": "invalid",
                }
            ]
        }
        self.assertFalse(validate_guidelines_schema(invalid_cat4))


class TestFetchSOTAGuidelines(unittest.TestCase):
    def setUp(self):
        self.sample_custom = {
            "version": "2.0.0",
            "categories": [
                {
                    "name": "Custom Category",
                    "description": "Custom Description",
                    "detection_rules": ["Rule A"],
                    "adversarial_questions": ["Question A?"],
                }
            ],
        }

    def test_offline_mode_reads_valid_cache(self):
        """When offline=True and cache exists with valid schema, load from cache."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            cache_file = cache_dir / "sota_guidelines.json"
            cache_file.write_text(json.dumps(self.sample_custom), encoding="utf-8")

            result = fetch_sota_guidelines(cache_dir=cache_dir, offline=True)
            self.assertEqual(result, self.sample_custom)

    def test_offline_mode_no_cache_falls_back_to_bundled(self):
        """When offline=True and no cache exists, return BUNDLED_TAXONOMY."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            result = fetch_sota_guidelines(cache_dir=cache_dir, offline=True)
            self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_offline_mode_corrupted_cache_falls_back_to_bundled(self):
        """When offline=True and cache has malformed JSON or invalid schema, return BUNDLED_TAXONOMY."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            cache_file = cache_dir / "sota_guidelines.json"
            cache_file.write_text("{malformed: json", encoding="utf-8")

            result = fetch_sota_guidelines(cache_dir=cache_dir, offline=True)
            self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_offline_mode_invalid_schema_cache_falls_back_to_bundled(self):
        """When offline=True and cache fails schema validation, return BUNDLED_TAXONOMY."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            cache_file = cache_dir / "sota_guidelines.json"
            cache_file.write_text(json.dumps({"invalid": "schema"}), encoding="utf-8")

            result = fetch_sota_guidelines(cache_dir=cache_dir, offline=True)
            self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_successful_http_fetch_and_caching(self):
        """When online and HTTP fetch succeeds, parse, cache, and return data."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/sota.json"
            raw_json = json.dumps(self.sample_custom).encode("utf-8")

            mock_response = mock.MagicMock()
            mock_response.read.return_value = raw_json
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
                result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)
                mock_urlopen.assert_called_once()
                self.assertEqual(result, self.sample_custom)

                # Verify cache file was written
                cache_file = cache_dir / "sota_guidelines.json"
                self.assertTrue(cache_file.is_file())
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                self.assertEqual(cached_data, self.sample_custom)

    def test_online_mode_http_error_falls_back_to_existing_cache(self):
        """When online fetch fails with HTTP error, warn and fall back to valid cache."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            cache_file = cache_dir / "sota_guidelines.json"
            cache_file.write_text(json.dumps(self.sample_custom), encoding="utf-8")

            url = "https://example.com/sota.json"
            with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("Failed to fetch SOTA guidelines", str(recorded_warnings[0].message))
                    self.assertEqual(result, self.sample_custom)

    def test_online_mode_http_timeout_falls_back_to_bundled_when_no_cache(self):
        """When online fetch times out and no cache exists, warn and fall back to bundled taxonomy."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/sota.json"
            with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("Failed to fetch SOTA guidelines", str(recorded_warnings[0].message))
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_malformed_json_falls_back_to_bundled(self):
        """When online fetch returns malformed JSON, warn and fall back to bundled taxonomy."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/sota.json"
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"{broken: json"
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_invalid_schema_response_falls_back_to_bundled(self):
        """When online fetch returns valid JSON that fails schema validation, warn and fall back to bundled."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/sota.json"
            mock_response = mock.MagicMock()
            mock_response.read.return_value = json.dumps({"unsupported": "format"}).encode("utf-8")
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("failed schema validation", str(recorded_warnings[0].message))
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_no_url_uses_cache_or_bundled(self):
        """When online mode is requested with no URL or empty string, read cache or bundled without error."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            # Without cache
            result = fetch_sota_guidelines(url="", cache_dir=cache_dir, offline=False)
            self.assertEqual(result, BUNDLED_TAXONOMY)

            # With cache
            cache_file = cache_dir / "sota_guidelines.json"
            cache_file.write_text(json.dumps(self.sample_custom), encoding="utf-8")
            result2 = fetch_sota_guidelines(url=None, cache_dir=cache_dir, offline=False)
            self.assertEqual(result2, self.sample_custom)

    def test_online_mode_unsupported_scheme_warns_and_falls_back(self):
        """Unsupported URL schemes (e.g. file://, ftp://) or missing netloc warn and fall back."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            for bad_url in ["file:///etc/passwd", "ftp://example.com/data.json", "http://", "gopher://bad"]:
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=bad_url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("Unsupported or invalid URL", str(recorded_warnings[0].message))
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_response_too_large_warns_and_falls_back(self):
        """Responses exceeding safety limits warn and fall back without hanging or OOM."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/large.json"
            mock_response = mock.MagicMock()
            # Return slightly more than 5 MB
            mock_response.read.return_value = b"x" * (5 * 1024 * 1024 + 2)
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("response exceeded", str(recorded_warnings[0].message))
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_online_mode_non_utf8_response_warns_and_falls_back(self):
        """Non-UTF-8 responses trigger a warning and gracefully fall back."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            url = "https://example.com/binary.json"
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"\x80\x81\x82\x83"
            mock_response.__enter__.return_value = mock_response

            with mock.patch("urllib.request.urlopen", return_value=mock_response):
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    warnings.simplefilter("always")
                    result = fetch_sota_guidelines(url=url, cache_dir=cache_dir, offline=False)

                    self.assertEqual(len(recorded_warnings), 1)
                    self.assertIn("Failed to fetch SOTA guidelines", str(recorded_warnings[0].message))
                    self.assertEqual(result, BUNDLED_TAXONOMY)

    def test_bundled_taxonomy_mutation_isolation(self):
        """Mutating the dict returned from fetch_sota_guidelines does not mutate BUNDLED_TAXONOMY."""
        with tempfile.TemporaryDirectory() as td:
            cache_dir = pathlib.Path(td)
            result = fetch_sota_guidelines(cache_dir=cache_dir, offline=True)
            original_name = BUNDLED_TAXONOMY["categories"][0]["name"]

            # Mutate the returned dictionary
            result["categories"][0]["name"] = "MUTATED_CATEGORY_NAME"
            self.assertEqual(BUNDLED_TAXONOMY["categories"][0]["name"], original_name)
            self.assertNotEqual(BUNDLED_TAXONOMY["categories"][0]["name"], "MUTATED_CATEGORY_NAME")


class TestCompileAdversarialRubric(unittest.TestCase):
    def test_compile_none_or_invalid_returns_bundled_rubric(self):
        """None or invalid data returns load_bundled_rubric()."""
        bundled_rubric = load_bundled_rubric()
        self.assertEqual(compile_adversarial_rubric(None), bundled_rubric)
        self.assertEqual(compile_adversarial_rubric({}), bundled_rubric)
        self.assertEqual(compile_adversarial_rubric({"categories": "invalid"}), bundled_rubric)

    def test_compile_bundled_taxonomy_contains_all_five_sections(self):
        """Compiling BUNDLED_TAXONOMY includes the 5 core sections and checklist rules."""
        content = compile_adversarial_rubric(BUNDLED_TAXONOMY)
        self.assertIn("# Adversarial Code Review Rubric & Failure Mode Taxonomy", content)
        self.assertIn("Sycophancy Detection", content)
        self.assertIn("Boundary Bug Catalog", content)
        self.assertIn("Test Mock Leakage", content)
        self.assertIn("Hallucinated Imports", content)
        self.assertIn("Untested Failure Branches", content)
        self.assertIn("- [ ] **", content)
        self.assertIn("- [ ] *Interrogation:*", content)

    def test_compile_custom_guidelines(self):
        """Compiling custom structured taxonomy produces correct headers and checklist items."""
        custom_data = {
            "categories": [
                {
                    "name": "Race Conditions & Locks",
                    "description": "Concurrency issues in multi-threaded workflows.",
                    "detection_rules": ["Shared variable mutation without mutex"],
                    "adversarial_questions": ["Is this thread-safe?"],
                }
            ]
        }
        content = compile_adversarial_rubric(custom_data)
        self.assertIn("# Adversarial Code Review Rubric & Failure Mode Taxonomy", content)
        self.assertIn("## 1. Race Conditions & Locks", content)
        self.assertIn("Concurrency issues in multi-threaded workflows.", content)
        self.assertIn("- [ ] **Shared variable mutation without mutex**", content)
        self.assertIn("- [ ] *Interrogation:* Is this thread-safe?", content)

    def test_compile_skips_empty_rules_and_questions(self):
        """Empty or whitespace-only rules and questions are skipped."""
        custom_data = {
            "categories": [
                {
                    "name": "Edge Cases",
                    "description": "Testing empty lists",
                    "detection_rules": ["Valid Rule", "   ", ""],
                    "adversarial_questions": ["Valid Question?", "", "  "],
                }
            ]
        }
        content = compile_adversarial_rubric(custom_data)
        self.assertIn("- [ ] **Valid Rule**", content)
        self.assertNotIn("- [ ] ****\n", content)
        self.assertIn("- [ ] *Interrogation:* Valid Question?", content)
        self.assertNotIn("- [ ] *Interrogation:* \n", content)


class TestSaveResearchArtifacts(unittest.TestCase):
    def test_save_artifacts_rubric_only(self):
        """save_research_artifacts writes adversarial_review.md in target_workspace/.agents/scratch/research/."""
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td)
            rubric_text = "# Test Rubric\n\nContent here."

            ret_path = save_research_artifacts(workspace, rubric_text)
            expected_path = workspace / ".agents" / "scratch" / "research" / "adversarial_review.md"

            self.assertEqual(ret_path, expected_path)
            self.assertTrue(expected_path.is_file())
            self.assertEqual(expected_path.read_text(encoding="utf-8"), rubric_text)

            # JSON file should not be created if raw_data is None
            json_file = workspace / ".agents" / "scratch" / "research" / "sota_guidelines.json"
            self.assertFalse(json_file.exists())

    def test_save_artifacts_with_raw_data(self):
        """save_research_artifacts writes both adversarial_review.md and sota_guidelines.json."""
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td)
            rubric_text = "# Test Rubric"
            raw_data = {"version": "1.0", "categories": []}

            ret_path = save_research_artifacts(workspace, rubric_text, raw_data=raw_data)
            expected_path = workspace / ".agents" / "scratch" / "research" / "adversarial_review.md"
            json_path = workspace / ".agents" / "scratch" / "research" / "sota_guidelines.json"

            self.assertEqual(ret_path, expected_path)
            self.assertTrue(expected_path.is_file())
            self.assertTrue(json_path.is_file())

            loaded_json = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_json, raw_data)

    def test_save_artifacts_creates_parent_directories_if_missing(self):
        """save_research_artifacts automatically creates non-existent parent directory tree."""
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td) / "nested" / "project"
            rubric_text = "# Test Rubric"

            ret_path = save_research_artifacts(workspace, rubric_text)
            self.assertTrue(ret_path.is_file())


if __name__ == "__main__":
    unittest.main()
