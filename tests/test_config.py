from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from behave_toolkit import ConfigError, Scope, load_config, load_yaml_file, load_yaml_text


class ConfigLoadingTests(unittest.TestCase):
    def test_load_yaml_text_normalizes_object_specs(self) -> None:
        config = load_yaml_text(
            """
            version: 1
            objects:
              api_client:
                factory: demo.clients.ApiClient
                scope: scenario
                kwargs:
                  base_url: https://example.test
                cleanup: close
            """
        )

        self.assertEqual(config.version, 1)
        self.assertEqual(config.require("api_client").scope, Scope.SCENARIO)
        self.assertEqual(
            config.require("api_client").kwargs,
            {"base_url": "https://example.test"},
        )

    def test_scope_alias_maps_testrun_to_global(self) -> None:
        config = load_config(
            {
                "objects": {
                    "browser": {
                        "factory": "demo.browser.Factory",
                        "scope": "testrun",
                    }
                }
            }
        )

        self.assertEqual(config.require("browser").scope, Scope.GLOBAL)

    def test_variables_are_loaded_from_root_section(self) -> None:
        config = load_config(
            {
                "variables": {
                    "api_base_url": "https://example.test",
                },
                "objects": {},
            }
        )

        self.assertEqual(
            config.require_variable("api_base_url"),
            "https://example.test",
        )

    def test_invalid_objects_section_raises_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_config({"objects": []})

    def test_load_yaml_file_reports_source_path_for_invalid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text("objects:\n  browser: [\n", encoding="utf-8")

            with self.assertRaises(ConfigError) as exc:
                load_yaml_file(config_path)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("Could not parse behave-toolkit config", message)


if __name__ == "__main__":
    unittest.main()
