from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["user", "admin"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    username: str
    email: EmailStr
    password_hash: str
    role: Role = "user"
    disabled: bool = False
    # default_factory: время считается при создании объекта, а не при импорте
    created_at: datetime = Field(default_factory=utcnow)


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Role = "user"  # Задание 1: роль можно передать при регистрации


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshToken(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    username: Optional[str] = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str