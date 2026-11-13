"""
Тесты масштабо- и дистанционной инвариантности и аугментации данных:
- Инвариантность Hand к размеру кисти (ближе/дальше от веб-камеры).
- Инвариантность Pose к ширине плеч и расстоянию до тела.
- Корректность физической аугментации (поворот, масштаб, микро-шум).
- Автоматическая аугментация при записи статических жестов в StaticGestureServer.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from project_omilia import db
from project_omilia.body import TORSO_REF_SCALE, Hand, Pose
from project_omilia.ml.augmentation import (
    augment_static_samples,
    augment_static_vector,
)
from project_omilia.services.static_service import StaticGestureServer


def _generate_synthetic_hand_landmarks(scale: float = 1.0, offset_x: float = 0.5, offset_y: float = 0.5):
    """Генерирует 21 реалистичную точку кисти MediaPipe с заданным масштабом и смещением."""
    # Запястье
    wrist = np.array([0.0, 0.0, 0.0])
    points = [wrist]

    # 5 пальцев, по 4 точки на каждый
    # 0: большой, 1: указательный, 2: средний, 3: безымянный, 4: мизинец
    finger_angles = [-0.4, -0.15, 0.0, 0.15, 0.35]
    finger_lengths = [0.08, 0.11, 0.12, 0.11, 0.09]

    for f_idx, (angle, total_len) in enumerate(zip(finger_angles, finger_lengths, strict=True)):
        base_dir = np.array([np.sin(angle), -np.cos(angle), 0.02 * f_idx])
        seg_len = total_len / 4.0
        # Основание пальца от запястья
        mcp = wrist + base_dir * (seg_len * 1.5)
        points.append(mcp)
        # 3 фаланги
        pip = mcp + base_dir * seg_len
        points.append(pip)
        dip = pip + base_dir * (seg_len * 0.8)
        points.append(dip)
        tip = dip + base_dir * (seg_len * 0.7)
        points.append(tip)

    # Применяем масштаб и смещение
    scaled_pts = []
    for p in points:
        pt = p * scale
        scaled_pts.append(SimpleNamespace(x=float(pt[0] + offset_x), y=float(pt[1] + offset_y), z=float(pt[2])))
    return scaled_pts


def _generate_synthetic_body_landmarks(scale: float = 1.0):
    """Генерирует 33 ключевые точки позы тела MediaPipe с масштабированием относительно центра (0.5, 0.4)."""
    cx, cy = 0.5, 0.4
    body = [SimpleNamespace(x=cx, y=cy, z=0.0) for _ in range(33)]
    # Нос (0)
    body[0] = SimpleNamespace(x=cx, y=cy + (-0.15 * scale), z=0.0)
    # Плечи: 11 (левое), 12 (правое)
    half_shoulder = (TORSO_REF_SCALE / 2.0) * scale
    body[11] = SimpleNamespace(x=cx - half_shoulder, y=cy + (0.05 * scale), z=0.0)
    body[12] = SimpleNamespace(x=cx + half_shoulder, y=cy + (0.05 * scale), z=0.0)
    # Запястья: 15 (правое), 16 (левое)
    body[15] = SimpleNamespace(x=cx + (0.15 * scale), y=cy + (0.02 * scale), z=0.0)
    body[16] = SimpleNamespace(x=cx - (0.15 * scale), y=cy + (0.02 * scale), z=0.0)
    return body


def test_hand_scale_invariance():
    """Проверяет, что вектор признаков кисти инвариантен к расстоянию до камеры (масштабу кисти)."""
    # Кисть на нормальном расстоянии (palm_scale ~ 0.25)
    hand_normal = _generate_synthetic_hand_landmarks(scale=2.5)
    # Кисть вдвое ближе к камере (palm_scale ~ 0.50)
    hand_close = _generate_synthetic_hand_landmarks(scale=5.0)

    h1 = Hand(hand_normal, is_right=True)
    h2 = Hand(hand_close, is_right=True)

    vec1 = np.array(h1.get_1d_array(), dtype=np.float32).flatten()
    vec2 = np.array(h2.get_1d_array(), dtype=np.float32).flatten()

    assert len(vec1) == 135  # 45 3D-векторов = 135
    assert len(vec2) == 135

    # Векторы фаланг и нормаль должны идеально совпадать после нормализации
    assert np.allclose(vec1, vec2, atol=1e-4)


def test_pose_distance_invariance():
    """Проверяет, что вектор признаков позы инвариантен к расстоянию человека до камеры."""
    # Дистанция 1: человек на нормальном расстоянии
    body1 = _generate_synthetic_body_landmarks(scale=1.0)
    hand1 = _generate_synthetic_hand_landmarks(scale=2.5, offset_x=body1[15].x, offset_y=body1[15].y)

    # Дистанция 2: человек сел ближе к камере (масштаб 1.6x)
    body2 = _generate_synthetic_body_landmarks(scale=1.6)
    hand2 = _generate_synthetic_hand_landmarks(scale=2.5 * 1.6, offset_x=body2[15].x, offset_y=body2[15].y)

    pose1 = Pose(body1, (hand1,))
    pose2 = Pose(body2, (hand2,))

    vec1 = pose1.get_1d_array_one_hand().flatten()
    vec2 = pose2.get_1d_array_one_hand().flatten()

    assert len(vec1) == 141
    assert len(vec2) == 141

    # Векторы смещения к носу (135..137) и груди (138..140) нормализованы по торсу,
    # поэтому вектор позы должен быть практически идентичен
    assert np.allclose(vec1, vec2, atol=1e-3)


def test_static_augmentation_vector():
    """Проверяет корректность генерации аугментированного вектора признаков."""
    vec = np.random.randn(141).astype(np.float32)
    # Нормализуем palm normal (60..62)
    norm = np.linalg.norm(vec[60:63])
    vec[60:63] /= norm

    # Аугментация с масштабом и поворотом
    aug = augment_static_vector(vec, scale=1.05, angle_deg=3.0, noise_sigma=0.002)

    assert aug.shape == (141,)
    assert aug.dtype == np.float32
    assert np.isfinite(aug).all()
    # Вектор изменился, но остался близким к исходному
    diff = np.linalg.norm(aug - vec)
    assert 0.0 < diff < 2.0


def test_static_augmentation_two_hands():
    """Проверяет аугментацию для жестов с 2 руками (282 признака)."""
    vec = np.random.randn(282).astype(np.float32)
    vec[60:63] /= np.linalg.norm(vec[60:63])
    vec[195:198] /= np.linalg.norm(vec[195:198])

    samples = [vec]
    augmented = augment_static_samples(samples, num_augmented_per_sample=3, seed=42)

    # 1 исходный + 3 аугментированных = 4
    assert len(augmented) == 4
    for s in augmented:
        assert s.shape == (282,)
        assert np.isfinite(s).all()


def test_static_service_auto_augmentation_on_record():
    """Проверяет автоматическую аугментацию при сохранении серии кадров в StaticGestureServer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_aug.db"
        db.init_db(test_db)

        server = StaticGestureServer(test_db)

        body = _generate_synthetic_body_landmarks(scale=1.0)
        hand = _generate_synthetic_hand_landmarks(scale=2.5, offset_x=body[15].x, offset_y=body[15].y)
        pose = Pose(body, (hand,))

        recording = []
        payload_frame = {
            "record_label": "тест_жест",
            "hands_count": 1,
            "record_finished": False,
        }

        # Записываем 3 кадра
        for _ in range(3):
            server._record_frame(payload_frame, pose, recording)

        assert len(recording) == 3

        # Завершающий кадр (record_finished=True)
        payload_finish = {
            "record_label": "тест_жест",
            "hands_count": 1,
            "record_finished": True,
        }
        res = server._record_frame(payload_finish, pose, recording)

        assert res["static_record"]["status"] == "saved"
        # 3 кадра + 1 завершающий кадр = 4 кадра; при num_augmented_per_sample=2 дают 4 + 4*2 = 12 сэмплов
        assert res["static_record"]["count"] == 12

        stats = server.get_combined_stats()
        assert stats.get("тест_жест") == 12

        # Проверяем, что k-NN модель обучилась и предсказывает этот жест
        pred_res = server.process_frame(
            {
                "hands_data": [[{"x": p.x, "y": p.y, "z": p.z} for p in hand]],
                "pose_landmarks": [{"x": p.x, "y": p.y, "z": p.z} for p in body],
                "hands_count": 1,
            },
            [],
        )
        assert pred_res["detected"] is True
        assert pred_res["name"] == "тест_жест"
        assert pred_res["confidence"] > 80.0
