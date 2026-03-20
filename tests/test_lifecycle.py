from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from behave.runner import scoped_context_layer

from behave_toolkit import (
    Scope,
    activate_feature_scope,
    activate_scenario_scope,
    install,
)
from test_support import EVENTS, make_context, reset_events


class LifecycleManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_events()

    def test_install_creates_global_objects_and_cleans_them_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  session_client:
                    factory: test_support.build_tracking_resource
                    scope: global
                    args:
                      - session
                    cleanup: close
                """,
                encoding="utf-8",
            )

            context = make_context()
            manager = install(context, config_path)

            self.assertEqual(EVENTS, [("create", "session")])
            self.assertEqual(context.session_client.label, "session")
            self.assertIs(manager.instance("session_client"), context.session_client)

            context._do_cleanups()  # pylint: disable=protected-access

            self.assertEqual(
                EVENTS,
                [("create", "session"), ("cleanup", "session")],
            )
            self.assertEqual(manager.active_objects(Scope.GLOBAL), {})
            self.assertFalse(hasattr(context, "session_client"))

    def test_feature_and_scenario_objects_follow_scope_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  browser_session:
                    factory: test_support.build_tracking_resource
                    scope: feature
                    inject_as: browser
                    args:
                      - browser
                    cleanup: close
                  api_client:
                    factory: test_support.build_tracking_resource
                    scope: scenario
                    args:
                      - api
                    cleanup: close
                """,
                encoding="utf-8",
            )

            context = make_context()
            manager = install(context, config_path)

            self.assertEqual(EVENTS, [])

            with scoped_context_layer(context, layer="feature"):
                activate_feature_scope(context)
                browser = context.browser

                self.assertEqual(EVENTS, [("create", "browser")])
                self.assertIs(manager.instance("browser_session"), browser)
                self.assertEqual(
                    manager.active_objects(Scope.FEATURE),
                    {"browser_session": browser},
                )

                with scoped_context_layer(context, layer="scenario"):
                    activate_scenario_scope(context)
                    api_client = context.api_client

                    self.assertEqual(
                        EVENTS,
                        [("create", "browser"), ("create", "api")],
                    )
                    self.assertIs(manager.instance("api_client"), api_client)
                    self.assertEqual(
                        manager.active_objects(Scope.SCENARIO),
                        {"api_client": api_client},
                    )

                self.assertEqual(
                    EVENTS,
                    [("create", "browser"), ("create", "api"), ("cleanup", "api")],
                )
                self.assertFalse(hasattr(context, "api_client"))
                self.assertTrue(hasattr(context, "browser"))

            self.assertEqual(
                EVENTS,
                [
                    ("create", "browser"),
                    ("create", "api"),
                    ("cleanup", "api"),
                    ("cleanup", "browser"),
                ],
            )
            self.assertEqual(manager.active_objects(Scope.FEATURE), {})
            self.assertFalse(hasattr(context, "browser"))

    def test_invalid_cleanup_attribute_raises_before_binding_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  api_client:
                    factory: test_support.build_tracking_resource
                    scope: scenario
                    args:
                      - api
                    cleanup: missing_method
                """,
                encoding="utf-8",
            )

            context = make_context()
            manager = install(context, config_path)

            with scoped_context_layer(context, layer="scenario"):
                with self.assertRaises(AttributeError) as exc:
                    activate_scenario_scope(context)

            self.assertIn("missing_method", str(exc.exception))
            self.assertFalse(hasattr(context, "api_client"))
            self.assertEqual(manager.active_objects(Scope.SCENARIO), {})

    def test_install_rejects_context_name_matching_manager_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  manager_alias:
                    factory: test_support.build_tracking_resource
                    scope: feature
                    inject_as: toolkit
                    args:
                      - bad
                """,
                encoding="utf-8",
            )

            context = make_context()
            with self.assertRaises(ValueError):
                install(context, config_path)

            self.assertFalse(hasattr(context, "toolkit"))

    def test_step_scope_activation_is_not_implemented_yet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  temp_value:
                    factory: test_support.build_tracking_resource
                    scope: step
                    args:
                      - temp
                """,
                encoding="utf-8",
            )

            context = make_context()
            manager = install(context, config_path)

            with self.assertRaises(NotImplementedError):
                manager.activate_scope(context, Scope.STEP)


if __name__ == "__main__":
    unittest.main()
