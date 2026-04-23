from __future__ import annotations

import logging
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_INIT_LOCK = Lock()
_IS_INITIALIZED = False


def ensure_agentscope_initialized(model_name: str | None = None) -> bool:
    """按需初始化 AgentScope 运行时。

    返回值表示 AgentScope 是否可用；不可用时不会抛异常，便于保留本地兜底逻辑。
    """
    global _IS_INITIALIZED
    if _IS_INITIALIZED:
        return True

    with _INIT_LOCK:
        if _IS_INITIALIZED:
            return True
        try:
            import agentscope  # type: ignore
        except Exception:
            logger.info("agentscope not installed, fallback to local assistant pipeline")
            return False

        try:
            init_kwargs: dict[str, Any] = {}
            if model_name:
                init_kwargs["model"] = model_name
            agentscope.init(**init_kwargs)
            _IS_INITIALIZED = True
            logger.info("agentscope runtime initialized")
            return True
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("failed to initialize agentscope runtime: %s", exc)
            return False


def is_agentscope_ready() -> bool:
    """返回 AgentScope 是否已成功初始化。"""
    return _IS_INITIALIZED
