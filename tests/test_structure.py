from dataclasses import fields

from app.agent import (
    ChatAssistant,
    ChessOpponentAssistant,
    ChessSuggestAssistant,
    MinesweeperAssistant,
)
from app.model import ChatHistory, Crop, CropInstance, LandPlot
from app.prompt import (
    CHAT_SYSTEM_PROMPT,
    CHESS_OPPONENT_SYSTEM_PROMPT,
    CHESS_SYSTEM_PROMPT,
    MINESWEEPER_SYSTEM_PROMPT,
)


def test_prompt_and_agent_modules_are_structured():
    assert CHAT_SYSTEM_PROMPT
    assert MINESWEEPER_SYSTEM_PROMPT
    assert CHESS_SYSTEM_PROMPT
    assert CHESS_OPPONENT_SYSTEM_PROMPT

    assert ChatAssistant(system_prompt=CHAT_SYSTEM_PROMPT).agent_config()["system_prompt"] == CHAT_SYSTEM_PROMPT
    assert MinesweeperAssistant(system_prompt=MINESWEEPER_SYSTEM_PROMPT).agent_config()["system_prompt"] == MINESWEEPER_SYSTEM_PROMPT
    assert ChessSuggestAssistant(system_prompt=CHESS_SYSTEM_PROMPT).agent_config()["system_prompt"] == CHESS_SYSTEM_PROMPT
    assert ChessOpponentAssistant(system_prompt=CHESS_OPPONENT_SYSTEM_PROMPT).agent_config()["system_prompt"] == CHESS_OPPONENT_SYSTEM_PROMPT


def test_database_table_models_define_expected_fields():
    assert [field.name for field in fields(ChatHistory)] == ["id", "player_id", "text", "created_at"]
    assert [field.name for field in fields(LandPlot)] == ["id", "price", "description", "level", "growth_multiplier"]
    assert [field.name for field in fields(Crop)] == ["id", "name", "growth_seconds", "price", "description"]
    assert [field.name for field in fields(CropInstance)] == [
        "id",
        "land_id",
        "crop_id",
        "planted_at",
        "last_state_update_at",
        "water",
        "fertility",
        "temperature",
    ]
