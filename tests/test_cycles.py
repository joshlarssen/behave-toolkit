from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from behave.configuration import Configuration
from behave.model import Feature
from behave.parser import parse_file
from behave.runner import Context, Runner

from behave_toolkit import IntegrationError, expand_scenario_cycles


class ScenarioCycleTests(unittest.TestCase):
    def test_expand_scenario_cycles_clones_tagged_scenarios_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = self._parse_feature(
                Path(tmpdir),
                """
                Feature: Scenario cycling

                  Scenario: Baseline
                    Given a baseline step

                  @cycling(3)
                  Scenario: Burst traffic
                    Given a repeated step
                """,
            )
            context = self._make_context([feature])

            added = expand_scenario_cycles(context)
            added_again = expand_scenario_cycles(context)

            self.assertEqual(added, 2)
            self.assertEqual(added_again, 0)
            self.assertEqual(
                [scenario.name for scenario in feature.run_items],
                [
                    "Baseline",
                    "Burst traffic",
                    "Burst traffic [cycle 2/3]",
                    "Burst traffic [cycle 3/3]",
                ],
            )

            original = feature.run_items[1]
            clone = feature.run_items[2]
            self.assertIsNot(clone, original)
            self.assertEqual([str(tag) for tag in clone.tags], ["cycling(3)"])
            self.assertIs(clone.parent, feature)
            self.assertIs(clone.feature, feature)
            self.assertIsNot(clone.steps[0], original.steps[0])
            self.assertEqual(clone.steps[0].name, original.steps[0].name)

    def test_expand_scenario_cycles_supports_scenarios_inside_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = self._parse_feature(
                Path(tmpdir),
                """
                Feature: Rule support

                  Rule: Operational safeguards
                    @cycling(2)
                    Scenario: Rule scenario
                      Given a repeated step
                """,
            )
            context = self._make_context([feature])

            added = expand_scenario_cycles(context)

            self.assertEqual(added, 1)
            rule = feature.run_items[0]
            self.assertEqual(
                [scenario.name for scenario in rule.run_items],
                ["Rule scenario", "Rule scenario [cycle 2/2]"],
            )

    def test_expand_scenario_cycles_rejects_invalid_tag_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = self._parse_feature(
                Path(tmpdir),
                """
                Feature: Bad cycle tag

                  @cycling(foo)
                  Scenario: Invalid tag
                    Given a step
                """,
            )
            context = self._make_context([feature])

            with self.assertRaises(IntegrationError) as exc:
                expand_scenario_cycles(context)

        message = str(exc.exception)
        self.assertIn("Invalid tag", message)
        self.assertIn("@cycling(3)", message)
        self.assertIn("cycle tag syntax", message)

    def test_expand_scenario_cycles_rejects_scenario_outlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = self._parse_feature(
                Path(tmpdir),
                """
                Feature: Outline cycle rejection

                  @cycling(2)
                  Scenario Outline: Login variants
                    Given I use <kind>

                    Examples:
                      | kind   |
                      | active |
                """,
            )
            context = self._make_context([feature])

            with self.assertRaises(IntegrationError) as exc:
                expand_scenario_cycles(context)

        message = str(exc.exception)
        self.assertIn("Scenario Outline", message)
        self.assertIn("Examples", message)

    def test_expand_scenario_cycles_requires_real_behave_context(self) -> None:
        with self.assertRaises(IntegrationError) as exc:
            expand_scenario_cycles(SimpleNamespace())

        message = str(exc.exception)
        self.assertIn("before_all", message)
        self.assertIn("_runner.features", message)

    def _parse_feature(self, directory: Path, text: str) -> Feature:
        feature_path = directory / "cycling.feature"
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
