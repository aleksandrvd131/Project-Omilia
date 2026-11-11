"""
API-роутер синтеза речи (Text-to-Speech).
"""

import io

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from gtts import gTTS

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("")
def synthesize_speech(text: str = Query(..., min_length=1, max_length=300, description="Текст для озвучивания")):
    """Синтезирует аудиофайл MP3 с произношением текста (русский язык)."""
    try:
        buffer = io.BytesIO()
        gTTS(text=text.strip(), lang="ru").write_to_fp(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/mpeg")
    except Exception as err:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Ошибка TTS: {err}"},
        )
