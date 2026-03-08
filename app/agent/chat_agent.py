from __future__ import annotations

import os
from typing import Any, Callable, Optional

from app.agent.base import AIAssistantBase

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback when openai is unavailable
    OpenAI = None


class ChatAssistant(AIAssistantBase):
    """聊天助手：结合历史聊天与知识检索生成回复。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        knowledge_search: Optional[Callable[..., list[str]]] = None,
        openai_client: Any | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
    ) -> None:
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self._knowledge_search = knowledge_search
        self._openai_client = openai_client or self._build_openai_client(
            api_key=openai_api_key,
            base_url=openai_base_url,
        )

    def reply(self, history: list[str], message: str) -> dict[str, str]:
        """根据聊天历史和用户输入生成日常对话回复。"""
        memories = "；".join(history) if history else "我们还没有历史聊天记录。"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search(message, n_results=1)
        tip_text = tips[0] if tips else "保持轻松交流。"
        fallback_response = (
            f"我记得你最近说过：{memories}。"
            f"你刚才说：{message}。"
            f"给你一个相关建议：{tip_text}"
        )
        if self._openai_client is None:
            return {"response": fallback_response}

        try:
            response = self._openai_client.responses.create(
                model=self.model_name,
                instructions=self.system_prompt or None,
                input=self._build_user_prompt(memories=memories, message=message, tip_text=tip_text),
            )
            output_text = (getattr(response, "output_text", "") or "").strip()
            if output_text:
                return {"response": output_text}
        except Exception:
            pass
        return {"response": fallback_response}

    def _build_openai_client(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
    ) -> Any | None:
        """根据环境变量按需构建 OpenAI 客户端。"""
        if OpenAI is None:
            return None
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            return None
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        client_kwargs: dict[str, str] = {"api_key": resolved_api_key}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        return OpenAI(**client_kwargs)

    def _build_user_prompt(self, *, memories: str, message: str, tip_text: str) -> str:
        """将聊天历史与知识提示整理为发送给 OpenAI 的用户输入。"""
        return (
            f"历史聊天：{memories}\n"
            f"玩家当前消息：{message}\n"
            f"知识库提示：{tip_text}\n"
            "请用自然、简洁、友好的中文直接回复玩家。"
        )
