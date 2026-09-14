from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


Difficulty = Literal["easy", "medium", "hard", "expert"]


class LessonCreate(BaseModel):
    url: HttpUrl
    language: str = Field(default="en", pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?$")
    difficulty: Difficulty = "medium"
    max_items: int = Field(default=20, ge=5, le=50)


class AttemptRequest(BaseModel):
    exercise_id: str
    answer: str | list[str]
    listens: int = Field(default=2, ge=1, le=50)
