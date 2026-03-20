from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ObjectSpec, ToolkitConfig, load_yaml_file
from .scopes import Scope


@dataclass(slots=True)
class LifecycleManager:
    """Lightweight entrypoint object attached to the Behave context."""

    config_path: Path
    config: ToolkitConfig
    namespace: str = "toolkit"

    def spec(self, name: str) -> ObjectSpec:
        return self.config.require(name)

    def list_objects(self) -> list[str]:
        return sorted(self.config.objects)

    def objects_for_scope(self, scope: Scope | str) -> list[ObjectSpec]:
        parsed_scope = Scope.parse(scope)
        return [spec for spec in self.config.objects.values() if spec.scope == parsed_scope]


def install(
    context: object,
    config_path: str | Path,
    *,
    namespace: str = "toolkit",
) -> LifecycleManager:
    """Load config and attach a manager object to the Behave context.

    The implementation intentionally stays small in the bootstrap version so the
    future object lifecycle engine can evolve behind a stable public API.
    """

    if hasattr(context, namespace):
        raise AttributeError(
            f"Context already has attribute '{namespace}'. Choose another namespace."
        )

    manager = LifecycleManager(
        config_path=Path(config_path),
        config=load_yaml_file(config_path),
        namespace=namespace,
    )
    setattr(context, namespace, manager)
    return manager
