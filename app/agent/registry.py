from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class AgentSpec:
    """Agent 定义：用于描述一个可构建的 assistant。"""

    key: str
    factory: Callable[..., Any]
    default_kwargs: dict[str, Any] = field(default_factory=dict)

    def build(self, **overrides: Any) -> Any:
        kwargs = {**self.default_kwargs, **overrides}
        return self.factory(**kwargs)


class AgentRegistry:
    """轻量注册中心，便于未来扩展更多 Agent。"""

    def __init__(self) -> None:
        self._specs: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.key] = spec

    def create(self, key: str, **overrides: Any) -> Any:
        spec = self._specs.get(key)
        if spec is None:
            raise KeyError(f"agent not found: {key}")
        return spec.build(**overrides)

    def has(self, key: str) -> bool:
        return key in self._specs

    def keys(self) -> tuple[str, ...]:
        return tuple(self._specs.keys())
