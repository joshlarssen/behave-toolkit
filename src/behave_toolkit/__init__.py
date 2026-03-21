"""Public package interface for behave-toolkit."""

from .config import ObjectSpec, ToolkitConfig, load_config, load_yaml_file, load_yaml_text
from .errors import ConfigError, DocumentationError, IntegrationError, ToolkitError
from .plugin import (
    LifecycleManager,
    activate_feature_scope,
    activate_global_scope,
    activate_scenario_scope,
    activate_scope,
    install,
)
from .scopes import Scope
from .step_docs import DocumentationResult, generate_step_docs

__all__ = [
    "ConfigError",
    "DocumentationError",
    "DocumentationResult",
    "IntegrationError",
    "LifecycleManager",
    "ObjectSpec",
    "Scope",
    "ToolkitConfig",
    "ToolkitError",
    "activate_feature_scope",
    "activate_global_scope",
    "activate_scenario_scope",
    "activate_scope",
    "generate_step_docs",
    "install",
    "load_config",
    "load_yaml_file",
    "load_yaml_text",
]

__version__ = "0.1.0"
