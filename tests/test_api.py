import re
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.assistants import (
    AIAssistantBase,
    ChatAssistant,
    ChessOpponentAssistant,
    ChessSuggestAssistant,
    MinesweeperAssistant,
)
from app.main import DB_PATH, _init_db, app

_init_db()

client = TestClient(app)
UCI_MOVE_LENGTH = 4
UCI_MOVE_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8]$")


def _upsert_player(account: str, name: str, gold: int = 0, level: int = 1) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO players (name, account, password, gold, level)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account) DO UPDATE SET
                name=excluded.name,
                gold=excluded.gold,
                level=excluded.level
            """,
            (name, account, "hashed-password", gold, level),
        )
        conn.commit()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_record_and_daily_chat():
    record = client.post(
        "/chat/record",
        json={"player_id": "player-1", "conversation_id": "conv-1", "role": "user", "text": "我喜欢下棋"},
    )
    assert record.status_code == 200
    assert record.json()["status"] == "saved"

    daily = client.post(
        "/chat/daily",
        json={"player_id": "player-1", "conversation_id": "conv-1", "message": "给我一个建议"},
    )
    assert daily.status_code == 200
    response = daily.json()["response"]
    assert response
    assert "我记得你最近说过" not in response
    assert "给你一个相关建议" not in response




def test_list_chat_messages_in_order():
    client.post(
        "/chat/record",
        json={"player_id": "player-order", "conversation_id": "conv-order", "role": "user", "text": "第一条"},
    )
    client.post(
        "/chat/record",
        json={"player_id": "player-order", "conversation_id": "conv-order", "role": "assistant", "text": "第二条"},
    )

    response = client.post(
        "/chat/messages",
        json={"player_id": "player-order", "conversation_id": "conv-order"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conv-order"
    assert [item["text"] for item in body["messages"]][-2:] == ["第一条", "第二条"]
    assert body["messages"][-2]["message_order"] < body["messages"][-1]["message_order"]
def test_chat_assistant_calls_openai_client():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="这是来自 OpenAI 的回复")

    assistant = ChatAssistant(
        system_prompt="你是测试助手",
        model_name="gpt-4o-mini",
        knowledge_search=lambda message, n_results=1: [f"知识：{message}"],
        openai_client=SimpleNamespace(responses=FakeResponses()),
    )

    result = assistant.reply(["之前聊过种地"], "给我一个建议")

    assert result == {"response": "这是来自 OpenAI 的回复"}
    assert captured["model"] == "gpt-4o-mini"
    assert captured["instructions"] == "你是测试助手"
    assert "之前聊过种地" in captured["input"]
    assert "给我一个建议" in captured["input"]
    assert "知识：给我一个建议" in captured["input"]


def test_chat_assistant_falls_back_when_openai_call_fails():
    class FakeResponses:
        def create(self, **kwargs):
            raise RuntimeError("network error")

    assistant = ChatAssistant(
        knowledge_search=lambda message, n_results=1: ["先深呼吸再继续"],
        openai_client=SimpleNamespace(responses=FakeResponses()),
    )

    result = assistant.reply(["我今天有点紧张"], "怎么放松")

    assert result["response"] == "先深呼吸再继续"


def test_chat_assistant_fallback_returns_memory_directly_without_fixed_phrase():
    assistant = ChatAssistant(openai_client=None)

    result = assistant.reply(
        ["玩家：请告诉我我的玩家信息", "助手：玩家信息：昵称阿苗，等级 8"],
        "你还记得我刚才问了什么吗",
    )

    assert "玩家信息" in result["response"]
    assert "我记得你最近说过" not in result["response"]


def test_non_chat_assistants_can_call_openai_client():
    captured = []

    class FakeResponses:
        def create(self, **kwargs):
            captured.append(kwargs)
            prompt = kwargs["input"]
            if "当前扫雷棋盘" in prompt:
                return SimpleNamespace(output_text="open 1 2")
            if "对手方" in prompt:
                return SimpleNamespace(output_text="建议走 e7e5")
            return SimpleNamespace(output_text="建议走 e2e4，优先控制中心")

    fake_client = SimpleNamespace(responses=FakeResponses())

    minesweeper = MinesweeperAssistant(openai_client=fake_client)
    chess = ChessSuggestAssistant(openai_client=fake_client)
    opponent = ChessOpponentAssistant(openai_client=fake_client)

    ms_result = minesweeper.suggest([[0, "?", 1], [1, "X", 1], [0, 1, 0]])
    chess_result = chess.suggest("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w", side_to_move="white")
    opponent_result = opponent.suggest(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",
        player_side="white",
    )

    assert ms_result == {"action": "open", "row": 1, "col": 2, "reason": "open 1 2"}
    assert chess_result == {"move": "e2e4", "reason": "建议走 e2e4，优先控制中心"}
    assert opponent_result == {"opponent_side": "black", "move": "e7e5"}
    assert len(captured) == 3
    assert all(item["model"] == "demo-model" for item in captured)


def test_non_chat_assistants_fall_back_when_openai_call_fails():
    class FakeResponses:
        def create(self, **kwargs):
            raise RuntimeError("network error")

    fake_client = SimpleNamespace(responses=FakeResponses())

    minesweeper = MinesweeperAssistant(openai_client=fake_client)
    chess = ChessSuggestAssistant(openai_client=fake_client)
    opponent = ChessOpponentAssistant(openai_client=fake_client)

    ms_result = minesweeper.suggest([[0, "?", 1], [1, "X", 1], [0, 1, 0]])
    chess_result = chess.suggest("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b", side_to_move="black")
    opponent_result = opponent.suggest(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",
        player_side="white",
    )

    assert ms_result["action"] == "open"
    assert ms_result["row"] == 0
    assert ms_result["col"] == 1
    assert chess_result == {"move": "e7e5", "reason": "控制中心并发展子力"}
    assert opponent_result == {"opponent_side": "black", "move": "e7e5"}


def test_game_suggestion_endpoints():
    ms = client.post(
        "/minesweeper/suggest",
        json={"board": [[0, "?", 1], [1, "X", 1], [0, 1, 0]]},
    )
    assert ms.status_code == 200
    assert ms.json()["action"] in {"open", "done"}

    chess = client.post(
        "/chess/suggest",
        json={
            "board_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",
            "side_to_move": "white",
        },
    )
    assert chess.status_code == 200
    assert "move" in chess.json()

    opponent = client.post(
        "/chess/opponent-move",
        json={
            "board_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w",
            "player_side": "white",
        },
    )
    assert opponent.status_code == 200
    body = opponent.json()
    assert body["opponent_side"] in {"white", "black"}
    assert len(body["move"]) == UCI_MOVE_LENGTH
    assert UCI_MOVE_PATTERN.match(body["move"])


def test_player_info_endpoint():
    _upsert_player("player-game-info", "资料玩家", gold=345, level=9)
    with sqlite3.connect(DB_PATH) as conn:
        expected_player_id = conn.execute(
            "SELECT id FROM players WHERE account=?",
            ("player-game-info",),
        ).fetchone()[0]

    response = client.get("/player/info/player-game-info")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "player": {
            "id": expected_player_id,
            "name": "资料玩家",
            "account": "player-game-info",
            "gold": 345,
            "level": 9,
        },
    }


def test_player_info_endpoint_rejects_unknown_player():
    response = client.get("/player/info/missing-player")

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "reason": "player not found: missing-player",
    }


def test_minesweeper_win_endpoint():
    _upsert_player("player-game-reward", "奖励玩家", gold=100)
    with sqlite3.connect(DB_PATH) as conn:
        expected_player_id = conn.execute(
            "SELECT id FROM players WHERE account=?",
            ("player-game-reward",),
        ).fetchone()[0]

    response = client.post(
        "/minesweeper/win",
        json={"player_id": "player-game-reward"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["added_gold"] == 10
    assert body["gold"] == 110
    assert body["player_id"] == str(expected_player_id)
    with sqlite3.connect(DB_PATH) as conn:
        saved_gold = conn.execute(
            "SELECT gold FROM players WHERE account=?",
            ("player-game-reward",),
        ).fetchone()[0]
    assert saved_gold == 110


def test_minesweeper_win_rejects_unknown_player():
    response = client.post(
        "/minesweeper/win",
        json={"player_id": "missing-player"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "reason": "player not found: missing-player",
    }


def test_assistants_are_independent_classes_with_config():
    chat = ChatAssistant(system_prompt="chat prompt", model_name="chat-model")
    minesweeper = MinesweeperAssistant(system_prompt="ms prompt", model_name="ms-model")
    chess = ChessSuggestAssistant(system_prompt="chess prompt", model_name="chess-model")
    opponent = ChessOpponentAssistant(system_prompt="op prompt", model_name="op-model")

    expected_configs = {
        chat: {"system_prompt": "chat prompt", "model_name": "chat-model"},
        minesweeper: {"system_prompt": "ms prompt", "model_name": "ms-model"},
        chess: {"system_prompt": "chess prompt", "model_name": "chess-model"},
        opponent: {"system_prompt": "op prompt", "model_name": "op-model"},
    }

    for assistant, expected in expected_configs.items():
        assert isinstance(assistant, AIAssistantBase)
        assert assistant.agent_config() == expected


def test_chess_assistants_can_fallback_to_fen_side():
    chess = ChessSuggestAssistant()
    fen_black = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
    suggest = chess.suggest(fen_black, side_to_move="")
    assert suggest["move"] == "e7e5"
    explicit = chess.suggest(fen_black, side_to_move="white")
    assert explicit["move"] == "e2e4"

    opponent = ChessOpponentAssistant()
    move = opponent.suggest(fen_black, player_side="")
    assert move["opponent_side"] == "white"
