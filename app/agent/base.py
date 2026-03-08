from __future__ import annotations

from abc import ABC
import os
import re
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback when openai is unavailable
    OpenAI = None

OLLAMA_URL = "http://localhost:11434/v1"
OLLAMA_KEY = "ollama"


class AIAssistantBase(ABC):
    """AI 助手基类：统一管理 system 提示词与模型名称。"""

    def __init__(
            self,
            *,
            system_prompt: str = "",
            model_name: str = "qwen3.5:2b",
            openai_client: Any | None = None,
            openai_api_key: str | None = OLLAMA_KEY,
            openai_base_url: str | None = OLLAMA_URL,
    ) -> None:
        self.system_prompt = system_prompt
        self.model_name = model_name
        self._openai_client = openai_client or self._build_openai_client(
            api_key=openai_api_key,
            base_url=openai_base_url,
        )

    def agent_config(self) -> dict[str, str]:
        """返回当前助手配置，便于作为 agent 元数据输出。"""
        return {"system_prompt": self.system_prompt, "model_name": self.model_name}

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

    def _call_openai(self, user_input: str) -> str | None:
        """调用 OpenAI Responses API，失败时返回 None 以便子类走本地兜底逻辑。"""
        if self._openai_client is None:
            return None
        try:
            response = self._openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt or ""},
                    {"role": "user", "content": user_input or ""},
                ],
                temperature=0.1,
                extra_body={"chat_template_kwargs": {"enable_thinking": False, "think": False}},
                response_format={"type": "json_object"},
            )

            output_text = response.choices[0].message.content
            if output_text:
                return output_text
            return output_text
        except Exception as e:
            return None
        return None

    @staticmethod
    def _extract_uci_move(text: str) -> str | None:
        """从文本中提取 UCI 走法。"""
        match = re.search(r"\b([a-h][1-8][a-h][1-8])\b", text.lower())
        if match:
            return match.group(1)
        return None
