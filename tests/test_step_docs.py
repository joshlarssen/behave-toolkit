from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from behave_toolkit import DocumentationError, DocumentationResult, generate_step_docs


class StepDocumentationTests(unittest.TestCase):
    def test_generate_step_docs_writes_sphinx_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir, result = self._generate_docs_fixture(Path(tmpdir))

            self.assertEqual(result.step_count, 3)
            self.assertEqual(result.type_count, 1)
            self.assertTrue((output_dir / "index.md").is_file())
            self.assertTrue((output_dir / "conf.py").is_file())
            self.assertTrue((output_dir / "steps" / "index.md").is_file())
            self.assertTrue((output_dir / "steps" / "given.md").is_file())
            self.assertTrue((output_dir / "steps" / "when.md").is_file())
            self.assertTrue((output_dir / "types" / "index.md").is_file())

            conf_text = (output_dir / "conf.py").read_text(encoding="utf-8")
            self.assertIn("'sphinx_design'", conf_text)

            root_index = (output_dir / "index.md").read_text(encoding="utf-8")
            self.assertIn("```{toctree}", root_index)
            self.assertIn("steps/index", root_index)
            self.assertIn("types/index", root_index)
            self.assertIn(":::{grid-item-card} Step reference", root_index)

            steps_index = (output_dir / "steps" / "index.md").read_text(encoding="utf-8")
            self.assertIn("given.md", steps_index)
            self.assertIn("when.md", steps_index)
            self.assertIn("then.md", steps_index)
            self.assertIn(":::{grid-item-card} Given", steps_index)

            given_index = (output_dir / "steps" / "given.md").read_text(encoding="utf-8")
            when_index = (output_dir / "steps" / "when.md").read_text(encoding="utf-8")
            self.assertIn("Use a custom status parser.", given_index)
            self.assertIn("Open a dashboard tab count.", when_index)
            self.assertIn("step_have_status_account(context, status)", given_index)
            self.assertIn("`{status:Status}`", given_index)
            self.assertIn("[`Status`](../types/status.md)", given_index)
            self.assertIn("`Status`", given_index)
            self.assertIn("step_open_tabs(context, count)", when_index)
            self.assertIn("`{count:d}`", when_index)
            self.assertIn("`int`", when_index)

            step_pages = sorted(
                path
                for path in (output_dir / "steps").glob("*.md")
                if path.name not in {"index.md", "given.md", "when.md", "then.md", "generic.md"}
            )
            self.assertEqual(len(step_pages), 3)

    def test_generated_step_pages_include_signatures_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir, _ = self._generate_docs_fixture(Path(tmpdir))
            step_pages = sorted(
                path
                for path in (output_dir / "steps").glob("*.md")
                if path.name not in {"index.md", "given.md", "when.md", "then.md", "generic.md"}
            )

            types_index = (output_dir / "types" / "index.md").read_text(encoding="utf-8")
            self.assertIn("[`Status`](status.md)", types_index)

            type_page = (output_dir / "types" / "status.md").read_text(encoding="utf-8")
            self.assertIn("Enum values", type_page)
            self.assertIn("`ACTIVE`", type_page)
            self.assertIn("`'active'`", type_page)
            self.assertIn("Given I have a {status:Status} account", type_page)

            matching_step_pages = [
                path
                for path in step_pages
                if "status" in path.read_text(encoding="utf-8")
            ]
            self.assertEqual(len(matching_step_pages), 1)
            step_page = matching_step_pages[0].read_text(encoding="utf-8")
            self.assertIn("[<- Back to given steps](given.md)", step_page)
            self.assertIn("## Quick reference", step_page)
            self.assertIn("## Signature", step_page)
            self.assertIn("## Full docstring", step_page)
            self.assertIn("[`Status`](../types/status.md)", step_page)
            self.assertIn("`{status:Status}`", step_page)
            self.assertIn("Use a custom status parser.", step_page)
            self.assertIn("step_have_status_account(context, status)", step_page)
            self.assertIn("`Given I have a active account`", step_page)
            self.assertIn("`features/demo.feature:", step_page)

    def test_generate_step_docs_is_repeatable_in_same_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            features_dir = self._write_behave_project(project_root)
            output_dir = project_root / "docs" / "behave-toolkit"

            first_result = generate_step_docs(features_dir, output_dir)
            second_result = generate_step_docs(features_dir, output_dir)

            self.assertEqual(first_result.step_count, second_result.step_count)
            self.assertEqual(first_result.type_count, second_result.type_count)
            step_pages = sorted(
                path
                for path in (output_dir / "steps").glob("*.md")
                if path.name not in {"index.md", "given.md", "when.md", "then.md", "generic.md"}
            )
            self.assertEqual(len(step_pages), 3)

    def test_generate_step_docs_requires_steps_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_dir = Path(tmpdir) / "features"
            features_dir.mkdir()

            with self.assertRaises(DocumentationError):
                generate_step_docs(features_dir, Path(tmpdir) / "docs")

    def _generate_docs_fixture(
        self,
        project_root: Path,
    ) -> tuple[Path, DocumentationResult]:
        features_dir = self._write_behave_project(project_root)
        output_dir = project_root / "docs" / "behave-toolkit"
        result = generate_step_docs(
            features_dir,
            output_dir,
            site_title="QA Step Catalog",
        )
        return output_dir, result

    def _write_behave_project(self, project_root: Path) -> Path:
        features_dir = project_root / "features"
        steps_dir = features_dir / "steps"
        steps_dir.mkdir(parents=True)

        (features_dir / "environment.py").write_text(
            """
from enum import Enum

import parse

from behave import register_type, use_step_matcher

use_step_matcher("cfparse")


class Status(Enum):
    ACTIVE = "active"
    PENDING = "pending"


@parse.with_pattern(r"active|pending")
def parse_status(text: str) -> Status:
    return Status(text)


register_type(Status=parse_status)
            """.strip(),
            encoding="utf-8",
        )

        (steps_dir / "account_steps.py").write_text(
            """
from behave import given, then, when


@given("I have a {status:Status} account")
def step_have_status_account(context, status):
    \"\"\"Use a custom status parser.\"\"\"
    del context, status


@when("I open {count:d} tabs")
def step_open_tabs(context, count):
    \"\"\"Open a dashboard tab count.\"\"\"
    del context, count


@then("the dashboard is ready")
def step_dashboard_ready(context):
    \"\"\"The dashboard should be fully loaded.\"\"\"
    del context
            """.strip(),
            encoding="utf-8",
        )

        (features_dir / "demo.feature").write_text(
            """
Feature: Demo step catalog

  Scenario: Account overview
    Given I have a active account
    When I open 2 tabs
    Then the dashboard is ready
            """.strip(),
            encoding="utf-8",
        )
        return features_dir


if __name__ == "__main__":
    unittest.main()
