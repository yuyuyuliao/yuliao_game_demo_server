from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
from app.assistants import (
    ChatAssistant,
    ChessOpponentAssistant,
    ChessSuggestAssistant,
    MINESWEEPER_UNKNOWN_CELL_MARKERS,
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
FARM_DEFAULT_WATER = 100.0
FARM_DEFAULT_FERTILITY = 100.0
FARM_DEFAULT_TEMPERATURE = 22.0
WATER_DECAY_PER_HOUR = 3.0
FERTILITY_DECAY_PER_HOUR = 1.5
LOW_WATER_THRESHOLD = 30.0
LOW_FERTILITY_THRESHOLD = 30.0
MIN_GROWTH_TEMPERATURE = 10.0
MAX_GROWTH_TEMPERATURE = 35.0
LOW_RESOURCE_GROWTH_FACTOR = 0.5
TEMPERATURE_GROWTH_FACTOR = 0.8
TEMPERATURE_CHANGE_PER_HOUR = 0.2
TEMPERATURE_MIN = -10.0
TEMPERATURE_MAX = 45.0
STAGE_HALF_RATIO = 0.5
STAGE_MATURE_RATIO = 1.0
STAGE_WITHER_RATIO = 1.5
MATURE_STAGE = "完全成熟"


def _init_db() -> None:
    """初始化聊天和种地系统所需表。"""
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS land_plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price INTEGER NOT NULL,
                description TEXT NOT NULL,
                level INTEGER NOT NULL,
                growth_multiplier REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                growth_seconds INTEGER NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crop_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                land_id INTEGER NOT NULL UNIQUE,
                crop_id INTEGER NOT NULL,
                planted_at DATETIME NOT NULL,
                last_state_update_at DATETIME NOT NULL,
                water REAL NOT NULL,
                fertility REAL NOT NULL,
                temperature REAL NOT NULL,
                FOREIGN KEY (land_id) REFERENCES land_plots(id),
                FOREIGN KEY (crop_id) REFERENCES crops(id)
            )
            """
        )
        land_count = conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0]
        if land_count == 0:
            conn.executemany(
                """
                INSERT INTO land_plots (price, description, level, growth_multiplier)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (100, "1号地：靠近小溪，土壤松软。", 1, 1.00),
                    (180, "2号地：有石板路，适合新手。", 1, 1.00),
                    (300, "3号地：老农留下的试验田。", 2, 1.10),
                    (480, "4号地：向阳高地，温度更稳定。", 2, 1.10),
                    (720, "5号地：微风谷地，生长速度更快。", 3, 1.20),
                    (1020, "6号地：传说中的金色土壤。", 4, 1.30),
                ],
            )
        crop_count = conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0]
        if crop_count == 0:
            conn.executemany(
                """
                INSERT INTO crops (name, growth_seconds, price, description)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("胡萝卜", 3600, 30, "成长稳定，适合练手。"),
                    ("玉米", 7200, 60, "成熟后收益更高。"),
                    ("草莓", 5400, 80, "甜度高但对水量要求更高。"),
                ],
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


class PlantRequest(BaseModel):
    """种植请求体。"""

    land_id: int = Field(gt=0)
    crop_id: int = Field(gt=0)


class HarvestRequest(BaseModel):
    """采集请求体。"""

    land_id: int = Field(gt=0)


def _parse_dt(value: str) -> datetime:
    """将数据库 DATETIME 字符串转换为 datetime。"""
    return datetime.fromisoformat(value)


def _apply_land_decay(conn: sqlite3.Connection, instance_row: sqlite3.Row) -> sqlite3.Row:
    """根据时间推进土地状态衰减与温度变化。"""
    now = datetime.now()
    last_update = _parse_dt(instance_row["last_state_update_at"])
    elapsed_hours = max(0.0, (now - last_update).total_seconds() / 3600)
    if elapsed_hours <= 0:
        return instance_row

    water = max(0.0, instance_row["water"] - elapsed_hours * WATER_DECAY_PER_HOUR)
    fertility = max(0.0, instance_row["fertility"] - elapsed_hours * FERTILITY_DECAY_PER_HOUR)
    # 温度按小时平滑变化，并限制在可接受区间内避免出现极端值。
    temperature = min(
        TEMPERATURE_MAX,
        max(TEMPERATURE_MIN, instance_row["temperature"] + elapsed_hours * TEMPERATURE_CHANGE_PER_HOUR),
    )

    conn.execute(
        """
        UPDATE crop_instances
        SET water=?, fertility=?, temperature=?, last_state_update_at=?
        WHERE id=?
        """,
        (water, fertility, temperature, now.isoformat(sep=" "), instance_row["id"]),
    )
    conn.commit()
    return conn.execute(
        """
        SELECT ci.id, ci.land_id, ci.crop_id, ci.planted_at, ci.last_state_update_at,
               ci.water, ci.fertility, ci.temperature, c.name AS crop_name, c.growth_seconds,
               c.price AS crop_price, c.description AS crop_description,
               lp.level AS land_level, lp.growth_multiplier AS growth_multiplier
        FROM crop_instances ci
        JOIN crops c ON c.id = ci.crop_id
        JOIN land_plots lp ON lp.id = ci.land_id
        WHERE ci.id = ?
        """,
        (instance_row["id"],),
    ).fetchone()


def _read_crop_instance(conn: sqlite3.Connection, land_id: int) -> Optional[sqlite3.Row]:
    """读取土地上的当前作物实例。"""
    return conn.execute(
        """
        SELECT ci.id, ci.land_id, ci.crop_id, ci.planted_at, ci.last_state_update_at,
               ci.water, ci.fertility, ci.temperature, c.name AS crop_name, c.growth_seconds,
               c.price AS crop_price, c.description AS crop_description,
               lp.level AS land_level, lp.growth_multiplier AS growth_multiplier
        FROM crop_instances ci
        JOIN crops c ON c.id = ci.crop_id
        JOIN land_plots lp ON lp.id = ci.land_id
        WHERE ci.land_id = ?
        """,
        (land_id,),
    ).fetchone()


def _calc_growth_stage(instance_row: sqlite3.Row) -> tuple[str, float]:
    """计算作物当前生长阶段及有效生长秒数。"""
    planted_at = _parse_dt(instance_row["planted_at"])
    elapsed_seconds = max(0.0, (datetime.now() - planted_at).total_seconds())
    growth_speed = instance_row["growth_multiplier"]
    if instance_row["water"] < LOW_WATER_THRESHOLD or instance_row["fertility"] < LOW_FERTILITY_THRESHOLD:
        growth_speed *= LOW_RESOURCE_GROWTH_FACTOR
    if (
        instance_row["temperature"] < MIN_GROWTH_TEMPERATURE
        or instance_row["temperature"] > MAX_GROWTH_TEMPERATURE
    ):
        growth_speed *= TEMPERATURE_GROWTH_FACTOR
    effective_seconds = elapsed_seconds * growth_speed
    growth_seconds = instance_row["growth_seconds"]
    if effective_seconds < growth_seconds * STAGE_HALF_RATIO:
        return "刚种下", effective_seconds
    if effective_seconds < growth_seconds * STAGE_MATURE_RATIO:
        return "长到一半", effective_seconds
    if effective_seconds < growth_seconds * STAGE_WITHER_RATIO:
        return MATURE_STAGE, effective_seconds
    return "枯萎", effective_seconds


def _build_farming_status(instance_row: sqlite3.Row) -> dict[str, Any]:
    """构建作物状态响应。"""
    stage, effective_seconds = _calc_growth_stage(instance_row)
    return {
        "land_id": instance_row["land_id"],
        "crop_id": instance_row["crop_id"],
        "crop_name": instance_row["crop_name"],
        "crop_description": instance_row["crop_description"],
        "growth_stage": stage,
        "growth_effective_seconds": round(effective_seconds, 2),
        "growth_total_seconds": instance_row["growth_seconds"],
        "land_level": instance_row["land_level"],
        "growth_multiplier": instance_row["growth_multiplier"],
        "water": round(instance_row["water"], 2),
        "fertility": round(instance_row["fertility"], 2),
        "temperature": round(instance_row["temperature"], 2),
        "can_harvest": stage == MATURE_STAGE,
    }


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


@app.get("/farm/lands")
def list_lands() -> dict[str, list[dict[str, Any]]]:
    """查询全部土地基础信息。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        lands = conn.execute(
            """
            SELECT id, price, description, level, growth_multiplier
            FROM land_plots
            ORDER BY id ASC
            """
        ).fetchall()
    return {"lands": [dict(land) for land in lands]}


@app.post("/farm/plant")
def plant_crop(payload: PlantRequest) -> dict[str, Any]:
    """在指定土地上种植作物。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        land = conn.execute("SELECT id FROM land_plots WHERE id=?", (payload.land_id,)).fetchone()
        if land is None:
            return {"status": "failed", "reason": "land not found"}
        crop = conn.execute(
            "SELECT id, name, growth_seconds FROM crops WHERE id=?",
            (payload.crop_id,),
        ).fetchone()
        if crop is None:
            return {"status": "failed", "reason": "crop not found"}
        active = _read_crop_instance(conn, payload.land_id)
        if active is not None:
            return {"status": "failed", "reason": "land already planted"}

        now_str = datetime.now().isoformat(sep=" ")
        conn.execute(
            """
            INSERT INTO crop_instances (
                land_id, crop_id, planted_at, last_state_update_at, water, fertility, temperature
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.land_id,
                payload.crop_id,
                now_str,
                now_str,
                FARM_DEFAULT_WATER,
                FARM_DEFAULT_FERTILITY,
                FARM_DEFAULT_TEMPERATURE,
            ),
        )
        conn.commit()
        instance = _read_crop_instance(conn, payload.land_id)
    return {"status": "planted", "crop_name": crop["name"], "land_id": payload.land_id, "state": _build_farming_status(instance)}


@app.get("/farm/status/{land_id}")
def query_crop_status(land_id: int) -> dict[str, Any]:
    """查询指定土地的作物状态。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        instance = _read_crop_instance(conn, land_id)
        if instance is None:
            return {"status": "empty", "land_id": land_id}
        refreshed = _apply_land_decay(conn, instance)
    return {"status": "growing", "state": _build_farming_status(refreshed)}


@app.post("/farm/harvest")
def harvest_crop(payload: HarvestRequest) -> dict[str, Any]:
    """采集成熟作物。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        instance = _read_crop_instance(conn, payload.land_id)
        if instance is None:
            return {"status": "failed", "reason": "no crop"}
        refreshed = _apply_land_decay(conn, instance)
        stage, _ = _calc_growth_stage(refreshed)
        if stage != MATURE_STAGE:
            return {"status": "failed", "reason": f"crop not ready: {stage}"}
        conn.execute("DELETE FROM crop_instances WHERE id=?", (refreshed["id"],))
        conn.commit()
        return {
            "status": "harvested",
            "land_id": payload.land_id,
            "crop_name": refreshed["crop_name"],
            "income": refreshed["crop_price"],
        }
