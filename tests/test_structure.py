from app.agent import (
    ChatAssistant,
    ChessOpponentAssistant,
    ChessSuggestAssistant,
    MinesweeperAssistant,
)
from app.model import BaseModel, ChatHistory, Crop, CropInstance, LandPlot
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
    assert issubclass(ChatHistory, BaseModel)
    assert issubclass(LandPlot, BaseModel)
    assert issubclass(Crop, BaseModel)
    assert issubclass(CropInstance, BaseModel)

    assert set(ChatHistory.__table__.columns.keys()) == {"player_id", "text", "created_at", "id"}
    assert set(LandPlot.__table__.columns.keys()) == {"price", "description", "level", "growth_multiplier", "id"}
    assert set(Crop.__table__.columns.keys()) == {"name", "growth_seconds", "price", "description", "profit_multiplier", "id"}
    assert set(CropInstance.__table__.columns.keys()) == {
        "land_id",
        "crop_id",
        "planted_at",
        "last_state_update_at",
        "water",
        "fertility",
        "temperature",
        "id",
    }
