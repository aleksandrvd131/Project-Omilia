import json
import tempfile
from pathlib import Path

import numpy as np

from project_omilia import db, math
from project_omilia.gestures import DynamicGestures, StaticGesture, dtw_distance


def test_optimized_math_functions():
    v1 = np.array([3.0, 4.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])

    # 1. vec_len and p_dist
    assert np.isclose(math.vec_len(v1), 5.0)
    assert np.isclose(math.p_dist(v1, v2), np.sqrt(3**2 + 3**2))

    # 2. vec_normalize
    norm_v1 = math.vec_normalize(v1)
    assert np.isclose(np.linalg.norm(norm_v1), 1.0)
    assert np.allclose(norm_v1, [0.6, 0.8, 0.0])
    # Zero vector safety
    assert np.allclose(math.vec_normalize(np.zeros(3)), np.zeros(3))

    # 3. vec_angle and vec_norm_angle
    angle = math.vec_angle(np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    assert np.isclose(angle, np.pi / 2)
    norm_angle = math.vec_norm_angle(np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    assert np.isclose(norm_angle, 0.5)

    # 4. scalar_to_vec
    s_vec = math.scalar_to_vec(0.42)
    assert s_vec.shape == (3,)
    assert np.allclose(s_vec, [0.42, 0.42, 0.42])


def test_fast_dtw_distance():
    a = np.array([[0.0], [1.0], [2.0]])
    b = np.array([[0.0], [0.0], [1.0], [2.0]])
    c = np.array([[2.0], [1.0], [0.0]])

    assert dtw_distance(a, b) == 0.0
    assert dtw_distance(b, b) == 0.0
    assert dtw_distance(a, c) > 0.0

    # Test random higher-dimensional sequences
    seq1 = np.random.randn(8, 141)
    seq2 = np.random.randn(8, 141)
    dist = dtw_distance(seq1, seq2)
    assert isinstance(dist, float)
    assert dist >= 0.0
    assert dtw_distance(seq1, seq1) == 0.0


def test_static_gesture_confidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_ml.db"
        db.init_db(test_db)

        engine = StaticGesture(test_db, 1)

        # Generate synthetic samples for 2 gestures
        vec_privet = [np.random.normal(loc=1.0, scale=0.05, size=141) for _ in range(5)]
        vec_pomogi = [np.random.normal(loc=5.0, scale=0.05, size=141) for _ in range(5)]

        engine.add_samples("привет", vec_privet)
        engine.add_samples("помоги", vec_pomogi)

        # Test prediction with Pose vector directly (debug_flag=True)
        target = np.random.normal(loc=1.0, scale=0.04, size=141)
        code, score, prediction, confidence = engine.predict(target, debug_flag=True)

        assert code == 0
        assert prediction == "привет"
        assert confidence > 50.0
        assert score < 1.0

        # Test distant unknown gesture
        alien_target = np.random.normal(loc=100.0, scale=1.0, size=141)
        code_alien, score_alien, pred_alien, conf_alien = engine.predict(alien_target, debug_flag=True)
        assert code_alien == -2  # Distance exceeded threshold
        assert conf_alien == 0.0


def test_dynamic_gestures_adaptive_threshold_and_evaluation():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_dyn.db"
        db.init_db(test_db)

        dyn = DynamicGestures(test_db)

        # 4 reference samples of length 8 and dimension 141
        base_seq = np.sin(np.linspace(0, np.pi, 8))[:, None] * np.ones((8, 141))
        references = [base_seq + np.random.normal(scale=0.05, size=base_seq.shape) for _ in range(4)]

        # Adaptive threshold calculation
        threshold = dyn.calculate_adaptive_threshold(references)
        assert threshold > 0.0

        # Close attempt
        attempt_close = base_seq + np.random.normal(scale=0.04, size=base_seq.shape)
        accepted, details = dyn.evaluate(attempt_close, references)
        assert accepted is True
        assert details["confidence"] > 20.0

        # Distant attempt
        attempt_far = base_seq + np.random.normal(loc=10.0, scale=1.0, size=base_seq.shape)
        accepted_far, details_far = dyn.evaluate(attempt_far, references)
        assert accepted_far is False


def test_static_gesture_joblib_persistence_and_invalidation(monkeypatch):
    import joblib
    from sklearn.neighbors import KNeighborsClassifier

    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "omilia.db"
        db.init_db(test_db)

        engine = StaticGesture(test_db, 1)
        expected_joblib = Path(tmpdir) / "omilia_static_1h.joblib"
        assert engine.model_path == expected_joblib
        assert not expected_joblib.exists()

        vec_a = [np.full(141, 1.0, dtype=np.float32) for _ in range(4)]
        vec_b = [np.full(141, 5.0, dtype=np.float32) for _ in range(4)]
        engine.add_samples("привет", vec_a)
        engine.add_samples("помоги", vec_b)

        # После обучения модель должна сохраниться в .joblib
        assert expected_joblib.exists()
        saved_payload = joblib.load(expected_joblib)
        assert saved_payload["hands_count"] == 1
        assert isinstance(saved_payload["model"], KNeighborsClassifier)

        # Повторная инициализация должна загрузить модель из .joblib без повторного fit()
        def fail_fit(*args, **kwargs):
            raise AssertionError("KNeighborsClassifier.fit не должен вызываться при актуальном .joblib")

        monkeypatch.setattr(KNeighborsClassifier, "fit", fail_fit)
        cached_engine = StaticGesture(test_db, 1)
        code, _, pred, conf = cached_engine.predict(np.full(141, 1.0, dtype=np.float32), debug_flag=True)
        assert code == 0
        assert pred == "привет"
        assert conf > 90.0
        assert cached_engine.get_dataset_stats() == {"привет": 4, "помоги": 4}

        # Если БД изменилась (добавлен новый жест напрямую), кэш должен инвалидироваться и переобучиться
        monkeypatch.undo()
        vec_c = np.full(141, 9.0, dtype=np.float32)
        db.insert_static_samples(test_db, [("спасибо", 1, json.dumps(vec_c.tolist()), vec_c.tobytes())] * 3)
        refreshed_engine = StaticGesture(test_db, 1)
        code_c, _, pred_c, _ = refreshed_engine.predict(vec_c, debug_flag=True)
        assert code_c == 0
        assert pred_c == "спасибо"

        # Повреждённый .joblib не должен ломать запуск — модель переобучается из БД
        expected_joblib.write_bytes(b"corrupted joblib payload")
        recovered_engine = StaticGesture(test_db, 1)
        code_rec, _, pred_rec, _ = recovered_engine.predict(vec_c, debug_flag=True)
        assert code_rec == 0
        assert pred_rec == "спасибо"

        # Если все данные удалены, устаревший .joblib должен удаляться
        for name in ("привет", "помоги", "спасибо"):
            db.delete_gesture(test_db, name)
        engine.reload()
        assert engine.model is None
        assert not expected_joblib.exists()


def test_dynamic_gestures_joblib_persistence_and_invalidation(monkeypatch):
    import joblib

    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "omilia.db"
        db.init_db(test_db)

        dyn = DynamicGestures(test_db)
        expected_joblib = Path(tmpdir) / "omilia_dynamic.joblib"
        assert dyn.model_path == expected_joblib
        assert not expected_joblib.exists()

        base_seq = np.sin(np.linspace(0, np.pi, 8))[:, None] * np.ones((8, 141))
        for i in range(3):
            dyn.add_sample("привет", base_seq + 0.02 * i)

        # Кэш динамики и предвычисленный порог должны сохраниться в .joblib
        assert expected_joblib.exists()
        saved_payload = joblib.load(expected_joblib)
        assert ("привет", 1) in saved_payload["samples"]
        assert ("привет", 1) in saved_payload["adaptive_thresholds"]
        expected_threshold = saved_payload["adaptive_thresholds"][("привет", 1)]

        # Повторный запуск должен загружать массивы и пороги из .joblib без json.loads и пересчёта DTW
        def fail_json_loads(*args, **kwargs):
            raise AssertionError("json.loads не должен вызываться при актуальном dynamic .joblib")

        def fail_threshold(self, *args, **kwargs):
            raise AssertionError("calculate_adaptive_threshold не должен вызываться при актуальном кэше")

        monkeypatch.setattr(json, "loads", fail_json_loads)
        monkeypatch.setattr(DynamicGestures, "calculate_adaptive_threshold", fail_threshold)

        cached_dyn = DynamicGestures(test_db)
        refs = cached_dyn.get_samples("привет", 1)
        assert len(refs) == 3
        assert cached_dyn.get_adaptive_threshold("привет", 1, refs) == expected_threshold

        # Прямое изменение БД должно инвалидировать кэш и пересобрать .joblib
        monkeypatch.undo()
        other_seq = np.ones((8, 141), dtype=float) * 3.0
        for _ in range(3):
            db.insert_dynamic_sample(test_db, "пока", 1, json.dumps(other_seq.tolist()), limit=10)

        refs_other = cached_dyn.get_samples("пока", 1)
        assert len(refs_other) == 3
        assert ("пока", 1) in cached_dyn.adaptive_thresholds

        # Повреждённый .joblib должен восстанавливаться из БД
        expected_joblib.write_bytes(b"corrupted dynamic joblib")
        recovered_dyn = DynamicGestures(test_db)
        assert len(recovered_dyn.get_samples("пока", 1)) == 3
        assert expected_joblib.exists()

        # Удаление всех динамических жестов должно удалять устаревший .joblib
        for name in ("привет", "пока"):
            db.delete_gesture(test_db, name)
        recovered_dyn.reload()
        assert not expected_joblib.exists()
