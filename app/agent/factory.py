from __future__ import annotations

import os
from typing import Any

from app.agent.agentscope_runtime import ensure_agentscope_initialized
from app.agent.chat_agent import ChatAssistant
from app.agent.chess_opponent_agent import ChessOpponentAssistant
from app.agent.chess_suggest_agent import ChessSuggestAssistant
from app.agent.minesweeper_agent import MinesweeperAssistant
from app.agent.registry import AgentRegistry, AgentSpec

DEFAULT_MODEL_NAME = os.getenv("OPENAI_CHAT_MODEL", "qwen3:1.7b")


def _build_chat_assistant(**overrides: Any) -> ChatAssistant:
    from app.command.chat_tools import read_player_farm_info, read_player_info
    from app.command.knowledge import knowledge_store
    from app.prompt import CHAT_SYSTEM_PROMPT

    ensure_agentscope_initialized(DEFAULT_MODEL_NAME)
    return ChatAssistant(
        system_prompt=CHAT_SYSTEM_PROMPT,
        model_name=DEFAULT_MODEL_NAME,
        knowledge_search=knowledge_store.search,
        player_info_reader=read_player_info,
        farm_info_reader=read_player_farm_info,
        **overrides,
    )


def _build_minesweeper_assistant(**overrides: Any) -> MinesweeperAssistant:
    from app.prompt import MINESWEEPER_SYSTEM_PROMPT

    ensure_agentscope_initialized(DEFAULT_MODEL_NAME)
    return MinesweeperAssistant(
        system_prompt=MINESWEEPER_SYSTEM_PROMPT,
        model_name=DEFAULT_MODEL_NAME,
        **overrides,
    )


def _build_chess_assistant(**overrides: Any) -> ChessSuggestAssistant:
    from app.command.knowledge import knowledge_store
    from app.prompt import CHESS_SYSTEM_PROMPT

    ensure_agentscope_initialized(DEFAULT_MODEL_NAME)
    return ChessSuggestAssistant(
        system_prompt=CHESS_SYSTEM_PROMPT,
        model_name=DEFAULT_MODEL_NAME,
        knowledge_search=knowledge_store.search,
        **overrides,
    )


def _build_chess_opponent_assistant(**overrides: Any) -> ChessOpponentAssistant:
    from app.prompt import CHESS_OPPONENT_SYSTEM_PROMPT

    ensure_agentscope_initialized(DEFAULT_MODEL_NAME)
    return ChessOpponentAssistant(
        system_prompt=CHESS_OPPONENT_SYSTEM_PROMPT,
        model_name=DEFAULT_MODEL_NAME,
        **overrides,
    )


def build_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(AgentSpec(key="chat", factory=_build_chat_assistant))
    registry.register(AgentSpec(key="minesweeper", factory=_build_minesweeper_assistant))
    registry.register(AgentSpec(key="chess_suggest", factory=_build_chess_assistant))
    registry.register(AgentSpec(key="chess_opponent", factory=_build_chess_opponent_assistant))
    return registry
