from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional, TypedDict

from langchain.tools import tool
from langgraph.graph import END, START, StateGraph

from app.agent.base import AIAssistantBase
from app.prompt.system_prompts import (
    CHAT_DAILY_PROMPT,
    CHAT_GAME_DATA_QUERY_PROMPT,
    CHAT_INTENT_RECOGNITION_PROMPT,
)

logger = logging.getLogger(__name__)

# 最近 8 条历史文本通常足够覆盖几轮连续对话，同时能避免兜底回复里塞入过长上下文。
CHAT_MEMORY_WINDOW = 8
DEFAULT_EMPTY_MEMORIES = "我们还没有历史聊天记录。"
MAX_TOOL_DECISION_LOG_LENGTH = 120
AVAILABLE_TOOLS = ("player_info", "farm_info", "game_guide")
AFFIRMATIVE_DECISION_VALUES = {"true", "1", "yes", "y", "是"}
PLAYER_INFO_KEYWORDS = ("玩家信息", "玩家资料", "我的资料", "我的信息", "等级", "金币", "账号", "昵称")
FARM_INFO_KEYWORDS = ("农场", "作物", "庄稼", "收成", "种植", "成熟", "可种", "可以种", "田地", "土地", "地块")
GAME_GUIDE_KEYWORDS = ("攻略", "技巧", "建议", "怎么玩", "如何", "怎么", "帮助", "扫雷", "国际象棋", "下棋", "开局")
NEGATION_PREFIXES = ("不需要", "不用", "不要", "别")
TOOL_INPUT_FIELD_MAP = {
    "player_info": "player_id",
    "farm_info": "player_id",
    "game_guide": "query",
}
MAX_REACT_STEPS = 4
FORBIDDEN_FARM_TERMS = (
    "普通黄地",
    "黄土地",
    "松软耕土",
    "肥沃黑土",
    "土壤肥力",
    "土壤",
    "土地价格",
    "购买土地",
)


class ChatAgentState(TypedDict, total=False):
    """聊天 agent 在 LangGraph 中流转的状态。"""

    player_id: str
    history: list[str]
    message: str
    memories: str
    intent: str
    intent_reason: str
    requested_tools: list[str]
    tool_outputs: dict[str, str]
    react_steps: list[dict[str, str]]
    react_action: str
    react_action_input: str
    react_iteration: int
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
        print(
            "[chat_agent] reply start "
            f"player_id={player_id!r} message={message!r} history_count={len(history)}"
        )
        result = self._graph.invoke(
            {
                "player_id": player_id,
                "history": history,
                "message": message,
            }
        )
        print(f"[chat_agent] reply final response={result.get('response')!r}")
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
            """读取玩家当前作物实例、种植状态与可种作物信息。"""
            if self._farm_info_reader is None:
                return "当前没有可用的作物种植信息读取工具。"
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
        graph.add_node("intent_agent", self._intent_agent)
        graph.add_node("select_agent", self._select_agent)
        graph.add_node("daily_chat_agent", self._daily_chat_agent)
        graph.add_node("game_data_agent", self._game_data_agent)
        graph.add_node("game_data_tool", self._react_run_tool)
        graph.add_edge(START, "remember")
        graph.add_edge("remember", "intent_agent")
        graph.add_edge("intent_agent", "select_agent")
        graph.add_conditional_edges(
            "select_agent",
            self._route_selected_agent,
            {
                "daily_chat": "daily_chat_agent",
                "game_data_query": "game_data_agent",
            },
        )
        graph.add_edge("daily_chat_agent", END)
        graph.add_conditional_edges(
            "game_data_agent",
            self._route_after_game_data_agent,
            {
                "run_tool": "game_data_tool",
                "finish": END,
            },
        )
        graph.add_edge("game_data_tool", "game_data_agent")
        return graph.compile()

    def _remember_history(self, state: ChatAgentState) -> ChatAgentState:
        """整理近期历史对话，作为短期记忆输入。"""
        history = state.get("history") or []
        memories = "；".join(history[-CHAT_MEMORY_WINDOW:]) if history else DEFAULT_EMPTY_MEMORIES
        print(f"[chat_agent] remember memories={memories!r}")
        return {"memories": memories}

    def _intent_agent(self, state: ChatAgentState) -> ChatAgentState:
        """意图识别 agent：判断进入日常对话还是游戏数据查询。"""
        prompt = self._build_intent_prompt(state)
        print(f"[chat_agent] intent_agent prompt={prompt!r}")
        output_text = self._call_openai(prompt)
        print(f"[chat_agent] intent_agent raw output={output_text!r}")
        intent, reason = self._parse_intent_output(output_text, state)
        print(f"[chat_agent] intent_agent parsed intent={intent!r} reason={reason!r}")
        return {"intent": intent, "intent_reason": reason}

    def _select_agent(self, state: ChatAgentState) -> ChatAgentState:
        """选择节点：把意图识别结果交给后续 agent。"""
        print(
            "[chat_agent] select_agent "
            f"intent={state.get('intent')!r} reason={state.get('intent_reason')!r}"
        )
        return {}

    @staticmethod
    def _route_selected_agent(state: ChatAgentState) -> str:
        """根据意图选择后续 agent。"""
        if state.get("intent") == "game_data_query":
            return "game_data_query"
        return "daily_chat"

    def _daily_chat_agent(self, state: ChatAgentState) -> ChatAgentState:
        """日常对话 agent：不调用工具，只根据历史和当前消息自然回复。"""
        prompt = self._build_daily_chat_prompt(state)
        print(f"[chat_agent] daily_chat_agent prompt={prompt!r}")
        output_text = self._call_openai(prompt)
        print(f"[chat_agent] daily_chat_agent raw output={output_text!r}")
        if not output_text:
            fallback = self._build_daily_fallback_response(state)
            print(f"[chat_agent] daily_chat_agent fallback={fallback!r}")
            return {"response": fallback}
        response = self._extract_response_text(output_text)
        if response:
            print(f"[chat_agent] daily_chat_agent response={response!r}")
            return {"response": response}
        print(f"[chat_agent] daily_chat_agent text response={output_text!r}")
        return {"response": output_text}

    def _game_data_agent(self, state: ChatAgentState) -> ChatAgentState:
        """游戏数据查询 agent：选择工具或基于 observation 生成最终回答。"""
        print(
            "[chat_agent] game_data_agent "
            f"iteration={state.get('react_iteration', 0)} steps={len(state.get('react_steps', []))}"
        )
        if state.get("react_iteration", 0) >= MAX_REACT_STEPS:
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] game_data_agent max steps fallback={fallback!r}")
            return {"response": fallback}
        next_required_action = self._next_required_react_action(state)
        if next_required_action is not None:
            action, action_input = next_required_action
            print(f"[chat_agent] game_data_agent planned action={action!r} reason=keyword matched")
            return {
                "react_action": action,
                "react_action_input": action_input,
            }

        prompt = self._build_game_data_prompt(state)
        print(f"[chat_agent] game_data_agent prompt={prompt!r}")
        output_text = self._call_openai(prompt)
        print(f"[chat_agent] game_data_agent raw output={output_text!r}")
        if not output_text:
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] game_data_agent unavailable fallback={fallback!r}")
            return {"response": fallback}

        decision = self._parse_react_decision(output_text)
        print(f"[chat_agent] game_data_agent parsed decision={decision!r}")
        final_answer = decision.get("final_answer", "")
        if final_answer:
            response = self._ensure_current_farm_answer(final_answer, state)
            print(f"[chat_agent] game_data_agent final_answer accepted={response!r}")
            return {"response": response}

        action = decision.get("action", "")
        if action in AVAILABLE_TOOLS:
            print(
                "[chat_agent] game_data_agent selected tool "
                f"action={action!r} action_input={decision.get('action_input', '')!r}"
            )
            return {
                "react_action": action,
                "react_action_input": decision.get("action_input", ""),
            }

        if self._looks_like_json(output_text):
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] game_data_agent json without action fallback={fallback!r}")
            return {"response": fallback}
        response = self._ensure_current_farm_answer(output_text, state)
        print(f"[chat_agent] game_data_agent text response={response!r}")
        return {"response": response}

    @staticmethod
    def _route_after_game_data_agent(state: ChatAgentState) -> str:
        """游戏数据查询 agent 结束或进入工具节点。"""
        return "finish" if state.get("response") else "run_tool"

    def _build_intent_prompt(self, state: ChatAgentState) -> str:
        """构造意图识别提示词。"""
        return (
            f"{CHAT_INTENT_RECOGNITION_PROMPT.strip()}\n"
            f"最近聊天：{state.get('memories', DEFAULT_EMPTY_MEMORIES)}\n"
            f"玩家当前消息：{state.get('message', '')}\n"
        )

    def _build_daily_chat_prompt(self, state: ChatAgentState) -> str:
        """构造日常对话 agent 提示词。"""
        return (
            f"{CHAT_DAILY_PROMPT.strip()}\n"
            f"最近聊天：{state.get('memories', DEFAULT_EMPTY_MEMORIES)}\n"
            f"玩家当前消息：{state.get('message', '')}\n"
        )

    def _build_game_data_prompt(self, state: ChatAgentState) -> str:
        """构造游戏数据查询 agent 提示词。"""
        player_id = state.get("player_id", "")
        scratchpad = self._build_react_scratchpad(state.get("react_steps", []))
        return (
            f"{CHAT_GAME_DATA_QUERY_PROMPT.strip()}\n"
            f"玩家 ID：{player_id}\n"
            f"最近聊天：{state.get('memories', DEFAULT_EMPTY_MEMORIES)}\n"
            f"玩家当前消息：{state.get('message', '')}\n"
            f"已有 ReAct 过程：{scratchpad or '暂无'}\n"
        )

    def _parse_intent_output(self, output_text: str | None, state: ChatAgentState) -> tuple[str, str]:
        """解析意图识别输出；不可用时按本地规则兜底。"""
        payload = self._parse_json_object(output_text or "") if output_text else None
        if payload is not None:
            intent = str(payload.get("intent") or "")
            if intent in {"daily_chat", "game_data_query"}:
                return intent, str(payload.get("reason") or "")
            if any(self._normalize_decision_flag(payload.get(tool_name)) for tool_name in AVAILABLE_TOOLS):
                return "game_data_query", "兼容旧工具选择 JSON"
        message = state.get("message", "")
        if any(self._fallback_tool_decisions(message).values()):
            return "game_data_query", "本地关键词规则命中游戏数据查询"
        return "daily_chat", "本地规则默认日常对话"

    def _build_daily_fallback_response(self, state: ChatAgentState) -> str:
        """日常对话模型不可用时的兜底回复。"""
        memories = state.get("memories", "")
        if memories and memories != DEFAULT_EMPTY_MEMORIES:
            return memories
        return "我在，继续说。"

    def _extract_response_text(self, output_text: str) -> str:
        """从 daily agent 模型输出中提取 response，兼容纯文本。"""
        payload = self._parse_json_object(output_text)
        if payload is None:
            return output_text
        response = self._extract_model_response(payload)
        return response

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

    @staticmethod
    def _route_after_react_reason(state: ChatAgentState) -> str:
        """根据 ReAct 推理结果决定是否执行工具。"""
        return "finish" if state.get("response") else "run_tool"

    def _react_reason(self, state: ChatAgentState) -> ChatAgentState:
        """ReAct 推理节点：决定继续调用工具，或给出最终总结。"""
        print(
            "[chat_agent] react_reason "
            f"iteration={state.get('react_iteration', 0)} steps={len(state.get('react_steps', []))}"
        )
        if state.get("react_iteration", 0) >= MAX_REACT_STEPS:
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] react max steps fallback={fallback!r}")
            return {"response": fallback}
        next_required_action = self._next_required_react_action(state)
        if next_required_action is not None:
            action, action_input = next_required_action
            print(f"[chat_agent] planned action={action!r} reason=keyword matched")
            return {
                "react_action": action,
                "react_action_input": action_input,
            }

        prompt = self._build_react_prompt(state)
        print(f"[chat_agent] ai prompt={prompt!r}")
        output_text = self._call_openai(prompt)
        print(f"[chat_agent] ai raw output={output_text!r}")
        if not output_text:
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] ai unavailable fallback={fallback!r}")
            return {"response": fallback}

        decision = self._parse_react_decision(output_text)
        print(f"[chat_agent] ai parsed decision={decision!r}")
        final_answer = decision.get("final_answer", "")
        if final_answer:
            response = self._ensure_current_farm_answer(final_answer, state)
            print(f"[chat_agent] ai final_answer accepted={response!r}")
            return {"response": response}

        action = decision.get("action", "")
        if action in AVAILABLE_TOOLS:
            print(
                "[chat_agent] ai selected tool "
                f"action={action!r} action_input={decision.get('action_input', '')!r}"
            )
            return {
                "react_action": action,
                "react_action_input": decision.get("action_input", ""),
            }

        if self._looks_like_json(output_text):
            fallback = self._build_react_fallback_response(state)
            print(f"[chat_agent] ai json without action fallback={fallback!r}")
            return {"response": fallback}
        response = self._ensure_current_farm_answer(output_text, state)
        print(f"[chat_agent] ai text response={response!r}")
        return {"response": response}

    def _next_required_react_action(self, state: ChatAgentState) -> tuple[str, str] | None:
        """Return the next keyword-required tool that has not run in this ReAct turn."""
        completed_actions = {
            step.get("action", "")
            for step in state.get("react_steps", [])
            if step.get("action")
        }
        for tool_name in self._ordered_required_tools(state.get("message", "")):
            if tool_name in completed_actions:
                continue
            if TOOL_INPUT_FIELD_MAP.get(tool_name) == "query":
                return tool_name, state.get("message", "")
            return tool_name, state.get("player_id", "")
        return None

    @staticmethod
    def _ordered_required_tools(message: str) -> list[str]:
        """Use local keyword rules to preserve deterministic multi-tool ordering."""
        tool_decisions = ChatAssistant._fallback_tool_decisions(message)
        return [
            tool_name
            for tool_name in AVAILABLE_TOOLS
            if tool_decisions.get(tool_name)
        ]

    def _react_run_tool(self, state: ChatAgentState) -> ChatAgentState:
        """ReAct 工具节点：执行模型选择的工具，并把结果作为 observation。"""
        action = state.get("react_action", "")
        action_input = state.get("react_action_input", "")
        print(f"[chat_agent] tool start action={action!r} action_input={action_input!r}")
        observation = self._invoke_chat_tool(action, action_input, state)
        print(f"[chat_agent] tool observation action={action!r} observation={observation!r}")
        steps = list(state.get("react_steps", []))
        steps.append(
            {
                "action": action,
                "action_input": action_input,
                "observation": observation,
            }
        )
        return {
            "react_steps": steps,
            "react_action": "",
            "react_action_input": "",
            "react_iteration": state.get("react_iteration", 0) + 1,
        }

    def _invoke_chat_tool(self, tool_name: str, action_input: str, state: ChatAgentState) -> str:
        """按 ReAct action 调用聊天工具。"""
        tool_instance = self._tool_map.get(tool_name)
        if tool_instance is None:
            print(f"[chat_agent] tool missing tool_name={tool_name!r}")
            return f"未知工具：{tool_name}"
        input_field = TOOL_INPUT_FIELD_MAP.get(tool_name)
        if input_field == "query":
            tool_input = {input_field: action_input or state.get("message", "")}
        else:
            tool_input = {input_field: action_input or state.get("player_id", "")} if input_field else {}
        print(f"[chat_agent] tool invoke tool_name={tool_name!r} tool_input={tool_input!r}")
        return str(tool_instance.invoke(tool_input))

    def _build_react_prompt(self, state: ChatAgentState) -> str:
        """构造 ReAct 提示词，让模型基于 observation 总结，而不是直接透传工具文本。"""
        memories = state.get("memories", DEFAULT_EMPTY_MEMORIES)
        message = state.get("message", "")
        player_id = state.get("player_id", "")
        scratchpad = self._build_react_scratchpad(state.get("react_steps", []))
        return (
            "你正在扮演游戏世界管理者爻光，请使用 ReAct 方式回答玩家。\n"
            "你可以先思考是否需要调用工具，工具返回的是 observation，只能作为依据，不能直接原样复制给玩家。\n"
            "可用工具：\n"
            "- player_info：查询玩家昵称、账号、等级、金币等基础资料，action_input 使用 player_id。\n"
            "- farm_info：查询玩家当前作物实例、种植状态和可种作物，action_input 使用 player_id。\n"
            "- game_guide：查询玩法攻略、技巧、入门建议，action_input 使用玩家问题。\n"
            "输出格式必须是 JSON，二选一：\n"
            '1. 调用工具：{"thought":"为什么需要工具","action":"farm_info","action_input":"1"}\n'
            '2. 最终回答：{"thought":"如何基于已有信息回答","final_answer":"给玩家的自然中文总结"}\n'
            "最终回答要求：\n"
            "- 根据 observation 归纳总结，给出面向玩家的自然建议。\n"
            "- 不要直接返回工具原文，要把作物状态和可种作物总结成玩家能直接执行的建议。\n"
            "- 当前游戏已经没有土地、田地、地块、土壤、土壤肥力、土地价格、购买土地等概念，不要提这些旧设定。\n"
            "- 如果 observation 提到水分、养分、温度，它们是作物实例状态，不是土地属性。\n"
            "- 不要暴露 thought、action、observation、JSON 字段名。\n"
            "- 回答简洁、主动，不要用问句结尾。\n"
            f"玩家 ID：{player_id}\n"
            f"最近聊天：{memories}\n"
            f"玩家当前消息：{message}\n"
            f"已有 ReAct 过程：{scratchpad or '暂无'}\n"
        )

    @staticmethod
    def _build_react_scratchpad(steps: list[dict[str, str]]) -> str:
        """整理 ReAct 已执行步骤。"""
        if not steps:
            return ""
        return "\n".join(
            f"Action: {step.get('action', '')}\n"
            f"Action Input: {step.get('action_input', '')}\n"
            f"Observation: {step.get('observation', '')}"
            for step in steps
        )

    @staticmethod
    def _parse_react_decision(output_text: str) -> dict[str, str]:
        """解析 ReAct JSON；失败时返回空决策，让调用方按纯文本处理。"""
        payload = ChatAssistant._parse_json_object(output_text)
        if payload is None:
            return {}
        for tool_name in AVAILABLE_TOOLS:
            if ChatAssistant._normalize_decision_flag(payload.get(tool_name)):
                return {
                    "action": tool_name,
                    "action_input": str(payload.get("action_input") or ""),
                    "final_answer": "",
                }
        return {
            "action": str(payload.get("action") or ""),
            "action_input": str(payload.get("action_input") or ""),
            "final_answer": str(payload.get("final_answer") or payload.get("response") or ""),
        }

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        """判断模型输出是否像 JSON，避免把格式化控制内容直接暴露给玩家。"""
        return ChatAssistant._parse_json_object(text) is not None

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        """解析直接 JSON 或 markdown JSON 代码块中的对象。"""
        candidates = [text.strip()]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _build_react_fallback_response(self, state: ChatAgentState) -> str:
        """模型不可用或循环超限时，根据 observation 做最小总结，避免直接透传工具原文。"""
        steps = state.get("react_steps", [])
        farm_observations = [
            step.get("observation", "")
            for step in steps
            if step.get("action") == "farm_info" and step.get("observation")
        ]
        other_observations = [
            step.get("observation", "")
            for step in steps
            if step.get("action") != "farm_info" and step.get("observation")
        ]
        if farm_observations:
            return "；".join(other_observations + [self._summarize_farm_observations(farm_observations)])
        if other_observations:
            return "；".join(other_observations)
        memories = state.get("memories", "")
        if memories and memories != DEFAULT_EMPTY_MEMORIES:
            return memories
        return "我现在还缺少足够的资料判断，建议先确认农场和作物数据已经初始化。"

    def _ensure_current_farm_answer(self, answer: str, state: ChatAgentState) -> str:
        """过滤旧 land 设定；命中时改用 observation 生成当前模型的回答。"""
        if not self._contains_forbidden_farm_term(answer):
            return answer
        print(f"[chat_agent] forbidden old farm terms detected answer={answer!r}")
        observations = [
            step.get("observation", "")
            for step in state.get("react_steps", [])
            if step.get("observation")
        ]
        if observations:
            return self._summarize_farm_observations(observations)
        return "当前游戏已经改为直接围绕作物实例管理。请优先查看已有作物状态，再从可种作物里选择成本和成熟时间适合的一种。"

    @staticmethod
    def _contains_forbidden_farm_term(text: str) -> bool:
        """识别已经废弃的 land/soil 旧设定。"""
        return any(term in text for term in FORBIDDEN_FARM_TERMS)

    @staticmethod
    def _summarize_farm_observations(observations: list[str]) -> str:
        """基于工具 observation 生成不含 land 概念的简洁种植建议。"""
        text = "；".join(observations)
        crop_section = text.split("可种作物：", 1)[1] if "可种作物：" in text else ""
        crop_names = re.findall(r"([^；。（]+)（成本", crop_section)
        unique_crop_names = list(dict.fromkeys(name.strip() for name in crop_names if name.strip()))

        active_match = re.search(r"当前(?:有|可查看)\s+(\d+)\s+个正在生长的作物实例", text)
        active_count = active_match.group(1) if active_match else ""
        harvest_count = text.count("可收获")

        parts = []
        if unique_crop_names:
            parts.append("现在可以种：" + "、".join(unique_crop_names) + "。")
        if active_count:
            status = f"当前有 {active_count} 个作物正在生长"
            if harvest_count:
                status += f"，其中 {harvest_count} 个已可收获"
            parts.append(status + "。")
        if unique_crop_names:
            first_crop = unique_crop_names[0]
            parts.append(f"优先选择{first_crop}这类成本较低、节奏稳定的作物；想提高单次收益时，再考虑后面的高价值作物。")
        return "".join(parts) or "当前可以从作物列表里选择一种开始种植，并优先处理已成熟的作物。"

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
        output_text = self._call_openai(
            self._build_user_prompt(memories=memories, message=message, tool_text=tool_text)
        )
        if output_text:
            try:
                payload = json.loads(output_text)
            except json.JSONDecodeError:
                return {"response": output_text}
            else:
                response = self._extract_model_response(payload)
                if response:
                    return {"response": response}
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
            "- farm_info：需要查询作物实例、种植状态、成熟情况、可种作物等农场信息时为 true。\n"
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
            "farm_info": "农场信息",
            "game_guide": "游戏攻略",
        }
        return "；".join(
            f"{labels.get(name, name)}：{value}"
            for name, value in tool_outputs.items()
            if value
        )

    @staticmethod
    def _extract_model_response(payload: object) -> str:
        """从模型 JSON 中提取最终回复文本，避免无 response 字段时打断接口。"""
        if not isinstance(payload, dict):
            return ""
        response = payload.get("response")
        return response if isinstance(response, str) else ""

    def _decide_tools_with_model(self, *, message: str, memories: str) -> dict[str, bool] | None:
        """优先交给模型做工具选择；无响应或响应无法解析时返回 None 走本地兜底。"""
        output_text = self._call_openai(self._build_tool_decision_prompt(memories=memories, message=message))
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
        """根据模型判定结果决定是否需要读取农场作物信息。"""
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
