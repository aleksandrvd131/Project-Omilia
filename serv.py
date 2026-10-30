import io
import json
import sys
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

sys.modules["sounddevice"] = None

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from gtts import gTTS

try:
    from project_omilia.engine import (
        DynamicTracker74,
        RSLWordAssembler,
        StaticSignEngine74,
    )
except ImportError:
    from bone_gesture_engine import (  # type: ignore[no-redef]
        DynamicTracker74,
        RSLWordAssembler,
        StaticSignEngine74,
    )

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "rsl_static_dataset_74.json"
RULES_PATH = BASE_DIR / "rsl_dynamic_rules.json"
INDEX_PATH = BASE_DIR / "index.html"

# Сигнатура детектора: принимает сырой payload и возвращает (hands_data, pose_landmarks)
LandmarkExtractor = Callable[[dict[str, Any]], tuple[list[dict], list[dict] | None]]


def default_extractor(payload: dict[str, Any]) -> tuple[list[dict], list[dict] | None]:
    """
    Дефолтный адаптер: ожидает координаты прямо в payload
    Когда реализуем детекцию MediaPipe в отдельном модуле, передадут
    функцию при инициализации GesturePipeline(detector=your_detector)
    """
    hands = payload.get("hands_data") or payload.get("hands") or []
    pose = payload.get("pose_landmarks") or payload.get("pose")
    return hands, pose


class GesturePipeline:
    """
    Сервисный слой: связывает веб-транспорт с математическим движком РЖЯ.
    Отвечает за диспетчеризацию действий пользователя и прогон точек через классификаторы.
    """

    def __init__(
        self,
        dataset_path: Path,
        rules_path: Path,
        detector: LandmarkExtractor | None = None,
    ):
        self.sign_engine = StaticSignEngine74(dataset_path=str(dataset_path))
        self.word_assembler = RSLWordAssembler(rules_path=str(rules_path))
        self.detector = detector or default_extractor

    def execute_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Обрабатывает команды управления словарем, правилами и текстом через pattern matching
        match action:
            case "delete_gesture":
                gesture_name = payload.get("gesture_name", "")
                stats = self.sign_engine.delete_gesture(gesture_name)
                return {
                    "detected": False,
                    "dataset_stats": stats,
                    "rules": self.word_assembler.rules,
                }

            case "add_dynamic_rule":
                rules = self.word_assembler.add_rule(
                    base_shape=payload.get("base_shape", "*"),
                    motion=payload.get("motion", ""),
                    target_word=payload.get("target_word", ""),
                )
                return {
                    "detected": False,
                    "rules": rules,
                    "dataset_stats": self.sign_engine.get_dataset_stats(),
                }

            case "delete_dynamic_rule":
                rules = self.word_assembler.delete_rule(payload.get("rule_key", ""))
                return {
                    "detected": False,
                    "rules": rules,
                    "dataset_stats": self.sign_engine.get_dataset_stats(),
                }

            case "clear_text":
                return {
                    "detected": False,
                    "spelled_text": self.word_assembler.clear_text(),
                }

            case "backspace_text":
                return {
                    "detected": False,
                    "spelled_text": self.word_assembler.backspace_text(),
                }

            case "space_text":
                text = self.word_assembler.space_text()
                words = text.strip().split()
                return {
                    "detected": False,
                    "spelled_text": text,
                    "speak_event": words[-1] if words else None,
                }

            case unknown:
                return {"detected": False, "error": f"Неизвестное действие: {unknown}"}

    def process_landmarks(
        self,
        hands_data: list[dict],
        pose_lms: list[dict] | None,
        tracker: DynamicTracker74,
        record_label: str | None = None,
    ) -> dict[str, Any]:
        # Прогоняет ориентиры через 74-мерный вектор, классификаторы и сборщик слов
        extraction = self.sign_engine.extract_74_features(hands_data, pose_lms)

        if extraction["active_count"] == 0:
            tracker.clear()
            return {
                "detected": False,
                "anchors": extraction.get("anchors"),
                "spelled_text": self.word_assembler.spelled_text,
                "rules": self.word_assembler.rules,
                "dataset_stats": self.sign_engine.get_dataset_stats(),
            }

        vec_74 = extraction["vector_74"]

        if record_label:
            self.sign_engine.add_sample(vec_74, record_label)

        # Классификация статики (тело + чистая форма пальцев)
        gesture_name, score, model_mode = self.sign_engine.predict(vec_74)
        shape_name, shape_score = self.sign_engine.predict_shape_only(vec_74)

        # Трекинг динамики во времени
        dyn_info = tracker.update(extraction)

        # Сборка финального слова или дактильной буквы
        word_info = self.word_assembler.process(
            static_label=gesture_name,
            static_score=score,
            motion=dyn_info["motion"],
            is_steady=dyn_info["is_steady"],
            shape_label=shape_name,
            shape_score=shape_score,
        )

        return {
            "detected": True,
            "gesture": gesture_name,
            "score": score,
            "model_mode": model_mode,
            "shape": shape_name,
            "shape_score": shape_score,
            "motion": dyn_info["motion"],
            "motion_progress": dyn_info["motion_progress"],
            "trails": dyn_info["trails"],
            "is_steady": dyn_info["is_steady"],
            "dynamic_word": word_info["dynamic_word"],
            "spelled_text": word_info["spelled_text"],
            "hold_progress": word_info["hold_progress"],
            "rules": word_info["rules"],
            "speak_event": word_info.get("speak_event"),
            "active_hands": extraction["active_hands"],
            "hands_summary": extraction["hands_summary"],
            "anchors": extraction["anchors"],
            "telemetry": extraction["telemetry"],
            "vector_74": vec_74,
            "dataset_stats": self.sign_engine.get_dataset_stats(),
        }

    async def handle_message(
        self,
        payload: dict[str, Any],
        tracker: DynamicTracker74,
    ) -> dict[str, Any]:
        # Главная точка входа для сообщений WebSocket
        match payload.get("action"):
            case str(action):
                return self.execute_action(action, payload)
            case None:
                # Извлекаем риентиры через заданный детектор и передаем в движок
                hands_data, pose_lms = self.detector(payload)
                return self.process_landmarks(
                    hands_data=hands_data,
                    pose_lms=pose_lms,
                    tracker=tracker,
                    record_label=payload.get("record_label"),
                )


pipeline: GesturePipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    # Инициализация движка без загрузки тяжелых моделей MediaPipe
    pipeline = GesturePipeline(
        dataset_path=DATASET_PATH,
        rules_path=RULES_PATH,
    )
    print("Сервер serv.py запущен (движок жестов инициализирован)")
    yield


app = FastAPI(title="Omilia Gesture Server", lifespan=lifespan)


@app.get("/")
async def index():
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return JSONResponse({"status": "ok", "message": "Project Omilia API is running"})


@app.get("/api/tts")
def synthesize_speech(text: str = Query(..., min_length=1, max_length=300)):
    # конвертация из речи в mp3 файд
    try:
        buffer = io.BytesIO()
        gTTS(text=text.strip(), lang="ru").write_to_fp(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/mpeg")
    except Exception as err:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": f"Ошибка TTS: {err}"})


@app.websocket("/ws/gestures")
async def gesture_ws(websocket: WebSocket):
    await websocket.accept()
    tracker = DynamicTracker74(buffer_size=14, cooldown_sec=0.85)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            if pipeline is not None:
                response = await pipeline.handle_message(payload, tracker)
                await websocket.send_json(response)

    except WebSocketDisconnect:
        pass
