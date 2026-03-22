from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from behave_toolkit import configure_loggers, install
from test_support import make_context


class LoggingConfigTests(unittest.TestCase):
    def test_configure_loggers_builds_named_loggers_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "behave-toolkit.yaml"
            escaped_tmpdir = tmpdir.replace("\\", "\\\\")
            config_path.write_text(
                f"""
                objects:
                  test_log_path:
                    factory: pathlib.Path
                    scope: global
                    args:
                      - {escaped_tmpdir}
                      - artifacts
                      - test-run.log

                logging:
                  test_run:
                    path:
                      $ref: test_log_path
                    logger_name: suite-tests
                    inject_as: test_logger
                    console: false
                """,
                encoding="utf-8",
            )

            context = make_context()
            manager = install(context, config_path)
            loggers = configure_loggers(context)
            logger = loggers["test_run"]
            logger.info("cycle 1/3 started")

            log_path = Path(tmpdir) / "artifacts" / "test-run.log"
            self.assertIs(context.test_logger, logger)
            self.assertIs(manager.logger("test_run"), logger)
            self.assertTrue(log_path.is_file())
            self.assertIn("cycle 1/3 started", log_path.read_text(encoding="utf-8"))

            context._do_cleanups()  # pylint: disable=protected-access

            self.assertFalse(hasattr(context, "test_logger"))
            self.assertEqual(logger.handlers, [])


if __name__ == "__main__":
    unittest.main()
