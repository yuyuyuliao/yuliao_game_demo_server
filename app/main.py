from __future__ import annotations

from contextlib import asynccontextmanager
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
from app.assistants import (
    ChatAssistant,
    ChessOpponentAssistant,
    ChessSuggestAssistant,
    MinesweeperAssistant,
)

from app.knowledge_parser import KnowledgeParser

try:
    import chromadb
except Exception:  # pragma: no cover - fallback when chromadb is unavailable
    chromadb = None


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"
CHROMA_PATH = str(DATA_DIR / "chroma")

def _init_db() -> None:
    """初始化聊天记录表。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


class KnowledgeStore:
    """知识检索封装：优先使用 Chroma，失败时回退到关键词匹配。"""

    def __init__(self) -> None:
        """加载知识文档并尝试初始化向量检索集合。"""
        self._docs = KnowledgeParser().load_documents()
        self._collection = None
        if chromadb is not None:
            try:
                client = chromadb.PersistentClient(path=CHROMA_PATH)
                self._collection = client.get_or_create_collection("game_knowledge")
                if self._collection.count() == 0 and self._docs:
                    ids = list(self._docs.keys())
                    docs = [self._docs[i] for i in ids]
                    self._collection.add(ids=ids, documents=docs)
            except Exception:
                self._collection = None

    def search(self, query: str, n_results: int = 2) -> list[str]:
        """根据查询语句返回最相关的知识文本。"""
        if self._collection is not None:
            try:
                result = self._collection.query(query_texts=[query], n_results=n_results)
                documents = result.get("documents", [[]])
                return documents[0] if documents else []
            except Exception:
                pass

        keywords = set(query.lower().split())
        ranked = sorted(
            self._docs.values(),
            key=lambda doc: sum(1 for k in keywords if k and k in doc.lower()),
            reverse=True,
        )
        return ranked[:n_results]


knowledge_store = KnowledgeStore()
chat_assistant = ChatAssistant(
    system_prompt="你是一个友好的聊天助手。",
    model_name="chat-model-v1",
    knowledge_search=knowledge_store.search,
)
minesweeper_assistant = MinesweeperAssistant(
    system_prompt="你是扫雷助手，请输出安全建议。",
    model_name="minesweeper-model-v1",
)
chess_assistant = ChessSuggestAssistant(
    system_prompt="你是下棋助手，请给出简洁开局建议。",
    model_name="chess-model-v1",
    knowledge_search=knowledge_store.search,
)
chess_opponent_assistant = ChessOpponentAssistant(
    system_prompt="你是下棋对手 AI，请根据局面给出对手走法。",
    model_name="chess-opponent-model-v1",
)


class ChatRecordRequest(BaseModel):
    """聊天记录写入请求体。"""

    player_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class DailyChatRequest(BaseModel):
    """日常聊天请求体，包含玩家ID和当前消息。"""

    player_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MinesweeperRequest(BaseModel):
    """扫雷建议请求体，board 为二维棋盘。"""

    board: list[list[Any]]


class ChessRequest(BaseModel):
    """国际象棋建议请求体。"""

    board_fen: str
    side_to_move: Optional[str] = "white"


class OpponentMoveRequest(BaseModel):
    """国际象棋对手落子请求体。"""

    board_fen: str
    player_side: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    _init_db()
    yield


app = FastAPI(title="yuliao game demo server", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查接口。"""
    return {"status": "ok"}


@app.post("/chat/record")
def record_chat(payload: ChatRecordRequest) -> dict[str, str]:
    """写入玩家聊天记录到 SQLite。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_history (player_id, text) VALUES (?, ?)",
            (payload.player_id, payload.text),
        )
        conn.commit()
    return {"status": "saved"}


@app.post("/chat/daily")
def daily_chat(payload: DailyChatRequest) -> dict[str, str]:
    """结合历史聊天与知识库返回日常回复。"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT text FROM chat_history WHERE player_id=? ORDER BY id DESC LIMIT 5",
            (payload.player_id,),
        ).fetchall()

    history = [r[0] for r in rows][::-1]
    memories = "；".join(history) if history else "我们还没有历史聊天记录。"
    tips = knowledge_store.search(payload.message, n_results=1)
    tip_text = tips[0] if tips else "保持轻松交流。"

    response = (
        f"我记得你最近说过：{memories}。"
        f"你刚才说：{payload.message}。"
        f"给你一个相关建议：{tip_text}"
    )
    return {"response": response}


def _unknown_cells(board: list[list[Any]]) -> list[tuple[int, int]]:
    """提取扫雷棋盘中的未知格坐标。"""
    unknown = []
    for r, row in enumerate(board):
        for c, value in enumerate(row):
            if value in MINESWEEPER_UNKNOWN_CELL_MARKERS:
                unknown.append((r, c))
    return unknown


@app.post("/minesweeper/suggest")
def minesweeper_suggest(payload: MinesweeperRequest) -> dict[str, Any]:
    """给出扫雷下一步建议。"""
    board = payload.board
    unknown = _unknown_cells(board)
    if not unknown:
        return {"action": "done", "reason": "no unknown cells"}
    row, col = unknown[0]
    return {
        "action": "open",
        "row": row,
        "col": col,
        "reason": "默认选择第一个未知格，可结合数字约束进一步推理",
    }


@app.post("/chess/suggest")
def chess_suggest(payload: ChessRequest) -> dict[str, str]:
    """给出国际象棋建议走法。"""
    side = (payload.side_to_move or "white").lower()
    move = "e2e4" if side == "white" else "e7e5"
    tips = knowledge_store.search("国际象棋 开局", n_results=1)
    return {"move": move, "reason": tips[0] if tips else "控制中心并发展子力"}


@app.post("/chess/opponent-move")
def chess_opponent_move(payload: OpponentMoveRequest) -> dict[str, str]:
    """模拟对手在当前局面下的下一步落子。"""
    side = payload.player_side.lower()
    opponent_side = "black" if side == "white" else "white"
    move = "e7e5" if opponent_side == "black" else "e2e4"
    return {"opponent_side": opponent_side, "move": move}
