from __future__ import annotations

from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.base import AIAssistantBase


class ChessSuggestState(TypedDict, total=False):
    """国际象棋建议 agent 在 LangGraph 中流转的状态。"""

    board_fen: str
    side_to_move: str
    side: str
    fallback_move: str
    fallback_reason: str
    model_output: str | None
    result: dict[str, str]


def _fen_side_to_move(board_fen: str) -> Optional[str]:
    """从 FEN 字符串解析当前走子方，返回 white/black。"""
    fields = board_fen.split()
    if len(fields) >= 2 and fields[1] in {"w", "b"}:
        return "white" if fields[1] == "w" else "black"
    return None


class ChessSuggestAssistant(AIAssistantBase):
    """下棋助手：给玩家提供一步简化的走棋建议。"""

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
        super().__init__(
            system_prompt=system_prompt,
            model_name=model_name,
            openai_client=openai_client,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
        )
        self._knowledge_search = knowledge_search
        self._graph = self._build_graph()

    def suggest(self, board_fen: str, side_to_move: Optional[str] = None) -> dict[str, str]:
        """根据走子方给出开局建议，并补充简短原因。"""
        result = self._graph.invoke(
            {
                "board_fen": board_fen,
                "side_to_move": side_to_move or "",
            }
        )
        return result["result"]

    def _build_graph(self):
        """构建基于 LangGraph 的国际象棋建议流程。"""
        graph = StateGraph(ChessSuggestState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("call_model", self._call_model)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "call_model")
        graph.add_edge("call_model", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _prepare_context(self, state: ChessSuggestState) -> ChessSuggestState:
        """解析走子方并准备本地兜底建议。"""
        board_fen = state.get("board_fen", "")
        side = (state.get("side_to_move") or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        move = "e2e4" if side == "white" else "e7e5"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search("国际象棋 开局", n_results=1)
        fallback_reason = tips[0] if tips else "控制中心并发展子力"
        return {
            "side": side,
            "fallback_move": move,
            "fallback_reason": fallback_reason,
        }

    def _call_model(self, state: ChessSuggestState) -> ChessSuggestState:
        """调用模型生成候选建议。"""
        output_text = self._call_openai(
            self._build_user_prompt(
                board_fen=state.get("board_fen", ""),
                side=state.get("side", "white"),
                move=state.get("fallback_move", "e2e4"),
                reason=state.get("fallback_reason", "控制中心并发展子力"),
            )
        )
        return {"model_output": output_text}

    def _finalize(self, state: ChessSuggestState) -> ChessSuggestState:
        """解析模型输出；不可用时返回本地兜底建议。"""
        move = state.get("fallback_move", "e2e4")
        reason = state.get("fallback_reason", "控制中心并发展子力")
        output_text = state.get("model_output")
        if output_text:
            result = {
                "move": self._extract_uci_move(output_text) or move,
                "reason": output_text,
            }
        else:
            result = {"move": move, "reason": reason}
        return {"result": result}

    def _build_user_prompt(self, *, board_fen: str, side: str, move: str, reason: str) -> str:
        """构造象棋建议请求，让模型在兜底走法基础上生成更自然的建议。"""
        return (
            f"当前棋盘 FEN：{board_fen}\n"
            f"当前走子方：{side}\n"
            f"本地兜底建议走法：{move}\n"
            f"本地兜底理由：{reason}\n"
            "请输出一步适合当前走子方的 UCI 走法，并用中文简短说明理由。"
        )
