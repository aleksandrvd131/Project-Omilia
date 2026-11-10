"""
Основное FastAPI приложение Project Omilia с подключением модулей и маршрутов.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from project_omilia.api import (
    auth_router,
    blitz_router,
    gestures_router,
    models_router,
    tts_router,
    ws_router,
)
from project_omilia.core.config import (
    DB_PATH,
    DEBUG_PATH,
    FRONTEND_DIR,
    INDEX_PATH,
)
from project_omilia import db
from project_omilia.services.dynamic_service import DynamicGestureServer
from project_omilia.services.static_service import StaticGestureServer, import_static_datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация базы данных, импорт эталонов и подготовка моделей классификации."""
    db.init_db(DB_PATH)
    import_static_datasets(DB_PATH)
    app.state.static_server = StaticGestureServer(DB_PATH)
    app.state.dynamic_server = DynamicGestureServer(DB_PATH)
    total_gestures = len(app.state.static_server.engine_1h.dataset) + len(app.state.static_server.engine_2h.dataset)
    print(f"Сервер Omiλia запущен. SQLite: {DB_PATH.name}, статических наборов: {total_gestures}")
    yield


def create_app() -> FastAPI:
    """Фабрика создания приложения FastAPI."""
    app = FastAPI(title="Project Omilia", version="0.2.0", lifespan=lifespan)

    # Раздача статических файлов фронтенда
    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    # Регистрация модульных API-роутеров
    app.include_router(auth_router)
    app.include_router(gestures_router)
    app.include_router(models_router)
    app.include_router(blitz_router)
    app.include_router(tts_router)
    app.include_router(ws_router)

    # Корневой маршрут пользовательского интерфейса
    @app.get("/", tags=["pages"])
    async def root():
        """Основной интерфейс платформы."""
        if INDEX_PATH.exists():
            return FileResponse(INDEX_PATH)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "index.html not found"})

    # Маршруты панели разработчика
    @app.get("/dev", tags=["pages"])
    @app.get("/debug", tags=["pages"])
    async def dev_page():
        """Панель разработчика (запись жестов, калибровка и дебаг)."""
        if DEBUG_PATH.exists():
            return FileResponse(DEBUG_PATH)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "debug.html not found"})

    return app


app = create_app()
