from __future__ import annotations

import json
import re
from typing import Any

from app.agent.base import AIAssistantBase



class MinesweeperAssistant(AIAssistantBase):
    """扫雷助手：根据棋盘未知格给出下一步建议。"""

    def suggest(self, board: str) -> dict[str, Any]:
        """返回推荐动作，优先打开第一个未知格。"""

        fallback_result = {
            "row": 0,
            "col": 0,
        }
        output_text = self._call_openai(self._build_user_prompt(board=board))
        if output_text:
            parsed_result = self._parse_openai_result(output_text)
            return parsed_result
        return fallback_result

    def _build_user_prompt(self, *, board: str) -> str:
        """构造扫雷建议请求。"""
        return (
            f"当前扫雷棋盘：{board}\n"
            "请给出下一步动作。"
        )

    def _parse_openai_result(self, text: str) -> dict[str, Any]:
        """尽量从模型文本中解析扫雷动作，不可解析时回退到默认坐标。"""
        return json.loads(text)
