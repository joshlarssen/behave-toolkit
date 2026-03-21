from __future__ import annotations

from enum import Enum

from .errors import ConfigError


class Scope(str, Enum):
    STEP = "step"
    SCENARIO = "scenario"
    FEATURE = "feature"
    GLOBAL = "global"

    @classmethod
    def parse(cls, value: "Scope | str") -> "Scope":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower()
        aliases = {
            "testrun": "global",
            "test-run": "global",
            "run": "global",
        }
        normalized = aliases.get(normalized, normalized)

        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(scope.value for scope in cls)
            raise ConfigError(
                f"Unsupported scope '{value}'. Expected one of: {allowed}."
            ) from exc

    def context_layer(self) -> str:
        if self is Scope.GLOBAL:
            return "testrun"
        return str(self.value)
