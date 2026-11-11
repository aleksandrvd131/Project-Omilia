"""
API-роутер каталога жестов, прогресса обучения и управления датасетом.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from project_omilia import db
from project_omilia.api.deps import (
    get_current_user_from_request,
    get_dynamic_server,
    get_static_server,
    require_current_user,
)
from project_omilia.core.config import DB_PATH, GESTURE_METADATA
from project_omilia.gestures import COUNT_OF_SAMPLES
from project_omilia.schemas.gestures import LearnRequest
from project_omilia.services.dynamic_service import DynamicGestureServer
from project_omilia.services.static_service import StaticGestureServer

router = APIRouter(prefix="/api/gestures", tags=["gestures"])


@router.get("")
async def api_get_gestures(
    request: Request,
    authorization: str | None = Header(None),
    static_server: StaticGestureServer = Depends(get_static_server),
    dynamic_server: DynamicGestureServer = Depends(get_dynamic_server),
):
    """Каталог доступных жестов из SQLite с отметками о том, какие уже выучены текущим пользователем."""
    user = get_current_user_from_request(request, authorization)
    learned_set = set(g.strip().lower() for g in db.get_learned_gestures(DB_PATH, user["id"])) if user else set()

    combined_stats = static_server.get_combined_stats()
    dynamic_hands = dynamic_server.get_ready_gestures()
    db_gestures = {g["name"]: g for g in db.get_all_gestures(DB_PATH)}

    all_names = sorted(db_gestures.keys() | combined_stats.keys() | dynamic_hands.keys())
    gestures_list = []
    for norm_name in all_names:
        db_meta = db_gestures.get(norm_name)
        fallback_meta = GESTURE_METADATA.get(
            norm_name,
            {
                "title": norm_name.capitalize(),
                "category": "Общие жесты",
                "description": f"Статический жест «{norm_name}».",
                "tip": "Повторите положение кисти перед камерой.",
            },
        )
        title = (
            db_meta["title"] if db_meta and db_meta.get("title") else fallback_meta.get("title", norm_name.capitalize())
        )
        category = (
            db_meta["category"] if db_meta and db_meta.get("category") else fallback_meta.get("category", "Общие жесты")
        )
        description = (
            db_meta["description"] if db_meta and db_meta.get("description") else fallback_meta.get("description", "")
        )
        tip = db_meta["tip"] if db_meta and db_meta.get("tip") else fallback_meta.get("tip", "")

        hands_count = dynamic_hands.get(norm_name)
        is_dynamic = bool(hands_count or (db_meta and db_meta.get("is_dynamic")))

        gestures_list.append(
            {
                "name": norm_name,
                "title": title,
                "category": category,
                "description": (
                    "Динамический жест. Покажите движение целиком после отсчёта." if is_dynamic else description
                ),
                "tip": (
                    f"Покажите жест {'одной рукой' if hands_count == 1 else 'двумя руками'} за одну секунду."
                    if is_dynamic
                    else tip
                ),
                "samples_count": COUNT_OF_SAMPLES if is_dynamic else combined_stats.get(norm_name, 0),
                "dynamic_hands_count": hands_count,
                "is_dynamic": is_dynamic,
                "is_learned": norm_name in learned_set,
            }
        )

    # Сортировка: сначала невыученные, затем выученные
    gestures_list.sort(key=lambda g: (g["is_learned"], g["name"]))
    total_learned = sum(1 for g in gestures_list if g["is_learned"])

    return {
        "status": "ok",
        "gestures": gestures_list,
        "total_count": len(gestures_list),
        "learned_count": total_learned,
        "total_learned": total_learned,
        "total_available": len(gestures_list),
    }


@router.post("")
async def api_save_gesture(
    gesture_data: dict,
):
    """Добавление или обновление жеста в SQLite каталоге."""
    name = gesture_data.get("name", "").strip().lower()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название жеста не указано",
        )
    db.upsert_gesture(DB_PATH, gesture_data)
    return {"status": "ok", "gesture": db.get_gesture(DB_PATH, name)}


@router.post("/learn")
async def api_learn_gesture(
    data: LearnRequest,
    user: dict = Depends(require_current_user),
):
    """Фиксация жеста как успешно выученного пользователем."""
    gesture_name = data.gesture_name.strip().lower()
    if not gesture_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя жеста не указано",
        )

    success = db.mark_gesture_learned(DB_PATH, user["id"], gesture_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сохранения прогресса в базе данных",
        )

    learned = db.get_learned_gestures(DB_PATH, user["id"])
    return {
        "status": "ok",
        "learned_gestures": learned,
        "learned_count": len(learned),
    }


@router.delete("/{gesture_name}")
async def api_delete_gesture(
    gesture_name: str,
    static_server: StaticGestureServer = Depends(get_static_server),
):
    """Удаляет жест из датасета модели."""
    norm_name = gesture_name.strip().lower()
    static_server.delete_gesture(norm_name)
    return {
        "status": "ok",
        "deleted": norm_name,
        "dataset_stats": static_server.get_combined_stats(),
        "dataset_info": static_server.get_combined_info(),
    }
