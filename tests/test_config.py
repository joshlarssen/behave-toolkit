from __future__ import annotations

import unittest

from behave_toolkit import Scope, load_config, load_yaml_text


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

    def test_invalid_objects_section_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            load_config({"objects": []})


if __name__ == "__main__":
    unittest.main()
