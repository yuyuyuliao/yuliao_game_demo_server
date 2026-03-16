from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional, TypedDict

from langchain.tools import tool
from langgraph.graph import END, START, StateGraph

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


class ChatAgentState(TypedDict, total=False):
    """聊天 agent 在 LangGraph 中流转的状态。"""

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
        self._graph = self._build_graph()

    def reply(self, history: list[str], message: str, player_id: str = "") -> dict[str, str]:
        """根据聊天历史和用户输入生成日常对话回复。"""
        result = self._graph.invoke(
            {
                "player_id": player_id,
                "history": history,
                "message": message,
            }
        )
        print(result)
        return {"response": result["response"]}

    def _build_tools(self) -> dict[str, Any]:
        """构建 LangChain tool，供 LangGraph 工作流按需调用。"""

        @tool
        def read_player_info_tool(player_id: str) -> str:
            """读取玩家基础信息，包括昵称、账号、等级和金币。"""
            if self._player_info_reader is None:
                return "当前没有可用的玩家资料读取工具。"
            return self._player_info_reader(player_id)

        @tool
        def read_player_farm_tool(player_id: str) -> str:
            """读取玩家当前可查看的田地与作物信息。"""
            if self._farm_info_reader is None:
                return "当前没有可用的田地信息读取工具。"
            return self._farm_info_reader(player_id)

        @tool
        def search_game_guide_tool(query: str) -> str:
            """查询游戏攻略或技巧，优先从向量知识库中检索答案。"""
            if self._knowledge_search is None:
                return "当前没有可用的攻略知识库。"
            documents = self._knowledge_search(query, n_results=2)
            if not documents:
                return "知识库里暂时没有查到相关攻略。"
            return "；".join(documents)

        return {
            "player_info": read_player_info_tool,
            "farm_info": read_player_farm_tool,
            "game_guide": search_game_guide_tool,
        }

    def _build_graph(self):
        """构建基于 LangGraph 的聊天编排流程。"""
        graph = StateGraph(ChatAgentState)
        graph.add_node("remember", self._remember_history)
        graph.add_node("decide_tools", self._decide_tools)
        graph.add_node("run_tools", self._run_tools)
        graph.add_node("generate_reply", self._generate_reply)
        graph.add_edge(START, "remember")
        graph.add_edge("remember", "decide_tools")
        graph.add_conditional_edges(
            "decide_tools",
            self._route_after_decision,
            {
                "run_tools": "run_tools",
                "generate_reply": "generate_reply",
            },
        )
        graph.add_edge("run_tools", "generate_reply")
        graph.add_edge("generate_reply", END)
        return graph.compile()

    def _remember_history(self, state: ChatAgentState) -> ChatAgentState:
        """整理近期历史对话，作为短期记忆输入。"""
        history = state.get("history") or []
        memories = "；".join(history[-CHAT_MEMORY_WINDOW:]) if history else DEFAULT_EMPTY_MEMORIES
        return {"memories": memories}

    def _decide_tools(self, state: ChatAgentState) -> ChatAgentState:
        """根据玩家问题内容决定是否需要触发工具。"""
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
        """根据是否需要查询工具决定后续节点。"""
        return "run_tools" if state.get("requested_tools") else "generate_reply"

    def _run_tools(self, state: ChatAgentState) -> ChatAgentState:
        """执行已选中的工具并收集结果。"""
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
        """综合记忆与工具结果生成最终回复。"""
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
        output_text = self._call_openai(
            self._build_user_prompt(memories=memories, message=message, tool_text=tool_text)
        )
        output_text = json.loads(output_text)
        print(f"生成回复时模型输出：{output_text}")
        if output_text:
            return output_text
        return {"response": fallback_response}

    def _build_fallback_response(
        self,
        *,
        memories: str,
        message: str,
        tool_outputs: dict[str, str],
        tool_text: str,
    ) -> str:
        """在未调用大模型时，尽量直接返回已经得到的结论，避免生硬套话。"""
        guide_text = tool_outputs.get("game_guide")
        if len(tool_outputs) == 1 and guide_text:
            return guide_text
        if tool_text:
            return tool_text
        if memories and memories != DEFAULT_EMPTY_MEMORIES:
            return memories
        return "想聊什么就继续告诉我吧。"

    def _build_user_prompt(self, *, memories: str, message: str, tool_text: str) -> str:
        """将聊天历史与工具结果整理为发送给 OpenAI 的用户输入。"""
        return (
            f"历史聊天：{memories}\n"
            f"玩家当前消息：{message}\n"
            f"工具查询结果：{tool_text or '本轮无需调用工具，直接自然聊天即可。'}\n"
            "请用自然、简洁、友好的中文直接回复玩家；如工具已返回信息，请优先结合工具结果帮助玩家。"
        )

    def _build_tool_decision_prompt(self, *, memories: str, message: str) -> str:
        """将上下文整理成工具选择提示词，让模型判断本轮是否需要查资料。"""
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
        """将各个工具的结果整理成便于回复的文字。"""
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
        """优先交给模型做工具选择；无响应或响应无法解析时返回 None 走本地兜底。"""
        output_text = self._call_openai(self._build_tool_decision_prompt(memories=memories, message=message))
        print(output_text)
        if not output_text:
            return None
        return self._parse_tool_decisions(output_text)

    @staticmethod
    def _parse_tool_decisions(output_text: str) -> dict[str, bool] | None:
        """解析模型返回的工具判断 JSON。"""
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            snippet = output_text[:MAX_TOOL_DECISION_LOG_LENGTH]
            if len(output_text) > MAX_TOOL_DECISION_LOG_LENGTH:
                snippet += "...(truncated)"
            logger.warning(
                "聊天工具判定返回的 JSON 解析失败，响应片段：%s",
                snippet,
            )
            return None
        return {
            tool_name: ChatAssistant._normalize_decision_flag(payload.get(tool_name))
            for tool_name in AVAILABLE_TOOLS
        }

    @staticmethod
    def _normalize_decision_flag(value: object) -> bool:
        """把模型返回的字段值规整为布尔值，兼容少量字符串化布尔输出。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in AFFIRMATIVE_DECISION_VALUES
        return False

    @staticmethod
    def _needs_player_info(tool_decisions: dict[str, bool]) -> bool:
        """根据模型判定结果决定是否需要读取玩家信息。"""
        return bool(tool_decisions.get("player_info"))

    @staticmethod
    def _needs_farm_info(tool_decisions: dict[str, bool]) -> bool:
        """根据模型判定结果决定是否需要读取田地信息。"""
        return bool(tool_decisions.get("farm_info"))

    @staticmethod
    def _needs_game_guide(tool_decisions: dict[str, bool]) -> bool:
        """根据模型判定结果决定是否需要检索游戏攻略。"""
        return bool(tool_decisions.get("game_guide"))

    @staticmethod
    def _fallback_tool_decisions(message: str) -> dict[str, bool]:
        """当模型暂时不可用时，使用旧规则兜底，避免工具能力整体失效。"""
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
        """简单过滤明显否定表达，减少工具误触发。"""
        return any(
            keyword in message and all(f"{prefix}{keyword}" not in message for prefix in NEGATION_PREFIXES)
            for keyword in keywords
        )
