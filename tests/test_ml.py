"""
Тесты алгоритмов машинного обучения: векторизованный DTW, адаптивные пороги, экспорт ONNX.
"""

import tempfile
from pathlib import Path

import numpy as np

from project_omilia import db
from project_omilia.gestures import (
    CURRICULUM_LEVELS,
    GESTURE_DEFINITIONS,
    DynamicGestures,
    dtw_distance,
    get_curriculum_level,
)
from project_omilia.ml.onnx_exporter import (
    export_classifier_metadata,
    export_onnx_model_bytes,
)


def test_dtw_distance_symmetry_and_identity():
    # Одинаковые последовательности дают нулевое расстояние
    seq_a = np.ones((10, 141), dtype=float)
    assert dtw_distance(seq_a, seq_a) == 0.0

    # Симметрия
    seq_b = np.full((12, 141), 2.0, dtype=float)
    dist_ab = dtw_distance(seq_a, seq_b)
    dist_ba = dtw_distance(seq_b, seq_a)
    assert np.isclose(dist_ab, dist_ba)
    assert dist_ab > 0.0


def test_dynamic_gestures_adaptive_threshold():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        engine = DynamicGestures(db_path)

        # Синтетические эталоны
        ref1 = np.ones((15, 141), dtype=float)
        ref2 = np.ones((15, 141), dtype=float) * 1.05
        ref3 = np.ones((15, 141), dtype=float) * 0.95

        threshold = engine.calculate_adaptive_threshold([ref1, ref2, ref3])
        assert threshold > 0.0
        assert threshold < 10.0


def test_onnx_model_exporter_generates_valid_binary():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)

        # Добавим тестовые сэмплы
        for name in ("привет", "да", "нет"):
            samples = []
            for _ in range(5):
                vec = np.random.randn(141).astype(np.float32)
                samples.append((name, 1, "[]", vec.tobytes()))
            db.insert_static_samples(db_path, samples)

        # Экспорт метаданных классификатора в JSON
        meta = export_classifier_metadata(db_path, hands_count=1)
        assert meta["status"] == "ok"
        assert meta["num_features"] == 141
        assert "привет" in meta["labels"]
        assert len(meta["centroids"]) == len(meta["labels"])

        # Экспорт бинарного файла ONNX
        onnx_bytes = export_onnx_model_bytes(db_path, hands_count=1)
        assert isinstance(onnx_bytes, bytes)
        assert len(onnx_bytes) > 500  # Модель содержит узлы Gemm, Softmax и тензоры весов


def test_curriculum_definitions_and_level_mapping():
    """Тестирование полноты словаря GESTURE_DEFINITIONS и функции get_curriculum_level для всех жестов Slovo."""
    lvl1 = ["а", "б", "в", "г", "д", "е", "и", "о", "с", "у"]
    lvl2 = ["1", "2", "3", "4", "5"]
    lvl3 = ["привет", "спасибо", "помоги", "пожалуйста", "да", "нет", "мир", "хорошо"]
    lvl4 = ["дом", "мама", "папа", "семья", "любовь", "стоп", "книга", "я", "ты"]

    assert len(CURRICULUM_LEVELS) == 4

    for name in lvl1:
        assert name in GESTURE_DEFINITIONS, f"Gesture '{name}' is missing in GESTURE_DEFINITIONS"
        defn = GESTURE_DEFINITIONS[name]
        assert defn.level == 1
        assert defn.level_title == "Дактильный алфавит"
        assert get_curriculum_level(name) == (1, "Дактильный алфавит")

    for name in lvl2:
        assert name in GESTURE_DEFINITIONS, f"Gesture '{name}' is missing in GESTURE_DEFINITIONS"
        defn = GESTURE_DEFINITIONS[name]
        assert defn.level == 2
        assert defn.level_title == "Числительные и счёт"
        assert get_curriculum_level(name) == (2, "Числительные и счёт")

    for name in lvl3:
        assert name in GESTURE_DEFINITIONS, f"Gesture '{name}' is missing in GESTURE_DEFINITIONS"
        defn = GESTURE_DEFINITIONS[name]
        assert defn.level == 3
        assert defn.level_title == "Базовый этикет"
        assert get_curriculum_level(name) == (3, "Базовый этикет")

    for name in lvl4:
        assert name in GESTURE_DEFINITIONS, f"Gesture '{name}' is missing in GESTURE_DEFINITIONS"
        defn = GESTURE_DEFINITIONS[name]
        assert defn.level == 4
        assert defn.level_title == "Семья и окружение"
        assert get_curriculum_level(name) == (4, "Семья и окружение")
