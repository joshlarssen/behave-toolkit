from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from behave_toolkit import (
    ConfigError,
    IntegrationError,
    Scope,
    activate_feature_scope,
    install,
)


class PluginInstallationTests(unittest.TestCase):
    def test_install_attaches_manager_to_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  browser:
                    factory: pathlib.Path
                    scope: feature
                    args:
                      - .
                """,
                encoding="utf-8",
            )

            context = SimpleNamespace()
            manager = install(context, config_path)

            self.assertIs(context.toolkit, manager)
            self.assertEqual(manager.list_objects(), ["browser"])
            self.assertEqual(manager.objects_for_scope(Scope.FEATURE)[0].name, "browser")

    def test_install_rejects_namespace_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text("objects: {}", encoding="utf-8")

            context = SimpleNamespace(toolkit="occupied")
            with self.assertRaises(IntegrationError) as exc:
                install(context, config_path)

        message = str(exc.exception)
        self.assertIn("namespace 'toolkit'", message)
        self.assertIn("Choose another namespace", message)

    def test_activate_feature_scope_without_install_mentions_before_all(self) -> None:
        with self.assertRaises(IntegrationError) as exc:
            activate_feature_scope(SimpleNamespace())

        message = str(exc.exception)
        self.assertIn("before_all", message)
        self.assertIn("install(context, ...)", message)
        self.assertIn("activate_feature_scope", message)

    def test_install_reports_invalid_scope_with_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  browser:
                    factory: pathlib.Path
                    scope: invalid
                    args:
                      - .
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                install(SimpleNamespace(), config_path, activate_global=False)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("Unsupported scope 'invalid'", message)

    def test_install_reports_bad_factory_import_with_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  browser:
                    factory: demo.browser.Factory
                    scope: feature
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                install(SimpleNamespace(), config_path, activate_global=False)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("demo.browser.Factory", message)
        self.assertIn("importable", message)

    def test_install_accepts_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "behave-toolkit"
            config_dir.mkdir()
            (config_dir / "10-objects.yaml").write_text(
                """
                objects:
                  browser:
                    factory: pathlib.Path
                    scope: feature
                    args:
                      - .
                """,
                encoding="utf-8",
            )

            context = SimpleNamespace()
            manager = install(context, config_dir)

        self.assertIs(context.toolkit, manager)
        self.assertEqual(manager.list_objects(), ["browser"])


if __name__ == "__main__":
    unittest.main()
