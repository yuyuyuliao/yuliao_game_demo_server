from __future__ import annotations

from typing import Optional

from app.agent.base import AIAssistantBase
from app.agent.chess_suggest_agent import _fen_side_to_move


class ChessOpponentAssistant(AIAssistantBase):
    """下棋对手助手：模拟对手一方给出应对走法。"""

    def suggest(self, board_fen: str, player_side: Optional[str] = None) -> dict[str, str]:
        """根据玩家方位推导对手方并返回对应默认走法。"""
        side = (player_side or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        opponent_side = "black" if side == "white" else "white"
        move = "e7e5" if opponent_side == "black" else "e2e4"
        return {"opponent_side": opponent_side, "move": move}
