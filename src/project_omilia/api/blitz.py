"""
API-роутер блиц-опроса («Проверить себя»).
"""

import random

from fastapi import APIRouter, Depends, Query

from project_omilia import db
from project_omilia.api.deps import (
    get_dynamic_server,
    get_static_server,
    require_current_user,
)
from project_omilia.core.config import DB_PATH, GESTURE_METADATA
from project_omilia.services.dynamic_service import DynamicGestureServer
from project_omilia.services.static_service import StaticGestureServer

router = APIRouter(prefix="/api/blitz", tags=["blitz"])


@router.get("/questions")
async def api_blitz_questions(
    count: int = Query(5, ge=1, le=20, description="Количество вопросов в блице"),
    user: dict = Depends(require_current_user),
    static_server: StaticGestureServer = Depends(get_static_server),
    dynamic_server: DynamicGestureServer = Depends(get_dynamic_server),
):
    """Генерирует случайную подвыборку вопросов для блиц-опроса из выученных жестов пользователя."""
    learned = db.get_learned_gestures(DB_PATH, user["id"])
    static_names = static_server.get_combined_stats().keys()
    dynamic_hands = dynamic_server.get_ready_gestures()
    available_names = static_names | dynamic_hands.keys()

    learned = [name.strip().lower() for name in learned if name.strip().lower() in available_names]
    if not learned:
        return {
            "status": "ok",
            "questions": [],
            "message": "Для блица выучи хотя бы один доступный жест в словаре.",
        }

    sample_size = min(len(learned), count)
    selected = random.sample(learned, sample_size)

    questions = []
    combined_info = static_server.get_combined_info()
    for name in selected:
        meta = GESTURE_METADATA.get(name, {})
        dyn_hands = dynamic_hands.get(name)
        static_info = combined_info.get(name)
        hands_count = dyn_hands if dyn_hands else (static_info["hands"] if static_info else 1)
        tip = meta.get("tip", "Покажите жест на камеру")
        if dyn_hands:
            hand_instruction = "одной рукой" if dyn_hands == 1 else "двумя руками"
            tip = f"Покажите жест {hand_instruction} за одну секунду."
        questions.append(
            {
                "gesture_name": name,
                "title": meta.get("title", name.capitalize()),
                "tip": tip,
                "hands_count": hands_count,
                "dynamic_hands_count": dyn_hands,
            }
        )

    return {
        "status": "ok",
        "questions": questions,
        "total_available": len(learned),
    }
