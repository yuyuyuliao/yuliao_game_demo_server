from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent import ChatAssistant
from app.command.chat_tools import read_player_farm_info, read_player_info
from app.main import DB_PATH, _init_db, app

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "20260307_seed_farm_data.py"

client = TestClient(app)


def _seed_farm_defaults() -> None:
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db-path", str(DB_PATH)],
        check=True,
        cwd=REPO_ROOT,
    )


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
        conn.execute("DELETE FROM chat_history WHERE player_id=?", (account,))
        conn.commit()


def _plant_crop(land_id: int, crop_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM crop_instances WHERE land_id=?", (land_id,))
        conn.execute(
            """
            INSERT INTO crop_instances
                (land_id, crop_id, planted_at, last_state_update_at, water, fertility, temperature)
            VALUES
                (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 88.0, 76.0, 21.5)
            """,
            (land_id, crop_id),
        )
        conn.commit()


def setup_module() -> None:
    _init_db()
    _seed_farm_defaults()


def test_chat_tools_can_read_player_and_farm_info():
    _upsert_player("player-tool", "阿苗", gold=520, level=8)
    _plant_crop(1, 1)

    player_info = read_player_info("player-tool")
    farm_info = read_player_farm_info("player-tool")

    assert "阿苗" in player_info
    assert "等级：8" in player_info
    assert "金币：520" in player_info
    assert "阿苗当前可查看" in farm_info
    assert "胡萝卜" in farm_info


def test_chat_agent_uses_model_judgement_to_select_tools():
    assistant = ChatAssistant()
    captured_prompts: list[str] = []

    def fake_call_openai(prompt: str) -> str:
        captured_prompts.append(prompt)
        return '{"player_info": true, "farm_info": true, "game_guide": true}'

    assistant._call_openai = fake_call_openai

    result = assistant._decide_tools(
        {
            "message": "我想看看现在账号发展得怎么样，顺便讲讲地里长势，再给点新手入门方向。",
            "memories": "上轮我们提过胡萝卜和仓库。",
        }
    )

    assert result["requested_tools"] == ["player_info", "farm_info", "game_guide"]
    assert captured_prompts
    assert "上轮我们提过胡萝卜和仓库" in captured_prompts[0]
    assert "新手入门方向" in captured_prompts[0]


def test_chat_agent_falls_back_when_tool_judgement_model_unavailable():
    assistant = ChatAssistant()
    assistant._call_openai = lambda prompt: None

    result = assistant._decide_tools(
        {
            "message": "请告诉我我的玩家信息、田地情况，再给我一点胡萝卜攻略。",
            "memories": "我们还没有历史聊天记录。",
        }
    )

    assert result["requested_tools"] == ["player_info", "farm_info", "game_guide"]


def test_daily_chat_can_use_tools_and_remember_previous_talk():
    _upsert_player("player-memory", "小农", gold=300, level=5)
    _plant_crop(2, 1)

    first = client.post(
        "/chat/daily",
        json={"player_id": "player-memory", "message": "请告诉我我的玩家信息、田地情况，再给我一点胡萝卜攻略"},
    )
    assert first.status_code == 200
    first_text = first.json()["response"]
    assert "玩家信息：" in first_text
    assert "田地信息：" in first_text
    assert "游戏攻略：" in first_text
    assert "胡萝卜" in first_text

    second = client.post(
        "/chat/daily",
        json={"player_id": "player-memory", "message": "你还记得我刚才问了什么吗"},
    )
    assert second.status_code == 200
    second_text = second.json()["response"]
    assert "玩家信息" in second_text
    assert "田地" in second_text
