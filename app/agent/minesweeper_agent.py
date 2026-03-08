from __future__ import annotations

import re
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
        fallback_result = {
            "action": "open",
            "row": row,
            "col": col,
            "reason": "默认选择第一个未知格，可结合数字约束进一步推理",
        }
        output_text = self._call_openai(self._build_user_prompt(board=board, fallback=fallback_result))
        if output_text:
            parsed_result = self._parse_openai_result(output_text, row=row, col=col)
            parsed_result["reason"] = output_text
            return parsed_result
        return fallback_result

    def _build_user_prompt(self, *, board: list[list[Any]], fallback: dict[str, Any]) -> str:
        """构造扫雷建议请求。"""
        return (
            f"当前扫雷棋盘：{board}\n"
            f"本地兜底动作：{fallback['action']}\n"
            f"本地兜底坐标：({fallback['row']}, {fallback['col']})\n"
            "请给出下一步动作。优先输出 open/flag/done，并在需要时给出 row col。"
        )

    def _parse_openai_result(self, text: str, *, row: int, col: int) -> dict[str, Any]:
        """尽量从模型文本中解析扫雷动作，不可解析时回退到默认坐标。"""
        lowered = text.lower()
        action = "flag" if "flag" in lowered else "done" if "done" in lowered else "open"
        if action == "done":
            return {"action": "done"}
        numbers = [int(value) for value in re.findall(r"-?\d+", text)]
        if len(numbers) >= 2:
            row, col = numbers[0], numbers[1]
        return {"action": action, "row": row, "col": col}
