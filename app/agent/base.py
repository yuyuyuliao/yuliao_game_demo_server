from __future__ import annotations

from abc import ABC
import logging
import os
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback when openai is unavailable
    OpenAI = None

OLLAMA_URL = "http://localhost:11434/v1"
OLLAMA_KEY = "ollama"

logger = logging.getLogger(__name__)


class OpenAICompatibleChatModel(SimpleChatModel):
    """LangChain chat model adapter for OpenAI-compatible chat completion APIs."""

    client: Any
    model_name: str
    temperature: float = 0.1
    response_format: dict[str, str] | None = None

    @property
    def _llm_type(self) -> str:
        return "openai-compatible-chat"

    def _call(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        chat = getattr(self.client, "chat", None)
        completions = getattr(chat, "completions", None)
        if completions is None:
            return self._call_responses_api(messages, stop=stop, **kwargs)

        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": [self._message_to_openai_payload(message) for message in messages],
            "temperature": self.temperature,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False, "think": False}},
        }
        if stop:
            request_kwargs["stop"] = stop
        response_format = kwargs.get("response_format", self.response_format)
        if response_format:
            request_kwargs["response_format"] = response_format

        response = completions.create(**request_kwargs)
        content = response.choices[0].message.content
        return content or ""

    def _call_responses_api(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        instructions = "\n".join(
            str(message.content)
            for message in messages
            if isinstance(message, SystemMessage) and message.content
        )
        input_text = "\n".join(
            str(message.content)
            for message in messages
            if not isinstance(message, SystemMessage) and message.content
        )
        request_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "instructions": instructions,
            "input": input_text,
            "temperature": self.temperature,
        }
        if stop:
            request_kwargs["stop"] = stop
        response_format = kwargs.get("response_format", self.response_format)
        if response_format:
            request_kwargs["response_format"] = response_format

        response = self.client.responses.create(**request_kwargs)
        return getattr(response, "output_text", "") or ""

    @staticmethod
    def _message_to_openai_payload(message: BaseMessage) -> dict[str, Any]:
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            role = "user"
        return {"role": role, "content": message.content}


class AIAssistantBase(ABC):
    """AI 助手基类：统一管理 system 提示词与模型名称。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "qwen3:4b",
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
        self._chat_model = self._build_chat_model(self._openai_client)

    def agent_config(self) -> dict[str, str]:
        """返回当前助手配置，便于作为 agent 元数据输出。"""
        return {"system_prompt": self.system_prompt, "model_name": self.model_name}

    def _build_openai_client(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
    ) -> Any | None:
        """根据配置构建 OpenAI 兼容客户端。"""
        if OpenAI is None:
            return None
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY") or OLLAMA_KEY
        if not resolved_api_key:
            return None
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL") or OLLAMA_URL
        client_kwargs: dict[str, str] = {"api_key": resolved_api_key}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        return OpenAI(**client_kwargs)

    def _build_chat_model(self, client: Any | None) -> OpenAICompatibleChatModel | None:
        """把 OpenAI 兼容客户端包装成 LangChain ChatModel。"""
        if client is None:
            return None
        return OpenAICompatibleChatModel(
            client=client,
            model_name=self.model_name,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

    def _call_openai(self, user_input: str) -> str | None:
        """通过 LangChain ChatModel 调用模型，失败时返回 None 以便子类兜底。"""
        if self._chat_model is None:
            return None
        try:
            response = self._chat_model.invoke(
                [
                    SystemMessage(content=self.system_prompt or ""),
                    HumanMessage(content=user_input or ""),
                ]
            )
            return str(response.content) if response.content else None
        except Exception:
            logger.exception("调用聊天模型失败")
            return None

    @staticmethod
    def _extract_uci_move(text: str) -> str | None:
        """从文本中提取 UCI 走法。"""
        match = re.search(r"\b([a-h][1-8][a-h][1-8])\b", text.lower())
        if match:
            return match.group(1)
        return None
