from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypedDict

from app.agent.agentscope_runtime import ensure_agentscope_initialized, is_agentscope_ready
from app.agent.base import AIAssistantBase

logger = logging.getLogger(__name__)

# 最近 8 条历史文本通常足够覆盖几轮连续对话，同时能避免兜底回复里塞入过长上下文。
CHAT_MEMORY_WINDOW = 8
DEFAULT_EMPTY_MEMORIES = "我们还没有历史聊天记录。"
MAX_TOOL_DECISION_LOG_LENGTH = 120
AVAILABLE_TOOLS = ("player_info", "farm_info", "game_guide")
AFFIRMATIVE_DECISION_VALUES = {"true", "1", "yes", "y", "是"}
PLAYER_INFO_KEYWORDS = ("玩家信息", "玩家资料", "我的资料", "我的信息", "等级", "金币", "账号", "昵称")
FARM_INFO_KEYWORDS = ("田地", "农田", "土地", "地块", "农场", "作物", "庄稼", "收成", "种植")
GAME_GUIDE_KEYWORDS = ("攻略", "技巧", "建议", "怎么玩", "如何", "怎么", "帮助", "扫雷", "国际象棋", "下棋", "开局")
NEGATION_PREFIXES = ("不需要", "不用", "不要", "别")
TOOL_INPUT_FIELD_MAP = {
    "player_info": "player_id",
    "farm_info": "player_id",
    "game_guide": "query",
}


@dataclass(slots=True)
class LocalTool:
    """最小工具封装，保持 invoke 接口兼容。"""

    fn: Callable[..., str]

    def invoke(self, payload: dict[str, str]) -> str:
        return self.fn(**payload)


class ChatAgentState(TypedDict, total=False):
    player_id: str
    history: list[str]
    message: str
    memories: str
    requested_tools: list[str]
    tool_outputs: dict[str, str]
    response: str


class ChatAssistant(AIAssistantBase):
    """聊天助手：结合历史聊天与知识检索生成回复。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        knowledge_search: Optional[Callable[..., list[str]]] = None,
        player_info_reader: Optional[Callable[[str], str]] = None,
        farm_info_reader: Optional[Callable[[str], str]] = None,
        openai_client: Any | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
        temperature: float = 1,
    ) -> None:
        super().__init__(
            system_prompt=system_prompt,
            model_name=model_name,
            openai_client=openai_client,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            temperature=temperature,
        )
        self._knowledge_search = knowledge_search
        self._player_info_reader = player_info_reader
        self._farm_info_reader = farm_info_reader
        self._tool_map = self._build_tools()

        # 尝试初始化 AgentScope，失败时自动回退到本地编排。
        self._agentscope_enabled = ensure_agentscope_initialized(model_name)

    def reply(self, history: list[str], message: str, player_id: str = "") -> dict[str, str]:
        state: ChatAgentState = {
            "player_id": player_id,
            "history": history,
            "message": message,
        }
        state.update(self._remember_history(state))
        state.update(self._decide_tools(state))
        if self._route_after_decision(state) == "run_tools":
            state.update(self._run_tools(state))
        state.update(self._generate_reply(state))
        return {"response": state["response"]}

    def _build_tools(self) -> dict[str, LocalTool]:
        def read_player_info_tool(player_id: str) -> str:
            if self._player_info_reader is None:
                return "当前没有可用的玩家资料读取工具。"
            return self._player_info_reader(player_id)

        def read_player_farm_tool(player_id: str) -> str:
            if self._farm_info_reader is None:
                return "当前没有可用的田地信息读取工具。"
            return self._farm_info_reader(player_id)

        def search_game_guide_tool(query: str) -> str:
            if self._knowledge_search is None:
                return "当前没有可用的攻略知识库。"
            documents = self._knowledge_search(query, n_results=2)
            if not documents:
                return "知识库里暂时没有查到相关攻略。"
            return "；".join(documents)

        return {
            "player_info": LocalTool(read_player_info_tool),
            "farm_info": LocalTool(read_player_farm_tool),
            "game_guide": LocalTool(search_game_guide_tool),
        }

    def _remember_history(self, state: ChatAgentState) -> ChatAgentState:
        history = state.get("history") or []
        memories = "；".join(history[-CHAT_MEMORY_WINDOW:]) if history else DEFAULT_EMPTY_MEMORIES
        return {"memories": memories}

    def _decide_tools(self, state: ChatAgentState) -> ChatAgentState:
        message = state.get("message", "")
        memories = state.get("memories", DEFAULT_EMPTY_MEMORIES)
        tool_decisions = self._decide_tools_with_model(message=message, memories=memories)
        if tool_decisions is None:
            logger.warning("聊天工具判定模型不可用或返回无效结果，已回退到本地规则。")
            tool_decisions = self._fallback_tool_decisions(message)
        requested_tools: list[str] = []
        if self._needs_player_info(tool_decisions):
            requested_tools.append("player_info")
        if self._needs_farm_info(tool_decisions):
            requested_tools.append("farm_info")
        if self._needs_game_guide(tool_decisions):
            requested_tools.append("game_guide")
        return {"requested_tools": requested_tools}

    @staticmethod
    def _route_after_decision(state: ChatAgentState) -> str:
        return "run_tools" if state.get("requested_tools") else "generate_reply"

    def _run_tools(self, state: ChatAgentState) -> ChatAgentState:
        outputs: dict[str, str] = {}
        for tool_name in state.get("requested_tools", []):
            tool_instance = self._tool_map.get(tool_name)
            if tool_instance is None:
                continue
            input_field = TOOL_INPUT_FIELD_MAP.get(tool_name)
            if input_field == "query":
                tool_input = {input_field: state.get("message", "")}
            else:
                tool_input = {input_field: state.get("player_id", "")} if input_field else {}
            outputs[tool_name] = tool_instance.invoke(tool_input)
        return {"tool_outputs": outputs}

    def _generate_reply(self, state: ChatAgentState) -> ChatAgentState:
        memories = state.get("memories", DEFAULT_EMPTY_MEMORIES)
        message = state.get("message", "")
        tool_outputs = state.get("tool_outputs", {})
        tool_text = self._build_tool_text(tool_outputs)
        fallback_response = self._build_fallback_response(
            memories=memories,
            message=message,
            tool_outputs=tool_outputs,
            tool_text=tool_text,
        )
        if self._openai_client is None:
            return {"response": fallback_response}

        # AgentScope 可用时沿用同一提示词入口，为后续替换成 AgentScope Agent 留接口。
        if self._agentscope_enabled and is_agentscope_ready():
            logger.debug("agentscope runtime ready for chat assistant")

        output_text = self._call_openai(
            self._build_user_prompt(memories=memories, message=message, tool_text=tool_text)
        )
        try:
            payload = json.loads(output_text) if output_text else None
        except (TypeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and payload.get("response"):
            return {"response": str(payload["response"])}
        if isinstance(output_text, str) and output_text.strip():
            return {"response": output_text}
        return {"response": fallback_response}

    def _build_fallback_response(
        self,
        *,
        memories: str,
        message: str,
        tool_outputs: dict[str, str],
        tool_text: str,
    ) -> str:
        guide_text = tool_outputs.get("game_guide")
        if len(tool_outputs) == 1 and guide_text:
            return guide_text
        if tool_text:
            return tool_text
        if memories and memories != DEFAULT_EMPTY_MEMORIES:
            return memories
        return "想聊什么就继续告诉我吧。"

    def _build_user_prompt(self, *, memories: str, message: str, tool_text: str) -> str:
        return (
            f"历史聊天：{memories}\n"
            f"玩家当前消息：{message}\n"
            f"工具查询结果：{tool_text or '本轮无需调用工具，直接自然聊天即可。'}\n"
            "请用自然、简洁、友好的中文直接回复玩家；如工具已返回信息，请优先结合工具结果帮助玩家。"
        )

    def _build_tool_decision_prompt(self, *, memories: str, message: str) -> str:
        return (
            "请判断当前玩家消息是否需要调用工具，并只返回 JSON 对象，不要输出额外解释。\n"
            "可选字段只有：player_info、farm_info、game_guide。\n"
            "字段含义如下：\n"
            "- player_info：需要查询玩家昵称、账号、等级、金币等基础资料时为 true。\n"
            "- farm_info：需要查询田地、作物、种植状态等农场信息时为 true。\n"
            "- game_guide：需要查询玩法攻略、技巧、入门建议时为 true。\n"
            "判断要求：\n"
            "1. 普通寒暄、情绪安慰、回忆历史聊天时，通常都应为 false。\n"
            "2. 如果玩家在一句话里同时需要多个工具，可以同时返回多个 true。\n"
            "3. 结合最近聊天理解代词、省略和上下文。\n"
            f"最近聊天：{memories}\n"
            f"玩家当前消息：{message}\n"
            '请仅返回类似 {"player_info": false, "farm_info": true, "game_guide": false} 的 JSON。'
        )

    @staticmethod
    def _build_tool_text(tool_outputs: dict[str, str]) -> str:
        if not tool_outputs:
            return ""
        labels = {
            "player_info": "玩家信息",
            "farm_info": "田地信息",
            "game_guide": "游戏攻略",
        }
        return "；".join(
            f"{labels.get(name, name)}：{value}"
            for name, value in tool_outputs.items()
            if value
        )

    def _decide_tools_with_model(self, *, message: str, memories: str) -> dict[str, bool] | None:
        output_text = self._call_openai(self._build_tool_decision_prompt(memories=memories, message=message))
        if not output_text:
            return None
        return self._parse_tool_decisions(output_text)

    @staticmethod
    def _parse_tool_decisions(output_text: str) -> dict[str, bool] | None:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            snippet = output_text[:MAX_TOOL_DECISION_LOG_LENGTH]
            if len(output_text) > MAX_TOOL_DECISION_LOG_LENGTH:
                snippet += "...(truncated)"
            logger.warning("聊天工具判定返回的 JSON 解析失败，响应片段：%s", snippet)
            return None
        return {
            tool_name: ChatAssistant._normalize_decision_flag(payload.get(tool_name))
            for tool_name in AVAILABLE_TOOLS
        }

    @staticmethod
    def _normalize_decision_flag(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in AFFIRMATIVE_DECISION_VALUES
        return False

    @staticmethod
    def _needs_player_info(tool_decisions: dict[str, bool]) -> bool:
        return bool(tool_decisions.get("player_info"))

    @staticmethod
    def _needs_farm_info(tool_decisions: dict[str, bool]) -> bool:
        return bool(tool_decisions.get("farm_info"))

    @staticmethod
    def _needs_game_guide(tool_decisions: dict[str, bool]) -> bool:
        return bool(tool_decisions.get("game_guide"))

    @staticmethod
    def _fallback_tool_decisions(message: str) -> dict[str, bool]:
        return {
            tool_name: ChatAssistant._contains_positive_keyword(message, keywords)
            for tool_name, keywords in (
                ("player_info", PLAYER_INFO_KEYWORDS),
                ("farm_info", FARM_INFO_KEYWORDS),
                ("game_guide", GAME_GUIDE_KEYWORDS),
            )
        }

    @staticmethod
    def _contains_positive_keyword(message: str, keywords: tuple[str, ...]) -> bool:
        return any(
            keyword in message and all(f"{prefix}{keyword}" not in message for prefix in NEGATION_PREFIXES)
            for keyword in keywords
        )
