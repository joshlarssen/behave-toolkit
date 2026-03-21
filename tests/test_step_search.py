from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path

from behave_toolkit.step_search import main as step_search_main
from behave_toolkit.step_search import search_steps
from test_support import write_step_docs_fixture


class StepSearchTests(unittest.TestCase):
    def test_search_steps_ranks_custom_status_step_from_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_dir = write_step_docs_fixture(Path(tmpdir))

            results = search_steps(str(features_dir), "custom status parser", limit=3)

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].title, "Given I have a {status:Status} account")
            self.assertIn("custom status parser", (results[0].summary or "").casefold())
            self.assertEqual(results[0].page_path, results[0].html_path.replace(".html", ".md"))

    def test_search_steps_ranks_tab_step_from_docstring_words(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_dir = write_step_docs_fixture(Path(tmpdir))

            results = search_steps(str(features_dir), "dashboard tab count", limit=3)

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].title, "When I open {count:d} tabs")
            self.assertIn("dashboard tab count", (results[0].summary or "").casefold())

    def test_search_cli_can_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_dir = write_step_docs_fixture(Path(tmpdir))
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = step_search_main(
                    [
                        "--features-dir",
                        str(features_dir),
                        "--limit",
                        "2",
                        "--json",
                        "active account",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(output.getvalue())
            self.assertGreaterEqual(len(payload), 1)
            self.assertEqual(payload[0]["title"], "Given I have a {status:Status} account")


if __name__ == "__main__":
    unittest.main()
