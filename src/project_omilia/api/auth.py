"""
API-роутер аутентификации и профиля пользователя.
"""

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from project_omilia import db
from project_omilia.api.deps import (
    get_token_from_request,
    require_current_user,
)
from project_omilia.core.config import DB_PATH
from project_omilia.schemas.auth import AuthRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def api_register(data: AuthRequest):
    """Регистрация нового аккаунта."""
    user, err = db.register_user(DB_PATH, data.username, data.password)
    if err:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": err})
    return {"status": "ok", "user": user}


@router.post("/login")
async def api_login(data: AuthRequest):
    """Вход в аккаунт по логину и паролю."""
    user, err = db.login_user(DB_PATH, data.username, data.password)
    if err:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": err})
    return {"status": "ok", "user": user}


@router.get("/me")
async def api_me(user: dict = Depends(require_current_user)):
    """Получение профиля текущего авторизованного пользователя и списка выученных жестов."""
    learned = db.get_learned_gestures(DB_PATH, user["id"])
    return {
        "status": "ok",
        "user": user,
        "learned_gestures": learned,
    }


@router.post("/logout")
async def api_logout(request: Request, authorization: str | None = Header(None)):
    """Выход из аккаунта и инвалидация токена сессии."""
    token = get_token_from_request(request, authorization)
    if token:
        db.logout_user(DB_PATH, token)
    return {"status": "ok"}
