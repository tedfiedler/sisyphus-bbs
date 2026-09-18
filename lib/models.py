"""Pydantic request models and the form-validation helper used by the routes.

Routes accept ``Form()`` fields and pass them through :func:`validate`, which
returns either a validated model or a single human-readable error string
suitable for rendering back into a template. Validators raise ``ValueError``
with the exact wording shown to the user.
"""

import re

from pydantic import BaseModel, Field, ValidationError, field_validator

# Usernames must start with a letter or digit and may then contain letters,
# digits, underscore, dot, or hyphen. Keeping the set narrow means a username
# is safe to interpolate anywhere it is displayed.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$")

# bcrypt rejects anything over 72 bytes outright, so that is a hard ceiling
# rather than a policy choice.
MAX_PASSWORD_BYTES = 72

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_username(value: str) -> str:
    """Validate a username, returning it stripped of surrounding whitespace."""
    value = value.strip()
    if not 2 <= len(value) <= 32:
        raise ValueError("Username must be between 2 and 32 characters.")
    if not _USERNAME_RE.match(value):
        raise ValueError(
            "Username must start with a letter or number and may contain "
            "only letters, numbers, and _ . -"
        )
    return value


def _clean_password(value: str) -> str:
    """Validate a password against the length limits bcrypt can accept."""
    if len(value) < 4:
        raise ValueError("Password must be at least 4 characters.")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return value


class UserCreate(BaseModel):
    """A new user registration."""

    username: str
    password: str
    email: str = ""

    _check_username = field_validator("username")(_clean_username)
    _check_password = field_validator("password")(_clean_password)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if len(value) > 254 or not _EMAIL_RE.match(value):
            raise ValueError("Email address is not valid.")
        return value


class UserLogin(BaseModel):
    """A login attempt.

    Only length is bounded here: credentials are checked against the
    database, and rejecting an over-long password early keeps it away
    from bcrypt, which raises on inputs above its 72-byte limit.

    The username bound is deliberately looser than :class:`UserCreate`'s so
    that accounts registered before those rules existed can still sign in.
    """

    username: str = Field(max_length=100)
    password: str = Field(max_length=MAX_PASSWORD_BYTES)


class UserOut(BaseModel):
    """A public-facing user profile returned in API responses."""

    id: int
    username: str
    email: str
    created_at: str
    access_level: int


class BoardCreate(BaseModel):
    """A request to create a new discussion board."""

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=256)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Board name cannot be empty.")
        return value


class ThreadCreate(BaseModel):
    """A new thread with a subject and opening post."""

    subject: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("subject")
    @classmethod
    def _check_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Subject cannot be empty.")
        return value


class PostCreate(BaseModel):
    """A reply post within a thread."""

    body: str = Field(min_length=1, max_length=20000)

    @field_validator("body")
    @classmethod
    def _check_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Post cannot be empty.")
        return value


class FileUploadMeta(BaseModel):
    """Metadata accompanying a file upload."""

    area: str = Field(default="general", max_length=32)
    description: str = Field(default="", max_length=256)


class ChatMessage(BaseModel):
    """An outgoing chat message with a target channel and body."""

    channel: str = Field(default="lobby", max_length=64)
    message: str = Field(min_length=1, max_length=2000)


class ProfileText(BaseModel):
    """Free-text profile fields (About Me, landing message)."""

    text: str = Field(default="", max_length=2000)


def validate(model: type[BaseModel], **values):
    """Validate form values against *model*.

    Returns ``(instance, None)`` on success, or ``(None, message)`` where
    *message* is a single human-readable string describing the first problem.
    """
    try:
        return model(**values), None
    except ValidationError as exc:
        error = exc.errors()[0]
        message = error["msg"]
        # Pydantic prefixes messages raised from validators; drop the noise.
        if message.startswith("Value error, "):
            message = message[len("Value error, "):]
        elif error["type"] in ("string_too_short", "string_too_long", "missing"):
            field = str(error["loc"][0]).replace("_", " ") if error["loc"] else "Input"
            message = f"{field.capitalize()}: {message.lower()}"
        return None, message
