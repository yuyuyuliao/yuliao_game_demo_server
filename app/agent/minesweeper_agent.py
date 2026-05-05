from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.base import AIAssistantBase


class MinesweeperState(TypedDict, total=False):
    """扫雷 agent 在 LangGraph 中流转的状态。"""

    board: Any
    fallback_result: dict[str, Any]
    model_output: str | None
    result: dict[str, Any]


class MinesweeperAssistant(AIAssistantBase):
    """扫雷助手：根据棋盘未知格给出下一步建议。"""

    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        openai_client: Any | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        super().__init__(
            system_prompt=system_prompt,
            model_name=model_name,
            openai_client=openai_client,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            temperature=temperature,
        )
        self._graph = self._build_graph()

    def suggest(self, board: Any) -> dict[str, Any]:
        """返回推荐动作，优先打开第一个未知格。"""
        result = self._graph.invoke({"board": board})
        return result["result"]

    def _build_graph(self):
        """构建基于 LangGraph 的扫雷建议流程。"""
        graph = StateGraph(MinesweeperState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("call_model", self._call_model)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "call_model")
        graph.add_edge("call_model", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _prepare_context(self, state: MinesweeperState) -> MinesweeperState:
        """准备扫雷本地兜底动作。"""
        return {"fallback_result": self._fallback_action(state.get("board", ""))}

    def _call_model(self, state: MinesweeperState) -> MinesweeperState:
        """调用模型生成扫雷动作。"""
        output_text = self._call_openai(self._build_user_prompt(board=state.get("board", "")))
        return {"model_output": output_text}

    def _finalize(self, state: MinesweeperState) -> MinesweeperState:
        """解析模型输出；不可解析时返回兜底坐标。"""
        fallback_result = state.get("fallback_result", {"row": 0, "col": 0})
        output_text = state.get("model_output")
        if output_text:
            return {"result": self._parse_openai_result(output_text, fallback_result)}
        return {"result": fallback_result}

    def _build_user_prompt(self, *, board: Any) -> str:
        """构造扫雷建议请求。"""
        return (
            f"当前扫雷棋盘：{board}\n"
            '请只返回 JSON，例如 {"row": 0, "col": 0}。'
        )

    def _parse_openai_result(self, text: str, fallback_result: dict[str, Any] | None = None) -> dict[str, Any]:
        """尽量从模型文本中解析扫雷动作，不可解析时回退到默认坐标。"""
        fallback = fallback_result or {"row": 0, "col": 0}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return self._parse_text_action(text, fallback)
        if not isinstance(payload, dict):
            return fallback
        row = payload.get("row")
        col = payload.get("col")
        if isinstance(row, int) and isinstance(col, int):
            action = payload.get("action", "open")
            result = {"action": action, "row": row, "col": col}
            if "reason" in payload:
                result["reason"] = payload["reason"]
            return result
        return fallback

    @staticmethod
    def _parse_text_action(text: str, fallback_result: dict[str, Any]) -> dict[str, Any]:
        match = re.search(r"\b(open|flag)\s+(\d+)\s+(\d+)\b", text, re.IGNORECASE)
        if not match:
            return fallback_result
        return {
            "action": match.group(1).lower(),
            "row": int(match.group(2)),
            "col": int(match.group(3)),
            "reason": text,
        }

    @staticmethod
    def _fallback_action(board: Any) -> dict[str, Any]:
        if isinstance(board, list):
            for row_index, row in enumerate(board):
                if not isinstance(row, list):
                    continue
                for col_index, cell in enumerate(row):
                    if cell == "?":
                        return {"action": "open", "row": row_index, "col": col_index}
            return {"action": "done", "row": -1, "col": -1}
        return {"action": "open", "row": 0, "col": 0}
