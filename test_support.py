from __future__ import annotations

from behave.configuration import Configuration
from behave.runner import Context, Runner

EVENTS: list[tuple[str, str]] = []


class TrackingResource:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False
        EVENTS.append(("create", label))

    def close(self) -> None:
        self.closed = True
        EVENTS.append(("cleanup", self.label))


def build_tracking_resource(label: str) -> TrackingResource:
    return TrackingResource(label)


def make_context() -> Context:
    config = Configuration(load_config=False)
    return Context(runner=Runner(config))


def reset_events() -> None:
    EVENTS.clear()
