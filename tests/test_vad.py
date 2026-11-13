"""
Тестирование оптимизации DTW с полосовым окном Сакое-Чиба (Sakoe-Chiba band)
и детекции активности жестов (Gesture Activity Detection / VAD).
"""

import subprocess
import time
from pathlib import Path

import numpy as np
import pytest

from project_omilia.services.dynamic_service import (
    DynamicGestureServer,
    dtw_distance,
    sakoe_chiba_dtw,
)


def test_sakoe_chiba_dtw_identity():
    """Идентичные последовательности дают нулевое расстояние."""
    seq1 = np.random.randn(8, 141)
    assert sakoe_chiba_dtw(seq1, seq1) == 0.0
    assert dtw_distance(seq1, seq1) == 0.0

    seq_1d = np.array([1.0, 2.0, 3.0, 4.0])
    assert sakoe_chiba_dtw(seq_1d, seq_1d) == 0.0


def test_sakoe_chiba_dtw_symmetry():
    """Симметричность расстояния DTW при равной и разной длине последовательностей."""
    seq_a = np.random.randn(8, 141)
    seq_b = np.random.randn(8, 141)
    dist_ab = sakoe_chiba_dtw(seq_a, seq_b)
    dist_ba = sakoe_chiba_dtw(seq_b, seq_a)
    assert np.isclose(dist_ab, dist_ba)
    assert dist_ab > 0.0

    # Разная длина последовательностей
    seq_short = np.random.randn(6, 141)
    seq_long = np.random.randn(10, 141)
    dist_sl = sakoe_chiba_dtw(seq_short, seq_long)
    dist_ls = sakoe_chiba_dtw(seq_long, seq_short)
    assert np.isclose(dist_sl, dist_ls)
    assert dist_sl > 0.0


def test_sakoe_chiba_penalizes_extreme_time_warping():
    """Окно Сакое-Чиба штрафует экстремальные временные сдвиги (time-warping artifacts).

    Если жест произошёл в первой половине клипа A (кадры 2..3),
    а в клипе B во второй половине (кадры 7..8), unconstrained DTW нереалистично
    сопоставляет их с расстоянием 0.0. Окно Сакое-Чиба (r = 2) запрещает экстремальный
    сдвиг через весь клип (|2 - 7| = 5 > 2) и штрафует артефакт.
    """
    length = 10
    seq_a = np.zeros((length, 141), dtype=np.float64)
    seq_a[2:4, :] = 5.0  # Жест в первой половине клипа

    seq_b = np.zeros((length, 141), dtype=np.float64)
    seq_b[7:9, :] = 5.0  # Жест во второй половине клипа

    # При широком окне (вырождение в unconstrained DTW) промежуточный жест сопоставляется
    unconstrained_dist = sakoe_chiba_dtw(seq_a, seq_b, radius=10)

    # При узком окне Сакое-Чиба (r = 2) экстремальный сдвиг запрещён
    constrained_dist = sakoe_chiba_dtw(seq_a, seq_b, radius=2)

    assert unconstrained_dist == 0.0
    assert constrained_dist > 5.0


def test_sakoe_chiba_speedup():
    """Сопоставление с окном Сакое-Чиба работает в разы быстрее полного перебора."""
    seq_a = np.random.randn(16, 141)
    seq_b = np.random.randn(16, 141)

    # Замер времени полного перебора (r = 16)
    t0 = time.perf_counter()
    for _ in range(150):
        sakoe_chiba_dtw(seq_a, seq_b, radius=16)
    t_full = time.perf_counter() - t0

    # Замер времени с полосой Сакое-Чиба (r = 2)
    t0 = time.perf_counter()
    for _ in range(150):
        sakoe_chiba_dtw(seq_a, seq_b, radius=2)
    t_band = time.perf_counter() - t0

    # Векторизованный band DTW выполняется быстрее
    assert t_band < t_full
    assert t_band < 0.2  # Должен отрабатывать быстрее 200 мс на 150 пар


def test_sakoe_chiba_input_validation():
    """Проверка валидации некорректных данных."""
    # Пустые последовательности
    empty = np.empty((0, 141))
    assert sakoe_chiba_dtw(empty, empty) == 0.0

    # Несовпадающие размерности признаков
    s1 = np.ones((8, 141))
    s2 = np.ones((8, 282))
    with pytest.raises(ValueError, match="Несовпадающая размерность"):
        sakoe_chiba_dtw(s1, s2)

    # Неконечные значения (NaN, Inf)
    bad_seq = np.ones((8, 141))
    bad_seq[2, 5] = np.nan
    with pytest.raises(ValueError, match="некорректные значения"):
        sakoe_chiba_dtw(bad_seq, s1)


def test_dynamic_gesture_server_dtw_integration(tmp_path: Path):
    """Интеграция Sakoe-Chiba DTW с DynamicGestureServer."""
    from project_omilia import db

    test_db = tmp_path / "test_vad.db"
    db.init_db(test_db)

    server = DynamicGestureServer(test_db)
    assert hasattr(server, "sakoe_chiba_dtw")
    assert hasattr(server, "dtw_distance")

    s1 = np.random.randn(8, 141)
    s2 = np.random.randn(8, 141)
    dist = server.dtw_distance(s1, s2)
    assert isinstance(dist, float)
    assert dist >= 0.0


def test_frontend_motion_vad_node_suite():
    """Прогон Node.js тестов VAD и динамического клипа."""
    project_root = Path(__file__).resolve().parent.parent
    js_test_code = """
    const fs = require('node:fs');
    const vm = require('node:vm');
    const assert = require('node:assert/strict');

    const source = 'src/project_omilia/frontend/dynamic-clip.js';
    const window = {};
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), { window });
    const { estimateWristVelocity, detectMotionSegment, selectFrames } = window.omiliaDynamicClip;

    // 1. Тест оценки скорости запястья: velocity = hypot(dx, dy) / dt
    assert.equal(estimateWristVelocity(0.06, 0.08, 100), 0.001);
    assert.equal(estimateWristVelocity(0, 0, 100), 0);

    // 2. Тест отсечения статического начала и конца (Gesture Activity Detection)
    function makeFrame(t, x, y) {
      const hand = Array.from({ length: 21 }, (_, i) => ({
        x: i === 0 ? x : x + 0.02,
        y: i === 0 ? y : y + 0.02,
        z: 0
      }));
      const pose = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
      return { t_ms: t, hands_data: [hand], pose_landmarks: pose };
    }

    const frames = [];
    // Статика в начале: t = 0..200 ms (рука неподвижна в точке 0.2, 0.5)
    for (let t = 0; t <= 200; t += 40) frames.push(makeFrame(t, 0.2, 0.5));
    // Активный динамический жест: t = 240..680 ms (рука движется от 0.2 до 0.8)
    for (let t = 240; t <= 680; t += 40) {
      const alpha = (t - 240) / 440;
      frames.push(makeFrame(t, 0.2 + alpha * 0.6, 0.5));
    }
    // Статика в конце: t = 720..960 ms (рука неподвижна в точке 0.8, 0.5)
    for (let t = 720; t <= 960; t += 40) frames.push(makeFrame(t, 0.8, 0.5));

    // Проверяем детектор диапазона активности
    const segment = detectMotionSegment(frames);
    assert.ok(segment !== null, 'VAD segment must be detected');
    assert.ok(segment.startMs >= 160 && segment.startMs <= 280);
    assert.ok(segment.endMs >= 640 && segment.endMs <= 760);

    // Проверяем, что selectFrames сфокусировался на фазе активного движения
    const selected = selectFrames(frames, 1);
    assert.equal(selected.length, 8);
    // Все выбранные кадры должны принадлежать сегменту жеста, а не статике на краях
    const activeSelected = selected.filter(f => f.t_ms >= 200 && f.t_ms <= 720);
    assert.ok(activeSelected.length >= 7, 'Selected frames must focus on dynamic motion');
    """

    result = subprocess.run(
        ["node", "-e", js_test_code],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Node VAD test failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
