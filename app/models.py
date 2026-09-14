from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Difficulty = Literal["easy", "medium", "hard", "expert"]


class LessonCreate(BaseModel):
    url: HttpUrl
    language: str = Field(default="en", pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?$")
    difficulty: Difficulty = "medium"
    max_items: int = Field(default=20, ge=5, le=50)


class AttemptRequest(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=80)
    answer: str | list[str]
    listens: int = Field(default=2, ge=1, le=50)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str | list[str]):
        if isinstance(value, str):
            if not value.strip() or len(value) > 2000:
                raise ValueError("La respuesta debe contener entre 1 y 2000 caracteres")
            return value
        if not value or len(value) > 10:
            raise ValueError("La respuesta debe contener entre 1 y 10 elementos")
        if any(not item.strip() or len(item) > 200 for item in value):
            raise ValueError("Cada respuesta debe contener entre 1 y 200 caracteres")
        return value
