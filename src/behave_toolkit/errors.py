"""Public exception types for behave-toolkit."""

from __future__ import annotations


class ToolkitError(RuntimeError):
    """Base exception for behave-toolkit failures."""


class ConfigError(ToolkitError):
    """Configuration loading or validation failed."""


class IntegrationError(ToolkitError):
    """Behave context integration or scope activation failed."""


class DocumentationError(ToolkitError):
    """Step documentation generation failed."""
