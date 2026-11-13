"""
Тесты интеграции набора данных Slovo RSL в SQLite базу данных и модели StaticGesture.
"""

import json

from project_omilia import db
from project_omilia.core.config import DATASET_PATH_1H, DATASET_PATH_2H, DB_PATH
from project_omilia.gestures import StaticGesture
from project_omilia.ml.slovo_generator import (
    SLOVO_GESTURES,
    generate_canonical_vector,
)


def test_slovo_gestures_in_sqlite_db():
    """Проверяет наличие метаданных всех жестов Slovo в таблице gestures."""
    all_gestures = db.get_all_gestures(DB_PATH)
    gesture_map = {g["name"]: g for g in all_gestures}

    for name, sdef in SLOVO_GESTURES.items():
        assert name in gesture_map, f"Жест '{name}' отсутствует в таблице gestures"
        entry = gesture_map[name]
        assert entry["hands_count"] == sdef.hands_count
        assert entry["is_dynamic"] == 0
        assert len(entry["title"]) > 0
        assert len(entry["category"]) > 0


def test_slovo_samples_in_sqlite_db():
    """Проверяет наличие не менее 20 сэмплов для каждого жеста Slovo в static_gesture_samples."""
    samples_1h = db.get_static_samples(DB_PATH, hands_count=1)
    samples_2h = db.get_static_samples(DB_PATH, hands_count=2)

    counts_1h: dict[str, int] = {}
    for row in samples_1h:
        counts_1h[row["gesture_name"]] = counts_1h.get(row["gesture_name"], 0) + 1

    counts_2h: dict[str, int] = {}
    for row in samples_2h:
        counts_2h[row["gesture_name"]] = counts_2h.get(row["gesture_name"], 0) + 1

    for name, sdef in SLOVO_GESTURES.items():
        if sdef.hands_count == 1:
            assert name in counts_1h, f"Жест '{name}' (1 рука) отсутствует в static_gesture_samples"
            assert counts_1h[name] >= 20, f"Жест '{name}' имеет {counts_1h[name]} сэмплов (< 20)"
        else:
            assert name in counts_2h, f"Жест '{name}' (2 руки) отсутствует в static_gesture_samples"
            assert counts_2h[name] >= 20, f"Жест '{name}' имеет {counts_2h[name]} сэмплов (< 20)"


def test_static_gesture_models_reload_and_classification():
    """Проверяет перезагрузку StaticGesture(DB_PATH, 1) и StaticGesture(DB_PATH, 2) и точность классификации."""
    model_1h = StaticGesture(DB_PATH, hands_count=1)
    assert model_1h.model is not None, "Модель StaticGesture для 1 руки не обучена"
    assert len(model_1h.dataset) >= 17

    model_2h = StaticGesture(DB_PATH, hands_count=2)
    assert model_2h.model is not None, "Модель StaticGesture для 2 рук не обучена"
    assert "дом" in model_2h.dataset
    assert "книга" in model_2h.dataset

    # Проверка точности классификации канонических векторов
    for name, sdef in SLOVO_GESTURES.items():
        can_vec = generate_canonical_vector(name).reshape(1, -1)
        if sdef.hands_count == 1:
            pred = model_1h.model.predict(can_vec)[0]
            assert pred == name, f"1-ручный жест '{name}' классифицирован как '{pred}'"
        else:
            pred = model_2h.model.predict(can_vec)[0]
            assert pred == name, f"2-ручный жест '{name}' классифицирован как '{pred}'"


def test_json_datasets_consistency():
    """Проверяет целостность и согласованность omilia_static_1h.json и omilia_static_2h.json."""
    assert DATASET_PATH_1H.is_file()
    assert DATASET_PATH_2H.is_file()

    with open(DATASET_PATH_1H, "r", encoding="utf-8") as f:
        data_1h = json.load(f)

    with open(DATASET_PATH_2H, "r", encoding="utf-8") as f:
        data_2h = json.load(f)

    for name, sdef in SLOVO_GESTURES.items():
        if sdef.hands_count == 1:
            assert name in data_1h, f"Жест '{name}' отсутствует в omilia_static_1h.json"
            samples = data_1h[name]
            assert len(samples) >= 20
            for vec in samples:
                assert len(vec) == 141
        else:
            assert name in data_2h, f"Жест '{name}' отсутствует в omilia_static_2h.json"
            samples = data_2h[name]
            assert len(samples) >= 20
            for vec in samples:
                assert len(vec) == 282
