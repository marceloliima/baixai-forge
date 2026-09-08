import pytest
from pydantic import ValidationError

from baixai_forge.models import DownloadRequest


def test_video_quality_validation():
    request = DownloadRequest(url="youtu.be/test", media_type="video", quality="1080")
    assert request.url.startswith("https://")


def test_invalid_audio_quality():
    with pytest.raises(ValidationError):
        DownloadRequest(url="https://youtu.be/test", media_type="mp3", quality="1080")
