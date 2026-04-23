from __future__ import annotations

from abc import ABC
import re
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

OLLAMA_URL = "http://localhost:11434/v1"
OLLAMA_KEY = "ollama"


class AIAssistantBase(ABC):
    """AI 助手基类：统一管理 system 提示词与模型名称。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        openai_client: Any | None = None,
        openai_api_key: str | None = OLLAMA_KEY,
        openai_base_url: str | None = OLLAMA_URL,
        temperature: float = 0.1,
    ) -> None:
        self.system_prompt = system_prompt
        self.model_name = model_name
        self.temperature = temperature
        self._openai_client = openai_client or self._build_openai_client(
            api_key=openai_api_key,
            base_url=openai_base_url,
        )

    def agent_config(self) -> dict[str, str]:
        return {"system_prompt": self.system_prompt, "model_name": self.model_name}

    def _build_openai_client(self, *, api_key: str | None, base_url: str | None) -> Any | None:
        if OpenAI is None:
            return None
        resolved_api_key = api_key or OLLAMA_KEY
        if not resolved_api_key:
            return None
        client_kwargs: dict[str, str] = {"api_key": resolved_api_key}
        resolved_base_url = base_url or OLLAMA_URL
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        return OpenAI(**client_kwargs)

    def _call_openai(self, user_input: str) -> str | None:
        if self._openai_client is None:
            return None
        try:
            if hasattr(self._openai_client, "responses"):
                response = self._openai_client.responses.create(
                    model=self.model_name,
                    instructions=self.system_prompt or "",
                    input=user_input or "",
                    temperature=self.temperature,
                )
                return getattr(response, "output_text", None)

            response = self._openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt or ""},
                    {"role": "user", "content": user_input or ""},
                ],
                temperature=self.temperature,
                extra_body={"chat_template_kwargs": {"enable_thinking": False, "think": False}},
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception:
            return None

    @staticmethod
    def _extract_uci_move(text: str) -> str | None:
        match = re.search(r"\b([a-h][1-8][a-h][1-8])\b", text.lower())
        if match:
            return match.group(1)
        return None
