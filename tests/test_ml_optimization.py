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
