from project_omilia.api.auth import router as auth_router
from project_omilia.api.blitz import router as blitz_router
from project_omilia.api.gestures import router as gestures_router
from project_omilia.api.models import router as models_router
from project_omilia.api.tts import router as tts_router
from project_omilia.api.websocket import router as ws_router

__all__ = [
    "auth_router",
    "gestures_router",
    "models_router",
    "blitz_router",
    "tts_router",
    "ws_router",
]
