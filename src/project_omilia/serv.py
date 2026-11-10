from pathlib import Path
from types import SimpleNamespace
import io
import json
import random
import sqlite3
from contextlib import asynccontextmanager
from math import isfinite
from typing import Any

import numpy as np
from fastapi import FastAPI, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from pydantic import BaseModel

from project_omilia.body import Pose
from project_omilia.gestures import COUNT_OF_GESTURES, COUNT_OF_SAMPLES, DynamicGestures, StaticGesture
import project_omilia.db as db


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATASET_PATH_1H = BASE_DIR / "omilia_static_1h.json"
DATASET_PATH_2H = BASE_DIR / "omilia_static_2h.json"
LEGACY_DATASET_PATH = BASE_DIR / "omilia_static.json"
INDEX_PATH = FRONTEND_DIR / "index.html"
DEBUG_PATH = BASE_DIR / "debug.html"
DB_PATH = BASE_DIR / "omilia.db"
DYNAMIC_DTW_THRESHOLDS = {("нет", 1): 4.3}

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
    def __init__(self, db_path: Path) -> None:
        self.engine = DynamicGestures(db_path)

    def get_ready_gestures(self) -> dict[str, int]:
        ready = {}
        for name, hands_count in DYNAMIC_DTW_THRESHOLDS:
            if name not in ready and db.count_dynamic_samples(self.engine.db_path, name, hands_count) == COUNT_OF_SAMPLES:
                ready[name] = hands_count
        return ready

    def prepare_dynamic_clip(self, frames: list, hands_count: int) -> np.ndarray:
        if len(frames) != COUNT_OF_GESTURES:
            raise ValueError("Ожидается клип из восьми кадров.")

        expected_shape = (141 * hands_count,)
        vectors = []

        for number, frame in enumerate(frames, start=1):
            if not isinstance(frame, dict):
                raise ValueError(f"Кадр {number}: ожидался объект с точками.")
            hands_data = frame.get("hands_data")
            pose_landmarks = frame.get("pose_landmarks")
            if not isinstance(hands_data, list) or len(hands_data) != hands_count:
                raise ValueError(f"Кадр {number}: ожидалось кистей: {hands_count}.")
            if any(not isinstance(hand, list) or len(hand) != 21 for hand in hands_data):
                raise ValueError(f"Кадр {number}: ожидалось 21 точка на кисть.")
            if not isinstance(pose_landmarks, list) or len(pose_landmarks) != 33:
                raise ValueError(f"Кадр {number}: ожидалось 33 точки тела.")

            try:
                pose = make_pose(hands_data, pose_landmarks)
                if pose is None:
                    raise ValueError("Не удалось построить позу.")
                vector = self.engine.extract_vector(pose)
            except (KeyError, TypeError, ValueError, ArithmeticError) as error:
                raise ValueError(f"Кадр {number}: некорректные координаты.") from error

            if vector.shape != expected_shape or not np.isfinite(vector).all():
                raise ValueError(f"Кадр {number}: некорректные признаки.")
            vectors.append(vector)

        return np.stack(vectors)

    def process_dynamic_clip(self, payload: dict[str, Any]) -> dict[str, Any]:
        response: dict[str, Any] = {"type": "dynamic_clip"}
        if type(payload.get("attempt_id")) is int:
            response["attempt_id"] = payload["attempt_id"]
        try:
            hands_count = payload.get("hands_count")
            if type(hands_count) is not int or hands_count not in (1, 2):
                raise ValueError("Выбери режим одной или двух рук.")
            frames = payload.get("frames")
            if not isinstance(frames, list):
                raise ValueError("В пакете нет списка кадров.")

            mode = payload.get("mode")
            if mode not in (None, "record", "verify", "practice"):
                raise ValueError("Неизвестный режим динамического клипа.")
            if mode in ("record", "verify", "practice"):
                label = payload.get("label")
                if not isinstance(label, str) or not label.strip():
                    raise ValueError("Укажи название жеста.")
                label = label.strip().lower()

            if mode in ("verify", "practice"):
                raw_threshold = payload.get("max_distance") if mode == "verify" else None
                if raw_threshold is None:
                    raw_threshold = DYNAMIC_DTW_THRESHOLDS.get((label, hands_count))
                    if raw_threshold is None:
                        if mode == "practice":
                            raise ValueError("Динамическая практика для этого жеста пока недоступна.")
                        raise ValueError("Для этого жеста и режима рук задай порог DTW.")
                try:
                    if type(raw_threshold) not in (int, float):
                        raise ValueError
                    threshold = float(raw_threshold)
                    if not isfinite(threshold) or threshold < 0:
                        raise ValueError
                except (ValueError, OverflowError):
                    raise ValueError("Порог DTW должен быть конечным числом от 0.") from None

                references = self.engine.get_samples(label, hands_count)
                if len(references) != COUNT_OF_SAMPLES:
                    raise ValueError(
                        f"Для жеста «{label}» в этом режиме рук записано "
                        f"{len(references)} из {COUNT_OF_SAMPLES} эталонов."
                    )

            sequence = self.prepare_dynamic_clip(frames, hands_count)
            if mode == "record":
                count = self.engine.add_sample(label, sequence)
                return {
                    **response, "status": "recorded", "label": label, "count": count,
                    "dynamic_dataset": db.list_dynamic_samples(self.engine.db_path),
                }
            if mode in ("verify", "practice"):
                accepted, distances = self.engine.evaluate(sequence, references, max_distance=threshold)
                if mode == "verify":
                    response["distances"] = distances
                return {
                    **response,
                    "status": "verified",
                    "label": label,
                    "accepted": accepted,
                    "distance": distances["mean_nearest_three"],
                    "max_distance": threshold,
                }
        except ValueError as error:
            return {**response, "status": "retry", "reason": str(error)}
        except sqlite3.Error as error:
            print(f"[Динамические жесты] Ошибка SQLite: {error}")
            return {**response, "status": "retry", "reason": "Не удалось обратиться к эталонам."}

        return {**response, "status": "ok", "shape": list(sequence.shape)}


def import_static_datasets(db_path: Path) -> None:
    if db.static_samples_imported(db_path):
        return

    def read_dataset(path: Path) -> dict:
        if not path.is_file() or path.stat().st_size == 0:
            return {}
        dataset = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(dataset, dict):
            raise ValueError(f"Некорректный набор статических жестов: {path.name}")
        return dataset

    split = {1: read_dataset(DATASET_PATH_1H), 2: read_dataset(DATASET_PATH_2H)}
    missing = {hands for hands, dataset in split.items() if not dataset}
    legacy = read_dataset(LEGACY_DATASET_PATH) if missing else {}

    samples = []
    for hands, dataset in split.items():
        width = 141 * hands
        for label, vectors in (dataset or legacy).items():
            name = label.strip().lower()
            if not name or not isinstance(vectors, list):
                raise ValueError("Некорректная запись в старом наборе статических жестов.")
            for values in vectors:
                vector = np.asarray(values, dtype=float)
                if not dataset and vector.shape == (141 * (3 - hands),):
                    continue
                if vector.shape != (width,) or not np.isfinite(vector).all():
                    raise ValueError(f"Некорректный эталон статического жеста «{name}».")
                samples.append((name, hands, json.dumps(vector.tolist(), allow_nan=False)))

    db.import_static_samples(db_path, samples)


class StaticGestureServer:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.engine_1h = StaticGesture(db_path, 1)
        self.engine_2h = StaticGesture(db_path, 2)

    def get_combined_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for engine in (self.engine_1h, self.engine_2h):
            for name, count in engine.get_dataset_stats().items():
                stats[name] = stats.get(name, 0) + count
        return stats

    def get_combined_info(self) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for engine in (self.engine_1h, self.engine_2h):
            for name, count in engine.get_dataset_stats().items():
                item = info.setdefault(name, {"count": 0, "hands": engine.hands_count, "hand_counts": {}})
                item["count"] += count
                item["hand_counts"][engine.hands_count] = count
        return info

    def _record_frame(
        self,
        payload: dict[str, Any],
        pose: Pose | None,
        recording: list[tuple[str, int, np.ndarray]],
    ) -> dict[str, Any]:
        raw_label = payload["record_label"]
        label = raw_label.strip().lower() if isinstance(raw_label, str) else ""
        finished = bool(payload.get("record_finished"))
        hands = payload.get("hands_count")
        if hands not in (1, 2):
            hands = 1 if pose is None or pose.left_hand is None else 2

        if recording and recording[0][:2] != (label, hands):
            recording.clear()
        engine = self.engine_1h if hands == 1 else self.engine_2h
        result = None
        try:
            if not label or pose is None:
                raise ValueError("Кисть не обнаружена.")
            vector = engine.extract_vector(pose)
            if vector.shape != (141 * hands,) or not np.isfinite(vector).all():
                raise ValueError("Кадр не подходит для выбранного режима рук.")
            if len(recording) >= 15:
                recording.clear()
                raise ValueError("Слишком много кадров в серии.")
            recording.append((label, hands, vector))

            if finished:
                engine.add_samples(label, [sample for _, _, sample in recording])
                result = {"status": "saved", "label": label, "count": len(recording)}
            message = f"Запись: {label}"
        except (ValueError, ArithmeticError, sqlite3.Error) as error:
            print(f"[Статическая запись] {error}")
            message = "Не удалось обработать кадр."
            if finished:
                result = {"status": "retry", "reason": "Не удалось сохранить статический жест. Повторите запись."}
        finally:
            if finished:
                recording.clear()

        response = {
            "detected": pose is not None,
            "gesture": message,
            "name": message,
            "dataset_stats": self.get_combined_stats(),
            "dataset_info": self.get_combined_info(),
        }
        if result is not None:
            response["static_record"] = result
        return response

    def process_frame(
        self, payload: dict[str, Any], recording: list[tuple[str, int, np.ndarray]],
    ) -> dict[str, Any]:
        hands_data = payload.get("hands_data") or payload.get("hands") or []
        pose_landmarks = payload.get("pose_landmarks")
        record_label = payload.get("record_label")
        hands_count = payload.get("hands_count")  # 1 или 2 из тумблера

        # ЖЕСТКИЙ ТУМБЛЕР РЕЖИМА 1 РУКА:
        # Если тумблер в режиме 1 рука (или hands_count == 1):
        # захватывается строго 1 рука. Если случайно попадает вторая рука — отсекаем её!
        if hands_count == 1 and len(hands_data) > 1:
            hands_data = hands_data[:1]

        try:
            pose = make_pose(hands_data, pose_landmarks)
        except (KeyError, TypeError, ValueError):
            pose = None
        if record_label:
            return self._record_frame(payload, pose, recording)
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

        # Режим классификации / тестирования:
        # Если тумблер установлен на 2 руки, а в кадре только 1 рука:
        if hands_count == 2 and pose.left_hand is None:
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
            if engine.model is None:
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
        db.delete_static_gesture(self.db_path, gesture_name.strip().lower())
        self.engine_1h.reload()
        self.engine_2h.reload()

    def handle_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "train_dataset":
                self.engine_1h.reload()
                self.engine_2h.reload()
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
    import_static_datasets(DB_PATH)
    server = StaticGestureServer(DB_PATH)
    dynamic_server = DynamicGestureServer(DB_PATH)
    total_gestures = len(server.engine_1h.dataset) + len(server.engine_2h.dataset)
    print(f"Сервер Omiλia запущен. SQLite: {DB_PATH.name}, статических наборов: {total_gestures}")
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

    dynamic_hands = dynamic_server.get_ready_gestures() if dynamic_server else {}

    gestures_list = []
    for norm_name in combined_stats.keys() | dynamic_hands.keys():
        hands_count = dynamic_hands.get(norm_name)
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
                "description": (
                    "Динамический жест. Покажите движение целиком после отсчёта."
                    if hands_count else meta.get("description", "")
                ),
                "tip": (
                    f"Покажите жест {'одной рукой' if hands_count == 1 else 'двумя руками'} за одну секунду."
                    if hands_count else meta.get("tip", "")
                ),
                "samples_count": COUNT_OF_SAMPLES if hands_count else combined_stats[norm_name],
                "dynamic_hands_count": hands_count,
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
    static_names = server.get_combined_stats().keys() if server else set()
    dynamic_hands = dynamic_server.get_ready_gestures() if dynamic_server else {}
    available_names = static_names | dynamic_hands.keys()
    learned = [name.strip().lower() for name in learned if name.strip().lower() in available_names]
    if not learned:
        return {
            "status": "ok",
            "questions": [],
            "message": "Для блица выучи хотя бы один доступный жест в словаре.",
        }

    # Выбираем случайную подвыборку из уже выученных жестов
    sample_size = min(len(learned), count)
    selected = random.sample(learned, sample_size)

    questions = []
    for name in selected:
        meta = GESTURE_METADATA.get(name, {})
        hands_count = dynamic_hands.get(name)
        tip = meta.get("tip", "Покажите жест на камеру")
        if hands_count:
            hand_instruction = "одной рукой" if hands_count == 1 else "двумя руками"
            tip = f"Покажите жест {hand_instruction} за одну секунду."
        questions.append(
            {
                "gesture_name": name,
                "title": meta.get("title", name.capitalize()),
                "tip": tip,
                "dynamic_hands_count": hands_count,
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
    recording: list[tuple[str, int, np.ndarray]] = []

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
                    action = payload["action"]
                    if action == "cancel_static_recording":
                        recording.clear()
                        continue
                    if action == "delete_gesture":
                        recording.clear()
                    response = server.handle_action(action, payload)
                    if action == "get_dataset_stats":
                        response["dynamic_dataset"] = db.list_dynamic_samples(DB_PATH)
                else:
                    response = server.process_frame(payload, recording)

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
