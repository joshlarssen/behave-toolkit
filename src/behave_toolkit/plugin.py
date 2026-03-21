from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import pkgutil
from typing import Any, Callable, Protocol, cast

from .config import ObjectSpec, ToolkitConfig, load_yaml_file
from .errors import ConfigError, IntegrationError
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


@dataclass(slots=True)
class _ActivationState:
    scope: Scope
    context: object
    cleanup_context: SupportsCleanup
    pending_instances: list[_PendingInstance] = field(default_factory=list)
    created_instances: dict[str, Any] = field(default_factory=dict)
    creating_names: list[str] = field(default_factory=list)
    variable_stack: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _ValidationState:
    validated_objects: set[str] = field(default_factory=set)
    object_stack: list[str] = field(default_factory=list)
    variable_stack: list[str] = field(default_factory=list)


def _make_instance_store() -> dict[Scope, dict[str, Any]]:
    return {scope: {} for scope in Scope}


def _require_cleanup_context(context: object) -> SupportsCleanup:
    add_cleanup = getattr(context, "add_cleanup", None)
    if not callable(add_cleanup):
        raise IntegrationError(
            "behave-toolkit requires the real Behave context object with "
            "add_cleanup(). Call install() and activate_*_scope() from "
            "environment.py hooks."
        )
    return cast(SupportsCleanup, context)


def _scope_rank(scope: Scope) -> int:
    order = {
        Scope.GLOBAL: 0,
        Scope.FEATURE: 1,
        Scope.SCENARIO: 2,
        Scope.STEP: 3,
    }
    return order[scope]


def _scope_helper_name(scope: Scope) -> str:
    helpers = {
        Scope.GLOBAL: "activate_global_scope",
        Scope.FEATURE: "activate_feature_scope",
        Scope.SCENARIO: "activate_scenario_scope",
        Scope.STEP: "activate_scope",
    }
    return helpers[scope]


def _scope_hook_name(scope: Scope) -> str:
    hooks = {
        Scope.GLOBAL: "before_all",
        Scope.FEATURE: "before_feature",
        Scope.SCENARIO: "before_scenario",
        Scope.STEP: "before_step",
    }
    return hooks[scope]


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
                raise self._config_error(
                    f"Object '{spec.name}' cannot use context name "
                    f"'{self.namespace}' because it is reserved for the toolkit "
                    "manager."
                )

            aliases = aliases_by_scope[spec.scope]
            if spec.context_name in aliases:
                raise self._config_error(
                    f"Scope '{spec.scope.value}' defines context name "
                    f"'{spec.context_name}' more than once."
                )
            aliases.add(spec.context_name)

        validation_state = _ValidationState()
        for spec in self.config.objects.values():
            self._resolve_factory(spec)
        for spec in self.config.objects.values():
            self._validate_object_spec(spec, validation_state)

    def _config_error(self, message: str) -> ConfigError:
        return ConfigError(
            f"Invalid behave-toolkit config '{self.config_path}': {message}"
        )

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
            raise IntegrationError(
                f"Scope '{parsed_scope.value}' is already active. Call "
                f"{_scope_helper_name(parsed_scope)}(context) once from "
                f"{_scope_hook_name(parsed_scope)}."
            )

        state = _ActivationState(
            scope=parsed_scope,
            context=context,
            cleanup_context=_require_cleanup_context(context),
        )

        try:
            for spec in self.objects_for_scope(parsed_scope):
                self._ensure_current_scope_object(state, spec.name)

            layer = parsed_scope.context_layer()
            created: dict[str, Any] = {}
            for pending in state.pending_instances:
                self._instances[parsed_scope][pending.spec.name] = pending.instance
                setattr(context, pending.spec.context_name, pending.instance)
                state.cleanup_context.add_cleanup(pending.cleanup, layer=layer)
                created[pending.spec.name] = pending.instance

            return created
        except Exception as exc:
            for pending in reversed(state.pending_instances):
                pending.cleanup()
            if isinstance(exc, (ConfigError, IntegrationError)):
                raise

            object_name = state.creating_names[-1] if state.creating_names else None
            if object_name is None:
                message = (
                    f"Could not activate scope '{parsed_scope.value}' from "
                    f"behave-toolkit config '{self.config_path}': {exc}"
                )
            else:
                message = (
                    f"Could not activate scope '{parsed_scope.value}' from "
                    f"behave-toolkit config '{self.config_path}' while creating "
                    f"object '{object_name}': {exc}"
                )
            raise IntegrationError(message) from exc

    def activate_global_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.GLOBAL)

    def activate_feature_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.FEATURE)

    def activate_scenario_scope(self, context: object) -> dict[str, Any]:
        return self.activate_scope(context, Scope.SCENARIO)

    def _ensure_current_scope_object(self, state: _ActivationState, name: str) -> Any:
        if name in state.created_instances:
            return state.created_instances[name]

        spec = self.config.require(name)
        if spec.scope is not state.scope:
            raise IntegrationError(
                f"Object '{name}' belongs to scope '{spec.scope.value}', not "
                f"'{state.scope.value}'."
            )

        if name in state.creating_names:
            cycle = " -> ".join([*state.creating_names, name])
            raise self._config_error(f"Circular object reference detected: {cycle}")

        state.creating_names.append(name)
        try:
            instance = self._instantiate(spec, state)
            cleanup = self._build_cleanup_callback(state.context, state.scope, spec, instance)
            state.created_instances[name] = instance
            state.pending_instances.append(
                _PendingInstance(spec=spec, instance=instance, cleanup=cleanup)
            )
            return instance
        finally:
            state.creating_names.pop()

    def _instantiate(self, spec: ObjectSpec, state: _ActivationState) -> Any:
        factory = self._resolve_factory(spec)
        args = self._resolve_value(spec.args, spec, state)
        kwargs = self._resolve_value(spec.kwargs, spec, state)
        return factory(*args, **kwargs)

    def _resolve_factory(self, spec: ObjectSpec) -> FactoryCallable:
        try:
            target = pkgutil.resolve_name(spec.factory)
        except (AttributeError, ImportError, ValueError) as exc:
            raise self._config_error(
                f"Could not resolve factory '{spec.factory}' for object "
                f"'{spec.name}'. Ensure the callable is importable from the "
                "active environment."
            ) from exc

        if not callable(target):
            raise self._config_error(
                f"Factory '{spec.factory}' for object '{spec.name}' is not callable."
            )
        return cast(FactoryCallable, target)

    def _resolve_value(self, value: Any, spec: ObjectSpec, state: _ActivationState) -> Any:
        if isinstance(value, tuple):
            return tuple(self._resolve_value(item, spec, state) for item in value)
        if isinstance(value, list):
            return [self._resolve_value(item, spec, state) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                return self._resolve_reference_marker(value, spec, state)
            if "$var" in value:
                return self._resolve_variable_marker(value, spec, state)
            return {
                key: self._resolve_value(item, spec, state)
                for key, item in value.items()
            }
        return value

    def _resolve_reference_marker(
        self,
        marker: dict[str, Any],
        spec: ObjectSpec,
        state: _ActivationState,
    ) -> Any:
        extra_keys = set(marker) - {"$ref", "attr"}
        if extra_keys:
            extras = ", ".join(sorted(extra_keys))
            raise self._config_error(
                f"Object '{spec.name}' uses unsupported $ref keys: {extras}"
            )

        ref_name = marker.get("$ref")
        if not isinstance(ref_name, str) or not ref_name.strip():
            raise self._config_error(
                f"Object '{spec.name}' requires a non-empty string in '$ref'."
            )

        attr_path = marker.get("attr")
        if attr_path is not None and (not isinstance(attr_path, str) or not attr_path.strip()):
            raise self._config_error(
                f"Object '{spec.name}' requires 'attr' to be a non-empty string when used."
            )

        target = self._resolve_object_reference(ref_name.strip(), spec, state)
        if attr_path is None:
            return target
        return self._resolve_attribute_path(target, ref_name.strip(), attr_path)

    def _resolve_variable_marker(
        self,
        marker: dict[str, Any],
        spec: ObjectSpec,
        state: _ActivationState,
    ) -> Any:
        extra_keys = set(marker) - {"$var"}
        if extra_keys:
            extras = ", ".join(sorted(extra_keys))
            raise self._config_error(
                f"Object '{spec.name}' uses unsupported $var keys: {extras}"
            )

        variable_name = marker.get("$var")
        if not isinstance(variable_name, str) or not variable_name.strip():
            raise self._config_error(
                f"Object '{spec.name}' requires a non-empty string in '$var'."
            )

        variable_name = variable_name.strip()
        if variable_name in state.variable_stack:
            cycle = " -> ".join([*state.variable_stack, variable_name])
            raise self._config_error(f"Circular variable reference detected: {cycle}")

        raw_value = self._require_variable(spec, variable_name)
        state.variable_stack.append(variable_name)
        try:
            return self._resolve_value(raw_value, spec, state)
        finally:
            state.variable_stack.pop()

    def _resolve_object_reference(
        self,
        dependency_name: str,
        spec: ObjectSpec,
        state: _ActivationState,
    ) -> Any:
        dependency_spec = self._require_object(spec, dependency_name)
        if _scope_rank(dependency_spec.scope) > _scope_rank(spec.scope):
            raise self._config_error(
                f"Object '{spec.name}' in scope '{spec.scope.value}' cannot depend on "
                f"'{dependency_name}' in narrower scope '{dependency_spec.scope.value}'."
            )

        if dependency_spec.scope is spec.scope:
            return self._ensure_current_scope_object(state, dependency_name)

        active_instances = self._instances[dependency_spec.scope]
        if dependency_name not in active_instances:
            raise IntegrationError(
                f"Object '{spec.name}' depends on '{dependency_name}', but scope "
                f"'{dependency_spec.scope.value}' is not active. Call "
                f"{_scope_helper_name(dependency_spec.scope)}(context) from "
                f"{_scope_hook_name(dependency_spec.scope)} first."
            )
        return active_instances[dependency_name]

    def _resolve_attribute_path(
        self,
        value: Any,
        dependency_name: str,
        attr_path: str,
    ) -> Any:
        current = value
        for part in attr_path.split("."):
            if not part:
                raise self._config_error(
                    f"Reference to '{dependency_name}' contains an empty attr segment."
                )
            try:
                current = getattr(current, part)
            except AttributeError as exc:
                raise self._config_error(
                    f"Referenced object '{dependency_name}' does not provide "
                    f"attribute path '{attr_path}'."
                ) from exc
        return current

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
            raise self._config_error(
                f"Object '{spec.name}' requested cleanup '{spec.cleanup}', but "
                f"'{type(instance).__name__}' does not provide it."
            )
        if not callable(cleanup_attr):
            raise self._config_error(
                f"Object '{spec.name}' cleanup '{spec.cleanup}' is not callable."
            )
        return cast(CleanupCallback, cleanup_attr)

    def _require_object(self, spec: ObjectSpec, name: str) -> ObjectSpec:
        try:
            return self.config.require(name)
        except KeyError as exc:
            known = ", ".join(self.list_objects()) or "<none>"
            raise self._config_error(
                f"Object '{spec.name}' references unknown object '{name}'. "
                f"Known objects: {known}."
            ) from exc

    def _require_variable(self, spec: ObjectSpec, name: str) -> Any:
        try:
            return self.config.require_variable(name)
        except KeyError as exc:
            known = ", ".join(sorted(self.config.variables)) or "<none>"
            raise self._config_error(
                f"Object '{spec.name}' references unknown variable '{name}'. "
                f"Known variables: {known}."
            ) from exc

    def _validate_object_spec(
        self,
        spec: ObjectSpec,
        state: _ValidationState,
    ) -> None:
        if spec.name in state.validated_objects:
            return
        if spec.name in state.object_stack:
            cycle = " -> ".join([*state.object_stack, spec.name])
            raise self._config_error(f"Circular object reference detected: {cycle}")

        state.object_stack.append(spec.name)
        try:
            self._validate_value(spec.args, spec, "args", state)
            self._validate_value(spec.kwargs, spec, "kwargs", state)
        finally:
            state.object_stack.pop()

        state.validated_objects.add(spec.name)

    def _validate_value(
        self,
        value: Any,
        spec: ObjectSpec,
        location: str,
        state: _ValidationState,
    ) -> None:
        if isinstance(value, tuple):
            for index, item in enumerate(value):
                self._validate_value(item, spec, f"{location}[{index}]", state)
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                self._validate_value(item, spec, f"{location}[{index}]", state)
            return

        if isinstance(value, dict):
            if "$ref" in value:
                self._validate_reference_marker(value, spec, location, state)
                return
            if "$var" in value:
                self._validate_variable_marker(value, spec, location, state)
                return

            for key, item in value.items():
                child_location = (
                    f"{location}.{key}"
                    if isinstance(key, str)
                    else f"{location}[{key!r}]"
                )
                self._validate_value(item, spec, child_location, state)

    def _validate_reference_marker(
        self,
        marker: dict[str, Any],
        spec: ObjectSpec,
        location: str,
        state: _ValidationState,
    ) -> None:
        extra_keys = set(marker) - {"$ref", "attr"}
        if extra_keys:
            extras = ", ".join(sorted(extra_keys))
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' uses unsupported "
                f"$ref keys: {extras}."
            )

        ref_name = marker.get("$ref")
        if not isinstance(ref_name, str) or not ref_name.strip():
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' requires a non-empty "
                "string in '$ref'."
            )
        ref_name = ref_name.strip()

        attr_path = marker.get("attr")
        if attr_path is not None:
            if not isinstance(attr_path, str) or not attr_path.strip():
                raise self._config_error(
                    f"Object '{spec.name}' field '{location}.attr' must be a "
                    "non-empty string."
                )
            if any(not part for part in attr_path.split(".")):
                raise self._config_error(
                    f"Object '{spec.name}' field '{location}.attr' must not "
                    "contain empty path segments."
                )

        dependency_spec = self._require_known_object(spec, ref_name, location)
        if _scope_rank(dependency_spec.scope) > _scope_rank(spec.scope):
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' cannot reference "
                f"'{ref_name}' in narrower scope '{dependency_spec.scope.value}'."
            )

        if ref_name in state.object_stack:
            cycle = " -> ".join([*state.object_stack, ref_name])
            raise self._config_error(f"Circular object reference detected: {cycle}")

        self._validate_object_spec(dependency_spec, state)

    def _validate_variable_marker(
        self,
        marker: dict[str, Any],
        spec: ObjectSpec,
        location: str,
        state: _ValidationState,
    ) -> None:
        extra_keys = set(marker) - {"$var"}
        if extra_keys:
            extras = ", ".join(sorted(extra_keys))
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' uses unsupported "
                f"$var keys: {extras}."
            )

        variable_name = marker.get("$var")
        if not isinstance(variable_name, str) or not variable_name.strip():
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' requires a non-empty "
                "string in '$var'."
            )
        variable_name = variable_name.strip()

        if variable_name in state.variable_stack:
            cycle = " -> ".join([*state.variable_stack, variable_name])
            raise self._config_error(f"Circular variable reference detected: {cycle}")

        raw_value = self._require_known_variable(spec, variable_name, location)
        state.variable_stack.append(variable_name)
        try:
            self._validate_value(raw_value, spec, f"variables.{variable_name}", state)
        finally:
            state.variable_stack.pop()

    def _require_known_object(
        self,
        spec: ObjectSpec,
        name: str,
        location: str,
    ) -> ObjectSpec:
        try:
            return self.config.require(name)
        except KeyError as exc:
            known = ", ".join(self.list_objects()) or "<none>"
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' references unknown "
                f"object '{name}'. Known objects: {known}."
            ) from exc

    def _require_known_variable(
        self,
        spec: ObjectSpec,
        name: str,
        location: str,
    ) -> Any:
        try:
            return self.config.require_variable(name)
        except KeyError as exc:
            known = ", ".join(sorted(self.config.variables)) or "<none>"
            raise self._config_error(
                f"Object '{spec.name}' field '{location}' references unknown "
                f"variable '{name}'. Known variables: {known}."
            ) from exc


def _require_manager(
    context: object,
    namespace: str,
    *,
    caller: str,
) -> LifecycleManager:
    manager = getattr(context, namespace, None)
    if not isinstance(manager, LifecycleManager):
        raise IntegrationError(
            f"Context does not contain a behave-toolkit manager at '{namespace}'. "
            "Call install(context, ...) from before_all before calling "
            f"{caller}(context)."
        )
    return manager


def activate_scope(
    context: object,
    scope: Scope | str,
    *,
    namespace: str = "toolkit",
) -> dict[str, Any]:
    parsed_scope = Scope.parse(scope)
    caller = _scope_helper_name(parsed_scope)
    return _require_manager(
        context,
        namespace,
        caller=caller,
    ).activate_scope(context, parsed_scope)


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

    resolved_path = Path(config_path).expanduser().resolve()
    if hasattr(context, namespace):
        raise IntegrationError(
            f"Could not install behave-toolkit under namespace '{namespace}': "
            "the context already defines that attribute. Choose another namespace."
        )

    manager = LifecycleManager(
        config_path=resolved_path,
        config=load_yaml_file(resolved_path),
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
