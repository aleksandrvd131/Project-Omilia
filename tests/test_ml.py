"""
Тесты алгоритмов машинного обучения: векторизованный DTW, адаптивные пороги, экспорт ONNX.
"""

import tempfile
from pathlib import Path

import numpy as np

from project_omilia import db
from project_omilia.gestures import DynamicGestures, dtw_distance
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
