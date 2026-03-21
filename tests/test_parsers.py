from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from behave.matchers import ParseMatcher, get_step_matcher_factory

from behave_toolkit import ConfigError, configure_parsers, generate_step_docs
from behave_toolkit.step_docs import _preserve_behave_state

SUPPORT_MODULE = "demo_support_types"


class ParserHelperTests(unittest.TestCase):
    def test_configure_parsers_registers_types_and_sets_step_matcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            self._write_support_module(project_root)
            config_path = project_root / "behave-toolkit.yaml"
            config_path.write_text(
                textwrap.dedent(
                    """
                version: 1
                parsers:
                  step_matcher: cfparse
                  types:
                    Status:
                      converter: demo_support_types.parse_status
                      pattern: active|pending
                      regex_group_count: 0
                    """
                ).strip(),
                encoding="utf-8",
            )

            with _preserve_behave_state():
                sys.path.insert(0, str(project_root))
                try:
                    registered = configure_parsers(config_path)
                    self.assertEqual(
                        get_step_matcher_factory().current_matcher.NAME,
                        "cfparse",
                    )
                    self.assertIn("Status", ParseMatcher.TYPE_REGISTRY)
                    self.assertIn("Status", registered)
                    self.assertEqual(registered["Status"]("active").name, "ACTIVE")
                    self.assertEqual(
                        getattr(registered["Status"], "pattern", None),
                        "active|pending",
                    )
                    self.assertEqual(getattr(registered["Status"], "regex_group_count", None), 0)
                finally:
                    sys.path.pop(0)

    def test_configure_parsers_requires_pattern_for_converter_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            self._write_support_module(project_root)
            config_path = project_root / "behave-toolkit.yaml"
            config_path.write_text(
                textwrap.dedent(
                    """
                version: 1
                parsers:
                  types:
                    Status:
                      converter: demo_support_types.parse_status
                    """
                ).strip(),
                encoding="utf-8",
            )

            with _preserve_behave_state():
                sys.path.insert(0, str(project_root))
                try:
                    with self.assertRaises(ConfigError) as exc:
                        configure_parsers(config_path)
                finally:
                    sys.path.pop(0)

        message = str(exc.exception)
        self.assertIn(str(config_path.resolve()), message)
        self.assertIn("must define 'pattern'", message)

    def test_generate_step_docs_supports_configured_parser_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            features_dir = project_root / "features"
            steps_dir = features_dir / "steps"
            steps_dir.mkdir(parents=True)

            self._write_support_module(project_root)
            (features_dir / "behave-toolkit.yaml").write_text(
                textwrap.dedent(
                    """
                version: 1
                parsers:
                  step_matcher: cfparse
                  types:
                    Status:
                      enum: demo_support_types.Status
                      case_sensitive: false
                    """
                ).strip(),
                encoding="utf-8",
            )
            (features_dir / "environment.py").write_text(
                textwrap.dedent(
                    """
                from pathlib import Path

                from behave_toolkit import configure_parsers

                CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")
                configure_parsers(CONFIG_PATH)
                    """
                ).strip(),
                encoding="utf-8",
            )
            (steps_dir / "account_steps.py").write_text(
                textwrap.dedent(
                    """
                from behave import given

                from demo_support_types import Status


                @given("I have a {status:Status} account")
                def step_have_status_account(context, status: Status) -> None:
                    \"\"\"Use a configured parser helper.

                    Args:
                        context: The Behave context for the current scenario.
                        status (Status): Parsed enum value from the configured helper.

                    Returns:
                        None: The step does not return a value.

                    Raises:
                        AssertionError: If the parsed status cannot be accepted.
                    \"\"\"
                    del context, status
                    """
                ).strip(),
                encoding="utf-8",
            )
            (features_dir / "demo.feature").write_text(
                textwrap.dedent(
                    """
                Feature: Configured parser helpers

                  Scenario: Account status
                    Given I have a ACTIVE account
                    """
                ).strip(),
                encoding="utf-8",
            )

            output_dir = project_root / "docs" / "behave-toolkit"
            result = generate_step_docs(features_dir, output_dir)

            self.assertEqual(result.step_count, 1)
            self.assertEqual(result.type_count, 1)

            type_page = (output_dir / "types" / "status.md").read_text(encoding="utf-8")
            self.assertIn("- Converter: `parse_status()`", type_page)
            self.assertIn("Parse textual values into `Status`.", type_page)
            self.assertIn("- Parse pattern: `(?i:active|pending)`", type_page)
            self.assertIn("demo_support_types.py", type_page)
            self.assertIn("## Enum values", type_page)
            self.assertIn("### Arguments", type_page)
            self.assertIn("### Returns", type_page)
            self.assertIn("### Raises", type_page)

            step_page = next(
                path
                for path in (output_dir / "steps").glob("*.md")
                if path.name not in {"index.md", "given.md", "when.md", "then.md", "generic.md"}
            ).read_text(encoding="utf-8")
            self.assertIn("[`Status`](../types/status.md)", step_page)
            self.assertIn("Use a configured parser helper.", step_page)
            self.assertIn("Given I have a ACTIVE account", step_page)

    def test_generate_step_docs_preserves_enum_values_for_converter_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            features_dir = project_root / "features"
            steps_dir = features_dir / "steps"
            steps_dir.mkdir(parents=True)

            support_module = "demo_priority_support"
            sys.modules.pop(support_module, None)
            (project_root / f"{support_module}.py").write_text(
                textwrap.dedent(
                    """
                from __future__ import annotations

                from enum import Enum


                class Priority(Enum):
                    LOW = "low"
                    HIGH = "high"


                def parse_priority(text: str) -> Priority:
                    \"\"\"Convert a raw token into a Priority enum.\"\"\"
                    return Priority(text)
                    """
                ).strip(),
                encoding="utf-8",
            )
            (features_dir / "behave-toolkit.yaml").write_text(
                textwrap.dedent(
                    f"""
                version: 1
                parsers:
                  step_matcher: cfparse
                  types:
                    Priority:
                      converter: {support_module}.parse_priority
                      pattern: low|high
                    """
                ).strip(),
                encoding="utf-8",
            )
            (features_dir / "environment.py").write_text(
                textwrap.dedent(
                    """
                from pathlib import Path

                from behave_toolkit import configure_parsers

                CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")
                configure_parsers(CONFIG_PATH)
                    """
                ).strip(),
                encoding="utf-8",
            )
            (steps_dir / "queue_steps.py").write_text(
                textwrap.dedent(
                    f"""
                from behave import when

                from {support_module} import Priority


                @when("I choose the {{priority:Priority}} queue")
                def step_choose_priority_queue(context, priority: Priority) -> None:
                    \"\"\"Use a configured converter wrapper.\"\"\"
                    del context, priority
                    """
                ).strip(),
                encoding="utf-8",
            )
            (features_dir / "demo.feature").write_text(
                textwrap.dedent(
                    """
                Feature: Configured converter parser helpers

                  Scenario: Queue selection
                    When I choose the low queue
                    """
                ).strip(),
                encoding="utf-8",
            )

            output_dir = project_root / "docs" / "behave-toolkit"
            sys.path.insert(0, str(project_root))
            try:
                result = generate_step_docs(features_dir, output_dir)
            finally:
                sys.path.pop(0)
                sys.modules.pop(support_module, None)

            self.assertEqual(result.step_count, 1)
            self.assertEqual(result.type_count, 1)

            type_page = (output_dir / "types" / "priority.md").read_text(encoding="utf-8")
            self.assertIn("## Enum values", type_page)
            self.assertIn("`HIGH`", type_page)
            self.assertIn("Convert a raw token into a Priority enum.", type_page)

    def _write_support_module(self, project_root: Path) -> None:
        sys.modules.pop(SUPPORT_MODULE, None)
        (project_root / f"{SUPPORT_MODULE}.py").write_text(
            textwrap.dedent(
                """
            from enum import Enum


            class Status(Enum):
                ACTIVE = "active"
                PENDING = "pending"


            def parse_status(text: str) -> Status:
                \"\"\"Convert a raw token into a Status enum.\"\"\"
                return Status(text)
                """
            ).strip(),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
