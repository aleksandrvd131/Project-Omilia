"""
WebSocket-эндпоинт для передачи видеокадров и распознавания жестов в реальном времени.
"""

import json
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import numpy as np

from project_omilia.core.config import DB_PATH
from project_omilia import db
from project_omilia.services.dynamic_service import DynamicGestureServer
from project_omilia.services.static_service import StaticGestureServer

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/gestures")
async def gesture_ws(websocket: WebSocket):
    """Потоковый двусторонний обмен между браузером и моделями распознавания."""
    await websocket.accept()
    recording: list[tuple[str, int, np.ndarray]] = []

    static_server: StaticGestureServer | None = getattr(websocket.app.state, "static_server", None)
    dynamic_server: DynamicGestureServer | None = getattr(websocket.app.state, "dynamic_server", None)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            if static_server is None or dynamic_server is None:
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
                    response = static_server.handle_action(action, payload)
                    if action == "get_dataset_stats":
                        response["dynamic_dataset"] = db.list_dynamic_samples(DB_PATH)
                else:
                    response = static_server.process_frame(payload, recording)

                await websocket.send_json(response)
            except Exception as err:
                print(f"[WebSocket] Ошибка обработки кадра: {err}")

    except WebSocketDisconnect:
        pass
