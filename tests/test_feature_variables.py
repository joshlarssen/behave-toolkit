from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from behave.configuration import Configuration
from behave.model import Feature
from behave.parser import parse_file
from behave.runner import Context, Runner

from behave_toolkit import IntegrationError, install, substitute_feature_variables


class FeatureVariableSubstitutionTests(unittest.TestCase):
    def test_substitute_feature_variables_replaces_feature_text_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature = self._parse_feature(
                root,
                """
                Feature: {{var:suite_name}}
                  About {{var:run_label}}

                  Background: Shared {{var:run_label}} setup
                    Given a background step {{var:user_kind}}

                  Scenario: Login {{var:run_label}}
                    Given I use {{var:user_kind}}
                      \"\"\"
                      doc {{var:doc_value}}
                      \"\"\"
                    And a table
                      | {{var:column_name}} | state |
                      | {{var:cell_value}} | ok |
                """,
            )
            context = self._install_context(
                feature,
                """
                version: 1
                variables:
                  suite_name: Billing smoke
                  run_label: nightly
                  user_kind: active
                  doc_value: ready
                  column_name: target
                  cell_value: report.json
                """,
            )

            replacements = substitute_feature_variables(context)
            second_pass = substitute_feature_variables(context)

            scenario = feature.walk_scenarios()[0]
            self.assertEqual(replacements, 9)
            self.assertEqual(second_pass, 0)
            self.assertEqual(feature.name, "Billing smoke")
            self.assertEqual(feature.description, ["About nightly"])
            self.assertIsNotNone(feature.background)
            self.assertEqual(feature.background.name, "Shared nightly setup")
            self.assertEqual(feature.background.steps[0].name, "a background step active")
            self.assertEqual(scenario.name, "Login nightly")
            self.assertEqual(scenario.steps[0].name, "I use active")
            self.assertEqual(scenario.steps[0].text, "doc ready")
            self.assertEqual(scenario.steps[1].table.headings, ["target", "state"])
            self.assertEqual(scenario.steps[1].table.rows[0].cells, ["report.json", "ok"])

    def test_substitute_feature_variables_supports_nested_variable_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature = self._parse_feature(
                root,
                """
                Feature: Nested vars

                  Scenario: Alias
                    Given the status is {{var:selected_status}}
                """,
            )
            context = self._install_context(
                feature,
                """
                version: 1
                variables:
                  base_status: active
                  selected_status:
                    $var: base_status
                """,
            )

            replacements = substitute_feature_variables(context)

            self.assertEqual(replacements, 1)
            self.assertEqual(feature.walk_scenarios()[0].steps[0].name, "the status is active")

    def test_substitute_feature_variables_updates_scenario_outline_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature = self._parse_feature(
                root,
                """
                Feature: Outline feature

                  Scenario Outline: {{var:suite_name}} <kind>
                    Given {{var:prefix}} <kind>

                    Examples:
                      | kind |
                      | {{var:first_kind}} |
                      | guest |
                """,
            )
            context = self._install_context(
                feature,
                """
                version: 1
                variables:
                  suite_name: Login
                  prefix: hello
                  first_kind: active
                """,
            )

            substitute_feature_variables(context)

            outline = feature.run_items[0]
            self.assertEqual(outline.name, "Login <kind>")
            self.assertEqual(outline.steps[0].name, "hello <kind>")
            self.assertEqual(outline.examples[0].table.rows[0].cells[0], "active")
            self.assertEqual(
                [scenario.name for scenario in outline.scenarios],
                ["Login active -- @1.1 ", "Login guest -- @1.2 "],
            )
            self.assertEqual(
                [scenario.steps[0].name for scenario in outline.scenarios],
                ["hello active", "hello guest"],
            )

    def test_substitute_feature_variables_requires_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = self._parse_feature(
                Path(tmpdir),
                """
                Feature: Missing install

                  Scenario: Broken
                    Given a step
                """,
            )
            context = self._make_context([feature])

            with self.assertRaises(IntegrationError) as exc:
                substitute_feature_variables(context)

        self.assertIn("install(context, ...)", str(exc.exception))
        self.assertIn("before_all", str(exc.exception))

    def test_substitute_feature_variables_rejects_unknown_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature = self._parse_feature(
                root,
                """
                Feature: Unknown variable

                  Scenario: Broken
                    Given a step {{var:missing_name}}
                """,
            )
            context = self._install_context(
                feature,
                """
                version: 1
                variables:
                  known_name: ok
                """,
            )

            with self.assertRaises(IntegrationError) as exc:
                substitute_feature_variables(context)

        message = str(exc.exception)
        self.assertIn(str(feature.filename), message)
        self.assertIn("missing_name", message)
        self.assertIn("known_name", message)

    def test_substitute_feature_variables_rejects_non_scalar_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature = self._parse_feature(
                root,
                """
                Feature: Non scalar variable

                  Scenario: Broken
                    Given a step {{var:matrix}}
                """,
            )
            context = self._install_context(
                feature,
                """
                version: 1
                variables:
                  matrix:
                    row:
                      - 1
                      - 2
                """,
            )

            with self.assertRaises(IntegrationError) as exc:
                substitute_feature_variables(context)

        self.assertIn("matrix", str(exc.exception))
        self.assertIn("scalar string, number, or boolean", str(exc.exception))

    def _install_context(self, feature: Feature, config_text: str) -> Context:
        context = self._make_context([feature])
        config_path = Path(feature.filename).with_name("behave-toolkit.yaml")
        config_path.write_text(textwrap.dedent(config_text).strip(), encoding="utf-8")
        install(context, config_path)
        return context

    def _parse_feature(self, directory: Path, text: str) -> Feature:
        feature_path = directory / "variables.feature"
        feature_path.write_text(textwrap.dedent(text).strip(), encoding="utf-8")
        return parse_file(str(feature_path))

    def _make_context(self, features: list[Feature]) -> Context:
        runner = Runner(Configuration(load_config=False))
        runner.features = list(features)
        context = Context(runner)
        context._behave_toolkit_test_runner = runner  # pylint: disable=protected-access
        return context


if __name__ == "__main__":
    unittest.main()
