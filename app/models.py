from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Difficulty = Literal["easy", "medium", "hard", "expert"]
SourceType = Literal["video", "movie"]


class LessonCreate(BaseModel):
    url: HttpUrl
    language: str = Field(default="en", pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?$")
    difficulty: Difficulty = "medium"
    source_type: SourceType = "video"
    # 0 means adaptive: generate as many verified exercises as the video supports,
    # capped internally to keep lessons practical.
    max_items: int = Field(default=20, ge=0, le=50)
    manual_transcript: str | None = Field(default=None, max_length=100_000)

    @field_validator("manual_transcript")
    @classmethod
    def validate_manual_transcript(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value) < 10:
            raise ValueError("La transcripción manual es demasiado corta")
        return value


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
