from pydantic import BaseModel, Field


class LearnRequest(BaseModel):
    gesture_name: str = Field(..., min_length=1, max_length=100, description="Название выученного жеста")
