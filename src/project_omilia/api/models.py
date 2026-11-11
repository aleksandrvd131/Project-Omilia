"""
API-роутер отдачи моделей машинного обучения для клиентского инференса в браузере.
Поддерживает ONNX-модели (onnxruntime-web) и оптимизированные центроидные классификаторы.
"""

from fastapi import APIRouter, HTTPException, Query, Response, status

from project_omilia.core.config import DB_PATH
from project_omilia.ml.onnx_exporter import (
    export_classifier_metadata,
    export_onnx_model_bytes,
)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/static-classifier")
async def get_static_classifier_metadata(
    hands: int = Query(default=1, ge=1, le=2, description="Количество рук (1 или 2)"),
):
    """Возвращает параметры модели (веса, центроиды, пороги) в JSON для сверхбыстрого инференса в JS."""
    try:
        data = export_classifier_metadata(DB_PATH, hands_count=hands)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось экспортировать параметры классификатора: {e}",
        ) from e


@router.get("/static-onnx")
async def get_static_onnx_model(
    hands: int = Query(default=1, ge=1, le=2, description="Количество рук (1 или 2)"),
):
    """Возвращает скомпилированную бинарную ONNX-модель для запуска через onnxruntime-web."""
    try:
        onnx_bytes = export_onnx_model_bytes(DB_PATH, hands_count=hands)
        filename = f"omilia_static_{hands}h.onnx"
        return Response(
            content=onnx_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "public, max-age=60",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сгенерировать ONNX модель: {e}",
        ) from e
