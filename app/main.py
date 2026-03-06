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
    def __init__(self) -> None:
        self._docs = {
            "minesweeper-1": "扫雷技巧：如果一个数字周围已标记雷数量等于该数字，其余未知格都是安全格。",
            "minesweeper-2": "扫雷技巧：如果一个数字周围未知格数量等于该数字减去已标记雷数量，未知格都是雷。",
            "chess-1": "国际象棋开局建议：白方常见第一步是e2e4或d2d4以控制中心。",
            "chess-2": "国际象棋建议：发展轻子并尽早王车易位，避免重复走同一枚子。",
        }
        self._collection = None
        if chromadb is not None:
            try:
                client = chromadb.PersistentClient(path=CHROMA_PATH)
                self._collection = client.get_or_create_collection("game_knowledge")
                if self._collection.count() == 0:
                    ids = list(self._docs.keys())
                    docs = [self._docs[i] for i in ids]
                    self._collection.add(ids=ids, documents=docs)
            except Exception:
                self._collection = None

    def search(self, query: str, n_results: int = 2) -> list[str]:
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
    player_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class DailyChatRequest(BaseModel):
    player_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MinesweeperRequest(BaseModel):
    board: list[list[Any]]


class ChessRequest(BaseModel):
    board_fen: str
    side_to_move: Optional[str] = "white"


class OpponentMoveRequest(BaseModel):
    board_fen: str
    player_side: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_db()
    yield


app = FastAPI(title="yuliao game demo server", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat/record")
def record_chat(payload: ChatRecordRequest) -> dict[str, str]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_history (player_id, text) VALUES (?, ?)",
            (payload.player_id, payload.text),
        )
        conn.commit()
    return {"status": "saved"}


@app.post("/chat/daily")
def daily_chat(payload: DailyChatRequest) -> dict[str, str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT text FROM chat_history WHERE player_id=? ORDER BY id DESC LIMIT 5",
            (payload.player_id,),
        ).fetchall()

    history = [r[0] for r in rows][::-1]
    return chat_assistant.reply(history, payload.message)


@app.post("/minesweeper/suggest")
def minesweeper_suggest(payload: MinesweeperRequest) -> dict[str, Any]:
    return minesweeper_assistant.suggest(payload.board)


@app.post("/chess/suggest")
def chess_suggest(payload: ChessRequest) -> dict[str, str]:
    return chess_assistant.suggest(payload.board_fen, payload.side_to_move)


@app.post("/chess/opponent-move")
def chess_opponent_move(payload: OpponentMoveRequest) -> dict[str, str]:
    return chess_opponent_assistant.suggest(payload.board_fen, payload.player_side)
