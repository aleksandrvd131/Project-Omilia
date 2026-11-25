"""Единый DTW с ограничением растяжения времени для динамических жестов."""

import numpy as np


def dtw_distance(
    seq1: np.ndarray,
    seq2: np.ndarray,
    radius: int | None = None,
) -> float:
    """Вычисляет расстояние DTW с полосовым окном Сакое-Чиба (Sakoe-Chiba band).

    Радиус окна: r = max(|len(seq1) - len(seq2)|, max(1, int(0.2 * max(len(seq1), len(seq2)))))
    Ограничение полосы окна:
    - Ограничивает допустимое растяжение последовательностей по времени;
    - Штрафует экстремальные временные деформации (time-warping artifacts).
    """
    s1 = np.asarray(seq1, dtype=np.float64)
    s2 = np.asarray(seq2, dtype=np.float64)

    if not np.isfinite(s1).all() or not np.isfinite(s2).all():
        raise ValueError("Последовательности для DTW содержат некорректные значения (NaN или Inf).")

    if s1.ndim == 1:
        s1 = s1[:, None]
    if s2.ndim == 1:
        s2 = s2[:, None]

    n, m = len(s1), len(s2)
    if n == 0 or m == 0:
        return 0.0

    if s1.shape[-1] != s2.shape[-1]:
        raise ValueError(f"Несовпадающая размерность признаков кадров: {s1.shape[-1]} != {s2.shape[-1]}.")

    len_diff = abs(n - m)
    if radius is None:
        band_radius = max(len_diff, max(1, int(0.2 * max(n, m))))
    else:
        band_radius = max(len_diff, int(radius))

    # Векторизованный расчёт попарных квадратичных расстояний через broadcasting
    diff = s1[:, None, :] - s2[None, :, :]
    dist_sq = np.sum(diff * diff, axis=-1)

    # Таблица динамического программирования с граничными условиями
    dp = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    dp[0, 0] = 0.0

    for i in range(1, n + 1):
        j_start = max(1, i - band_radius)
        j_end = min(m, i + band_radius)
        for j in range(j_start, j_end + 1):
            cost = dist_sq[i - 1, j - 1]
            prev = min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
            dp[i, j] = cost + prev

    return float(np.sqrt(dp[n, m]))
