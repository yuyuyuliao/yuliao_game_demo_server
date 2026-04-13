from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import chat_api, farm_api, game_api
from app.main import _init_db, app

_init_db()

client = TestClient(app)


def test_game_api_endpoints_delegate_to_matching_command_run(monkeypatch):
    monkeypatch.setattr(
        game_api.minesweeper_suggest_command,
        "run",
        lambda board: {"command": "minesweeper_suggest", "board": board},
    )
    monkeypatch.setattr(
        game_api.chess_suggest_command,
        "run",
        lambda board_fen, side_to_move=None: {
            "command": "chess_suggest",
            "board_fen": board_fen,
            "side_to_move": side_to_move,
        },
    )
    monkeypatch.setattr(
        game_api.chess_opponent_move_command,
        "run",
        lambda board_fen, player_side: {
            "command": "chess_opponent_move",
            "board_fen": board_fen,
            "player_side": player_side,
        },
    )

    async def fake_minesweeper_win(player_id: str):
        return {"command": "minesweeper_win", "player_id": player_id}

    monkeypatch.setattr(game_api.minesweeper_win_command, "run", fake_minesweeper_win)

    assert client.post("/minesweeper/suggest", json={"board": "demo-board"}).json() == {
        "command": "minesweeper_suggest",
        "board": "demo-board",
    }
    assert client.post(
        "/chess/suggest",
        json={"board_fen": "demo-fen", "side_to_move": "white"},
    ).json() == {
        "command": "chess_suggest",
        "board_fen": "demo-fen",
        "side_to_move": "white",
    }
    assert client.post(
        "/chess/opponent-move",
        json={"board_fen": "demo-opponent-fen", "player_side": "black"},
    ).json() == {
        "command": "chess_opponent_move",
        "board_fen": "demo-opponent-fen",
        "player_side": "black",
    }
    assert client.post("/minesweeper/win", json={"player_id": "player-99"}).json() == {
        "command": "minesweeper_win",
        "player_id": "player-99",
    }


def test_chat_api_endpoints_delegate_to_matching_command_run(monkeypatch):
    async def fake_record_chat(player_id: str, text: str):
        return {"command": "record_chat", "player_id": player_id, "text": text}

    async def fake_daily_chat(player_id: str, message: str):
        return {"command": "daily_chat", "player_id": player_id, "message": message}

    monkeypatch.setattr(chat_api.record_chat_command, "run", fake_record_chat)
    monkeypatch.setattr(chat_api.daily_chat_command, "run", fake_daily_chat)

    assert client.post("/chat/record", json={"player_id": "p-1", "text": "hello"}).json() == {
        "command": "record_chat",
        "player_id": "p-1",
        "text": "hello",
    }
    assert client.post("/chat/daily", json={"player_id": "p-2", "message": "hi"}).json() == {
        "command": "daily_chat",
        "player_id": "p-2",
        "message": "hi",
    }


def test_farm_api_endpoints_delegate_to_matching_command_run(monkeypatch):
    async def fake_list_crops():
        return {"crops": [{"id": 66, "name": "delegated-crop"}]}

    async def fake_list_lands():
        return {"lands": [{"id": 99, "name": "delegated-land"}]}

    async def fake_plant_crop(land_id: int, crop_id: int):
        return {"command": "plant_crop", "land_id": land_id, "crop_id": crop_id}

    async def fake_query_crop_status(land_id: int):
        return {"command": "query_crop_status", "land_id": land_id}

    async def fake_harvest_crop(land_id: int):
        return {"command": "harvest_crop", "land_id": land_id}

    monkeypatch.setattr(farm_api.list_crops_command, "run", fake_list_crops)
    monkeypatch.setattr(farm_api.list_lands_command, "run", fake_list_lands)
    monkeypatch.setattr(farm_api.plant_crop_command, "run", fake_plant_crop)
    monkeypatch.setattr(farm_api.query_crop_status_command, "run", fake_query_crop_status)
    monkeypatch.setattr(farm_api.harvest_crop_command, "run", fake_harvest_crop)

    assert client.get("/farm/crops").json() == {"crops": [{"id": 66, "name": "delegated-crop"}]}
    assert client.get("/farm/lands").json() == {"lands": [{"id": 99, "name": "delegated-land"}]}
    assert client.post("/farm/plant", json={"land_id": 2, "crop_id": 3}).json() == {
        "command": "plant_crop",
        "land_id": 2,
        "crop_id": 3,
    }
    assert client.get("/farm/status/4").json() == {
        "command": "query_crop_status",
        "land_id": 4,
    }
    assert client.post("/farm/harvest", json={"land_id": 5}).json() == {
        "command": "harvest_crop",
        "land_id": 5,
    }
