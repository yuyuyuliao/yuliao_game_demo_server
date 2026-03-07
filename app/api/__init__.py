from app.api.chat_api import router as chat_router
from app.api.farm_api import router as farm_router
from app.api.game_api import router as game_router
from app.api.health_api import router as health_router

__all__ = ["health_router", "chat_router", "game_router", "farm_router"]
