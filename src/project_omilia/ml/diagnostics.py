"""
Модуль биометрической диагностики и формирования контекстных подсказок (Smart Diagnostic Feedback).

Сравнивает вектор признаков пользователя с эталонным центроидом целевого жеста
и генерирует точные рекомендации на естественном языке:
1. Анализ угла ориентации нормали ладони (к экрану, от экрана, вбок, вверх/вниз).
2. Анализ сгибания и разгибания каждого из 5 пальцев (согните / выпрямите указательный и т.д.).
3. Анализ смыкания пальцев (пинчи / щепоть).
4. Анализ пространственного положения руки относительно груди и лица (выше / ниже / правее / левее).
"""

from typing import Any

import numpy as np

FINGER_NAMES = [
    "большой палец",
    "указательный палец",
    "средний палец",
    "безымянный палец",
    "мизинец",
]

FINGER_KEYS = ["thumb", "index", "middle", "ring", "pinky"]


def _diagnose_hand(
    user_vec: np.ndarray,
    target_vec: np.ndarray,
    offset: int = 0,
    hand_prefix: str = "",
) -> tuple[list[str], dict[str, Any], list[int]]:
    """Анализирует форму и ориентацию одной кисти (135 признаков).

    Возвращает:
        hints: список рекомендаций по исправлению позы руки.
        finger_status: словарь статусов каждого пальца ('ok', 'straighten', 'bend').
        problem_fingers: индексы пальцев (0..4), требующих корректировки (для подсветки в UI).
    """
    hints: list[str] = []
    finger_status: dict[str, Any] = {}
    problem_fingers: list[int] = []

    # 1. Анализ ориентации ладони (вектор нормали: offset + 60..62)
    u_norm = user_vec[offset + 60 : offset + 63]
    t_norm = target_vec[offset + 60 : offset + 63]

    u_len = float(np.linalg.norm(u_norm))
    t_len = float(np.linalg.norm(t_norm))

    if u_len > 1e-4 and t_len > 1e-4:
        u_u = u_norm / u_len
        t_u = t_norm / t_len
        dot = float(np.clip(np.dot(u_u, t_u), -1.0, 1.0))

        # Если угол между нормалями больше ~45 градусов (dot < 0.70)
        if dot < 0.70:
            dz = float(t_u[2] - u_u[2])
            dx = float(t_u[0] - u_u[0])
            dy = float(t_u[1] - u_u[1])

            if dz > 0.45:
                hints.append(f"{hand_prefix}Поверните ладонь к экрану")
            elif dz < -0.45:
                hints.append(f"{hand_prefix}Поверните ладонь тыльной стороной к экрану")
            elif abs(dx) > abs(dy):
                if dx > 0.4:
                    hints.append(f"{hand_prefix}Поверните ладонь правее")
                elif dx < -0.4:
                    hints.append(f"{hand_prefix}Поверните ладонь левее")
            else:
                if dy > 0.4:
                    hints.append(f"{hand_prefix}Направьте ладонь ниже")
                elif dy < -0.4:
                    hints.append(f"{hand_prefix}Направьте ладонь выше")

    # 2. Анализ сгибания каждого пальца (углы между фалангами: offset + 63..107)
    # По 3 угла на палец (индексы 0, 3, 6 относительно начала пальца)
    bend_diffs: list[tuple[float, int, str]] = []

    for f_idx in range(5):
        key = FINGER_KEYS[f_idx]
        name = FINGER_NAMES[f_idx]
        base_idx = offset + 63 + (f_idx * 9)

        # Суммарный угол сгибания 3 сочленений пальца (каждый угол от 0 до ~1.0)
        u_bend = float(user_vec[base_idx] + user_vec[base_idx + 3] + user_vec[base_idx + 6])
        t_bend = float(target_vec[base_idx] + target_vec[base_idx + 3] + target_vec[base_idx + 6])
        diff = u_bend - t_bend

        if diff > 0.38:
            # У пользователя палец согнут сильнее, чем нужно в эталоне
            finger_status[key] = "straighten"
            problem_fingers.append(f_idx)
            bend_diffs.append((diff, f_idx, f"{hand_prefix}Выпрямите {name}"))
        elif diff < -0.38:
            # У пользователя палец прямой, а в эталоне должен быть согнут
            finger_status[key] = "bend"
            problem_fingers.append(f_idx)
            bend_diffs.append((-diff, f_idx, f"{hand_prefix}Согните {name}"))
        else:
            finger_status[key] = "ok"

    # Сортируем ошибки сгибания по величине отклонения (самые критичные первыми)
    bend_diffs.sort(key=lambda x: x[0], reverse=True)
    for _, _, hint_text in bend_diffs:
        hints.append(hint_text)

    # 3. Анализ смыкания пальцев с большим (пинчи: offset + 120..131)
    # Указательный к большому: offset + 120
    u_pinch_idx = float(user_vec[offset + 120])
    t_pinch_idx = float(target_vec[offset + 120])
    if t_pinch_idx < 0.40 and u_pinch_idx > 0.70:
        hints.append(f"{hand_prefix}Сомкните кончики большого и указательного пальцев")

    return hints, finger_status, problem_fingers


def diagnose_static_gesture(
    user_vector: np.ndarray,
    target_vector: np.ndarray,
    hands_count: int = 1,
) -> dict[str, Any]:
    """Выполняет дифференциальную диагностику между позой пользователя и целевым жестом.

    Возвращает структурированный словарь с рекомендациями, статусом пальцев и пространственными ошибками.
    """
    user_vec = np.asarray(user_vector, dtype=np.float32).flatten()
    target_vec = np.asarray(target_vector, dtype=np.float32).flatten()

    expected_dim = 141 * hands_count
    if len(user_vec) != expected_dim or len(target_vec) != expected_dim:
        return {
            "is_matching": False,
            "score": 0.0,
            "primary_hint": None,
            "hints": [],
            "problem_fingers": [],
            "finger_status": {},
        }

    # Евклидово расстояние между полными векторами признаков
    score = float(np.linalg.norm(user_vec - target_vec))

    all_hints: list[str] = []
    all_problem_fingers: list[int] = []
    all_finger_status: dict[str, Any] = {}

    if hands_count == 1:
        hints, f_status, p_fingers = _diagnose_hand(user_vec, target_vec, offset=0)
        all_hints.extend(hints)
        all_problem_fingers.extend(p_fingers)
        all_finger_status = f_status

        # 4. Анализ положения кисти относительно груди (138..140)
        u_chest = user_vec[138:141]
        t_chest = target_vec[138:141]
        # В координатах кадра +Y направлен вниз, поэтому большее Y означает более низкое положение
        dy = float(u_chest[1] - t_chest[1])
        dx = float(t_chest[0] - u_chest[0])

        if dy > 0.38:
            all_hints.append("Поднимите руку чуть выше")
        elif dy < -0.38:
            all_hints.append("Опустите руку чуть ниже")
        elif dx > 0.38:
            all_hints.append("Сдвиньте руку чуть правее")
        elif dx < -0.38:
            all_hints.append("Сдвиньте руку чуть левее")

    else:
        # Анализ для двух рук
        r_hints, r_status, r_fingers = _diagnose_hand(user_vec, target_vec, offset=0, hand_prefix="Правая рука: ")
        l_hints, l_status, l_fingers = _diagnose_hand(user_vec, target_vec, offset=135, hand_prefix="Левая рука: ")

        all_hints.extend(r_hints)
        all_hints.extend(l_hints)
        all_problem_fingers.extend(r_fingers)
        all_problem_fingers.extend([f + 5 for f in l_fingers])  # 5..9 для левой руки
        all_finger_status = {"right": r_status, "left": l_status}

    is_matching = bool(score <= 1.25 and len(all_problem_fingers) == 0 and len(all_hints) == 0)

    primary_hint = None
    if is_matching:
        primary_hint = "✨ Отлично! Удерживайте позу..."
    elif all_hints:
        primary_hint = f"💡 Подсказка: {all_hints[0]}"

    return {
        "is_matching": is_matching,
        "score": round(score, 2),
        "primary_hint": primary_hint,
        "hints": all_hints[:4],  # До 4 наиболее важных подсказок
        "problem_fingers": all_problem_fingers,
        "finger_status": all_finger_status,
    }
