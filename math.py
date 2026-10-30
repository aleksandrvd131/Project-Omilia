import numpy as np

EPS: float = 1e-7


def vec_len(a: np.ndarray) -> float:
    return float(np.linalg.norm(a))


def p_dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def vec_normalize(a: np.ndarray) -> np.ndarray:
    length = vec_len(a)
    if length < EPS:
        return np.zeros_like(a)
    return a / length


def vec_angle(a: np.ndarray, b: np.ndarray) -> float:
    len_a = vec_len(a)
    len_b = vec_len(b)
    if len_a < EPS or len_b < EPS:
        return 0.0
    cos_theta = np.clip(np.dot(a, b) / (len_a * len_b), -1.0, 1.0)
    return float(np.arccos(cos_theta))


def vec_norm_angle(a: np.ndarray, b: np.ndarray) -> float:
    return vec_angle(a, b) / np.pi


def scalar_to_vec(a: float) -> np.ndarray:
    return np.array((a, a, a), dtype=np.float32)
