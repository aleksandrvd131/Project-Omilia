import numpy as np
from project_omilia.errors import IncorrectDataError

EPS: float = 1e-8

def vec_len(A: np.ndarray) -> float:
    return np.sqrt(A[0] ** 2 + A[1] ** 2 + A[2] ** 2)

def dot_dist(A: np.ndarray, B: np.ndarray) -> float:
    return vec_len(A - B)

def vec_normalize(A: np.ndarray) -> np.ndarray:
    len_A = vec_len(A)
    if len_A < EPS:
        raise IncorrectDataError(
            "Division by zero while trying to normalize vector.\n"
        )
    return A / vec_len(A)

def vec_angle(A: np.ndarray, B: np.ndarray) -> float:
    len_A = vec_len(A)
    len_B = vec_len(B)
    if len_A < EPS or len_B < EPS:
        raise IncorrectDataError(
            "Division by zero while trying to calculate angle between vectors.\n"
        )
    return np.arccos(np.clip(np.dot(A, B) / (len_A * len_B), -1.0, 1.0))

def vec_norm_angle(A: np.ndarray, B: np.ndarray) -> float:
    return vec_angle(A, B) / np.pi
