from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from behave.runner import scoped_context_layer

from behave_toolkit import (
    ConfigError,
    IntegrationError,
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
                    factory: test_support.build_dependent_resource
                    scope: scenario
                    args:
                      - $ref: browser_session
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
                    self.assertIs(api_client.dependency, browser)
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

    def test_variables_and_stdlib_factories_can_be_combined(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                variables:
                  report_name: report.json
                objects:
                  workspace:
                    factory: tempfile.TemporaryDirectory
                    scope: feature
                    cleanup: cleanup
                  workspace_path:
                    factory: pathlib.Path
                    scope: feature
                    args:
                      - $ref: workspace
                        attr: name
                  report_path:
                    factory: pathlib.Path
                    scope: scenario
                    args:
                      - $ref: workspace_path
                      - $var: report_name
                """,
                encoding="utf-8",
            )

            context = make_context()
            install(context, config_path)

            with scoped_context_layer(context, layer="feature"):
                activate_feature_scope(context)
                self.assertEqual(context.workspace_path, Path(context.workspace.name))

                with scoped_context_layer(context, layer="scenario"):
                    activate_scenario_scope(context)
                    self.assertEqual(
                        context.report_path,
                        Path(context.workspace.name) / "report.json",
                    )

    def test_invalid_narrower_scope_reference_is_rejected_during_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  scenario_value:
                    factory: test_support.build_tracking_resource
                    scope: scenario
                    args:
                      - scenario
                    cleanup: close
                  feature_value:
                    factory: test_support.build_dependent_resource
                    scope: feature
                    args:
                      - $ref: scenario_value
                      - feature
                    cleanup: close
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                install(make_context(), config_path)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("args[0]", message)
        self.assertIn("narrower scope", message)

    def test_circular_object_references_are_rejected_during_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  alpha:
                    factory: test_support.build_dependent_resource
                    scope: scenario
                    args:
                      - $ref: beta
                      - alpha
                    cleanup: close
                  beta:
                    factory: test_support.build_dependent_resource
                    scope: scenario
                    args:
                      - $ref: alpha
                      - beta
                    cleanup: close
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                install(make_context(), config_path)

        self.assertIn("Circular object reference", str(exc.exception))

    def test_missing_variable_is_rejected_during_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            config_path.write_text(
                """
                objects:
                  report_path:
                    factory: pathlib.Path
                    scope: scenario
                    args:
                      - $var: missing_name
                """,
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as exc:
                install(make_context(), config_path)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("missing_name", message)
        self.assertIn("args[0]", message)

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
                with self.assertRaises(ConfigError) as exc:
                    activate_scenario_scope(context)

            message = str(exc.exception)
            self.assertIn(str(config_path.resolve()), message)
            self.assertIn("missing_method", message)
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
            with self.assertRaises(ConfigError):
                install(context, config_path)

            self.assertFalse(hasattr(context, "toolkit"))

    def test_missing_global_dependency_reports_hook_order(self) -> None:
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
                  api_client:
                    factory: test_support.build_dependent_resource
                    scope: scenario
                    args:
                      - $ref: session_client
                      - api
                    cleanup: close
                """,
                encoding="utf-8",
            )

            context = make_context()
            install(context, config_path, activate_global=False)

            with scoped_context_layer(context, layer="scenario"):
                with self.assertRaises(IntegrationError) as exc:
                    activate_scenario_scope(context)

        message = str(exc.exception)
        self.assertIn("activate_global_scope(context)", message)
        self.assertIn("before_all", message)

    def test_step_scope_is_rejected_during_install(self) -> None:
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

            with self.assertRaises(ConfigError) as exc:
                install(make_context(), config_path)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("Unsupported scope 'step'", message)


if __name__ == "__main__":
    unittest.main()
