from pydantic import BaseModel, Field


class LearnRequest(BaseModel):
    gesture_name: str = Field(..., min_length=1, max_length=100, description="Название выученного жеста")


class GestureImportItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str | None = None
    category: str | None = None
    description: str | None = None
    tip: str | None = None
    hands_count: int = Field(default=1, ge=1, le=2)
    is_dynamic: int | bool = Field(default=0)
    created_at: str | None = None


class SampleImportItem(BaseModel):
    gesture_name: str = Field(..., min_length=1, max_length=100)
    hands_count: int = Field(default=1, ge=1, le=2)
    features_json: str | list[float] | None = None
    features_blob: str | list[float] | None = None


class DatasetImportPayload(BaseModel):
    version: str | None = None
    exported_at: str | None = None
    clear_existing_samples: bool = False
    gestures: list[GestureImportItem] = Field(default_factory=list)
    static_gesture_samples: list[SampleImportItem] = Field(default_factory=list)
