from pydantic import BaseModel, Field
from datetime import datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=128)
    email: str = ""


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    created_at: str
    access_level: int


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    sort_order: int = 0


class ThreadCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1)


class PostCreate(BaseModel):
    body: str = Field(min_length=1)


class FileUploadMeta(BaseModel):
    area: str = "general"
    description: str = ""


class ChatMessage(BaseModel):
    channel: str = "lobby"
    message: str = Field(min_length=1, max_length=2000)
