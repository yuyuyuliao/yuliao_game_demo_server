from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.base import AIAssistantBase
from app.agent.chess_suggest_agent import _fen_side_to_move


class ChessOpponentState(TypedDict, total=False):
    """国际象棋对手 agent 在 LangGraph 中流转的状态。"""

    board_fen: str
    player_side: str
    opponent_side: str
    fallback_move: str
    model_output: str | None
    result: dict[str, str]


class ChessOpponentAssistant(AIAssistantBase):
    """下棋对手助手：模拟对手一方给出应对走法。"""

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

    def suggest(self, board_fen: str, player_side: Optional[str] = None) -> dict[str, str]:
        """根据玩家方位推导对手方并返回对应默认走法。"""
        result = self._graph.invoke(
            {
                "board_fen": board_fen,
                "player_side": player_side or "",
            }
        )
        return result["result"]

    def _build_graph(self):
        """构建基于 LangGraph 的对手走棋流程。"""
        graph = StateGraph(ChessOpponentState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("call_model", self._call_model)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "call_model")
        graph.add_edge("call_model", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _prepare_context(self, state: ChessOpponentState) -> ChessOpponentState:
        """解析玩家方位、对手方位和本地兜底走法。"""
        board_fen = state.get("board_fen", "")
        side = (state.get("player_side") or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        opponent_side = "black" if side == "white" else "white"
        move = "e7e5" if opponent_side == "black" else "e2e4"
        return {
            "player_side": side,
            "opponent_side": opponent_side,
            "fallback_move": move,
        }

    def _call_model(self, state: ChessOpponentState) -> ChessOpponentState:
        """调用模型生成对手候选走法。"""
        output_text = self._call_openai(
            self._build_user_prompt(
                board_fen=state.get("board_fen", ""),
                player_side=state.get("player_side", "white"),
                opponent_side=state.get("opponent_side", "black"),
                move=state.get("fallback_move", "e7e5"),
            )
        )
        return {"model_output": output_text}

    def _finalize(self, state: ChessOpponentState) -> ChessOpponentState:
        """解析模型输出；不可用时返回本地兜底走法。"""
        opponent_side = state.get("opponent_side", "black")
        move = state.get("fallback_move", "e7e5")
        output_text = state.get("model_output")
        if output_text:
            result = {
                "opponent_side": opponent_side,
                "move": self._extract_uci_move(output_text) or move,
            }
        else:
            result = {"opponent_side": opponent_side, "move": move}
        return {"result": result}

    def _build_user_prompt(
        self,
        *,
        board_fen: str,
        player_side: str,
        opponent_side: str,
        move: str,
    ) -> str:
        """构造对手走棋请求。"""
        return (
            f"当前棋盘 FEN：{board_fen}\n"
            f"玩家方：{player_side}\n"
            f"对手方：{opponent_side}\n"
            f"本地兜底建议走法：{move}\n"
            "请输出对手下一步的 UCI 走法。"
        )
