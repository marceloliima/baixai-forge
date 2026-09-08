"""Domain models and API schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .platforms import InvalidMediaUrl, normalize_url


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    RETRYING = "retrying"
    CANCELLING = "cancelling"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

    @property
    def terminal(self) -> bool:
        return self in {self.DONE, self.ERROR, self.CANCELLED, self.INTERRUPTED}


VIDEO_QUALITIES = ("best", "2160", "1440", "1080", "720", "480", "360")
AUDIO_QUALITIES = ("320", "256", "192", "128", "96")


class DownloadRequest(BaseModel):
    url: str = Field(min_length=3, max_length=8192)
    media_type: Literal["video", "mp3"] = "video"
    quality: str = "1080"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        try:
            return normalize_url(value)
        except InvalidMediaUrl as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def validate_quality(self) -> "DownloadRequest":
        allowed = VIDEO_QUALITIES if self.media_type == "video" else AUDIO_QUALITIES
        if self.quality not in allowed:
            raise ValueError(f"Qualidade inválida para {self.media_type}: {self.quality}.")
        return self


@dataclass(slots=True)
class JobRecord:
    id: str
    url: str
    platform: str
    platform_name: str
    media_type: str
    quality: str
    status: JobStatus
    message: str
    created_at: float
    updated_at: float
    finished_at: float | None = None
    progress: float = 0.0
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None
    attempts: int = 0
    title: str | None = None
    uploader: str | None = None
    duration: float | None = None
    result_relpath: str | None = None
    result_size: int | None = None
    error_code: str | None = None
    error_message: str | None = None

    def public(self) -> dict[str, object | None]:
        return {
            "id": self.id,
            "url": self.url,
            "platform": self.platform,
            "platform_name": self.platform_name,
            "media_type": self.media_type,
            "quality": self.quality,
            "status": self.status.value,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "progress": round(max(0.0, min(100.0, self.progress)), 1),
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed": self.speed,
            "eta": self.eta,
            "attempts": self.attempts,
            "title": self.title,
            "uploader": self.uploader,
            "duration": self.duration,
            "filename": Path(self.result_relpath).name if self.result_relpath else None,
            "filesize": self.result_size,
            "error_code": self.error_code,
            "error": self.error_message,
            "download_url": f"/api/files/{self.id}" if self.status == JobStatus.DONE else None,
        }
