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
        output_text = self._call_openai(
            self._build_user_prompt(
                board_fen=board_fen,
                player_side=side,
                opponent_side=opponent_side,
                move=move,
            )
        )
        if output_text:
            return {
                "opponent_side": opponent_side,
                "move": self._extract_uci_move(output_text) or move,
            }
        return {"opponent_side": opponent_side, "move": move}

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
