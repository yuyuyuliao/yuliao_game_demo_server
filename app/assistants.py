from __future__ import annotations

from abc import ABC
from typing import Any, Callable, Optional

MINESWEEPER_UNKNOWN_CELL_MARKERS = {"?", "X", "x", -1, "U", "u"}


def _fen_side_to_move(board_fen: str) -> Optional[str]:
    fields = board_fen.split()
    if len(fields) >= 2 and fields[1] in {"w", "b"}:
        return "white" if fields[1] == "w" else "black"
    return None


class AIAssistantBase(ABC):
    def __init__(self, *, system_prompt: str = "", model_name: str = "demo-model") -> None:
        self.system_prompt = system_prompt
        self.model_name = model_name

    def agent_config(self) -> dict[str, str]:
        return {"system_prompt": self.system_prompt, "model_name": self.model_name}


class ChatAssistant(AIAssistantBase):
    def __init__(
        self,
        *,
        system_prompt: str = "",
        model_name: str = "demo-model",
        knowledge_search: Optional[Callable[..., list[str]]] = None,
    ) -> None:
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self._knowledge_search = knowledge_search

    def reply(self, history: list[str], message: str) -> dict[str, str]:
        memories = "；".join(history) if history else "我们还没有历史聊天记录。"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search(message, n_results=1)
        tip_text = tips[0] if tips else "保持轻松交流。"
        response = (
            f"我记得你最近说过：{memories}。"
            f"你刚才说：{message}。"
            f"给你一个相关建议：{tip_text}"
        )
        return {"response": response}


class MinesweeperAssistant(AIAssistantBase):
    def suggest(self, board: list[list[Any]]) -> dict[str, Any]:
        unknown = []
        for r, row in enumerate(board):
            for c, value in enumerate(row):
                if value in MINESWEEPER_UNKNOWN_CELL_MARKERS:
                    unknown.append((r, c))

        if not unknown:
            return {"action": "done", "reason": "no unknown cells"}

        row, col = unknown[0]
        return {
            "action": "open",
            "row": row,
            "col": col,
            "reason": "默认选择第一个未知格，可结合数字约束进一步推理",
        }


class ChessSuggestAssistant(AIAssistantBase):
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
        side = (side_to_move or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        move = "e2e4" if side == "white" else "e7e5"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search("国际象棋 开局", n_results=1)
        return {"move": move, "reason": tips[0] if tips else "控制中心并发展子力"}


class ChessOpponentAssistant(AIAssistantBase):
    def suggest(self, board_fen: str, player_side: Optional[str] = None) -> dict[str, str]:
        side = (player_side or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        opponent_side = "black" if side == "white" else "white"
        move = "e7e5" if opponent_side == "black" else "e2e4"
        return {"opponent_side": opponent_side, "move": move}
