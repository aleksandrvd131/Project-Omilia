import numpy as np

EPS: float = 1e-8


def vec_len(A: np.ndarray) -> float:
    """Вычисляет длину вектора."""
    return float(np.linalg.norm(A))


def p_dist(A: np.ndarray, B: np.ndarray) -> float:
    """Евклидово расстояние между двумя точками."""
    return vec_len(A - B)


def vec_normalize(A: np.ndarray) -> np.ndarray:
    """Нормализует вектор к единичной длине с защитой от деления на ноль."""
    norm = vec_len(A)
    if norm < EPS:
        return np.zeros_like(A, dtype=float)
    return A / norm


def vec_angle(A: np.ndarray, B: np.ndarray) -> float:
    """Вычисляет угол между двумя векторами в радианах."""
    len_a = vec_len(A)
    len_b = vec_len(B)
    if len_a < EPS or len_b < EPS:
        return 0.0
    cos_val = np.clip(np.dot(A, B) / (len_a * len_b), -1.0, 1.0)
    return float(np.arccos(cos_val))


def vec_norm_angle(A: np.ndarray, B: np.ndarray) -> float:
    """Нормализованный угол в диапазоне [0, 1]."""
    return vec_angle(A, B) / np.pi


def scalar_to_vec(A: float) -> np.ndarray:
    """Преобразует скаляр в 3D-вектор (A, A, A) для согласования размерности признаков."""
    return np.full(3, A, dtype=float)
