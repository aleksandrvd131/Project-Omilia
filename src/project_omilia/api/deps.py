"""
Зависимости FastAPI (Dependencies) для аутентификации и доступа к сервисам.
"""

from typing import Any
from fastapi import Header, HTTPException, Request, status

from project_omilia.core.config import DB_PATH
from project_omilia import db
from project_omilia.services.dynamic_service import DynamicGestureServer
from project_omilia.services.static_service import StaticGestureServer


def get_token_from_request(request: Request, authorization: str | None = None) -> str | None:
    """Извлекает токен авторизации из заголовка Authorization (Bearer) или query-параметра token."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    if "token" in request.query_params:
        return request.query_params["token"]
    return None


def get_current_user_from_request(
    request: Request, authorization: str | None = Header(None)
) -> dict[str, Any] | None:
    """Получает объект текущего пользователя или None, если запрос не авторизован."""
    token = get_token_from_request(request, authorization)
    if token:
        return db.get_user_by_token(DB_PATH, token)
    return None


def require_current_user(
    request: Request, authorization: str | None = Header(None)
) -> dict[str, Any]:
    """Строгая зависимость: возвращает пользователя либо выбрасывает 401 Unauthorized."""
    user = get_current_user_from_request(request, authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    return user


def require_admin_user(
    request: Request, authorization: str | None = Header(None)
) -> dict[str, Any]:
    """Строгая зависимость: требует роль 'admin' (или разрешает при пустой БД), иначе 403 Forbidden."""
    token = get_token_from_request(request, authorization)
    if not db.has_admin_access(DB_PATH, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав. Требуются права администратора.",
        )
    user = get_current_user_from_request(request, authorization)
    return user or {"role": "admin", "username": "admin"}


def get_static_server(request: Request) -> StaticGestureServer:
    """Зависимость для получения экземпляра StaticGestureServer из state приложения."""
    server = getattr(request.app.state, "static_server", None)
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Сервис статических жестов не инициализирован",
        )
    return server


def get_dynamic_server(request: Request) -> DynamicGestureServer:
    """Зависимость для получения экземпляра DynamicGestureServer из state приложения."""
    server = getattr(request.app.state, "dynamic_server", None)
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Сервис динамических жестов не инициализирован",
        )
    return server
