from pathlib import Path
from types import SimpleNamespace
import io
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from gtts import gTTS

from project_omilia.body import Pose
from project_omilia.gestures import StaticGesture


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "omilia_static.json"
INDEX_PATH = BASE_DIR / "index.html"


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

        # Режим записи жеста в датасет
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global server
    server = StaticGestureServer(dataset_path=DATASET_PATH)
    print(f"Сервер запущен. Датасет: {DATASET_PATH.name} (жестов: {len(server.engine.dataset)})")
    yield


app = FastAPI(title="Project Omilia", lifespan=lifespan)


@app.get("/")
async def root():
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return JSONResponse(status_code=404, content={"error": "index.html not found"})


@app.get("/api/tts")
def synthesize_speech(text: str = Query(..., min_length=1, max_length=300)):
    try:
        buffer = io.BytesIO()
        gTTS(text=text.strip(), lang="ru").write_to_fp(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/mpeg")
    except Exception as err:
        return JSONResponse(status_code=500, content={"error": f"Ошибка TTS: {err}"})


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
