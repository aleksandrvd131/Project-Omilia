"""
Тесты биометрической диагностики и формирования контекстных подсказок (Smart Diagnostic Feedback):
- Проверка диагностики ориентации нормали ладони.
- Проверка диагностики сгибания и разгибания отдельных пальцев.
- Проверка диагностики пространственного положения руки относительно груди.
- Проверка корректного распознавания matching позы.
- Интеграционная проверка генерации подсказок в StaticGestureServer.
"""

import tempfile
from pathlib import Path

import numpy as np

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.ml.diagnostics import diagnose_static_gesture
from project_omilia.services.static_service import StaticGestureServer
from tests.test_invariance_and_augmentation import (
    _generate_synthetic_body_landmarks,
    _generate_synthetic_hand_landmarks,
)


def _create_base_vector(hands_count: int = 1) -> np.ndarray:
    """Создаёт базовый валидный вектор признаков."""
    dim = 141 * hands_count
    vec = np.zeros(dim, dtype=np.float32)

    for h in range(hands_count):
        offset = h * 135
        # Нормаль ладони смотрит на экран (Z = 1.0)
        vec[offset + 60 : offset + 63] = [0.0, 0.0, 1.0]
        # Пальцы полусогнуты (углы 0.2 на сустав)
        for f in range(5):
            base = offset + 63 + f * 9
            vec[base] = 0.2
            vec[base + 3] = 0.2
            vec[base + 6] = 0.2

    # Положение относительно груди (138..140)
    vec[138:141] = [0.15, -0.05, 0.0]
    return vec


def test_diagnose_palm_orientation_turn_to_camera():
    """Тест: пользователь отвернул ладонь от экрана -> подсказка повернуть к экрану."""
    target = _create_base_vector(1)
    target[60:63] = [0.0, 0.0, 1.0]  # Цель: ладонь к экрану

    user = _create_base_vector(1)
    user[60:63] = [0.0, 0.0, -1.0]  # Пользователь: тыльная сторона к экрану

    res = diagnose_static_gesture(user, target, hands_count=1)

    assert res["is_matching"] is False
    assert any("Поверните ладонь к экрану" in h for h in res["hints"])
    assert "Поверните ладонь к экрану" in res["primary_hint"]


def test_diagnose_finger_straighten():
    """Тест: указательный палец согнут, а в эталоне должен быть прямым -> подсказка выпрямить."""
    target = _create_base_vector(1)
    # Указательный палец прямой (углы ~0.05)
    target[72] = 0.05
    target[75] = 0.05
    target[78] = 0.05

    user = _create_base_vector(1)
    # Указательный палец сильно согнут (углы ~0.35)
    user[72] = 0.35
    user[75] = 0.35
    user[78] = 0.35

    res = diagnose_static_gesture(user, target, hands_count=1)

    assert res["is_matching"] is False
    assert 1 in res["problem_fingers"]  # Индекс 1 = указательный палец
    assert any("Выпрямите указательный палец" in h for h in res["hints"])
    assert res["finger_status"]["index"] == "straighten"


def test_diagnose_finger_bend():
    """Тест: большой палец прямой, а в эталоне должен быть согнут -> подсказка согнуть."""
    target = _create_base_vector(1)
    # Большой палец согнут (углы ~0.4)
    target[63] = 0.4
    target[66] = 0.4
    target[69] = 0.4

    user = _create_base_vector(1)
    # Большой палец прямой
    user[63] = 0.05
    user[66] = 0.05
    user[69] = 0.05

    res = diagnose_static_gesture(user, target, hands_count=1)

    assert 0 in res["problem_fingers"]  # Индекс 0 = большой палец
    assert any("Согните большой палец" in h for h in res["hints"])
    assert res["finger_status"]["thumb"] == "bend"


def test_diagnose_hand_position_height():
    """Тест: рука опущена слишком низко относительно эталона -> подсказка поднять руку."""
    target = _create_base_vector(1)
    target[139] = -0.20  # Высокое положение относительно груди

    user = _create_base_vector(1)
    user[139] = 0.30  # Низкое положение (+Y направлен вниз)

    res = diagnose_static_gesture(user, target, hands_count=1)

    assert any("Поднимите руку чуть выше" in h for h in res["hints"])


def test_diagnose_matching_gesture():
    """Тест: поза совпадает с эталоном -> is_matching=True, поздравительная подсказка."""
    target = _create_base_vector(1)
    # Пользователь показывает позу с минимальным отклонением
    user = target + np.random.normal(0, 0.02, size=141).astype(np.float32)

    res = diagnose_static_gesture(user, target, hands_count=1)

    assert res["is_matching"] is True
    assert "✨" in res["primary_hint"]
    assert len(res["problem_fingers"]) == 0


def test_static_service_diagnostics_integration():
    """Тест: интеграция с StaticGestureServer при передаче target_gesture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "diag_test.db"
        db.init_db(test_db)
        server = StaticGestureServer(test_db)

        # Сохраним один эталон жеста "привет"
        body = _generate_synthetic_body_landmarks(scale=1.0)
        hand = _generate_synthetic_hand_landmarks(scale=2.5, offset_x=body[15].x, offset_y=body[15].y)
        pose = Pose(body, (hand,))
        vec = server.engine_1h.extract_vector(pose)

        server.engine_1h.add_samples("привет", [vec] * 5)
        server._refresh_stats()

        # Запрос кадра с целевым жестом "привет"
        res = server.process_frame(
            {
                "hands_data": [[{"x": p.x, "y": p.y, "z": p.z} for p in hand]],
                "pose_landmarks": [{"x": p.x, "y": p.y, "z": p.z} for p in body],
                "hands_count": 1,
                "target_gesture": "привет",
            },
            [],
        )

        assert res["detected"] is True
        assert "diagnostics" in res
        assert res["diagnostics"]["is_matching"] is True
        assert "✨" in res["diagnostics"]["primary_hint"]
