from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent import ChatAssistant
from app.agent.chat_agent import DEFAULT_EMPTY_MEMORIES
from app.command import chat_command
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


def _plant_crop(index: int, crop_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM crop_instances WHERE "index"=?', (index,))
        conn.execute(
            """
            INSERT INTO crop_instances
                ("index", crop_id, planted_at, last_state_update_at, water, fertility, temperature)
            VALUES
                (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 88.0, 76.0, 21.5)
            """,
            (index, crop_id),
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
    assert "等级：" in player_info
    assert "金币：520" in player_info
    assert "阿苗当前可查看" in farm_info
    assert "胡萝卜" in farm_info


def test_chat_agent_uses_model_judgement_to_select_tools():
    assistant = ChatAssistant()
    captured_prompts: list[str] = []

    def fake_call_openai(prompt: str) -> str:
        captured_prompts.append(prompt)
        return '{"player_info": true, "farm_info": true, "game_guide": true}'

    with patch.object(assistant, "_call_openai", side_effect=fake_call_openai):
        result = assistant._decide_tools(
            {
                "message": "我想看看现在账号发展怎么样，顺便讲讲地里长势，再给点新手入门方向。",
                "memories": "上轮我们提过胡萝卜和仓库。",
            }
        )

    assert result["requested_tools"] == ["player_info", "farm_info", "game_guide"]
    assert captured_prompts
    assert "上轮我们提过胡萝卜和仓库" in captured_prompts[0]
    assert "新手入门方向" in captured_prompts[0]


def test_chat_agent_falls_back_when_tool_judgement_model_unavailable(caplog: pytest.LogCaptureFixture):
    assistant = ChatAssistant()

    caplog.clear()
    with patch.object(assistant, "_call_openai", return_value=None):
        result = assistant._decide_tools(
            {
                "message": "请告诉我我的玩家信息、田地情况，再给我一点胡萝卜攻略。",
                "memories": DEFAULT_EMPTY_MEMORIES,
            }
        )

    assert result["requested_tools"] == ["player_info", "farm_info", "game_guide"]
    assert "聊天工具判定模型不可用或返回无效结果，已回退到本地规则。" in caplog.text


def test_game_data_query_runs_player_info_before_farm_info_when_both_are_needed():
    calls: list[str] = []
    prompts: list[str] = []

    def read_player(player_id: str) -> str:
        calls.append("player_info")
        assert player_id == "player-seq"
        return "\u91d1\u5e01\uff1a520"

    def read_farm(player_id: str) -> str:
        calls.append("farm_info")
        assert player_id == "player-seq"
        return "\u53ef\u79cd\u4f5c\u7269\uff1a\u80e1\u841d\u535c"

    assistant = ChatAssistant(
        player_info_reader=read_player,
        farm_info_reader=read_farm,
    )
    model_outputs = iter(
        [
            '{"intent":"game_data_query","reason":"needs player and farm data"}',
            '{"final_answer":"\u4f60\u73b0\u5728\u6709 520 \u91d1\u5e01\uff0c\u53ef\u4ee5\u79cd\u80e1\u841d\u535c\u3002"}',
        ]
    )

    def fake_call_openai(prompt: str) -> str:
        prompts.append(prompt)
        return next(model_outputs)

    with patch.object(assistant, "_call_openai", side_effect=fake_call_openai):
        result = assistant.reply(
            [],
            "\u6211\u73b0\u5728\u6709\u591a\u5c11\u91d1\u5e01\uff0c\u53ef\u4ee5\u79cd\u4e9b\u4ec0\u4e48\uff1f",
            player_id="player-seq",
        )

    assert calls == ["player_info", "farm_info"]
    assert len(prompts) == 2
    assert "\u91d1\u5e01\uff1a520" in prompts[-1]
    assert "\u53ef\u79cd\u4f5c\u7269\uff1a\u80e1\u841d\u535c" in prompts[-1]
    assert result["response"] == "\u4f60\u73b0\u5728\u6709 520 \u91d1\u5e01\uff0c\u53ef\u4ee5\u79cd\u80e1\u841d\u535c\u3002"


def test_daily_chat_can_use_tools_and_remember_previous_talk():
    _upsert_player("player-memory", "小农", gold=300, level=5)
    _plant_crop(2, 1)

    with patch.object(
        chat_command.chat_assistant,
        "_call_openai",
        side_effect=[
            '{"player_info": true, "farm_info": true, "game_guide": true}',
            '{"response": "玩家信息：小农。田地信息：2 号地里有胡萝卜。游戏攻略：先保证水肥。"}',
            '{"player_info": false, "farm_info": false, "game_guide": false}',
            '{"response": "你刚才问了玩家信息、田地情况和胡萝卜攻略。"}',
        ],
    ):
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
