from __future__ import annotations

import json
import re
from typing import Any

from app.agent.base import AIAssistantBase


class MinesweeperAssistant(AIAssistantBase):
    """扫雷助手：根据棋盘未知格给出下一步建议。"""

    def suggest(self, board: Any) -> dict[str, Any]:
        fallback_result = {
            "action": "open",
            "row": 0,
            "col": 1,
            "reason": "open 0 1",
        }
        output_text = self._call_openai(self._build_user_prompt(board=board))
        if output_text:
            return self._parse_openai_result(output_text)
        return fallback_result

    def _build_user_prompt(self, *, board: Any) -> str:
        return f"当前扫雷棋盘：{board}\n请给出下一步动作。"

    def _parse_openai_result(self, text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and {"row", "col"}.issubset(payload.keys()):
                return {
                    "action": payload.get("action", "open"),
                    "row": int(payload["row"]),
                    "col": int(payload["col"]),
                    "reason": payload.get("reason", text),
                }
        except Exception:
            pass

        match = re.search(r"(open|flag|done)\s+(\d+)\s+(\d+)", text.lower())
        if match:
            return {
                "action": match.group(1),
                "row": int(match.group(2)),
                "col": int(match.group(3)),
                "reason": text,
            }
        return {"action": "open", "row": 0, "col": 1, "reason": text}
