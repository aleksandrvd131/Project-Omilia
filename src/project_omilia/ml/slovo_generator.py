"""
Генератор анатомических 3D-моделей ключевых точек жестов РЖЯ (Slovo RSL Dataset).

Модуль синтеза канонических 21-точечных 3D-моделей кистей рук для распознавания
жестов Русского жестового языка (РЖЯ) на топологии MediaPipe Hands:
- Уровень 1 (Дактильный алфавит): 'г', 'д', 'е', 'и', 'о', 'с', 'у'
- Уровень 2 (Числительные и счёт): '1', '2', '3', '4', '5'
- Уровни 3 и 4 (Повседневные жесты): 'хорошо', 'мир', 'любовь', 'стоп', 'книга' (2 руки)

Топология MediaPipe Hand (21 ключевая точка):
0: Wrist (Запястье)
1-4: Thumb (Большой палец: CMC, MCP, IP, TIP)
5-8: Index (Указательный палец: MCP, PIP, DIP, TIP)
9-12: Middle (Средний палец: MCP, PIP, DIP, TIP)
13-16: Ring (Безымянный палец: MCP, PIP, DIP, TIP)
17-20: Pinky (Мизинец: MCP, PIP, DIP, TIP)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from project_omilia.ml.augmentation import augment_static_samples
from project_omilia.services.pose_service import make_pose

# ============================================================================
# Топология MediaPipe Hands (21 точка)
# ============================================================================
WRIST: int = 0
THUMB_CMC: int = 1
THUMB_MCP: int = 2
THUMB_IP: int = 3
THUMB_TIP: int = 4

INDEX_MCP: int = 5
INDEX_PIP: int = 6
INDEX_DIP: int = 7
INDEX_TIP: int = 8

MIDDLE_MCP: int = 9
MIDDLE_PIP: int = 10
MIDDLE_DIP: int = 11
MIDDLE_TIP: int = 12

RING_MCP: int = 13
RING_PIP: int = 14
RING_DIP: int = 15
RING_TIP: int = 16

PINKY_MCP: int = 17
PINKY_PIP: int = 18
PINKY_DIP: int = 19
PINKY_TIP: int = 20

LandmarkDict = dict[str, float]
HandLandmarks = list[LandmarkDict]


@dataclass(frozen=True)
class SlovoGestureDefinition:
    """Полное описание жеста из набора Slovo RSL с анатомической разметкой."""

    name: str
    title: str
    level: int
    level_title: str
    category: str
    description: str
    tip: str
    hands_count: int
    hands_landmarks: list[HandLandmarks]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "level": self.level,
            "level_title": self.level_title,
            "category": self.category,
            "description": self.description,
            "tip": self.tip,
            "hands_count": self.hands_count,
            "hands_landmarks": self.hands_landmarks,
        }


def _norm_vec(v: np.ndarray) -> np.ndarray:
    """Нормализует 3D-вектор к единичной длине."""
    length = float(np.linalg.norm(v))
    if length < 1e-8:
        return np.array([0.0, -1.0, 0.0], dtype=np.float32)
    return v / length


def build_hand_landmarks(
    wrist: tuple[float, float, float],
    finger_specs: dict[str, Any],
    is_right: bool = True,
) -> HandLandmarks:
    """Генерирует 21 анатомическую ключевую точку кисти MediaPipe.

    Параметры:
        wrist: (x, y, z) координаты запястья в диапазоне [0, 1].
        finger_specs: словарь состояний пальцев (thumb, index, middle, ring, pinky).
        is_right: True для правой кисти, False для левой.
    """
    wx, wy, wz = wrist
    s = 1.0 if is_right else -1.0

    pts: list[LandmarkDict | None] = [None] * 21
    pts[WRIST] = {"x": round(wx, 5), "y": round(wy, 5), "z": round(wz, 5)}

    # Базовые суставы пясти (MCP) и CMC большого пальца
    pts[THUMB_CMC] = {
        "x": round(wx - 0.025 * s, 5),
        "y": round(wy - 0.045, 5),
        "z": round(wz - 0.005, 5),
    }
    pts[THUMB_MCP] = {
        "x": round(wx - 0.050 * s, 5),
        "y": round(wy - 0.075, 5),
        "z": round(wz - 0.012, 5),
    }
    pts[INDEX_MCP] = {
        "x": round(wx - 0.045 * s, 5),
        "y": round(wy - 0.125, 5),
        "z": round(wz + 0.005, 5),
    }
    pts[MIDDLE_MCP] = {
        "x": round(wx - 0.010 * s, 5),
        "y": round(wy - 0.145, 5),
        "z": round(wz, 5),
    }
    pts[RING_MCP] = {
        "x": round(wx + 0.025 * s, 5),
        "y": round(wy - 0.135, 5),
        "z": round(wz - 0.005, 5),
    }
    pts[PINKY_MCP] = {
        "x": round(wx + 0.055 * s, 5),
        "y": round(wy - 0.115, 5),
        "z": round(wz - 0.010, 5),
    }

    # Построение большого пальца (THUMB: точки 1..4)
    t_mode = finger_specs.get("thumb", "fist")
    mcp_t = np.array([pts[THUMB_MCP]["x"], pts[THUMB_MCP]["y"], pts[THUMB_MCP]["z"]])  # type: ignore

    if t_mode == "up":
        # Жест «хорошо» (Thumbs up) — палец вертикально вверх над кулаком
        d1 = np.array([0.005 * s, -0.034, -0.005])
        d2 = np.array([0.005 * s, -0.028, -0.002])
    elif t_mode == "side":
        # Жест буквы «Г» — палец строго горизонтально под прямым углом 90°
        d1 = np.array([-0.038 * s, 0.002, -0.005])
        d2 = np.array([-0.032 * s, 0.004, -0.002])
    elif t_mode == "spread":
        # Широко раскрытый палец под 45° («5», «любовь», «у», «3»)
        d1 = np.array([-0.028 * s, -0.024, -0.005])
        d2 = np.array([-0.024 * s, -0.020, -0.002])
    elif t_mode == "c_curve":
        # Нижняя дуга буквы «С»
        d1 = np.array([-0.022 * s, -0.018, -0.015])
        d2 = np.array([-0.010 * s, -0.020, -0.010])
    elif t_mode == "o_curve":
        # Кольцо буквы «О» (касание кончиков пальцев)
        d1 = np.array([-0.012 * s, -0.024, -0.025])
        d2 = np.array([-0.005 * s, -0.022, -0.022])
    elif t_mode == "d_touch":
        # Буква «Д» — большой палец согнут навстречу согнутым пальцам у основания
        d1 = np.array([0.010 * s, -0.022, -0.022])
        d2 = np.array([0.012 * s, -0.015, -0.018])
    elif t_mode == "palm":
        # Число «4» — большой палец прижат поперек ладони
        d1 = np.array([0.030 * s, -0.012, -0.015])
        d2 = np.array([0.026 * s, 0.002, -0.012])
    elif t_mode == "flat":
        # Жесты «стоп» и «книга» — палец вытянут вдоль ладони
        d1 = np.array([-0.012 * s, -0.030, -0.005])
        d2 = np.array([-0.008 * s, -0.026, -0.002])
    else:
        # Кулак: палец согнут поверх пальцев («1», «2», «мир», «и», «е»)
        d1 = np.array([0.025 * s, -0.018, -0.022])
        d2 = np.array([0.022 * s, 0.005, -0.016])

    p_ip = mcp_t + d1
    p_tip = p_ip + d2
    pts[THUMB_IP] = {"x": round(float(p_ip[0]), 5), "y": round(float(p_ip[1]), 5), "z": round(float(p_ip[2]), 5)}
    pts[THUMB_TIP] = {"x": round(float(p_tip[0]), 5), "y": round(float(p_tip[1]), 5), "z": round(float(p_tip[2]), 5)}

    # Построение 4 длинных пальцев: Index, Middle, Ring, Pinky
    finger_params = [
        ("index", INDEX_MCP, [0.040, 0.026, 0.022], -0.08 * s),
        ("middle", MIDDLE_MCP, [0.045, 0.029, 0.024], 0.00),
        ("ring", RING_MCP, [0.040, 0.026, 0.022], 0.06 * s),
        ("pinky", PINKY_MCP, [0.030, 0.020, 0.017], 0.14 * s),
    ]

    for fname, base_idx, lens, def_spread in finger_params:
        mode = finger_specs.get(fname, "fist")
        mcp = np.array([pts[base_idx]["x"], pts[base_idx]["y"], pts[base_idx]["z"]])  # type: ignore
        l1, l2, l3 = lens

        if mode == "extended":
            spread = finger_specs.get(f"{fname}_spread", def_spread)
            dir_v = _norm_vec(np.array([np.sin(spread), -np.cos(spread), 0.0]))
            p_pip = mcp + dir_v * l1
            p_dip = p_pip + dir_v * l2
            p_tip = p_dip + dir_v * l3
        elif mode == "claw":
            # Буква «Е» — полусогнутый гребень
            p_pip = mcp + np.array([0.0, -0.018, -0.025])
            p_dip = p_pip + np.array([0.0, 0.015, -0.020])
            p_tip = p_dip + np.array([0.0, 0.022, -0.005])
        elif mode == "c_curve":
            # Буква «С» — полукруглая дуга
            p_pip = mcp + np.array([-0.015 * s, -0.028, -0.015])
            p_dip = p_pip + np.array([-0.010 * s, -0.012, -0.020])
            p_tip = p_dip + np.array([0.012 * s, 0.008, -0.018])
        elif mode == "o_curve":
            # Буква «О» и база буквы «Д» — пальцы согнуты в кольцо
            p_pip = mcp + np.array([-0.012 * s, -0.025, -0.020])
            p_dip = p_pip + np.array([-0.008 * s, -0.005, -0.025])
            p_tip = p_dip + np.array([-0.005 * s, 0.020, -0.015])
        else:
            # Кулак (плотно согнутый палец)
            p_pip = mcp + np.array([0.0, -0.005, -0.026])
            p_dip = p_pip + np.array([0.0, 0.028, -0.008])
            p_tip = p_dip + np.array([0.0, 0.018, 0.018])

        pts[base_idx + 1] = {
            "x": round(float(p_pip[0]), 5),
            "y": round(float(p_pip[1]), 5),
            "z": round(float(p_pip[2]), 5),
        }
        pts[base_idx + 2] = {
            "x": round(float(p_dip[0]), 5),
            "y": round(float(p_dip[1]), 5),
            "z": round(float(p_dip[2]), 5),
        }
        pts[base_idx + 3] = {
            "x": round(float(p_tip[0]), 5),
            "y": round(float(p_tip[1]), 5),
            "z": round(float(p_tip[2]), 5),
        }

    return pts  # type: ignore


# ============================================================================
# Спецификации канонических жестов Slovo RSL
# ============================================================================


def _build_slovo_definitions() -> dict[str, SlovoGestureDefinition]:
    """Строит полный словарь всех 17 новых жестов Slovo RSL."""
    defs: dict[str, SlovoGestureDefinition] = {}

    # ------------------------------------------------------------------------
    # Уровень 1: Дактильный алфавит ('г', 'д', 'е', 'и', 'о', 'с', 'у')
    # ------------------------------------------------------------------------
    defs["г"] = SlovoGestureDefinition(
        name="г",
        title="Буква Г",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и большой пальцы образуют прямой угол буквой Г.",
        tip="Держите руку прямо, большой и указательный пальцы образуют угол 90 градусов.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "side",
                    "index": "extended",
                    "index_spread": 0.0,
                    "middle": "fist",
                    "ring": "fist",
                    "pinky": "fist",
                },
                is_right=True,
            )
        ],
    )

    defs["д"] = SlovoGestureDefinition(
        name="д",
        title="Буква Д",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец поднят вверх, остальные пальцы согнуты в кольцо с большим.",
        tip="Поднимите указательный палец строго вверх, средний и безымянный сомкните с большим.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "d_touch",
                    "index": "extended",
                    "index_spread": 0.0,
                    "middle": "o_curve",
                    "ring": "o_curve",
                    "pinky": "o_curve",
                },
                is_right=True,
            )
        ],
    )

    defs["е"] = SlovoGestureDefinition(
        name="е",
        title="Буква Е",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы полусогнуты к ладони в форме гребня буквы Е.",
        tip="Слегка согните все пальцы вперед, ладонь направлена в камеру.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {"thumb": "fist", "index": "claw", "middle": "claw", "ring": "claw", "pinky": "claw"},
                is_right=True,
            )
        ],
    )

    defs["и"] = SlovoGestureDefinition(
        name="и",
        title="Буква И",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Мизинец поднят вертикально вверх, остальные пальцы сжаты в кулак.",
        tip="Поднимите только мизинец, остальные пальцы держите прижатыми.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "fist",
                    "index": "fist",
                    "middle": "fist",
                    "ring": "fist",
                    "pinky": "extended",
                    "pinky_spread": 0.0,
                },
                is_right=True,
            )
        ],
    )

    defs["о"] = SlovoGestureDefinition(
        name="о",
        title="Буква О",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы образуют кольцо с большим пальцем в форме буквы О.",
        tip="Соедините кончики пальцев в круг перед камерой.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {"thumb": "o_curve", "index": "o_curve", "middle": "o_curve", "ring": "o_curve", "pinky": "o_curve"},
                is_right=True,
            )
        ],
    )

    defs["с"] = SlovoGestureDefinition(
        name="с",
        title="Буква С",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Кисть образует полукруглую форму буквы С с открытым зазором.",
        tip="Согните ладонь в форме буквы С, удерживая зазор между кончиками пальцев.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {"thumb": "c_curve", "index": "c_curve", "middle": "c_curve", "ring": "c_curve", "pinky": "c_curve"},
                is_right=True,
            )
        ],
    )

    defs["у"] = SlovoGestureDefinition(
        name="у",
        title="Буква У",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой палец и мизинец отставлены в стороны (форма рожек буквы У).",
        tip="Выпрямите большой палец и мизинец, три средних пальца прижаты к ладони.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "spread",
                    "index": "fist",
                    "middle": "fist",
                    "ring": "fist",
                    "pinky": "extended",
                    "pinky_spread": 0.28,
                },
                is_right=True,
            )
        ],
    )

    # ------------------------------------------------------------------------
    # Уровень 2: Числительные и счёт ('1', '2', '3', '4', '5')
    # ------------------------------------------------------------------------
    defs["1"] = SlovoGestureDefinition(
        name="1",
        title="Число 1",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Указательный палец поднят вверх, остальные пальцы сжаты в кулак.",
        tip="Поднимите указательный палец перед камерой, остальные плотно сожмите.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "fist",
                    "index": "extended",
                    "index_spread": 0.0,
                    "middle": "fist",
                    "ring": "fist",
                    "pinky": "fist",
                },
                is_right=True,
            )
        ],
    )

    defs["2"] = SlovoGestureDefinition(
        name="2",
        title="Число 2",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Указательный и средний пальцы выпрямлены вверх параллельно.",
        tip="Выпрямите указательный и средний пальцы вверх, большой придерживает безымянный и мизинец.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "fist",
                    "index": "extended",
                    "index_spread": -0.02,
                    "middle": "extended",
                    "middle_spread": 0.02,
                    "ring": "fist",
                    "pinky": "fist",
                },
                is_right=True,
            )
        ],
    )

    defs["3"] = SlovoGestureDefinition(
        name="3",
        title="Число 3",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Большой, указательный и средний пальцы выпрямлены.",
        tip="Покажите три пальца: большой, указательный и средний; остальные прижаты.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "spread",
                    "index": "extended",
                    "index_spread": -0.05,
                    "middle": "extended",
                    "middle_spread": 0.05,
                    "ring": "fist",
                    "pinky": "fist",
                },
                is_right=True,
            )
        ],
    )

    defs["4"] = SlovoGestureDefinition(
        name="4",
        title="Число 4",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Четыре пальца выпрямлены вверх, большой палец прижат к ладони.",
        tip="Выпрямите четыре пальца вверх, большой спрятан внутри ладони.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "palm",
                    "index": "extended",
                    "index_spread": -0.10,
                    "middle": "extended",
                    "middle_spread": -0.03,
                    "ring": "extended",
                    "ring_spread": 0.04,
                    "pinky": "extended",
                    "pinky_spread": 0.12,
                },
                is_right=True,
            )
        ],
    )

    defs["5"] = SlovoGestureDefinition(
        name="5",
        title="Число 5",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Все пять пальцев широко раскрыты ладонью к зрителю.",
        tip="Раскройте все пять пальцев максимально широко перед камерой.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "spread",
                    "index": "extended",
                    "index_spread": -0.22,
                    "middle": "extended",
                    "middle_spread": -0.03,
                    "ring": "extended",
                    "ring_spread": 0.16,
                    "pinky": "extended",
                    "pinky_spread": 0.35,
                },
                is_right=True,
            )
        ],
    )

    # ------------------------------------------------------------------------
    # Уровни 3 и 4: Повседневные жесты ('хорошо', 'мир', 'любовь', 'стоп', 'книга')
    # ------------------------------------------------------------------------
    defs["хорошо"] = SlovoGestureDefinition(
        name="хорошо",
        title="Хорошо",
        level=3,
        level_title="Базовый этикет",
        category="Оценки и статус",
        description="Кулак с поднятым вертикально вверх большим пальцем (жест одобрения).",
        tip="Сожмите пальцы в кулак и уверенно поднимите большой палец вверх.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {"thumb": "up", "index": "fist", "middle": "fist", "ring": "fist", "pinky": "fist"},
                is_right=True,
            )
        ],
    )

    defs["мир"] = SlovoGestureDefinition(
        name="мир",
        title="Мир",
        level=3,
        level_title="Базовый этикет",
        category="Понятия и статус",
        description="Указательный и средний пальцы широко разведены в форме буквы V (знак мира).",
        tip="Широко разведите указательный и средний пальцы буквой V.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "fist",
                    "index": "extended",
                    "index_spread": -0.28,
                    "middle": "extended",
                    "middle_spread": 0.24,
                    "ring": "fist",
                    "pinky": "fist",
                },
                is_right=True,
            )
        ],
    )

    defs["любовь"] = SlovoGestureDefinition(
        name="любовь",
        title="Любовь",
        level=4,
        level_title="Семья и окружение",
        category="Эмоции и чувства",
        description="Большой, указательный пальцы и мизинец выпрямлены (международный жест ILY).",
        tip="Выпрямите большой, указательный пальцы и мизинец, средний и безымянный прижмите.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "spread",
                    "index": "extended",
                    "index_spread": -0.05,
                    "middle": "fist",
                    "ring": "fist",
                    "pinky": "extended",
                    "pinky_spread": 0.22,
                },
                is_right=True,
            )
        ],
    )

    defs["стоп"] = SlovoGestureDefinition(
        name="стоп",
        title="Стоп",
        level=4,
        level_title="Семья и окружение",
        category="Указания и команды",
        description="Открытая прямая ладонь направлена вперед пальцами вверх (знак остановки).",
        tip="Покажите раскрытую прямую ладонь перед камерой, пальцы сомкнуты вместе.",
        hands_count=1,
        hands_landmarks=[
            build_hand_landmarks(
                (0.60, 0.65, 0.0),
                {
                    "thumb": "flat",
                    "index": "extended",
                    "index_spread": -0.03,
                    "middle": "extended",
                    "middle_spread": 0.00,
                    "ring": "extended",
                    "ring_spread": 0.03,
                    "pinky": "extended",
                    "pinky_spread": 0.06,
                },
                is_right=True,
            )
        ],
    )

    # Двуручный жест «книга» (Level 4)
    hr_book = build_hand_landmarks(
        (0.56, 0.60, 0.0),
        {
            "thumb": "flat",
            "index": "extended",
            "index_spread": -0.15,
            "middle": "extended",
            "middle_spread": -0.12,
            "ring": "extended",
            "ring_spread": -0.09,
            "pinky": "extended",
            "pinky_spread": -0.06,
        },
        is_right=True,
    )
    hl_book = build_hand_landmarks(
        (0.44, 0.60, 0.0),
        {
            "thumb": "flat",
            "index": "extended",
            "index_spread": 0.15,
            "middle": "extended",
            "middle_spread": 0.12,
            "ring": "extended",
            "ring_spread": 0.09,
            "pinky": "extended",
            "pinky_spread": 0.06,
        },
        is_right=False,
    )

    defs["книга"] = SlovoGestureDefinition(
        name="книга",
        title="Книга",
        level=4,
        level_title="Семья и окружение",
        category="Предметы и окружение",
        description="Две раскрытые ладони соприкасаются ребрами мизинцев, раскрываясь как книга.",
        tip="Соедините обе ладони ребрами перед грудью под углом, как раскрытую книгу.",
        hands_count=2,
        hands_landmarks=[hr_book, hl_book],
    )

    return defs


SLOVO_GESTURES: dict[str, SlovoGestureDefinition] = _build_slovo_definitions()


# ============================================================================
# Публичный API для dataset_builder и тестов
# ============================================================================


def get_slovo_gesture(name: str) -> SlovoGestureDefinition:
    """Возвращает метаданные и анатомические точки жеста по имени."""
    key = name.strip().lower()
    if key not in SLOVO_GESTURES:
        raise KeyError(f"Неизвестный жест Slovo: '{name}'. Доступно: {list(SLOVO_GESTURES.keys())}")
    return SLOVO_GESTURES[key]


def get_slovo_landmarks(name: str) -> list[HandLandmarks]:
    """Возвращает список кистей с 21 точкой для жеста (1 или 2 кисти)."""
    return get_slovo_gesture(name).hands_landmarks


def get_all_slovo_gestures() -> dict[str, SlovoGestureDefinition]:
    """Возвращает все зарегистрированные жесты Slovo."""
    return dict(SLOVO_GESTURES)


def get_all_slovo_landmarks() -> dict[str, list[HandLandmarks]]:
    """Возвращает словарь всех жестов с их списками ключевых точек."""
    return {name: item.hands_landmarks for name, item in SLOVO_GESTURES.items()}


def generate_canonical_vector(name: str) -> np.ndarray:
    """Генерирует канонический 1D-вектор признаков (141 или 282 элемента)."""
    gesture = get_slovo_gesture(name)
    pose = make_pose(gesture.hands_landmarks, pose_landmarks=None)
    if pose is None:
        raise RuntimeError(f"Не удалось построить Pose для жеста «{name}»")

    if gesture.hands_count == 1:
        vec = pose.get_1d_array_one_hand().flatten()
    else:
        vec = pose.get_1d_array_two_hands().flatten()

    return vec.astype(np.float32)


def generate_augmented_samples(
    name: str,
    num_samples: int = 20,
    seed: int | None = 42,
) -> list[np.ndarray]:
    """Генерирует канонический эталон плюс синтезированные аугментированные вариации.

    Параметры:
        name: имя жеста из Slovo RSL.
        num_samples: общее целевое количество сэмплов (по умолчанию 20).
        seed: случайное зерно для воспроизводимости.
    """
    base_vec = generate_canonical_vector(name)
    if num_samples <= 1:
        return [base_vec]

    num_augmented = num_samples - 1
    samples = augment_static_samples(
        [base_vec],
        num_augmented_per_sample=num_augmented,
        scale_range=(0.94, 1.06),
        angle_deg_range=(-4.0, 4.0),
        noise_sigma=0.003,
        seed=seed,
    )
    return samples


def build_db_records(
    num_augmented_per_gesture: int = 20,
    seed: int = 42,
) -> list[tuple[str, int, str, bytes]]:
    """Формирует список записей для таблицы `static_gesture_samples` в SQLite.

    Возвращает список кортежей:
        (gesture_name, hands_count, features_json, features_blob)
    """
    records: list[tuple[str, int, str, bytes]] = []

    for idx, (name, gesture) in enumerate(SLOVO_GESTURES.items()):
        samples = generate_augmented_samples(
            name,
            num_samples=num_augmented_per_gesture,
            seed=seed + idx,
        )
        for vec in samples:
            vec_f32 = vec.astype(np.float32)
            features_json = json.dumps(vec_f32.tolist(), allow_nan=False)
            features_blob = vec_f32.tobytes()
            records.append((name, gesture.hands_count, features_json, features_blob))

    return records


def build_gesture_metadata_records() -> list[tuple[str, str, int, str, str, str, str, int, int]]:
    """Формирует метаданные для вставки в таблицу `gestures` в SQLite.

    Кортеж:
        (name, title, level, level_title, category, description, tip, hands_count, is_dynamic)
    """
    return [
        (
            g.name,
            g.title,
            g.level,
            g.level_title,
            g.category,
            g.description,
            g.tip,
            g.hands_count,
            0,  # is_dynamic = False
        )
        for g in SLOVO_GESTURES.values()
    ]


if __name__ == "__main__":
    print(f"=== Проверка генератора Slovo RSL ({len(SLOVO_GESTURES)} жестов) ===")
    all_gestures = get_all_slovo_gestures()
    for name, g in all_gestures.items():
        vec = generate_canonical_vector(name)
        print(f"[{g.level_title}] '{name}': {g.hands_count} рук, размерность вектора: {len(vec)}")

    # Проверка расстояний между каноническими жестами
    vecs_1h = {name: generate_canonical_vector(name) for name, g in all_gestures.items() if g.hands_count == 1}
    names = list(vecs_1h.keys())
    min_dist = float("inf")
    closest = None
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = float(np.linalg.norm(vecs_1h[names[i]] - vecs_1h[names[j]]))
            if d < min_dist:
                min_dist = d
                closest = (names[i], names[j])

    print(f"\nМинимальное расстояние между 1-ручными жестами: {min_dist:.4f} ({closest})")
    assert min_dist > 0.5, "Минимальное расстояние должно превышать 0.5 для надежного k-NN разделения"

    db_recs = build_db_records(num_augmented_per_gesture=20)
    print(f"Сгенерировано {len(db_recs)} записей для SQLite (20 сэмплов * {len(SLOVO_GESTURES)} жестов).")
