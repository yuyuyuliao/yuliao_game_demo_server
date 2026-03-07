from __future__ import annotations

from abc import ABC


class AIAssistantBase(ABC):
    """AI 助手基类：统一管理 system 提示词与模型名称。"""

    def __init__(self, *, system_prompt: str = "", model_name: str = "demo-model") -> None:
        self.system_prompt = system_prompt
        self.model_name = model_name

    def agent_config(self) -> dict[str, str]:
        """返回当前助手配置，便于作为 agent 元数据输出。"""
        return {"system_prompt": self.system_prompt, "model_name": self.model_name}
