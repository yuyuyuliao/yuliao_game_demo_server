from __future__ import annotations

from typing import Callable, Optional

from app.agent.base import AIAssistantBase


class ChatAssistant(AIAssistantBase):
    """聊天助手：结合历史聊天与知识检索生成回复。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        knowledge_search: Optional[Callable[..., list[str]]] = None,
    ) -> None:
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self._knowledge_search = knowledge_search

    def reply(self, history: list[str], message: str) -> dict[str, str]:
        """根据聊天历史和用户输入生成日常对话回复。"""
        memories = "；".join(history) if history else "我们还没有历史聊天记录。"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search(message, n_results=1)
        tip_text = tips[0] if tips else "保持轻松交流。"
        response = (
            f"我记得你最近说过：{memories}。"
            f"你刚才说：{message}。"
            f"给你一个相关建议：{tip_text}"
        )
        return {"response": response}
