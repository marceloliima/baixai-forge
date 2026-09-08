"""URL normalization and supported-platform detection.

The backend always detects the platform itself. Client-supplied platform names
are intentionally not trusted, which also blocks file:// and arbitrary-host
requests from reaching yt-dlp.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


class InvalidMediaUrl(ValueError):
    """Raised when a URL is invalid or outside the supported allow-list."""


@dataclass(frozen=True, slots=True)
class Platform:
    slug: str
    name: str
    domains: tuple[str, ...]


PLATFORMS: tuple[Platform, ...] = (
    Platform("youtube", "YouTube", ("youtube.com", "youtu.be")),
    Platform("instagram", "Instagram", ("instagram.com",)),
    Platform("tiktok", "TikTok", ("tiktok.com",)),
    Platform("facebook", "Facebook", ("facebook.com", "fb.watch")),
    Platform(
        "shopee",
        "Shopee",
        (
            "shopee.com.br",
            "shopee.com",
            "shp.ee",
            "shopee.com.my",
            "shopee.co.id",
            "shopee.co.th",
            "shopee.vn",
            "shopee.ph",
            "shopee.sg",
            "shopee.tw",
        ),
    ),
)


def normalize_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        raise InvalidMediaUrl("Cole um link válido.")
    if "://" not in value:
        value = "https://" + value

    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise InvalidMediaUrl("O link informado é inválido.") from exc

    if parts.scheme.lower() not in {"http", "https"}:
        raise InvalidMediaUrl("Somente links HTTP ou HTTPS são aceitos.")
    if not parts.hostname:
        raise InvalidMediaUrl("O link não possui um domínio válido.")
    if parts.username or parts.password:
        raise InvalidMediaUrl("Links com usuário ou senha embutidos não são aceitos.")

    host = parts.hostname.lower().rstrip(".")
    port = parts.port
    if port not in {None, 80, 443}:
        raise InvalidMediaUrl("Portas personalizadas não são aceitas.")

    # Keep the path/query required by sharing links, but remove fragments.
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def detect_platform(raw_url: str) -> Platform:
    url = normalize_url(raw_url)
    host = (urlsplit(url).hostname or "").lower()

    for platform in PLATFORMS:
        if any(host == domain or host.endswith("." + domain) for domain in platform.domains):
            return platform

    names = ", ".join(platform.name for platform in PLATFORMS)
    raise InvalidMediaUrl(f"Link não reconhecido. Plataformas aceitas: {names}.")
