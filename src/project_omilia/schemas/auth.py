from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=4, max_length=128, description="Пароль пользователя")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    token: str
    expires_at: str | None = None
