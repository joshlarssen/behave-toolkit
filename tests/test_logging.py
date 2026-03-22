from __future__ import annotations

import io
import logging
import tempfile
import unittest
from pathlib import Path

from behave_toolkit import configure_test_logging


class TestLoggingHelperTests(unittest.TestCase):
    def test_configure_test_logging_writes_file_and_console(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "artifacts" / "test-run.log"
            stream = io.StringIO()

            logger = configure_test_logging(
                log_path,
                logger_name="smoke-tests",
                console_stream=stream,
            )
            try:
                logger.info("Cycle 1/3 started")

                self.assertTrue(log_path.is_file())
                file_text = log_path.read_text(encoding="utf-8")
                self.assertIn("Cycle 1/3 started", file_text)
                self.assertIn("smoke-tests", file_text)
                self.assertIn("Cycle 1/3 started", stream.getvalue())
            finally:
                self._close_logger(logger)

    def test_configure_test_logging_replaces_existing_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_log_path = Path(tmpdir) / "first.log"
            second_log_path = Path(tmpdir) / "second.log"

            logger = configure_test_logging(
                first_log_path,
                logger_name="smoke-tests-reused",
                console=False,
            )
            try:
                logger.info("first message")

                logger = configure_test_logging(
                    second_log_path,
                    logger_name="smoke-tests-reused",
                    console=False,
                )
                logger.info("second message")

                self.assertIn("first message", first_log_path.read_text(encoding="utf-8"))
                self.assertNotIn("second message", first_log_path.read_text(encoding="utf-8"))
                self.assertIn("second message", second_log_path.read_text(encoding="utf-8"))
            finally:
                self._close_logger(logger)

    def test_configure_test_logging_rejects_unknown_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            with self.assertRaises(ValueError):
                configure_test_logging(log_path, level="LOUD")

    def _close_logger(self, logger: logging.Logger) -> None:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    unittest.main()
