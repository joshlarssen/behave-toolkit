from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import pkgutil
from typing import Any, Callable, Protocol, cast

from .config import ObjectSpec, ToolkitConfig, load_yaml_file
from .scopes import Scope

CleanupCallback = Callable[[], None]
FactoryCallable = Callable[..., Any]


class SupportsCleanup(Protocol):
    def add_cleanup(
        self,
        cleanup_func: CleanupCallback,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Register a cleanup callback for the current Behave context layer."""


@dataclass(slots=True)
class _PendingInstance:
    spec: ObjectSpec
    instance: Any
    cleanup: CleanupCallback


def _make_instance_store() -> dict[Scope, dict[str, Any]]:
    return {scope: {} for scope in Scope}


def _require_cleanup_context(context: object) -> SupportsCleanup:
    add_cleanup = getattr(context, "add_cleanup", None)
    if not callable(add_cleanup):
        raise TypeError("Behave context must provide an add_cleanup() method.")
    return cast(SupportsCleanup, context)


@dataclass(slots=True)
class LifecycleManager:
    """Entry point that manages configured objects across Behave scopes."""

    config_path: Path
    config: ToolkitConfig
    namespace: str = "toolkit"
    _instances: dict[Scope, dict[str, Any]] = field(default_factory=_make_instance_store)

    def validate(self) -> None:
        aliases_by_scope: dict[Scope, set[str]] = {scope: set() for scope in Scope}
        for spec in self.config.objects.values():
            if spec.context_name == self.namespace:
                raise ValueError(
                    f"Object '{spec.name}' cannot use context name '{self.namespace}' "
                    "because it is reserved for the toolkit manager."
                )

            aliases = aliases_by_scope[spec.scope]
            if spec.context_name in aliases:
                raise ValueError(
                    f"Scope '{spec.scope.value}' defines context name "
                    f"'{spec.context_name}' more than once."
                )
            aliases.add(spec.context_name)

    def spec(self, name: str) -> ObjectSpec:
        return self.config.require(name)

    def list_objects(self) -> list[str]:
        return sorted(self.config.objects)

    def objects_for_scope(self, scope: Scope | str) -> list[ObjectSpec]:
        parsed_scope = Scope.parse(scope)
        return [spec for spec in self.config.objects.values() if spec.scope == parsed_scope]

    def active_objects(self, scope: Scope | str) -> dict[str, Any]:
        parsed_scope = Scope.parse(scope)
        return dict(self._instances[parsed_scope])

    def instance(self, name: str) -> Any:
        for scope in (Scope.STEP, Scope.SCENARIO, Scope.FEATURE, Scope.GLOBAL):
            instances = self._instances[scope]
            if name in instances:
                return instances[name]

        known = ", ".join(self.list_objects()) or "<none>"
        raise KeyError(f"Object '{name}' is not active. Known configured objects: {known}")

    def activate_scope(self, context: object, scope: Scope | str) -> dict[str, Any]:
        parsed_scope = Scope.parse(scope)
        if parsed_scope is Scope.STEP:
            raise NotImplementedError(
                "Step scope is not implemented yet. It is planned as a later extension."
            )

        if self._instances[parsed_scope]:
            raise RuntimeError(f"Scope '{parsed_scope.value}' is already active.")

        cleanup_context = _require_cleanup_context(context)
        pending_instances: list[_PendingInstance] = []

        try:
            for spec in self.objects_for_scope(parsed_scope):
                instance = self._instantiate(spec)
                cleanup = self._build_cleanup_callback(context, parsed_scope, spec, instance)
                pending_instances.append(
                    _PendingInstance(spec=spec, instance=instance, cleanup=cleanup)
                )

            layer = parsed_scope.context_layer()
            created: dict[str, Any] = {}
            for pending in pending_instances:
                self._instances[parsed_scope][pending.spec.name] = pending.instance
                setattr(context, pending.spec.context_name, pending.instance)
                cleanup_context.add_cleanup(pending.cleanup, layer=layer)
                created[pending.spec.name] = pending.instance

            return created
        except Exception:
            for pending in reversed(pending_instances):
                pending.cleanup()
            raise

    def activate_global_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.GLOBAL)

    def activate_feature_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.FEATURE)

    def activate_scenario_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.SCENARIO)

    def _instantiate(self, spec: ObjectSpec) -> Any:
        factory = self._resolve_factory(spec)
        return factory(*spec.args, **spec.kwargs)

    def _resolve_factory(self, spec: ObjectSpec) -> FactoryCallable:
        try:
            target = pkgutil.resolve_name(spec.factory)
        except (AttributeError, ImportError, ValueError) as exc:
            raise ImportError(
                f"Could not resolve factory '{spec.factory}' for object '{spec.name}'."
            ) from exc

        if not callable(target):
            raise TypeError(
                f"Factory '{spec.factory}' for object '{spec.name}' is not callable."
            )
        return cast(FactoryCallable, target)

    def _build_cleanup_callback(
        self,
        context: object,
        scope: Scope,
        spec: ObjectSpec,
        instance: Any,
    ) -> CleanupCallback:
        cleanup_callable = self._resolve_cleanup_callable(spec, instance)
        finished = False

        def cleanup() -> None:
            nonlocal finished
            if finished:
                return

            finished = True
            try:
                if cleanup_callable is not None:
                    cleanup_callable()
            finally:
                self._instances[scope].pop(spec.name, None)
                try:
                    current_value = getattr(context, spec.context_name)
                except AttributeError:
                    current_value = None

                if current_value is instance:
                    delattr(context, spec.context_name)

        return cleanup

    def _resolve_cleanup_callable(
        self,
        spec: ObjectSpec,
        instance: Any,
    ) -> CleanupCallback | None:
        if spec.cleanup is None:
            return None

        cleanup_attr = getattr(instance, spec.cleanup, None)
        if cleanup_attr is None:
            raise AttributeError(
                f"Object '{spec.name}' requested cleanup '{spec.cleanup}', but "
                f"'{type(instance).__name__}' does not provide it."
            )
        if not callable(cleanup_attr):
            raise TypeError(
                f"Object '{spec.name}' cleanup '{spec.cleanup}' is not callable."
            )
        return cast(CleanupCallback, cleanup_attr)


def _require_manager(context: object, namespace: str) -> LifecycleManager:
    manager = getattr(context, namespace, None)
    if not isinstance(manager, LifecycleManager):
        raise AttributeError(
            f"Context does not contain a behave-toolkit manager at '{namespace}'. "
            "Call install() first."
        )
    return manager


def activate_scope(
    context: object,
    scope: Scope | str,
    *,
    namespace: str = "toolkit",
) -> dict[str, Any]:
    return _require_manager(context, namespace).activate_scope(context, scope)


def activate_global_scope(
    context: object,
    *,
    namespace: str = "toolkit",
) -> dict[str, Any]:
    return activate_scope(context, Scope.GLOBAL, namespace=namespace)


def activate_feature_scope(
    context: object,
    *,
    namespace: str = "toolkit",
) -> dict[str, Any]:
    return activate_scope(context, Scope.FEATURE, namespace=namespace)


def activate_scenario_scope(
    context: object,
    *,
    namespace: str = "toolkit",
) -> dict[str, Any]:
    return activate_scope(context, Scope.SCENARIO, namespace=namespace)


def install(
    context: object,
    config_path: str | Path,
    *,
    namespace: str = "toolkit",
    activate_global: bool = True,
) -> LifecycleManager:
    """Load config, attach the manager, and optionally activate global objects."""

    if hasattr(context, namespace):
        raise AttributeError(
            f"Context already has attribute '{namespace}'. Choose another namespace."
        )

    manager = LifecycleManager(
        config_path=Path(config_path),
        config=load_yaml_file(config_path),
        namespace=namespace,
    )
    manager.validate()
    setattr(context, namespace, manager)

    try:
        if activate_global and manager.objects_for_scope(Scope.GLOBAL):
            manager.activate_global_scope(context)
    except Exception:
        delattr(context, namespace)
        raise

    return manager
