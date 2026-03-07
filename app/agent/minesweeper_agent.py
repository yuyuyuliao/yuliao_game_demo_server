from __future__ import annotations

from typing import Any

from app.agent.base import AIAssistantBase

MINESWEEPER_UNKNOWN_CELL_MARKERS = {"?", "X", "x", -1, "U", "u"}


class MinesweeperAssistant(AIAssistantBase):
    """扫雷助手：根据棋盘未知格给出下一步建议。"""

    def suggest(self, board: list[list[Any]]) -> dict[str, Any]:
        """返回推荐动作，优先打开第一个未知格。"""
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
