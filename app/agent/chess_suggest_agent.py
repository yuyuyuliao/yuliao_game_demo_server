from __future__ import annotations

from typing import Any, Callable, Optional

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

    def suggest(self, board_fen: str, side_to_move: Optional[str] = None) -> dict[str, str]:
        """根据走子方给出开局建议，并补充简短原因。"""
        side = (side_to_move or "").lower()
        if side not in {"white", "black"}:
            side = _fen_side_to_move(board_fen) or "white"
        move = "e2e4" if side == "white" else "e7e5"
        tips = []
        if self._knowledge_search is not None:
            tips = self._knowledge_search("国际象棋 开局", n_results=1)
        fallback_reason = tips[0] if tips else "控制中心并发展子力"
        output_text = self._call_openai(
            self._build_user_prompt(
                board_fen=board_fen,
                side=side,
                move=move,
                reason=fallback_reason,
            )
        )
        if output_text:
            return {
                "move": self._extract_uci_move(output_text) or move,
                "reason": output_text,
            }
        return {"move": move, "reason": fallback_reason}

    def _build_user_prompt(self, *, board_fen: str, side: str, move: str, reason: str) -> str:
        """构造象棋建议请求，让模型在兜底走法基础上生成更自然的建议。"""
        return (
            f"当前棋盘 FEN：{board_fen}\n"
            f"当前走子方：{side}\n"
            f"本地兜底建议走法：{move}\n"
            f"本地兜底理由：{reason}\n"
            "请输出一步适合当前走子方的 UCI 走法，并用中文简短说明理由。"
        )
