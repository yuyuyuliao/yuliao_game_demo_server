from __future__ import annotations

from typing import Callable, Optional

from app.agent.base import AIAssistantBase


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
    ) -> None:
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self._knowledge_search = knowledge_search

    def suggest(self, board_fen: str, side_to_move: Optional[str] = None) -> dict[str, str]:
        """根据走子方给出开局建议，并补充简短原因。"""
        side = (side_to_move or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        move = "e2e4" if side == "white" else "e7e5"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search("国际象棋 开局", n_results=1)
        return {"move": move, "reason": tips[0] if tips else "控制中心并发展子力"}
