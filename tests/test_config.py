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

    def test_parser_helpers_are_loaded_from_root_section(self) -> None:
        config = load_config(
            {
                "parsers": {
                    "step_matcher": "cfparse",
                    "types": {
                        "Status": {
                            "enum": "demo.types.Status",
                            "case_sensitive": False,
                        },
                        "Priority": "demo.types.parse_priority",
                    },
                },
                "objects": {},
            }
        )

        self.assertEqual(config.parsers.step_matcher, "cfparse")
        self.assertEqual(config.parsers.types["Status"].enum, "demo.types.Status")
        self.assertFalse(config.parsers.types["Status"].case_sensitive)
        self.assertEqual(
            config.parsers.types["Priority"].converter,
            "demo.types.parse_priority",
        )

    def test_parser_type_requires_exactly_one_source(self) -> None:
        with self.assertRaises(ConfigError):
            load_config(
                {
                    "parsers": {
                        "types": {
                            "Status": {
                                "converter": "demo.types.parse_status",
                                "enum": "demo.types.Status",
                            }
                        }
                    }
                }
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

    def test_load_yaml_file_accepts_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "behave-toolkit"
            config_dir.mkdir()
            (config_dir / "00-variables.yaml").write_text(
                """
                version: 1
                variables:
                  report_name: report.json
                """,
                encoding="utf-8",
            )
            (config_dir / "10-objects.yaml").write_text(
                """
                objects:
                  report_path:
                    factory: pathlib.Path
                    scope: global
                    args:
                      - reports
                      - $var: report_name
                """,
                encoding="utf-8",
            )
            (config_dir / "20-parsers.yaml").write_text(
                """
                parsers:
                  step_matcher: cfparse
                  types:
                    Status:
                      converter: demo.types.parse_status
                      pattern: active|pending
                """,
                encoding="utf-8",
            )
            (config_dir / "30-logging.yaml").write_text(
                """
                logging:
                  test_run:
                    path:
                      $ref: report_path
                    logger_name: smoke-tests
                    inject_as: test_logger
                    console: false
                """,
                encoding="utf-8",
            )

            config = load_yaml_file(config_dir)

        self.assertEqual(config.version, 1)
        self.assertEqual(config.require_variable("report_name"), "report.json")
        self.assertEqual(config.require("report_path").scope, Scope.GLOBAL)
        self.assertEqual(config.parsers.step_matcher, "cfparse")
        self.assertEqual(
            config.parsers.types["Status"].converter,
            "demo.types.parse_status",
        )
        self.assertEqual(
            config.logging.loggers["test_run"].effective_logger_name,
            "smoke-tests",
        )
        self.assertEqual(config.logging.loggers["test_run"].context_name, "test_logger")

    def test_load_yaml_file_rejects_duplicate_names_across_directory_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "behave-toolkit"
            config_dir.mkdir()
            (config_dir / "10-objects.yaml").write_text(
                """
                objects:
                  browser:
                    factory: pathlib.Path
                    args:
                      - .
                """,
                encoding="utf-8",
            )
            (config_dir / "20-more-objects.yaml").write_text(
                """
                objects:
                  browser:
                    factory: pathlib.Path
                    args:
                      - elsewhere
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                load_yaml_file(config_dir)

        message = str(exc.exception)
        self.assertIn(str(config_dir.resolve()), message)
        self.assertIn("defines 'browser' more than once", message)

    def test_logging_level_is_validated_during_config_load(self) -> None:
        with self.assertRaises(ConfigError):
            load_config(
                {
                    "logging": {
                        "test_run": {
                            "path": "artifacts/test-run.log",
                            "level": "LOUD",
                        }
                    }
                }
            )


if __name__ == "__main__":
    unittest.main()
