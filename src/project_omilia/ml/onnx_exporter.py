"""
Модуль экспорта классификатора статических жестов в формат ONNX и легковесных весов.
Позволяет запускать инференс напрямую в браузере через onnxruntime-web с нулевой сетевой задержкой (0ms ping).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import numpy as np

from project_omilia import db

# ==========================================================
# Вспомогательный чистый сериализатор Protobuf для ONNX (IR-8 / Opset-17)
# Позволяет генерировать валидные .onnx файлы без внешних тяжёлых зависимостей protobuf
# ==========================================================


def _varint(val: int) -> bytes:
    """Кодирование целого числа в Protobuf Varint."""
    if val < 0:
        val = (1 << 64) + val
    res = bytearray()
    while val >= 0x80:
        res.append((val & 0x7F) | 0x80)
        val >>= 7
    res.append(val & 0x7F)
    return bytes(res)


def _tag(field_number: int, wire_type: int) -> bytes:
    return _varint((field_number << 3) | wire_type)


def _field_int(field: int, val: int) -> bytes:
    if val == 0:
        return b""
    return _tag(field, 0) + _varint(val)


def _field_string(field: int, s: str) -> bytes:
    data = s.encode("utf-8")
    return _tag(field, 2) + _varint(len(data)) + data


def _field_bytes(field: int, b: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(b)) + b


def _field_msg(field: int, msg: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(msg)) + msg


def _tensor_proto(name: str, shape: list[int], data: np.ndarray) -> bytes:
    """Сериализует тензор FLOAT32 в TensorProto."""
    # dims (field 1: packed int64 varints)
    dims_bytes = b"".join(_varint(d) for d in shape)
    payload = _tag(1, 2) + _varint(len(dims_bytes)) + dims_bytes
    # data_type = 1 (FLOAT) (field 2)
    payload += _tag(2, 0) + _varint(1)
    # name (field 4)
    payload += _field_string(4, name)
    # raw_data (field 9)
    raw = data.astype(np.float32).tobytes()
    payload += _field_bytes(9, raw)
    return payload


def _value_info_proto(name: str, shape: list[int]) -> bytes:
    """Сериализует описание входа/выхода в ValueInfoProto."""
    dims_bytes = b""
    for d in shape:
        dim_msg = _field_int(1, d)
        dims_bytes += _field_msg(1, dim_msg)

    tensor_shape_msg = dims_bytes
    # TypeProto.Tensor (elem_type=1 FLOAT, shape)
    tensor_type_msg = _field_int(1, 1) + _field_msg(2, tensor_shape_msg)
    # TypeProto
    type_msg = _field_msg(1, tensor_type_msg)
    # ValueInfoProto: name (field 1), type (field 2)
    return _field_string(1, name) + _field_msg(2, type_msg)


def _attribute_int(name: str, val: int) -> bytes:
    # name (field 1), i (field 3), type=2 INT (field 20)
    return _field_string(1, name) + _field_int(3, val) + _field_int(20, 2)


def _attribute_float(name: str, val: float) -> bytes:
    # name (field 1), f (field 2, 32-bit), type=1 FLOAT (field 20)
    f_bytes = _tag(2, 5) + struct.pack("<f", val)
    return _field_string(1, name) + f_bytes + _field_int(20, 1)


def _node_proto(
    op_type: str,
    name: str,
    inputs: list[str],
    outputs: list[str],
    attributes: list[bytes] | None = None,
) -> bytes:
    """Сериализует узел вычислительного графа в NodeProto."""
    payload = b""
    for inp in inputs:
        payload += _field_string(1, inp)
    for out in outputs:
        payload += _field_string(2, out)
    payload += _field_string(3, name)
    payload += _field_string(4, op_type)
    if attributes:
        for attr in attributes:
            payload += _field_msg(5, attr)
    return payload


def _build_onnx_model_bytes(
    num_features: int,
    labels: list[str],
    weight_matrix: np.ndarray,
    bias_vector: np.ndarray,
    hands_count: int,
) -> bytes:
    """Собирает полный байтовый поток ONNX ModelProto (IR v8, opset 17) для инференса в браузере."""
    num_classes = len(labels)

    # Узел 1: Gemm (General Matrix Multiply: Y = alpha * X * W + beta * B)
    # X: [1, num_features], W: [num_features, num_classes], B: [num_classes] -> logits: [1, num_classes]
    gemm_attrs = [_attribute_float("alpha", 1.0), _attribute_float("beta", 1.0)]
    gemm_node = _node_proto("Gemm", "gemm_layer", ["features", "weights", "biases"], ["logits"], gemm_attrs)

    # Узел 2: Softmax (axis=1) -> probabilities: [1, num_classes]
    softmax_attrs = [_attribute_int("axis", 1)]
    softmax_node = _node_proto("Softmax", "softmax_layer", ["logits"], ["probabilities"], softmax_attrs)

    # Тензоры-инициализаторы весов и смещений
    w_tensor = _tensor_proto("weights", [num_features, num_classes], weight_matrix)
    b_tensor = _tensor_proto("biases", [num_classes], bias_vector)

    # Входные и выходные описания
    input_info = _value_info_proto("features", [1, num_features])
    output_probs = _value_info_proto("probabilities", [1, num_classes])
    output_logits = _value_info_proto("logits", [1, num_classes])

    # GraphProto
    graph_payload = _field_msg(1, gemm_node) + _field_msg(1, softmax_node)
    graph_payload += _field_string(2, f"static_gesture_classifier_{hands_count}h")
    graph_payload += _field_msg(5, w_tensor) + _field_msg(5, b_tensor)
    graph_payload += _field_msg(11, input_info)
    graph_payload += _field_msg(12, output_probs) + _field_msg(12, output_logits)

    # OperatorSetIdProto (version 17)
    opset_msg = _field_string(1, "") + _field_int(2, 17)

    # MetadataProps (labels JSON, hands_count)
    meta_labels = _field_string(1, "labels") + _field_string(2, json.dumps(labels, ensure_ascii=False))
    meta_hands = _field_string(1, "hands_count") + _field_string(2, str(hands_count))

    # ModelProto
    model_payload = _field_int(1, 8)  # ir_version = 8
    model_payload += _field_string(2, "Project-Omilia")  # producer_name
    model_payload += _field_string(3, "0.2.0")  # producer_version
    model_payload += _field_string(4, "ai.omilia")  # domain
    model_payload += _field_string(6, "Static gesture classifier for WebAssembly/ONNX Runtime Web")
    model_payload += _field_msg(7, graph_payload)  # graph
    model_payload += _field_msg(14, opset_msg)  # opset_import
    model_payload += _field_msg(15, meta_labels)
    model_payload += _field_msg(15, meta_hands)

    return model_payload


# ==========================================================
# Экспорт модели и центроидов из SQLite датасета
# ==========================================================


def get_static_centroids(db_path: Path, hands_count: int) -> tuple[list[str], np.ndarray, np.ndarray, dict[str, int]]:
    """
    Вычисляет центроиды классов статических жестов и смещения ближайших эталонов.
    Возвращает: (labels, weight_matrix, bias_vector, sample_counts)
    """
    rows = db.get_static_samples(db_path, hands_count)
    dataset: dict[str, list[np.ndarray]] = {}

    for row in rows:
        blob = row["features_blob"] if "features_blob" in row.keys() else None
        if blob:
            vector = np.frombuffer(blob, dtype=np.float32)
        else:
            vector = np.asarray(json.loads(row["features_json"]), dtype=np.float32)
        dataset.setdefault(row["gesture_name"], []).append(vector)

    labels = sorted(dataset.keys())
    expected_dim = 141 * hands_count
    num_classes = len(labels)
    counts = {name: len(samples) for name, samples in dataset.items()}

    if num_classes == 0:
        # Пустой фолбэк для безопасного запуска
        w = np.zeros((expected_dim, 1), dtype=np.float32)
        b = np.zeros(1, dtype=np.float32)
        return ["—"], w, b, {"—": 0}

    # Матрица W: столбцы соответствуют центроидам классов
    # Смещение B: -0.5 * ||centroid||^2
    w_cols = []
    b_vals = []

    for name in labels:
        samples = dataset[name]
        mean_vec = np.mean(samples, axis=0).astype(np.float32)
        if mean_vec.shape[0] != expected_dim:
            mean_vec = np.pad(mean_vec, (0, max(0, expected_dim - mean_vec.shape[0])))[:expected_dim]
        w_cols.append(mean_vec)
        # B[c] = -0.5 * ||mu_c||^2
        norm_sq = float(np.sum(mean_vec * mean_vec))
        b_vals.append(-0.5 * norm_sq)

    weight_matrix = np.column_stack(w_cols).astype(np.float32)
    bias_vector = np.array(b_vals, dtype=np.float32)

    return labels, weight_matrix, bias_vector, counts


def export_classifier_metadata(db_path: Path, hands_count: int) -> dict[str, Any]:
    """Возвращает параметры модели (центроиды, веса, лейблы) в формате JSON для браузера."""
    labels, w_matrix, b_vector, counts = get_static_centroids(db_path, hands_count)
    expected_dim = 141 * hands_count

    # Транспонируем W, чтобы получить centroids: [num_classes, num_features]
    centroids = w_matrix.T.tolist()

    return {
        "status": "ok",
        "hands_count": hands_count,
        "num_features": expected_dim,
        "num_classes": len(labels),
        "labels": labels,
        "sample_counts": counts,
        "centroids": centroids,
        "biases": b_vector.tolist(),
        "max_distance": 2.0,
    }


def export_onnx_model_bytes(db_path: Path, hands_count: int) -> bytes:
    """Генерирует бинарный файл .onnx для переданного количества рук."""
    labels, w_matrix, b_vector, _ = get_static_centroids(db_path, hands_count)
    num_features = 141 * hands_count

    return _build_onnx_model_bytes(
        num_features=num_features,
        labels=labels,
        weight_matrix=w_matrix,
        bias_vector=b_vector,
        hands_count=hands_count,
    )
