from pydantic import BaseModel, ConfigDict, Field, field_validator


class GestureCard(BaseModel):
    """Поля карточки для записи и редактирования в панели разработчика."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=3000)
    tip: str = Field(min_length=1, max_length=1000)
    level: int = Field(ge=1, le=4)
    hands_count: int = Field(ge=1, le=2)
    is_dynamic: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.lower()


def recording_card(payload: dict, name: str, hands_count: int, is_dynamic: bool) -> dict | None:
    """Поддерживает старые клиенты, передающие только координаты и имя."""
    if payload.get("gesture") is None:
        return None
    card = GestureCard.model_validate(payload["gesture"]).model_dump()
    if (card["name"], card["hands_count"], card["is_dynamic"]) != (name, hands_count, is_dynamic):
        raise ValueError("Карточка не соответствует имени, числу рук или типу записываемого жеста.")
    return card


class LearnRequest(BaseModel):
    gesture_name: str = Field(..., min_length=1, max_length=100, description="Название выученного жеста")


class GestureImportItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str | None = None
    level: int | None = Field(default=None, ge=1, le=4)
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
