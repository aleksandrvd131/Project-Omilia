"""
Модуль классификации жестов:
- StaticGesture: классификация формы кисти на основе взвешенного k-NN
- DynamicGestures: сопоставление траекторий жестов через векторизованный DTW
- Curriculum Levels: формальная структура учебной программы (Уровни 1-4)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from tslearn.metrics import dtw

from project_omilia import db
from project_omilia.body import Pose
from project_omilia.errors import IncorrectDataError

COUNT_OF_GESTURES = 8
COUNT_OF_SAMPLES = 10


# ============================================================================
# Структура учебной программы (Curriculum Levels)
# ============================================================================

CURRICULUM_LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "level_title": "Дактильный алфавит",
        "title": "Дактильный алфавит",
        "description": "Буквы дактильного алфавита русского жестового языка (А, Б, В, ...)",
        "badge": "🔤",
        "unlock_threshold": 0.0,
    },
    2: {
        "level": 2,
        "level_title": "Числительные и счёт",
        "title": "Числительные и счёт",
        "description": "Базовые числа и счёт на пальцах (1, 2, 3, ...)",
        "badge": "🔢",
        "unlock_threshold": 0.7,
    },
    3: {
        "level": 3,
        "level_title": "Базовый этикет",
        "title": "Базовый этикет",
        "description": "Приветствия, формулы вежливости и базовый контакт (Привет, Спасибо, Да, Нет, ...)",
        "badge": "🤝",
        "unlock_threshold": 0.7,
    },
    4: {
        "level": 4,
        "level_title": "Семья и окружение",
        "title": "Семья и окружение",
        "description": "Семья, дом, близкие и окружающий мир (Дом, Мама, Папа, Я, Ты, ...)",
        "badge": "🏡",
        "unlock_threshold": 0.7,
    },
}


@dataclass
class GestureDefinition:
    """Определение жеста в учебной программе с уровнем сложности."""

    name: str
    title: str
    level: int
    level_title: str
    category: str = "Общие жесты"
    description: str = ""
    tip: str = ""
    hands_count: int = 1
    is_dynamic: bool = False

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
            "is_dynamic": self.is_dynamic,
        }


GESTURE_DEFINITIONS: dict[str, GestureDefinition] = {
    # Level 1: «Дактильный алфавит» (все 33 буквы русского дактиля: а-я)
    "а": GestureDefinition(
        name="а",
        title="Буква А",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы сжаты в кулак, большой палец прижат сбоку к указательному.",
        tip="Кулак направлен ладонью к зрителю, большой палец прижат сбоку.",
        hands_count=1,
        is_dynamic=False,
    ),
    "б": GestureDefinition(
        name="б",
        title="Буква Б",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Четыре пальца прямые вверх, большой палец согнут и прижат к основанию ладони.",
        tip="Пальцы сомкнуты вместе и направлены строго вверх.",
        hands_count=1,
        is_dynamic=False,
    ),
    "в": GestureDefinition(
        name="в",
        title="Буква В",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Четыре прямых пальца направлены вверх, большой палец отставлен под прямым углом в сторону.",
        tip="Держите четыре пальца вместе вертикально, отставив большой вбок.",
        hands_count=1,
        is_dynamic=False,
    ),
    "г": GestureDefinition(
        name="г",
        title="Буква Г",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и большой пальцы образуют прямой угол буквой Г.",
        tip="Держите руку прямо, пальцы образуют угол 90 градусов.",
        hands_count=1,
        is_dynamic=False,
    ),
    "д": GestureDefinition(
        name="д",
        title="Буква Д",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец поднят вверх, остальные согнуты в кольцо с большим.",
        tip="Поднимите указательный палец, зафиксируйте кисть.",
        hands_count=1,
        is_dynamic=False,
    ),
    "е": GestureDefinition(
        name="е",
        title="Буква Е",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы полусогнуты к ладони в форме гребня буквы Е.",
        tip="Слегка согните пальцы, ладонь направлена вперёд.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ё": GestureDefinition(
        name="ё",
        title="Буква Ё",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы полусогнуты гребнем буквы Е, большой палец отставлен горизонтально вбок.",
        tip="Согните пальцы гребнем вперед, отведя большой палец в сторону.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ж": GestureDefinition(
        name="ж",
        title="Буква Ж",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Все пять пальцев растопырены и согнуты полукругом дугой (лапка паука).",
        tip="Растопырьте полусогнутые пальцы веером перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "з": GestureDefinition(
        name="з",
        title="Буква З",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец согнут крючком вперед, остальные пальцы сжаты в кулак.",
        tip="Согните указательный палец крючком вперед, остальные пальцы сожмите.",
        hands_count=1,
        is_dynamic=False,
    ),
    "и": GestureDefinition(
        name="и",
        title="Буква И",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Мизинец поднят вертикально вверх, остальные пальцы сжаты в кулак.",
        tip="Поднимите вертикально вверх только мизинец, остальные пальцы сожмите в кулак.",
        hands_count=1,
        is_dynamic=False,
    ),
    "й": GestureDefinition(
        name="й",
        title="Буква Й",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Мизинец согнут крючком (знак Й с краткой), остальные пальцы сжаты в кулак.",
        tip="Согните мизинец крючком вверх, остальные пальцы сожмите в кулак.",
        hands_count=1,
        is_dynamic=False,
    ),
    "к": GestureDefinition(
        name="к",
        title="Буква К",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и средний пальцы выпрямлены вверх буквой V, большой поднят между ними.",
        tip="Поместите большой палец между выпрямленными указательным и средним.",
        hands_count=1,
        is_dynamic=False,
    ),
    "л": GestureDefinition(
        name="л",
        title="Буква Л",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой и указательный пальцы выпрямлены под углом шалашиком (буква Л).",
        tip="Выпрямите большой и указательный пальцы углом шалашика, остальные сожмите.",
        hands_count=1,
        is_dynamic=False,
    ),
    "м": GestureDefinition(
        name="м",
        title="Буква М",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Три пальца (указательный, средний, безымянный) согнуты вниз под прямым углом.",
        tip="Опустите три средних пальца вниз козырьком перед камерой, мизинец прижат.",
        hands_count=1,
        is_dynamic=False,
    ),
    "н": GestureDefinition(
        name="н",
        title="Буква Н",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и средний пальцы вытянуты горизонтально вперед (две перекладины Н).",
        tip="Вытяните указательный и средний пальцы вперед перед камерой, остальные сожмите.",
        hands_count=1,
        is_dynamic=False,
    ),
    "о": GestureDefinition(
        name="о",
        title="Буква О",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы образуют кольцо с большим пальцем в форме буквы О.",
        tip="Соедините кончики пальцев в круг перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "п": GestureDefinition(
        name="п",
        title="Буква П",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и средний пальцы выпрямлены параллельно горизонтально вбок.",
        tip="Вытяните указательный и средний пальцы горизонтально в сторону, остальные сожмите.",
        hands_count=1,
        is_dynamic=False,
    ),
    "р": GestureDefinition(
        name="р",
        title="Буква Р",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец направлен вверх, средний согнут дугой вперед (петелька буквы Р).",
        tip="Выпрямите указательный палец вверх, согнув средний палец дугой перед ним.",
        hands_count=1,
        is_dynamic=False,
    ),
    "с": GestureDefinition(
        name="с",
        title="Буква С",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Пальцы согнуты полукругом в форме буквы С, ладонь обращена вбок.",
        tip="Сформируйте пальцами полукруг в форме буквы С перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "т": GestureDefinition(
        name="т",
        title="Буква Т",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой палец просунут под согнутый указательный в плотном кулаке.",
        tip="Сожмите кулак, подложив большой палец под согнутый указательный.",
        hands_count=1,
        is_dynamic=False,
    ),
    "у": GestureDefinition(
        name="у",
        title="Буква У",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой палец и мизинец отставлены в стороны (форма рожек буквы У).",
        tip="Выпрямите большой палец и мизинец, три средних пальца прижаты к ладони.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ф": GestureDefinition(
        name="ф",
        title="Буква Ф",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой и указательный пальцы образуют кольцо, средний, безымянный и мизинец прямые вверх.",
        tip="Сомкните большой и указательный пальцы в круг, три остальных выпрямите вверх.",
        hands_count=1,
        is_dynamic=False,
    ),
    "х": GestureDefinition(
        name="х",
        title="Буква Х",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец согнут плавной дугой вбок, большой палец отставлен.",
        tip="Согните указательный палец дугой в сторону, остальные пальцы сожмите.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ц": GestureDefinition(
        name="ц",
        title="Буква Ц",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и средний пальцы выпрямлены вместе вверх, мизинец отведен вбок (хвостик Ц).",
        tip="Держите указательный и средний пальцы вместе вверх, а мизинец отведите в сторону.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ч": GestureDefinition(
        name="ч",
        title="Буква Ч",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Четыре пальца полусогнуты крючком вперед в форме чашечки/ковшика (буква Ч).",
        tip="Согните четыре пальца ковшиком вперед, ладонь направлена в камеру.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ш": GestureDefinition(
        name="ш",
        title="Буква Ш",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Три пальца (указательный, средний, безымянный) выпрямлены вверх трезубцем буквы Ш.",
        tip="Поднимите три пальца вертикально вверх, большой придерживает мизинец.",
        hands_count=1,
        is_dynamic=False,
    ),
    "щ": GestureDefinition(
        name="щ",
        title="Буква Щ",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Три пальца выпрямлены вверх как Ш, а мизинец согнут дугой вбок (хвостик буквы Щ).",
        tip="Поднимите три пальца вверх трезубцем, а мизинец отогните вбок хвостиком.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ъ": GestureDefinition(
        name="ъ",
        title="Буква Ъ",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой палец вбок, указательный выпрямлен вперед, средний согнут дугой (буква Ъ).",
        tip="Отведите большой палец вбок, указательный выпрямите, а средний согните дугой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ы": GestureDefinition(
        name="ы",
        title="Буква Ы",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный и мизинец выпрямлены вверх («рожки»), средний и безымянный в кольце с большим.",
        tip="Выпрямите указательный и мизинец вверх, соединив средний и безымянный с большим.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ь": GestureDefinition(
        name="ь",
        title="Буква Ь",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой и указательный пальцы образуют округлую петельку буквы Ь внизу.",
        tip="Соедините указательный и большой пальцы дугой внизу, остальные сожмите в кулак.",
        hands_count=1,
        is_dynamic=False,
    ),
    "э": GestureDefinition(
        name="э",
        title="Буква Э",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой и указательный пальцы образуют дугу буквы Э, средний выдвинут вперед как язычок.",
        tip="Сделайте дугу большим и указательным пальцами, выставив средний палец вперед посередине.",
        hands_count=1,
        is_dynamic=False,
    ),
    "ю": GestureDefinition(
        name="ю",
        title="Буква Ю",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Большой и указательный пальцы сомкнуты в кольцо сбоку, а мизинец поднят вверх (буква Ю).",
        tip="Сомкните большой и указательный пальцы в кольцо, подняв мизинец строго вверх.",
        hands_count=1,
        is_dynamic=False,
    ),
    "я": GestureDefinition(
        name="я",
        title="Буква Я",
        level=1,
        level_title="Дактильный алфавит",
        category="Дактиль (Алфавит)",
        description="Указательный палец поднят вверх, средний согнут петелькой, большой отставлен в сторону.",
        tip="Поднимите указательный палец, отведите большой вбок, а средний согните дугой перед ладонью.",
        hands_count=1,
        is_dynamic=False,
    ),
    # Level 2: «Числительные и счёт» (числа 1, 2, ...)
    "1": GestureDefinition(
        name="1",
        title="Число 1",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Указательный палец поднят вверх, остальные пальцы сжаты в кулак.",
        tip="Поднимите указательный палец перед камерой, остальные прижаты.",
        hands_count=1,
        is_dynamic=False,
    ),
    "2": GestureDefinition(
        name="2",
        title="Число 2",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Указательный и средний пальцы выпрямлены вверх буквой V.",
        tip="Выпрямите два пальца (указательный и средний) вверх.",
        hands_count=1,
        is_dynamic=False,
    ),
    "3": GestureDefinition(
        name="3",
        title="Число 3",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Большой, указательный и средний пальцы выпрямлены.",
        tip="Покажите три пальца, безымянный и мизинец прижаты к ладони.",
        hands_count=1,
        is_dynamic=False,
    ),
    "4": GestureDefinition(
        name="4",
        title="Число 4",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Четыре пальца выпрямлены вверх, большой палец прижат к ладони.",
        tip="Выпрямите четыре пальца вверх, большой спрятан внутри.",
        hands_count=1,
        is_dynamic=False,
    ),
    "5": GestureDefinition(
        name="5",
        title="Число 5",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Все пять пальцев широко раскрыты ладонью к зрителю.",
        tip="Раскройте все пять пальцев перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "10": GestureDefinition(
        name="10",
        title="Число 10",
        level=2,
        level_title="Числительные и счёт",
        category="Числительные",
        description="Обе ладони раскрыты перед камерой, показывая 10 пальцев.",
        tip="Покажите обе раскрытые ладони перед камерой.",
        hands_count=2,
        is_dynamic=False,
    ),
    # Level 3: «Базовый этикет» (Привет, Спасибо, и т.д.)
    "привет": GestureDefinition(
        name="привет",
        title="Привет",
        level=3,
        level_title="Базовый этикет",
        category="Приветствия",
        description="Раскрытая ладонь направлена вперёд на уровне плеча, пальцы прямые.",
        tip="Поднимите открытую ладонь на уровень лица или плеча, пальцы смотрят вверх.",
        hands_count=1,
        is_dynamic=False,
    ),
    "спасибо": GestureDefinition(
        name="спасибо",
        title="Спасибо",
        level=3,
        level_title="Базовый этикет",
        category="Вежливость",
        description="Ладонь направлена к собеседнику или пальцы согнуты у подбородка.",
        tip="Держите руку на уровне груди, ладонь открыта к камере.",
        hands_count=1,
        is_dynamic=False,
    ),
    "помоги": GestureDefinition(
        name="помоги",
        title="Помоги",
        level=3,
        level_title="Базовый этикет",
        category="Фразы помощи",
        description="Кисть направлена к собеседнику или раскрытая ладонь обращена вверх на уровне груди.",
        tip="Держите руку на уровне груди перед камерой, пальцы выпрямлены.",
        hands_count=1,
        is_dynamic=False,
    ),
    "пожалуйста": GestureDefinition(
        name="пожалуйста",
        title="Пожалуйста",
        level=3,
        level_title="Базовый этикет",
        category="Вежливость",
        description="Открытая ладонь приложена к центру груди с лёгким поклоном.",
        tip="Приложите ладонь к груди перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "да": GestureDefinition(
        name="да",
        title="Да",
        level=3,
        level_title="Базовый этикет",
        category="Базовые",
        description="Кисть сжата в кулак перед собой.",
        tip="Сожмите пальцы в плотный кулак перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "нет": GestureDefinition(
        name="нет",
        title="Нет",
        level=3,
        level_title="Базовый этикет",
        category="Базовые",
        description="Указательный палец поднят вертикально вверх, остальные прижаты (жест '1').",
        tip="Выпрямите указательный палец вертикально вверх, остальные сожмите.",
        hands_count=1,
        is_dynamic=True,
    ),
    "мир": GestureDefinition(
        name="мир",
        title="Мир",
        level=3,
        level_title="Базовый этикет",
        category="Базовый этикет",
        description="Указательный и средний пальцы разведены в форме буквы V (жест мира).",
        tip="Покажите жест «мир» (V-знак) указательным и средним пальцами перед камерой.",
        hands_count=1,
        is_dynamic=False,
    ),
    "хорошо": GestureDefinition(
        name="хорошо",
        title="Хорошо",
        level=3,
        level_title="Базовый этикет",
        category="Базовый этикет",
        description="Кулак с поднятым вертикально вверх большим пальцем (жест одобрения).",
        tip="Поднимите большой палец вверх, остальные пальцы плотно сожмите в кулак.",
        hands_count=1,
        is_dynamic=False,
    ),
    # Level 4: «Семья и окружение» (Дом, Мама, Папа, и т.д.)
    "дом": GestureDefinition(
        name="дом",
        title="Дом",
        level=4,
        level_title="Семья и окружение",
        category="Общие жесты",
        description="Обе ладони соприкасаются кончиками пальцев под углом, образуя крышу.",
        tip="Соедините кончики пальцев обеих рук перед грудью в форме крыши домика.",
        hands_count=2,
        is_dynamic=False,
    ),
    "мама": GestureDefinition(
        name="мама",
        title="Мама",
        level=4,
        level_title="Семья и окружение",
        category="Семья",
        description="Большой палец открытой ладони касается подбородка или щеки дважды.",
        tip="Приложите большой палец открытой ладони к подбородку.",
        hands_count=1,
        is_dynamic=False,
    ),
    "папа": GestureDefinition(
        name="папа",
        title="Папа",
        level=4,
        level_title="Семья и окружение",
        category="Семья",
        description="Большой палец открытой ладони касается лба дважды.",
        tip="Приложите большой палец к центру лба, ладонь раскрыта.",
        hands_count=1,
        is_dynamic=False,
    ),
    "семья": GestureDefinition(
        name="семья",
        title="Семья",
        level=4,
        level_title="Семья и окружение",
        category="Семья",
        description="Обе руки образуют круг от центра к себе, смыкаясь пальцами.",
        tip="Опишите полукруг обеими руками перед грудью, соединяя кончики пальцев.",
        hands_count=2,
        is_dynamic=False,
    ),
    "любовь": GestureDefinition(
        name="любовь",
        title="Любовь",
        level=4,
        level_title="Семья и окружение",
        category="Семья и окружение",
        description="Большой палец, указательный и мизинец выпрямлены (жест «Я люблю тебя» / ILY).",
        tip="Выпрямите большой палец, указательный и мизинец, средний и безымянный прижмите к ладони.",
        hands_count=1,
        is_dynamic=False,
    ),
    "стоп": GestureDefinition(
        name="стоп",
        title="Стоп",
        level=4,
        level_title="Семья и окружение",
        category="Семья и окружение",
        description="Раскрытая ладонь направлена вперёд пальцами вверх, останавливающий жест.",
        tip="Поднимите открытую ладонь перед грудью пальцами вверх, ладонь смотрит на камеру.",
        hands_count=1,
        is_dynamic=False,
    ),
    "книга": GestureDefinition(
        name="книга",
        title="Книга",
        level=4,
        level_title="Семья и окружение",
        category="Семья и окружение",
        description="Обе ладони соединены рёбрами перед грудью в форме открытой книги.",
        tip="Раскройте ладони перед собой и сомкните их рёбрами, изображая раскрытую книгу.",
        hands_count=2,
        is_dynamic=False,
    ),
    "ты": GestureDefinition(
        name="ты",
        title="Ты",
        level=4,
        level_title="Семья и окружение",
        category="Общие жесты",
        description="Указательный палец направлен на собеседника.",
        tip="Направьте указательный палец вперёд к камере.",
        hands_count=1,
        is_dynamic=False,
    ),
}


def get_curriculum_level(gesture_name: str, category: str = "") -> tuple[int, str]:
    """Возвращает (level: int, level_title: str) для жеста согласно учебной программе.

    - Level 1: «Дактильный алфавит» (буквы А, Б, В, ...);
    - Level 2: «Числительные и счёт» (числа 1, 2, ...);
    - Level 3: «Базовый этикет» (Привет, Спасибо, и т.д.);
    - Level 4: «Семья и окружение» (Дом, Мама, Папа, и т.д.).
    """
    norm = gesture_name.strip().lower()
    if norm in GESTURE_DEFINITIONS:
        defn = GESTURE_DEFINITIONS[norm]
        return defn.level, defn.level_title

    cat_norm = category.strip().lower()
    if "алфавит" in cat_norm or "дактиль" in cat_norm:
        return 1, "Дактильный алфавит"
    if "числительн" in cat_norm or "счёт" in cat_norm or "счет" in cat_norm or "цифр" in cat_norm:
        return 2, "Числительные и счёт"
    if "привет" in cat_norm or "вежливост" in cat_norm or "этикет" in cat_norm or "базов" in cat_norm:
        return 3, "Базовый этикет"
    if "семь" in cat_norm or "дом" in cat_norm or "окружен" in cat_norm:
        return 4, "Семья и окружение"

    # Эвристическое сопоставление по имени
    if len(norm) == 1 and norm.isalpha():
        return 1, "Дактильный алфавит"
    if norm.startswith("буква_") or norm.startswith("буква "):
        return 1, "Дактильный алфавит"
    if (
        norm.isdigit()
        or norm.startswith("число ")
        or norm in ("один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять", "десять")
    ):
        return 2, "Числительные и счёт"
    if norm in (
        "привет",
        "спасибо",
        "помоги",
        "да",
        "нет",
        "пожалуйста",
        "здравствуйте",
        "до свидания",
        "прости",
        "извини",
        "благодарю",
        "мир",
        "хорошо",
    ):
        return 3, "Базовый этикет"
    if norm in (
        "дом",
        "мама",
        "папа",
        "семья",
        "друг",
        "ты",
        "мы",
        "вы",
        "они",
        "брат",
        "сестра",
        "любовь",
        "стоп",
        "книга",
    ):
        return 4, "Семья и окружение"

    return 3, "Базовый этикет"


def get_curriculum_info(gesture_name: str, category: str = "") -> dict[str, Any]:
    """Возвращает метаданные уровня учебной программы: {'level': int, 'level_title': str}."""
    level, level_title = get_curriculum_level(gesture_name, category)
    return {
        "level": level,
        "level_title": level_title,
    }


def get_curriculum_levels() -> list[dict[str, Any]]:
    """Возвращает упорядоченный список формальных уровней учебного плана."""
    return list(CURRICULUM_LEVELS.values())


def get_all_curriculum_gestures() -> dict[str, dict[str, Any]]:
    """Возвращает словарь всех жестов учебной программы с level и level_title."""
    return {k: v.to_dict() for k, v in GESTURE_DEFINITIONS.items()}


class Gesture:
    """Базовый класс жеста с метаданными и помощниками учебной программы."""

    level: int = 1
    level_title: str = "Дактильный алфавит"

    @staticmethod
    def get_curriculum_info(gesture_name: str, category: str = "") -> dict[str, Any]:
        return get_curriculum_info(gesture_name, category)


class StaticGesture(Gesture):
    """Классификатор статических жестов (форма ладони и пальцев)."""

    def __init__(self, db_path: Path, hands_count: int) -> None:
        self.db_path = db_path
        self.hands_count = hands_count
        self.labels: list[str] = []
        self.vectors: np.ndarray | None = None
        self.model: KNeighborsClassifier | None = None
        self.reload()

    def reload(self) -> None:
        dataset: dict[str, list[np.ndarray]] = {}
        for row in db.get_static_samples(self.db_path, self.hands_count):
            blob = row["features_blob"] if "features_blob" in row else None
            if blob:
                vector = np.frombuffer(blob, dtype=np.float32)
            else:
                vector = np.asarray(json.loads(row["features_json"]), dtype=np.float32)
            dataset.setdefault(row["gesture_name"], []).append(vector)

        vectors = [vector for samples in dataset.values() for vector in samples]
        labels = [name for name, samples in dataset.items() for _ in samples]
        model = None
        if len(labels) >= 3:
            # weights='distance' взвешивает соседей обратно пропорционально расстоянию
            # algorithm='auto' использует BallTree/KDTree для быстрого O(log N) поиска
            model = KNeighborsClassifier(
                n_neighbors=min(len(labels), 3),
                weights="distance",
                metric="euclidean",
                algorithm="brute",
            )
            model.fit(np.asarray(vectors, dtype=np.float32), np.asarray(labels))

        self.dataset = dataset
        self.labels = labels
        self.vectors = np.asarray(vectors, dtype=np.float32) if vectors else None
        self.model = model

    def add_samples(self, name: str, vectors: list[np.ndarray]) -> None:
        samples = [
            (
                name,
                self.hands_count,
                json.dumps(vector.tolist(), allow_nan=False),
                vector.astype(np.float32).tobytes(),
            )
            for vector in vectors
        ]
        db.insert_static_samples(self.db_path, samples)
        self.reload()

    def get_dataset_stats(self) -> dict[str, int]:
        return {name: len(vectors) for name, vectors in self.dataset.items()}

    def extract_vector(self, pose: Pose) -> np.ndarray:
        if not isinstance(pose, Pose):
            raise TypeError("ERROR: No pose was given to gesture engine.\n")
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return data.astype(np.float32)

    """
    Code -255 - Unknown error
    Code -2 - Gesture is unknown (distance exceeded threshold)
    Code -1 - Not trained / hand count mismatch
    Code 0 - Success
    Code 1 - Waiting for calibration
    """

    def predict(self, target: Pose, debug_flag: bool = False) -> tuple[int, float, str, float]:
        """Предсказывает статический жест по ключевым точкам позы.
        Возвращает: (код_статуса, евклидово_расстояние, предсказанное_имя, уверенность_0_100)."""
        if not self.dataset:
            return -1, 0.0, "", 0.0

        if isinstance(target, Pose):
            vector = self.extract_vector(target)
        else:
            if debug_flag:
                vector = target
            else:
                raise IncorrectDataError("ERROR: Trying to predict non Pose object.\n")

        if vector is None or len(vector) == 0:
            return -1, 0.0, "", 0.0

        model = self.model
        if model is None or not self.labels:
            return -1, 0.0, "", 0.0

        try:
            x_arr = vector.reshape(1, -1)
            if x_arr.shape[1] != model.n_features_in_:
                return -1, 0.0, "", 0.0

            # Однократный поиск k-ближайших соседей без повторного вычисления
            distances, indices = model.kneighbors(x_arr)
            score = round(float(np.mean(distances[0][:3])), 2)
            max_distance = 2.0

            # Расчёт уверенности в процентах от 0 до 100%
            confidence = max(0.0, min(100.0, round((1.0 - (score / max_distance)) * 100, 1)))

            if score > max_distance:
                return -2, score, "", confidence

            neighbor_labels = [self.labels[idx] for idx in indices[0]]
            prediction = max(set(neighbor_labels), key=neighbor_labels.count)
            return 0, score, prediction, confidence

        except (ValueError, KeyError, IndexError, TypeError):
            return -255, 0.0, "", 0.0


def dtw_distance(attempt: np.ndarray, reference: np.ndarray) -> float:
    """Вычисляет расстояние DTW между последовательностями через tslearn."""
    return float(dtw(attempt, reference))


class DynamicGestures:
    """Движок распознавания динамических жестов на основе DTW."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path).resolve()

    def calculate_adaptive_threshold(self, references: list[np.ndarray], default_threshold: float = 4.5) -> float:
        """Автоматически вычисляет адаптивный порог DTW на основе эталонов."""
        if len(references) < 2:
            return default_threshold
        pairwise = []
        for i in range(len(references)):
            for j in range(i + 1, len(references)):
                pairwise.append(dtw(references[i], references[j]))
        if not pairwise:
            return default_threshold
        return round(float(np.mean(pairwise) * 1.35), 2)

    def add_sample(self, label: str, sequence: np.ndarray) -> int:
        label = label.strip().lower()
        if not label:
            raise ValueError("Укажи название жеста.")

        features = np.asarray(sequence, dtype=float)
        if features.ndim != 2 or features.shape[1] not in (141, 282):
            raise ValueError("Ожидается последовательность кадров по 141 или 282 признака.")
        if not np.isfinite(features).all():
            raise ValueError("Клип содержит некорректные значения.")

        hands_count = 1 if features.shape[1] == 141 else 2
        return db.insert_dynamic_sample(
            self.db_path,
            label,
            hands_count,
            json.dumps(features.tolist(), allow_nan=False),
            limit=COUNT_OF_SAMPLES,
        )

    def get_samples(self, label: str, hands_count: int) -> list[np.ndarray]:
        rows = db.get_dynamic_samples(self.db_path, label.strip().lower(), hands_count)
        return [np.asarray(json.loads(row), dtype=float) for row in rows]

    def extract_vector(self, pose: Pose) -> np.ndarray:
        if not isinstance(pose, Pose):
            raise TypeError("ERROR: No pose was given to gesture engine.\n")
        if pose.left_hand is None:
            data = pose.get_1d_array_one_hand().flatten()
        else:
            data = pose.get_1d_array_two_hands().flatten()

        return np.round(data, 8)

    def evaluate(
        self,
        attempt: np.ndarray,
        references: list[np.ndarray],
        *,
        max_distance: float | None = None,
    ) -> tuple[bool, dict[str, float]]:
        """Вычисляет оценки DTW и засчитывает жест по среднему k ближайших эталонов."""
        if len(references) < 3:
            raise ValueError(f"Недостаточно эталонов жеста (записано {len(references)}, требуется минимум 3).")
        if attempt.ndim != 2 or attempt.shape[1] not in (141, 282):
            raise ValueError("Некорректный формат попытки.")

        if max_distance is None or max_distance <= 0:
            max_distance = self.calculate_adaptive_threshold(references)

        attempt_shape = attempt.shape[1]
        distances = []
        for sample in references:
            if sample.shape[1] != attempt_shape:
                raise ValueError("Число рук в попытке не совпадает с эталоном.")
            distances.append(dtw(sample, attempt))

        k_nearest = min(3, len(distances))
        nearest = np.partition(distances, k_nearest - 1)[:k_nearest]
        mean_nearest = float(np.mean(nearest))
        mean_all = float(np.mean(distances))
        confidence = max(0.0, min(100.0, round((1.0 - (mean_nearest / max_distance)) * 100, 1)))

        return bool(mean_nearest <= max_distance), {
            "mean_all": round(mean_all, 2),
            "minimum": round(float(np.min(distances)), 2),
            "mean_nearest_three": round(mean_nearest, 2),
            "confidence": confidence,
            "threshold": round(max_distance, 2),
        }

    def verify(
        self,
        attempt: np.ndarray,
        references: list[np.ndarray],
        *,
        max_distance: float | None = None,
    ) -> tuple[bool, float]:
        """Возвращает результат проверки и среднее DTW трёх ближайших эталонов."""
        accepted, distances = self.evaluate(attempt, references, max_distance=max_distance)
        return accepted, distances["mean_nearest_three"]
