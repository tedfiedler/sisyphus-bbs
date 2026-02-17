"""Pydantic request and response models for the Sisyphus BBS API."""

from pydantic import BaseModel, Field
from datetime import datetime


class UserCreate(BaseModel):
    """Represent a new user registration request with username, password, and optional email."""

    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=128)
    email: str = ""


class UserLogin(BaseModel):
    """Represent a user login request with username and password credentials."""

    username: str
    password: str


class UserOut(BaseModel):
    """Represent a public-facing user profile returned in API responses."""

    id: int
    username: str
    email: str
    created_at: str
    access_level: int


class BoardCreate(BaseModel):
    """Represent a request to create a new discussion board."""

    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    sort_order: int = 0


class ThreadCreate(BaseModel):
    """Represent a request to create a new thread with a subject and body."""

    subject: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1)


class PostCreate(BaseModel):
    """Represent a request to create a new reply post within a thread."""

    body: str = Field(min_length=1)


class FileUploadMeta(BaseModel):
    """Represent metadata accompanying a file upload, including area and description."""

    area: str = "general"
    description: str = ""


class ChatMessage(BaseModel):
    """Represent an outgoing chat message with a target channel and message body."""

    channel: str = "lobby"
    message: str = Field(min_length=1, max_length=2000)
