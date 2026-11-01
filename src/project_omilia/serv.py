from pathlib import Path
from types import SimpleNamespace
import io
import json
import random
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from pydantic import BaseModel

from project_omilia.body import Pose
from project_omilia.gestures import StaticGesture
import project_omilia.db as db


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATASET_PATH = BASE_DIR / "omilia_static.json"
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
    "А": {
        "title": "Буква А",
        "category": "Дактиль (Алфавит)",
        "description": "Пальцы сжаты в кулак, большой палец прижат сбоку к указательному.",
        "tip": "Кулак направлен ладонью к зрителю, большой палец прижат сбоку.",
    },
    "Б": {
        "title": "Буква Б",
        "category": "Дактиль (Алфавит)",
        "description": "Четыре пальца прямые вверх, большой палец согнут и прижат к ладони.",
        "tip": "Пальцы сомкнуты вместе и направлены строго вверх.",
    },
    "В": {
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
        body[15] = SimpleNamespace(x=hands[0][0].x, y=hands[0][0].y, z=hands[0][0].z)
        if len(hands) > 1:
            body[16] = SimpleNamespace(x=hands[1][0].x, y=hands[1][0].y, z=hands[1][0].z)
        else:
            body[16] = SimpleNamespace(x=-1.0, y=-1.0, z=0.0)

    try:
        return Pose(body, tuple(hands))
    except Exception:
        return None


class StaticGestureServer:
    def __init__(self, dataset_path: Path):
        self.engine = StaticGesture(dataset_path=str(dataset_path))

    def process_frame(self, payload: dict[str, Any]) -> dict[str, Any]:
        hands_data = payload.get("hands_data") or []
        pose_landmarks = payload.get("pose_landmarks")
        record_label = payload.get("record_label")

        pose = make_pose(hands_data, pose_landmarks)
        if pose is None:
            return {
                "detected": False,
                "gesture": None,
                "score": None,
                "dataset_stats": self.engine.get_dataset_stats(),
            }

        # Режим записи жеста в датасет (через панель разработчика)
        if record_label:
            try:
                self.engine.add_sample(name=record_label, pose=pose)
                stats = self.engine.get_dataset_stats()
                print(f"[Запись] Сохранён сэмпл для '{record_label}' (всего: {stats.get(record_label, 0)})")
                return {
                    "detected": True,
                    "gesture": f"Запись: {record_label}",
                    "score": 1.0,
                    "dataset_stats": stats,
                }
            except Exception as err:
                print(f"[Запись] Ошибка сэмпла: {err}")
                return {
                    "detected": True,
                    "gesture": "Ошибка геометрии",
                    "score": 0.0,
                    "dataset_stats": self.engine.get_dataset_stats(),
                }

        # Режим классификации
        code, score, prediction = self.engine.predict(pose)

        total_samples = sum(len(v) for v in self.engine.dataset.values())
        if code == 0:
            gesture_name = prediction
        elif code == -1:
            if total_samples < 3:
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
            "score": score,
            "dataset_stats": self.engine.get_dataset_stats(),
        }

    def handle_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "delete_gesture":
                gesture_name = payload.get("gesture_name", "")
                stats = self.engine.delete_gesture(gesture_name)
                return {
                    "detected": False,
                    "dataset_stats": stats,
                }
            case _:
                return {
                    "detected": False,
                    "dataset_stats": self.engine.get_dataset_stats(),
                }


server: StaticGestureServer | None = None


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
    db.init_db(DB_PATH)
    server = StaticGestureServer(dataset_path=DATASET_PATH)
    print(f"Сервер запущен. Датасет: {DATASET_PATH.name} (жестов: {len(server.engine.dataset)})")
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
    """Скрытая страница для разработчиков (запись и удаление жестов)."""
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
    learned_set = set(db.get_learned_gestures(DB_PATH, user["id"])) if user else set()

    dataset_stats = server.engine.get_dataset_stats() if server else {}

    # Собираем список всех жестов, обученных в модели
    gestures_list = []
    for gesture_name, count in dataset_stats.items():
        meta = GESTURE_METADATA.get(
            gesture_name.lower(),
            {
                "title": gesture_name.capitalize(),
                "category": "Общие жесты",
                "description": f"Статический жест «{gesture_name}».",
                "tip": "Повторите положение кисти перед камерой.",
            },
        )
        gestures_list.append(
            {
                "name": gesture_name,
                "title": meta.get("title", gesture_name),
                "category": meta.get("category", "Общие жесты"),
                "description": meta.get("description", ""),
                "tip": meta.get("tip", ""),
                "samples_count": count,
                "is_learned": gesture_name in learned_set,
            }
        )

    # Сортировка: сначала невыученные, затем выученные
    gestures_list.sort(key=lambda g: (g["is_learned"], g["name"]))

    return {
        "status": "ok",
        "gestures": gestures_list,
        "total_count": len(gestures_list),
        "learned_count": len(learned_set),
    }


@app.post("/api/gestures/learn")
async def api_learn_gesture(
    data: LearnRequest, request: Request, authorization: str | None = Header(None)
):
    user = get_current_user_from_request(request, authorization)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    gesture_name = data.gesture_name.strip()
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
        meta = GESTURE_METADATA.get(gname.lower(), {})
        questions.append(
            {
                "gesture_name": gname,
                "title": meta.get("title", gname.capitalize()),
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
                if "action" in payload:
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
