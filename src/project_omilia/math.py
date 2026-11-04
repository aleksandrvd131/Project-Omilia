import numpy as np

EPS: float = 1e-8


def vec_len(A: np.ndarray) -> float:
    return float(np.sqrt(A[0] ** 2 + A[1] ** 2 + A[2] ** 2))


def p_dist(A: np.ndarray, B: np.ndarray) -> float:
    return vec_len(A - B)


def vec_normalize(A: np.ndarray) -> np.ndarray:
    len_A = vec_len(A)
    if len_A < EPS:
        return np.zeros_like(A, dtype=float)
    return A / len_A


def vec_angle(A: np.ndarray, B: np.ndarray) -> float:
    len_A = vec_len(A)
    len_B = vec_len(B)
    if len_A < EPS or len_B < EPS:
        return 0.0
    cos_val = np.clip(np.dot(A, B) / (len_A * len_B), -1.0, 1.0)
    return float(np.arccos(cos_val))


def vec_norm_angle(A: np.ndarray, B: np.ndarray) -> float:
    return vec_angle(A, B) / np.pi


def scalar_to_vec(A: float) -> np.ndarray:
    return np.array((A, A, A), dtype=float)
