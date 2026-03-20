from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from behave_toolkit import Scope, install


class PluginInstallationTests(unittest.TestCase):
    def test_install_attaches_manager_to_context(self) -> None:
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
            with self.assertRaises(AttributeError):
                install(context, config_path)


if __name__ == "__main__":
    unittest.main()
