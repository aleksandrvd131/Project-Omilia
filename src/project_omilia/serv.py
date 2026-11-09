from pathlib import Path
from types import SimpleNamespace
import io
import json
import random
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import FastAPI, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from pydantic import BaseModel

from project_omilia.body import Pose
from project_omilia.gestures import StaticGesture, DynamicGestures
import project_omilia.db as db


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATASET_PATH_1H = BASE_DIR / "omilia_static_1h.json"
DATASET_PATH_2H = BASE_DIR / "omilia_static_2h.json"
DYNAMIC_DATASET_PATH_1H = BASE_DIR / "omilia_dynamic_1h.json"
DYNAMIC_DATASET_PATH_2H = BASE_DIR / "omilia_dynamic_2h.json"
LEGACY_DATASET_PATH = BASE_DIR / "omilia_static.json"
INDEX_PATH = FRONTEND_DIR / "index.html"
DEBUG_PATH = BASE_DIR / "debug.html"
DB_PATH = BASE_DIR / "omilia.db"

# Базовые описания и подсказки для жестов
GESTURE_METADATA: dict[str, dict[str, str]] = {
    "привет": {
        "title": "Привет",
        "category": "Приветствия",
        "description": "Раскрытая ладонь направлена вперёд на уровне плеча, пальцы прямые.",
        "tip": "Поднимите открытую ладонь на уровень лица или плеча, пальцы смотрят вверх.",
    },
    "помоги": {
        "title": "Помоги",
        "category": "Фразы помощи",
        "description": "Кисть направлена к собеседнику или раскрытая ладонь обращена вверх на уровне груди.",
        "tip": "Держите руку на уровне груди перед камерой, пальцы выпрямлены.",
    },
    "дом": {
        "title": "Дом",
        "category": "Общие жесты",
        "description": "Обе ладони соприкасаются кончиками пальцев под углом, образуя крышу.",
        "tip": "Соедините кончики пальцев обеих рук перед грудью в форме крыши домика.",
    },
    "спасибо": {
        "title": "Спасибо",
        "category": "Вежливость",
        "description": "Ладонь направлена к собеседнику или пальцы согнуты у подбородка.",
        "tip": "Держите руку на уровне груди, ладонь открыта к камере.",
    },
    "да": {
        "title": "Да",
        "category": "Базовые",
        "description": "Кисть сжата в кулак перед собой.",
        "tip": "Сожмите пальцы в плотный кулак перед камерой.",
    },
    "нет": {
        "title": "Нет",
        "category": "Базовые",
        "description": "Указательный палец поднят вертикально вверх, остальные прижаты (жест '1').",
        "tip": "Выпрямите указательный палец вертикально вверх, остальные сожмите.",
    },
    "а": {
        "title": "Буква А",
        "category": "Дактиль (Алфавит)",
        "description": "Пальцы сжаты в кулак, большой палец прижат сбоку к указательному.",
        "tip": "Кулак направлен ладонью к зрителю, большой палец прижат сбоку.",
    },
    "б": {
        "title": "Буква Б",
        "category": "Дактиль (Алфавит)",
        "description": "Четыре пальца прямые вверх, большой палец согнут и прижат к ладони.",
        "tip": "Пальцы сомкнуты вместе и направлены строго вверх.",
    },
    "в": {
        "title": "Буква В",
        "category": "Дактиль (Алфавит)",
        "description": "Все пять пальцев широко раскрыты и направлены вверх.",
        "tip": "Раскройте ладонь максимально широко перед камерой.",
    },
}


def make_pose(hands_data: list, pose_landmarks: list | None) -> Pose | None:
    if not hands_data:
        return None

    hands: list[list[SimpleNamespace]] = []
    for hand in hands_data[:2]:
        if len(hand) == 21:
            hands.append([SimpleNamespace(x=p["x"], y=p["y"], z=p.get("z", 0.0)) for p in hand])

    if not hands:
        return None

    if pose_landmarks and len(pose_landmarks) == 33:
        body = [SimpleNamespace(x=p["x"], y=p["y"], z=p.get("z", 0.0)) for p in pose_landmarks]
    else:
        # Базовый скелет, если тело не попало в кадр целиком
        body = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(33)]
        body[0] = SimpleNamespace(x=0.5, y=0.25, z=0.0)
        body[11] = SimpleNamespace(x=0.4, y=0.45, z=0.0)
        body[12] = SimpleNamespace(x=0.6, y=0.45, z=0.0)
        # В Pose: body[15] - правое запястье, body[16] - левое запястье
        body[15] = SimpleNamespace(x=hands[0][0].x, y=hands[0][0].y, z=hands[0][0].z)
        if len(hands) > 1:
            body[16] = SimpleNamespace(x=hands[1][0].x, y=hands[1][0].y, z=hands[1][0].z)
        else:
            body[16] = SimpleNamespace(x=-1.0, y=-1.0, z=0.0)

    try:
        return Pose(body, tuple(hands))
    except Exception:
        return None

class DynamicGestureServer:

    def __init__(self, dataset_path_1h: Path, dataset_path_2h: Path) -> None:
        self.dataset_path_1h = Path(dataset_path_1h).resolve()
        self.dataset_path_2h = Path(dataset_path_2h).resolve()
        self.engine_1h = DynamicGestures(dataset_path_1h)
        self.engine_2h = DynamicGestures(dataset_path_2h)

    def prepare_dynamic_clip(self, frames: list , engine, hands_count) -> np.ndarray:
        if len(frames) != 8:
            raise ValueError("Incorrect count of frames")
        vectors = []

        expected_values = 141 if hands_count == 1 else 282

        for frame in frames:

            if frame.get("hands_data") is None or frame.get("pose_landmarks") is None:
                raise ValueError("Incorrect frame")

            hands_data = frame["hands_data"]
            pose_landmarks = frame["pose_landmarks"]

            if hands_count == 1 and len(hands_data) > 1:
                hands_data = hands_data[:1]

            pose = make_pose(hands_data, pose_landmarks)
            if pose is None:
                raise ValueError("Incorrect data")

            vector = engine.extract_vector(pose)
            if vector.shape != (expected_values,):
                raise ValueError("Incorrect vector")
            if not np.isfinite(vector).all():
                raise ValueError("Incorrect vector")

            vectors.append(vector)

        return np.stack(vectors)

    def process_dynamic_clip(self, payload) -> dict:
        try:
            if payload.get("hands_count") is None:
                raise ValueError("Hands count must be announced")
            if payload.get("frames") is None:
                raise ValueError("Frames must be announced")
        except ValueError as error:
            return {
                "type": "dynamic_clip",
                "status": "retry",
                "reason": str(error),
            }
        hands_count = payload["hands_count"]
        frames = payload["frames"]
        if hands_count not in [1, 2]:
            return {
                "type": "dynamic_clip",
                "status": "retry",
                "reason": "Invalid hands count",
            }
        try:
            if hands_count == 1:
                sequence = self.prepare_dynamic_clip(frames, self.engine_1h, 1)
            else:
                sequence = self.prepare_dynamic_clip(frames, self.engine_2h, 2)
        except ValueError as error:
            return {
                "type": "dynamic_clip",
                "status": "retry",
                "reason": str(error),
            }
        return {
            "type": "dynamic_clip",
            "status": "ok",
            "shape": list(sequence.shape),
        }


class StaticGestureServer:
    def __init__(self, dataset_path_1h: Path, dataset_path_2h: Path) -> None:
        self.dataset_path_1h = Path(dataset_path_1h).resolve()
        self.dataset_path_2h = Path(dataset_path_2h).resolve()

        # Автоматическая миграция из старого omilia_static.json при необходимости
        self._ensure_split_datasets()

        self.engine_1h = StaticGesture(dataset_path=str(self.dataset_path_1h))
        self.engine_2h = StaticGesture(dataset_path=str(self.dataset_path_2h))

    def _ensure_split_datasets(self) -> None:
        """Если файлов 1h или 2h нет, автоматически разделяет существующий omilia_static.json."""
        need_1h = not self.dataset_path_1h.exists() or self.dataset_path_1h.stat().st_size == 0
        need_2h = not self.dataset_path_2h.exists() or self.dataset_path_2h.stat().st_size == 0

        if (need_1h or need_2h) and LEGACY_DATASET_PATH.exists() and LEGACY_DATASET_PATH.stat().st_size > 0:
            try:
                with open(LEGACY_DATASET_PATH, mode="r", encoding="utf-8") as f:
                    legacy_data = json.load(f)

                data_1h: dict[str, list[list[float]]] = {}
                data_2h: dict[str, list[list[float]]] = {}

                for name, vectors in legacy_data.items():
                    if not vectors:
                        continue
                    dim = len(vectors[0])
                    if dim <= 141:
                        data_1h[name] = vectors
                    else:
                        data_2h[name] = vectors

                if need_1h and data_1h:
                    with open(self.dataset_path_1h, mode="w", encoding="utf-8") as f:
                        json.dump(data_1h, f, ensure_ascii=False, indent=2)
                    print(f"[Миграция] Создан {self.dataset_path_1h.name} с жестами: {list(data_1h.keys())}")

                if need_2h and data_2h:
                    with open(self.dataset_path_2h, mode="w", encoding="utf-8") as f:
                        json.dump(data_2h, f, ensure_ascii=False, indent=2)
                    print(f"[Миграция] Создан {self.dataset_path_2h.name} с жестами: {list(data_2h.keys())}")
            except Exception as err:
                print(f"[Миграция] Ошибка разделения датасетов: {err}")

    def get_combined_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for k, v in self.engine_1h.get_dataset_stats().items():
            stats[k] = v
        for k, v in self.engine_2h.get_dataset_stats().items():
            stats[k] = v
        return stats

    def get_combined_info(self) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for k, v in self.engine_1h.get_dataset_stats().items():
            info[k] = {"count": v, "hands": 1}
        for k, v in self.engine_2h.get_dataset_stats().items():
            info[k] = {"count": v, "hands": 2}
        return info

    def process_frame(self, payload: dict[str, Any]) -> dict[str, Any]:
        hands_data = payload.get("hands_data") or payload.get("hands") or []
        pose_landmarks = payload.get("pose_landmarks")
        record_label = payload.get("record_label")
        hands_count = payload.get("hands_count")  # 1 или 2 из тумблера
        record_finished = payload.get("record_finished", False)

        # ЖЕСТКИЙ ТУМБЛЕР РЕЖИМА 1 РУКА:
        # Если тумблер в режиме 1 рука (или hands_count == 1):
        # захватывается строго 1 рука. Если случайно попадает вторая рука — отсекаем её!
        if hands_count == 1 and len(hands_data) > 1:
            hands_data = hands_data[:1]

        pose = make_pose(hands_data, pose_landmarks)
        if pose is None:
            return {
                "detected": False,
                "gesture": None,
                "name": None,
                "score": None,
                "distance": None,
                "dataset_stats": self.get_combined_stats(),
                "dataset_info": self.get_combined_info(),
            }

        # Выбор движка классификации:
        if hands_count == 1:
            engine = self.engine_1h
        elif hands_count == 2:
            engine = self.engine_2h
        else:
            engine = self.engine_1h if pose.left_hand is None else self.engine_2h

        # Режим записи жеста в датасет (через панель разработчика)
        if record_label:
            norm_label = record_label.strip().lower()

            # Для двуручного жеста обязательно должно быть 2 руки
            if hands_count == 2 and len(hands_data) < 2:
                return {
                    "detected": True,
                    "gesture": "Требуется 2 руки",
                    "name": "Требуется 2 руки",
                    "score": 0.0,
                    "distance": 0.0,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }

            try:
                # ОПТИМИЗАЦИЯ: при сборе серии кадров (1..14) кадры накапливаются в ОЗУ,
                # а переобучение модели и сброс на диск происходят ТОЛЬКО на последнем кадре серии!
                is_last = bool(record_finished)
                engine.add_sample(
                    name=norm_label,
                    pose=pose,
                    auto_train=is_last,
                    auto_save=is_last,
                )
                if is_last:
                    engine.save_and_train()

                stats = self.get_combined_stats()
                info = self.get_combined_info()
                status_suffix = " [сохранено и переобучено]" if is_last else ""
                print(f"[Запись] Сэмпл для '{norm_label}' сохранён ({hands_count or 1} рук, всего: {stats.get(norm_label, 0)}){status_suffix}")

                return {
                    "detected": True,
                    "gesture": f"Запись: {norm_label}",
                    "name": f"Запись: {norm_label}",
                    "score": 1.0,
                    "distance": 1.0,
                    "dataset_stats": stats,
                    "dataset_info": info,
                }
            except Exception as err:
                print(f"[Запись] Ошибка сэмпла: {err}")
                return {
                    "detected": True,
                    "gesture": "Ошибка геометрии",
                    "name": "Ошибка геометрии",
                    "score": 0.0,
                    "distance": 0.0,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }

        # Режим классификации / тестирования:
        # Если тумблер установлен на 2 руки, а в кадре только 1 рука:
        if hands_count == 2 and len(hands_data) < 2:
            return {
                "detected": True,
                "gesture": "Покажите 2 руки",
                "name": "Покажите 2 руки",
                "score": 0.0,
                "distance": 0.0,
                "dataset_stats": self.get_combined_stats(),
                "dataset_info": self.get_combined_info(),
            }

        code, score, prediction = engine.predict(pose)

        total_samples = sum(len(v) for v in engine.dataset.values())
        if code == 0:
            gesture_name = prediction
        elif code == -1:
            dim = 141 if pose.left_hand is None else 282
            hands_num = 1 if dim == 141 else 2
            model_exists = hasattr(engine, "models") and dim in engine.models
            if not model_exists:
                gesture_name = f"Нет модели для {hands_num} рук(и)"
            elif total_samples < 3:
                gesture_name = f"Мало данных ({total_samples}/3)"
            else:
                gesture_name = "Не совпадает число рук"
        elif code == -2:
            gesture_name = "Неизвестный жест"
        else:
            gesture_name = "—"

        return {
            "detected": True,
            "gesture": gesture_name,
            "name": gesture_name,
            "score": score,
            "distance": score,
            "dataset_stats": self.get_combined_stats(),
            "dataset_info": self.get_combined_info(),
        }

    def delete_gesture(self, gesture_name: str) -> None:
        """Удаляет жест из обоих датасетов (1h и 2h), старого файла и базы данных."""
        norm_name = gesture_name.strip().lower()
        self.engine_1h.delete_gesture(norm_name)
        self.engine_2h.delete_gesture(norm_name)
        if LEGACY_DATASET_PATH.exists():
            try:
                with open(LEGACY_DATASET_PATH, mode="r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                if norm_name in legacy_data:
                    legacy_data.pop(norm_name)
                    from project_omilia.gestures import format_dataset_json_inline
                    with open(LEGACY_DATASET_PATH, mode="w", encoding="utf-8") as f:
                        f.write(format_dataset_json_inline(legacy_data))
            except Exception as err:
                print(f"[Удаление] Ошибка обновления legacy файла: {err}")
        db.remove_gesture_from_db(DB_PATH, norm_name)
        print(f"[Удаление] Жест '{norm_name}' успешно удален из датасета")

    def handle_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "train_dataset":
                self.engine_1h.save_and_train()
                self.engine_2h.save_and_train()
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case "delete_gesture":
                gesture_name = payload.get("gesture_name", "").strip().lower()
                self.delete_gesture(gesture_name)
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case "get_dataset_stats":
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }
            case _:
                return {
                    "detected": False,
                    "dataset_stats": self.get_combined_stats(),
                    "dataset_info": self.get_combined_info(),
                }


server: StaticGestureServer | None = None
dynamic_server: DynamicGestureServer | None = None


# DTO схемы для запросов
class AuthRequest(BaseModel):
    username: str
    password: str


class LearnRequest(BaseModel):
    gesture_name: str


def get_current_user_from_request(
    request: Request, authorization: str | None = Header(None)
) -> dict[str, Any] | None:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif "token" in request.query_params:
        token = request.query_params["token"]
    if token:
        return db.get_user_by_token(DB_PATH, token)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global server
    global dynamic_server
    db.init_db(DB_PATH)
    server = StaticGestureServer(dataset_path_1h=DATASET_PATH_1H, dataset_path_2h=DATASET_PATH_2H)
    dynamic_server = DynamicGestureServer(dataset_path_1h=DYNAMIC_DATASET_PATH_1H, dataset_path_2h=DYNAMIC_DATASET_PATH_2H)
    total_gestures = len(server.engine_1h.dataset) + len(server.engine_2h.dataset)
    print(f"Сервер Omiλia запущен. Датасеты: 1H={DATASET_PATH_1H.name}, 2H={DATASET_PATH_2H.name} (всего жестов: {total_gestures})")
    yield


app = FastAPI(title="Project Omilia", lifespan=lifespan)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# --- Статические страницы ---
@app.get("/")
async def root():
    """Основной интерфейс для пользователей (бело-зелёная тема)."""
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return JSONResponse(status_code=404, content={"error": "index.html not found"})


@app.get("/dev")
@app.get("/debug")
async def dev_page():
    """Панель разработчика (запись жестов, тест с жестким тумблером 1/2 рук)."""
    if DEBUG_PATH.exists():
        return FileResponse(DEBUG_PATH)
    return JSONResponse(status_code=404, content={"error": "debug.html not found"})


# --- Аутентификация ---
@app.post("/api/auth/register")
async def api_register(data: AuthRequest):
    user, err = db.register_user(DB_PATH, data.username, data.password)
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    return {"status": "ok", "user": user}


@app.post("/api/auth/login")
async def api_login(data: AuthRequest):
    user, err = db.login_user(DB_PATH, data.username, data.password)
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    return {"status": "ok", "user": user}


@app.get("/api/auth/me")
async def api_me(request: Request, authorization: str | None = Header(None)):
    user = get_current_user_from_request(request, authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Не авторизован"})
    learned = db.get_learned_gestures(DB_PATH, user["id"])
    return {
        "status": "ok",
        "user": user,
        "learned_gestures": learned,
    }


@app.post("/api/auth/logout")
async def api_logout(request: Request, authorization: str | None = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if token:
        db.logout_user(DB_PATH, token)
    return {"status": "ok"}


# --- Каталог жестов и прогресс ---
@app.get("/api/gestures")
async def api_get_gestures(request: Request, authorization: str | None = Header(None)):
    user = get_current_user_from_request(request, authorization)
    learned_set = set(g.strip().lower() for g in db.get_learned_gestures(DB_PATH, user["id"])) if user else set()

    combined_stats = server.get_combined_stats() if server else {}

    # Собираем список всех жестов, обученных в модели
    gestures_list = []
    for gesture_name, count in combined_stats.items():
        norm_name = gesture_name.strip().lower()
        meta = GESTURE_METADATA.get(
            norm_name,
            {
                "title": norm_name.capitalize(),
                "category": "Общие жесты",
                "description": f"Статический жест «{norm_name}».",
                "tip": "Повторите положение кисти перед камерой.",
            },
        )
        gestures_list.append(
            {
                "name": norm_name,
                "title": meta.get("title", norm_name.capitalize()),
                "category": meta.get("category", "Общие жесты"),
                "description": meta.get("description", ""),
                "tip": meta.get("tip", ""),
                "samples_count": count,
                "is_learned": norm_name in learned_set,
            }
        )

    # Сортировка: сначала невыученные, затем выученные
    gestures_list.sort(key=lambda g: (g["is_learned"], g["name"]))
    total_learned = sum(1 for g in gestures_list if g["is_learned"])

    return {
        "status": "ok",
        "gestures": gestures_list,
        "total_count": len(gestures_list),
        "learned_count": total_learned,
        "total_learned": total_learned,
        "total_available": len(gestures_list),
    }


@app.post("/api/gestures/learn")
async def api_learn_gesture(
    data: LearnRequest, request: Request, authorization: str | None = Header(None)
):
    user = get_current_user_from_request(request, authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    gesture_name = data.gesture_name.strip().lower()
    if not gesture_name:
        return JSONResponse(status_code=400, content={"error": "Имя жеста не указано"})

    success = db.mark_gesture_learned(DB_PATH, user["id"], gesture_name)
    if not success:
        return JSONResponse(status_code=500, content={"error": "Ошибка базы данных"})

    learned = db.get_learned_gestures(DB_PATH, user["id"])
    return {
        "status": "ok",
        "learned_gestures": learned,
        "learned_count": len(learned),
    }


@app.delete("/api/gestures/{gesture_name}")
async def api_delete_gesture(gesture_name: str):
    """Удаляет жест из датасета модели (вызывается из панели разработчика /dev)."""
    if server is None:
        return JSONResponse(status_code=500, content={"error": "Сервер не инициализирован"})

    norm_name = gesture_name.strip().lower()
    server.delete_gesture(norm_name)
    return {
        "status": "ok",
        "deleted": norm_name,
        "dataset_stats": server.get_combined_stats(),
        "dataset_info": server.get_combined_info(),
    }


# --- Блиц-опрос («Проверить себя») ---
@app.get("/api/blitz/questions")
async def api_blitz_questions(
    request: Request, count: int = Query(5, ge=1, le=20), authorization: str | None = Header(None)
):
    user = get_current_user_from_request(request, authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    learned = db.get_learned_gestures(DB_PATH, user["id"])
    if not learned:
        return {
            "status": "ok",
            "questions": [],
            "message": "У вас пока нет выученных жестов. Изучите хотя бы один жест в каталоге!",
        }

    # Выбираем случайную подвыборку из уже выученных жестов
    sample_size = min(len(learned), count)
    selected = random.sample(learned, sample_size)

    questions = []
    for gname in selected:
        norm = gname.strip().lower()
        meta = GESTURE_METADATA.get(norm, {})
        questions.append(
            {
                "gesture_name": norm,
                "title": meta.get("title", norm.capitalize()),
                "tip": meta.get("tip", "Покажите жест на камеру"),
            }
        )

    return {
        "status": "ok",
        "questions": questions,
        "total_available": len(learned),
    }


# --- Синтез речи ---
@app.get("/api/tts")
def synthesize_speech(text: str = Query(..., min_length=1, max_length=300)):
    try:
        buffer = io.BytesIO()
        gTTS(text=text.strip(), lang="ru").write_to_fp(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/mpeg")
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": f"Ошибка TTS: {err}"})


# --- WebSocket для камеры ---
@app.websocket("/ws/gestures")
async def gesture_ws(websocket: WebSocket):
    await websocket.accept()
    print("[WebSocket] Клиент подключился")

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            if server is None:
                continue

            try:
                if payload.get("type") == "dynamic_clip":
                    response = dynamic_server.process_dynamic_clip(payload)
                elif "action" in payload:
                    response = server.handle_action(payload["action"], payload)
                else:
                    response = server.process_frame(payload)

                await websocket.send_json(response)
            except Exception as err:
                print(f"[WebSocket] Ошибка обработки кадра: {err}")

    except WebSocketDisconnect:
        print("[WebSocket] Клиент отключился")


if __name__ == "__main__":
    import sys
    import uvicorn

    src_dir = str(Path(__file__).resolve().parent.parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    uvicorn.run("project_omilia.serv:app", host="0.0.0.0", port=8000, reload=False)
