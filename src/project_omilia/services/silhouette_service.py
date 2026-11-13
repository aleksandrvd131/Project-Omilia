"""
Сервис формирования анатомических ключевых точек (силуэтов-призраков) для статических жестов.

Использует топологию MediaPipe Hands (21 точка на кисть):
- Для Slovo-жестов возвращает канонические координаты из `slovo_generator.py`.
- Для остальных статических жестов предоставляет канонически рассчитанные анатомические модели.
- Для динамических жестов (`is_dynamic == True`) силуэт равен `None`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_omilia import db
from project_omilia.core.config import DB_PATH
from project_omilia.gestures import GESTURE_DEFINITIONS
from project_omilia.ml.slovo_generator import (
    SLOVO_GESTURES,
    HandLandmarks,
    build_hand_landmarks,
    get_slovo_landmarks,
)


def _build_additional_canonical_landmarks() -> dict[str, list[HandLandmarks]]:
    """Формирует канонические 21-точечные координаты для статических жестов вне Slovo."""
    landmarks: dict[str, list[HandLandmarks]] = {}

    # Уровень 1: Дактиль
    # 'а': кулак, большой палец прижат сбоку
    landmarks["а"] = [
        build_hand_landmarks(
            (0.60, 0.65, 0.0),
            {
                "thumb": "side",
                "index": "fist",
                "middle": "fist",
                "ring": "fist",
                "pinky": "fist",
            },
            is_right=True,
        )
    ]

    # 'б': 4 прямых пальца вверх, большой палец согнут поперек ладони
    landmarks["б"] = [
        build_hand_landmarks(
            (0.60, 0.65, 0.0),
            {
                "thumb": "palm",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'в': все пять пальцев широко раскрыты
    landmarks["в"] = [
        build_hand_landmarks(
            (0.60, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # Уровень 2: Числительные
    # '10': две раскрытые ладони (2 руки)
    landmarks["10"] = [
        build_hand_landmarks(
            (0.65, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        ),
        build_hand_landmarks(
            (0.35, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=False,
        ),
    ]

    # Уровень 3: Базовый этикет
    # 'привет': открытая ладонь вверх
    landmarks["привет"] = [
        build_hand_landmarks(
            (0.60, 0.60, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'спасибо': прямая плоская ладонь
    landmarks["спасибо"] = [
        build_hand_landmarks(
            (0.55, 0.65, 0.0),
            {
                "thumb": "flat",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'помоги': открытая ладонь направлена вперед
    landmarks["помоги"] = [
        build_hand_landmarks(
            (0.55, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'пожалуйста': ладонь у груди
    landmarks["пожалуйста"] = [
        build_hand_landmarks(
            (0.55, 0.65, 0.0),
            {
                "thumb": "flat",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'да': плотный кулак
    landmarks["да"] = [
        build_hand_landmarks(
            (0.60, 0.65, 0.0),
            {
                "thumb": "fist",
                "index": "fist",
                "middle": "fist",
                "ring": "fist",
                "pinky": "fist",
            },
            is_right=True,
        )
    ]

    # Уровень 4: Семья и окружение
    # 'дом': две ладони соприкасаются под углом («крыша»)
    landmarks["дом"] = [
        build_hand_landmarks(
            (0.58, 0.62, 0.0),
            {
                "thumb": "flat",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
                "index_spread": -0.35,
                "middle_spread": -0.25,
                "ring_spread": -0.15,
                "pinky_spread": -0.05,
            },
            is_right=True,
        ),
        build_hand_landmarks(
            (0.42, 0.62, 0.0),
            {
                "thumb": "flat",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
                "index_spread": 0.35,
                "middle_spread": 0.25,
                "ring_spread": 0.15,
                "pinky_spread": 0.05,
            },
            is_right=False,
        ),
    ]

    # 'мама': открытая ладонь
    landmarks["мама"] = [
        build_hand_landmarks(
            (0.55, 0.55, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'папа': открытая ладонь
    landmarks["папа"] = [
        build_hand_landmarks(
            (0.55, 0.45, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        )
    ]

    # 'семья': две кисти образуют округлый жест
    landmarks["семья"] = [
        build_hand_landmarks(
            (0.58, 0.65, 0.0),
            {
                "thumb": "c_curve",
                "index": "c_curve",
                "middle": "c_curve",
                "ring": "c_curve",
                "pinky": "c_curve",
            },
            is_right=True,
        ),
        build_hand_landmarks(
            (0.42, 0.65, 0.0),
            {
                "thumb": "c_curve",
                "index": "c_curve",
                "middle": "c_curve",
                "ring": "c_curve",
                "pinky": "c_curve",
            },
            is_right=False,
        ),
    ]

    # 'я': указательный палец
    landmarks["я"] = [
        build_hand_landmarks(
            (0.55, 0.65, 0.0),
            {
                "thumb": "fist",
                "index": "extended",
                "index_spread": 0.0,
                "middle": "fist",
                "ring": "fist",
                "pinky": "fist",
            },
            is_right=True,
        )
    ]

    # 'ты': указательный палец вперед
    landmarks["ты"] = [
        build_hand_landmarks(
            (0.55, 0.65, 0.0),
            {
                "thumb": "fist",
                "index": "extended",
                "index_spread": 0.0,
                "middle": "fist",
                "ring": "fist",
                "pinky": "fist",
            },
            is_right=True,
        )
    ]

    return landmarks


ADDITIONAL_CANONICAL_LANDMARKS: dict[str, list[HandLandmarks]] = _build_additional_canonical_landmarks()


def get_default_canonical_landmarks(hands_count: int = 1) -> list[HandLandmarks]:
    """Возвращает стандартный эталонный силуэт открытой ладони для кастомного статического жеста."""
    if hands_count <= 1:
        return [
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "spread",
                    "index": "extended",
                    "middle": "extended",
                    "ring": "extended",
                    "pinky": "extended",
                },
                is_right=True,
            )
        ]
    return [
        build_hand_landmarks(
            (0.65, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=True,
        ),
        build_hand_landmarks(
            (0.35, 0.65, 0.0),
            {
                "thumb": "spread",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
            is_right=False,
        ),
    ]


def get_gesture_silhouette(
    name: str,
    db_path: Path | None = None,
    static_server: Any = None,
    dynamic_server: Any = None,
) -> dict[str, Any] | None:
    """Возвращает метаданные силуэта и анатомические ключевые точки.

    Для статических жестов:
        {
            "name": norm_name,
            "is_dynamic": False,
            "hands_count": 1 или 2,
            "silhouette": list[list[dict]],
            "landmarks": list[list[dict]],
        }

    Для динамических жестов:
        {
            "name": norm_name,
            "is_dynamic": True,
            "hands_count": int,
            "silhouette": None,
            "landmarks": None,
            "message": "Силуэт-призрак доступен только для статических жестов",
        }

    Если жест не существует, возвращает `None`.
    """
    norm_name = name.strip().lower()
    if not norm_name:
        return None

    actual_db_path = db_path or DB_PATH
    db_meta = None
    try:
        db_meta = db.get_gesture(actual_db_path, norm_name)
    except Exception:
        pass

    gdef = GESTURE_DEFINITIONS.get(norm_name)
    dynamic_hands = dynamic_server.get_ready_gestures() if dynamic_server else {}

    # Проверка существования жеста
    is_known = (
        db_meta is not None
        or gdef is not None
        or norm_name in dynamic_hands
        or norm_name in SLOVO_GESTURES
        or norm_name in ADDITIONAL_CANONICAL_LANDMARKS
    )
    if not is_known and static_server:
        combined_stats = static_server.get_combined_stats()
        is_known = norm_name in combined_stats

    if not is_known:
        return None

    # Определение динамичности жеста
    is_dynamic = False
    if db_meta and bool(db_meta.get("is_dynamic")):
        is_dynamic = True
    elif norm_name in dynamic_hands:
        is_dynamic = True
    elif gdef and gdef.is_dynamic:
        is_dynamic = True

    hands_count = 1
    if db_meta and db_meta.get("hands_count"):
        hands_count = int(db_meta["hands_count"])
    elif gdef and gdef.hands_count:
        hands_count = int(gdef.hands_count)
    elif norm_name in dynamic_hands:
        hands_count = int(dynamic_hands[norm_name])

    # ДЛЯ ДИНАМИЧЕСКИХ ЖЕСТОВ: силуэт всегда отсутствует (None)
    if is_dynamic:
        return {
            "name": norm_name,
            "is_dynamic": True,
            "hands_count": hands_count,
            "silhouette": None,
            "landmarks": None,
            "message": "Силуэт-призрак доступен только для статических жестов",
        }

    # ДЛЯ СТАТИЧЕСКИХ ЖЕСТОВ: извлечение анатомических 21-точечных ориентиров
    if norm_name in SLOVO_GESTURES:
        landmarks = get_slovo_landmarks(norm_name)
    elif norm_name in ADDITIONAL_CANONICAL_LANDMARKS:
        landmarks = ADDITIONAL_CANONICAL_LANDMARKS[norm_name]
    else:
        landmarks = get_default_canonical_landmarks(hands_count=hands_count)

    return {
        "name": norm_name,
        "is_dynamic": False,
        "hands_count": len(landmarks),
        "silhouette": landmarks,
        "landmarks": landmarks,
    }
