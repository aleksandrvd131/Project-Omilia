"""
Модуль аугментации данных статических жестов (Static Gesture Data Augmentation).

Позволяет формировать физически корректные вариации биометрических признаков
для повышения устойчивости классификатора k-NN к естественному разбросу положения рук,
наклону кисти и шуму детекции MediaPipe:
1. Масштабирование (scale jitter: ±6..8%)
2. 2D-поворот в плоскости камеры вокруг оси Z (rotation jitter: ±3..5 градусов)
3. Микро-шум сенсора (Gaussian noise: sigma=0.003..0.005)
"""

import numpy as np


def _rotate_and_scale_vec3(
    vec: np.ndarray,
    cos_t: float,
    sin_t: float,
    scale: float,
) -> np.ndarray:
    """Поворачивает 3D-вектор вокруг оси Z на угол (cos, sin) и масштабирует."""
    rx = scale * (vec[0] * cos_t - vec[1] * sin_t)
    ry = scale * (vec[0] * sin_t + vec[1] * cos_t)
    rz = scale * vec[2]
    return np.array([rx, ry, rz], dtype=np.float32)


def _rotate_normal(vec: np.ndarray, cos_t: float, sin_t: float) -> np.ndarray:
    """Поворачивает единичный вектор нормали ладони вокруг оси Z."""
    rx = vec[0] * cos_t - vec[1] * sin_t
    ry = vec[0] * sin_t + vec[1] * cos_t
    rz = vec[2]
    norm = np.hypot(np.hypot(rx, ry), rz)
    if norm < 1e-8:
        return np.array([0.0, 0.0, 1.0], dtype=np.float32)
    return np.array([rx / norm, ry / norm, rz / norm], dtype=np.float32)


def augment_static_vector(
    vector: np.ndarray,
    scale: float = 1.0,
    angle_deg: float = 0.0,
    noise_sigma: float = 0.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Генерирует вариацию вектора признаков (141 или 282 элемента).

    Параметры:
        vector: одномерный массив float32 длины 141 (1 рука) или 282 (2 руки).
        scale: коэффициент масштабирования расстояний (например, 0.95 .. 1.05).
        angle_deg: угол поворота в плоскости камеры вокруг оси Z в градусах.
        noise_sigma: стандартное отклонение аддитивного гауссова шума.
        rng: генератор случайных чисел numpy.
    """
    vec = np.asarray(vector, dtype=np.float32).copy()
    dim = len(vec)
    if dim not in (141, 282):
        raise ValueError(f"Неподдерживаемая размерность вектора для аугментации: {dim} (ожидается 141 или 282)")

    if rng is None:
        rng = np.random.default_rng()

    rad = np.deg2rad(angle_deg)
    cos_t = float(np.cos(rad))
    sin_t = float(np.sin(rad))

    def process_hand(offset: int) -> None:
        # 1. 20 векторов фаланг (индексы offset + 0..59)
        for i in range(20):
            idx = offset + i * 3
            vec[idx : idx + 3] = _rotate_and_scale_vec3(vec[idx : idx + 3], cos_t, sin_t, scale)

        # 2. Нормаль ладони (индексы offset + 60..62)
        n_idx = offset + 60
        vec[n_idx : n_idx + 3] = _rotate_normal(vec[n_idx : n_idx + 3], cos_t, sin_t)

        # 3. Признаки формы (индексы offset + 63..134): углы и расстояния
        # Углы и расстояния инвариантны к жесткому вращению/масштабированию,
        # поэтому здесь накладывается только легкий шум сенсора
        pass

    if dim == 141:
        # Обработка правой руки
        process_hand(0)

        # 4. Векторы смещения относительно носа (135..137) и груди (138..140)
        vec[135:138] = _rotate_and_scale_vec3(vec[135:138], cos_t, sin_t, scale)
        vec[138:141] = _rotate_and_scale_vec3(vec[138:141], cos_t, sin_t, scale)

    else:
        # Режим 2 рук: 0..134 правая рука, 135..269 левая рука
        process_hand(0)
        process_hand(135)

        # Смещения к носу и груди для обеих рук (270..281)
        vec[270:273] = _rotate_and_scale_vec3(vec[270:273], cos_t, sin_t, scale)
        vec[273:276] = _rotate_and_scale_vec3(vec[273:276], cos_t, sin_t, scale)
        vec[276:279] = _rotate_and_scale_vec3(vec[276:279], cos_t, sin_t, scale)
        vec[279:282] = _rotate_and_scale_vec3(vec[279:282], cos_t, sin_t, scale)

    # Добавление гауссова шума сенсора
    if noise_sigma > 0:
        noise = rng.normal(loc=0.0, scale=noise_sigma, size=dim).astype(np.float32)
        vec += noise

    return np.round(vec, 8).astype(np.float32)


def augment_static_samples(
    samples: list[np.ndarray],
    num_augmented_per_sample: int = 2,
    scale_range: tuple[float, float] = (0.94, 1.06),
    angle_deg_range: tuple[float, float] = (-4.0, 4.0),
    noise_sigma: float = 0.004,
    seed: int | None = None,
) -> list[np.ndarray]:
    """Аугментирует список эталонов статического жеста.

    Возвращает список, включающий как исходные сэмплы, так и синтезированные
    вариации с вариацией масштаба, угла поворота и сенсорного микро-шума.
    """
    if not samples:
        return []

    rng = np.random.default_rng(seed)
    result: list[np.ndarray] = [np.asarray(s, dtype=np.float32).copy() for s in samples]

    for sample in samples:
        for _ in range(num_augmented_per_sample):
            scale = float(rng.uniform(scale_range[0], scale_range[1]))
            angle_deg = float(rng.uniform(angle_deg_range[0], angle_deg_range[1]))
            aug = augment_static_vector(
                sample,
                scale=scale,
                angle_deg=angle_deg,
                noise_sigma=noise_sigma,
                rng=rng,
            )
            result.append(aug)

    return result


# Псевдоним для удобства интеграции
augment_sample = augment_static_vector

