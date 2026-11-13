"""
Тесты генератора анатомических моделей жестов РЖЯ (Slovo RSL Dataset).

Проверяет:
1. Топологию ключевых точек MediaPipe (21 точка на кисть, координаты в [0, 1]).
2. Корректность извлечения векторов признаков (141 для 1 руки, 282 для 2 рук).
3. Межклассовую разделимость (расстояния между всеми жестами > 0.5).
4. Точность классификации k-NN на аугментированных сэмплах (100% точность).
5. Корректность формирования записей для базы данных SQLite.
"""

import json

import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from project_omilia.ml.slovo_generator import (
    SLOVO_GESTURES,
    build_db_records,
    build_gesture_metadata_records,
    generate_augmented_samples,
    generate_canonical_vector,
    get_all_slovo_gestures,
    get_slovo_gesture,
    get_slovo_landmarks,
)

EXPECTED_GESTURES_1H = [
    # Level 1: Дактильный алфавит (все 33 буквы: а-я)
    "а",
    "б",
    "в",
    "г",
    "д",
    "е",
    "ё",
    "ж",
    "з",
    "и",
    "й",
    "к",
    "л",
    "м",
    "н",
    "о",
    "п",
    "р",
    "с",
    "т",
    "у",
    "ф",
    "х",
    "ц",
    "ч",
    "ш",
    "щ",
    "ъ",
    "ы",
    "ь",
    "э",
    "ю",
    "я",
    # Level 2: Числительные и счёт
    "1",
    "2",
    "3",
    "4",
    "5",
    # Level 3 & 4: Повседневные жесты
    "хорошо",
    "мир",
    "любовь",
    "стоп",
]

EXPECTED_GESTURES_2H = ["книга"]


def test_slovo_gestures_presence_and_topology():
    """Проверяет присутствие всех 43 жестов (33 буквы дактиля) и валидность 21 ключевой точки MediaPipe."""
    all_gestures = get_all_slovo_gestures()
    expected_all = set(EXPECTED_GESTURES_1H + EXPECTED_GESTURES_2H)

    assert set(all_gestures.keys()) == expected_all
    assert len(all_gestures) == 43

    for name, g in all_gestures.items():
        assert get_slovo_gesture(name) == g
        assert get_slovo_landmarks(name) == g.hands_landmarks
        assert g.name == name
        assert g.level in (1, 2, 3, 4)
        assert len(g.level_title) > 0
        assert len(g.category) > 0
        assert len(g.description) > 0
        assert len(g.tip) > 0

        if name in EXPECTED_GESTURES_2H:
            assert g.hands_count == 2
            assert len(g.hands_landmarks) == 2
        else:
            assert g.hands_count == 1
            assert len(g.hands_landmarks) == 1

        for hand in g.hands_landmarks:
            assert len(hand) == 21, f"Жест '{name}' содержит {len(hand)} точек вместо 21"
            for idx, pt in enumerate(hand):
                assert "x" in pt and "y" in pt and "z" in pt
                x, y, z = pt["x"], pt["y"], pt["z"]
                assert 0.0 <= x <= 1.0, f"Точка {idx} кисти жеста '{name}' x={x} выходит за [0, 1]"
                assert 0.0 <= y <= 1.0, f"Точка {idx} кисти жеста '{name}' y={y} выходит за [0, 1]"
                assert -0.5 <= z <= 0.5, f"Точка {idx} кисти жеста '{name}' z={z} выходит за пределы"


def test_slovo_feature_vectors_dimensions_and_finiteness():
    """Проверяет размерность векторов признаков: 141 (1 рука) и 282 (2 руки)."""
    for name in EXPECTED_GESTURES_1H:
        vec = generate_canonical_vector(name)
        assert vec.shape == (141,), f"Вектор для '{name}' имеет размер {vec.shape}"
        assert vec.dtype == np.float32
        assert np.isfinite(vec).all(), f"Вектор для '{name}' содержит нечисловые значения"

    for name in EXPECTED_GESTURES_2H:
        vec = generate_canonical_vector(name)
        assert vec.shape == (282,), f"Вектор для '{name}' имеет размер {vec.shape}"
        assert vec.dtype == np.float32
        assert np.isfinite(vec).all(), f"Вектор для '{name}' содержит нечисловые значения"


def test_slovo_pairwise_class_separation():
    """Проверяет, что все жесты геометрически различимы (минимальное расстояние > 0.5)."""
    vecs_1h = {name: generate_canonical_vector(name) for name in EXPECTED_GESTURES_1H}
    names = list(vecs_1h.keys())

    min_dist = float("inf")
    closest_pair = None

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            d = float(np.linalg.norm(vecs_1h[n1] - vecs_1h[n2]))
            if d < min_dist:
                min_dist = d
                closest_pair = (n1, n2)

    assert min_dist > 0.5, f"Слишком близкие жесты: {closest_pair} (расстояние {min_dist:.4f})"


def test_slovo_knn_classification_with_augmentation():
    """Проверяет классификацию k-NN на аугментированном наборе (100% точность)."""
    samples: list[np.ndarray] = []
    labels: list[str] = []

    for name in EXPECTED_GESTURES_1H:
        aug_samples = generate_augmented_samples(name, num_samples=15, seed=42)
        assert len(aug_samples) == 15
        for s in aug_samples:
            samples.append(s)
            labels.append(name)

    X = np.array(samples)
    y = np.array(labels)

    knn = KNeighborsClassifier(n_neighbors=3, weights="distance")
    knn.fit(X, y)
    preds = knn.predict(X)
    acc = np.mean(preds == y)
    assert acc == 1.0, f"Точность классификации на обучающей выборке: {acc:.2%}"


def test_slovo_db_records_generation():
    """Проверяет генерацию записей базы данных SQLite для dataset_builder."""
    records = build_db_records(num_augmented_per_gesture=10, seed=123)
    assert len(records) == 10 * 43

    for name, hands_count, features_json, features_blob in records:
        assert name in SLOVO_GESTURES
        expected_dim = 141 if hands_count == 1 else 282

        # Проверка JSON
        parsed = json.loads(features_json)
        assert len(parsed) == expected_dim

        # Проверка BLOB
        from_blob = np.frombuffer(features_blob, dtype=np.float32)
        assert len(from_blob) == expected_dim
        assert np.allclose(parsed, from_blob, atol=1e-5)

    meta_records = build_gesture_metadata_records()
    assert len(meta_records) == 43
    for rec in meta_records:
        assert rec[0] in SLOVO_GESTURES
        assert rec[7] in (1, 2)  # hands_count
        assert rec[8] == 0  # is_dynamic = False
