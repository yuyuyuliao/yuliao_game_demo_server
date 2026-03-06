import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
UCI_MOVE_LENGTH = 4
UCI_MOVE_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8]$")


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_record_and_daily_chat():
    record = client.post(
        "/chat/record",
        json={"player_id": "player-1", "text": "我喜欢下棋"},
    )
    assert record.status_code == 200
    assert record.json()["status"] == "saved"

    daily = client.post(
        "/chat/daily",
        json={"player_id": "player-1", "message": "给我一个建议"},
    )
    assert daily.status_code == 200
    response = daily.json()["response"]
    assert "我记得你最近说过" in response
    assert "给你一个相关建议" in response


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
