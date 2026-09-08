"""Shopee Video share-link resolver.

Shopee share URLs (for example ``br.shp.ee/...``) are not reliably handled by
upstream yt-dlp.  The public Shopee Video share page currently embeds its media
metadata in Next.js' ``__NEXT_DATA__`` payload.  This module resolves that page
into a direct Shopee CDN MP4 URL before handing the media back to yt-dlp.

The resolver is intentionally isolated from the generic downloader so a Shopee
site change can be fixed without touching queueing, persistence or the API.
"""

from __future__ import annotations

import html
import json
import logging
import re
import threading
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .config import Settings

logger = logging.getLogger("baixai_forge.shopee")

# Keep this allow-list narrow: the resolver follows short-link redirects and
# must never become an arbitrary HTTP proxy/SSRF primitive.
_SHOPEE_PAGE_DOMAINS = (
    "shp.ee",
    "shopee.com",
    "shopee.com.br",
    "shopee.com.my",
    "shopee.co.id",
    "shopee.co.th",
    "shopee.vn",
    "shopee.ph",
    "shopee.sg",
    "shopee.tw",
)
_SHOPEE_CDN_DOMAINS = ("vod.susercontent.com",)
_MAX_REDIRECTS = 8
_MAX_HTML_BYTES = 5 * 1024 * 1024
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class ShopeeResolutionError(RuntimeError):
    """Raised when a Shopee link cannot be resolved to media."""

    def __init__(self, message: str, *, code: str = "SHOPEE_RESOLVE_FAILED", retryable: bool = False):
        super().__init__(message)
        self.public_message = message
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ShopeeMedia:
    page_url: str
    media_url: str
    original_media_url: str
    title: str | None = None
    uploader: str | None = None
    duration: float | None = None
    clean_variant: bool = False

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": _USER_AGENT,
            "Referer": self.page_url,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._inside = False
        self._chunks: list[str] = []
        self.og_title: str | None = None

    @property
    def next_data(self) -> str | None:
        value = "".join(self._chunks).strip()
        return value or None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        if tag.lower() == "script" and attrs_map.get("id") == "__NEXT_DATA__":
            self._inside = True
        elif tag.lower() == "meta" and attrs_map.get("property") == "og:title":
            self.og_title = attrs_map.get("content") or self.og_title

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._inside:
            self._inside = False

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._chunks.append(data)


class ShopeeResolver:
    """Resolve Shopee short/share URLs into direct video URLs."""

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    def resolve(self, url: str, cancel_event: threading.Event) -> ShopeeMedia:
        if cancel_event.is_set():
            raise ShopeeResolutionError("Operação cancelada.")

        # Users may paste a direct Shopee CDN URL. No page resolution is needed.
        if _is_shopee_cdn_url(url) and urlsplit(url).path.lower().endswith(".mp4"):
            return ShopeeMedia(
                page_url=url,
                media_url=url,
                original_media_url=url,
                clean_variant=False,
            )

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }
        timeout = httpx.Timeout(self.settings.socket_timeout_seconds)

        try:
            with httpx.Client(
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                page_html, final_url = self._get_page(client, url, cancel_event)
                parsed = parse_shopee_share_html(page_html, final_url)

                candidate = clean_shopee_mp4_url(parsed.original_media_url)
                if candidate and candidate != parsed.original_media_url:
                    if self._probe_media(client, candidate, final_url, cancel_event):
                        logger.info("Shopee clean media URL validada: %s", _redact_url(candidate))
                        return ShopeeMedia(
                            page_url=final_url,
                            media_url=candidate,
                            original_media_url=parsed.original_media_url,
                            title=parsed.title,
                            uploader=parsed.uploader,
                            duration=parsed.duration,
                            clean_variant=True,
                        )
                    logger.info("Variante limpa da Shopee não respondeu; usando URL original do payload.")

                return ShopeeMedia(
                    page_url=final_url,
                    media_url=parsed.original_media_url,
                    original_media_url=parsed.original_media_url,
                    title=parsed.title,
                    uploader=parsed.uploader,
                    duration=parsed.duration,
                    clean_variant=False,
                )
        except ShopeeResolutionError:
            raise
        except httpx.TimeoutException as exc:
            raise ShopeeResolutionError(
                "A Shopee demorou demais para responder.",
                code="SHOPEE_TIMEOUT",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            retryable = status == 429 or status >= 500
            raise ShopeeResolutionError(
                f"A Shopee recusou a página do vídeo (HTTP {status}).",
                code="SHOPEE_HTTP_ERROR",
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            raise ShopeeResolutionError(
                "Não foi possível abrir o link da Shopee.",
                code="SHOPEE_NETWORK_ERROR",
                retryable=True,
            ) from exc
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            logger.exception("Falha analisando página Shopee")
            raise ShopeeResolutionError(
                "A página da Shopee mudou e o vídeo não pôde ser localizado.",
                code="SHOPEE_PAYLOAD_CHANGED",
                retryable=False,
            ) from exc

    def _get_page(
        self,
        client: httpx.Client,
        initial_url: str,
        cancel_event: threading.Event,
    ) -> tuple[str, str]:
        current = initial_url
        for _ in range(_MAX_REDIRECTS + 1):
            if cancel_event.is_set():
                raise ShopeeResolutionError("Operação cancelada.", code="CANCELLED_BY_USER")
            _validate_shopee_page_url(current)
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ShopeeResolutionError(
                            "O redirecionamento da Shopee veio sem destino.",
                            code="SHOPEE_BAD_REDIRECT",
                        )
                    current = urljoin(str(response.url), location)
                    continue

                response.raise_for_status()
                final_url = str(response.url)
                _validate_shopee_page_url(final_url)

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if cancel_event.is_set():
                        raise ShopeeResolutionError("Operação cancelada.", code="CANCELLED_BY_USER")
                    total += len(chunk)
                    if total > _MAX_HTML_BYTES:
                        raise ShopeeResolutionError(
                            "A página da Shopee retornou dados demais e foi recusada por segurança.",
                            code="SHOPEE_PAGE_TOO_LARGE",
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                return raw.decode(encoding, errors="replace"), final_url

        raise ShopeeResolutionError(
            "O link da Shopee redirecionou vezes demais.",
            code="SHOPEE_TOO_MANY_REDIRECTS",
        )

    def _probe_media(
        self,
        client: httpx.Client,
        media_url: str,
        page_url: str,
        cancel_event: threading.Event,
    ) -> bool:
        if cancel_event.is_set():
            raise ShopeeResolutionError("Operação cancelada.")
        if not _is_shopee_cdn_url(media_url):
            return False
        headers = {
            "User-Agent": _USER_AGENT,
            "Referer": page_url,
            "Range": "bytes=0-0",
            "Accept": "*/*",
        }
        try:
            with client.stream("GET", media_url, headers=headers) as response:
                return response.status_code in {200, 206}
        except httpx.HTTPError:
            return False


def parse_shopee_share_html(page_html: str, page_url: str) -> ShopeeMedia:
    """Parse a Shopee Video share page without performing network requests."""
    parser = _NextDataParser()
    parser.feed(page_html)

    payload = parser.next_data
    if payload:
        data = json.loads(html.unescape(payload))
        page_props = data.get("props", {}).get("pageProps", {})
        media_info = page_props.get("mediaInfo", {})
        video = media_info.get("video", {})
        user_info = media_info.get("userInfo", {})
        media_url = _as_text(video.get("watermarkVideoUrl"))
        if media_url:
            return ShopeeMedia(
                page_url=page_url,
                media_url=media_url,
                original_media_url=media_url,
                title=_as_text(video.get("caption")) or parser.og_title,
                uploader=_as_text(user_info.get("videoUserName")),
                duration=_duration_seconds(video.get("duration")),
            )

    # Defensive fallback for minor markup changes where __NEXT_DATA__ is still
    # present as text but the HTML parser cannot isolate it.
    match = re.search(r'"watermarkVideoUrl"\s*:\s*"(?P<url>https?:\\?/\\?/[^\"]+\.mp4[^\"]*)"', page_html)
    if match:
        raw = match.group("url")
        try:
            media_url = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            media_url = raw.replace("\\/", "/")
        return ShopeeMedia(
            page_url=page_url,
            media_url=media_url,
            original_media_url=media_url,
            title=parser.og_title,
        )

    raise ShopeeResolutionError(
        "A página abriu, mas não foi encontrado um vídeo MP4 no payload da Shopee.",
        code="SHOPEE_MEDIA_NOT_FOUND",
    )


def clean_shopee_mp4_url(url: str) -> str | None:
    """Derive Shopee's cleaner MP4 path when the CDN filename carries tokens.

    Example::

        name.16003551755115279.9253.mp4 -> name.mp4

    The transformation is deliberately restricted to Shopee's video CDN and
    to a two-numeric-token suffix immediately before ``.mp4``.
    """
    if not _is_shopee_cdn_url(url):
        return None
    parts = urlsplit(url)
    match = re.match(r"^(?P<base>.+?)\.\d{8,}\.\d+\.mp4$", parts.path, flags=re.IGNORECASE)
    if not match:
        return None
    clean_path = f"{match.group('base')}.mp4"
    return urlunsplit((parts.scheme, parts.netloc, clean_path, "", ""))


def _validate_shopee_page_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ShopeeResolutionError("Redirecionamento inválido da Shopee.", code="SHOPEE_BAD_REDIRECT")
    host = parts.hostname.lower().rstrip(".")
    if not any(host == domain or host.endswith("." + domain) for domain in _SHOPEE_PAGE_DOMAINS):
        raise ShopeeResolutionError("A Shopee redirecionou para um domínio não permitido.", code="SHOPEE_REDIRECT_BLOCKED")
    if parts.port not in {None, 80, 443}:
        raise ShopeeResolutionError("A Shopee redirecionou para uma porta não permitida.", code="SHOPEE_REDIRECT_BLOCKED")


def _is_shopee_cdn_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return False
    host = parts.hostname.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in _SHOPEE_CDN_DOMAINS)


def _duration_seconds(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    # Shopee's current page payload reports milliseconds (e.g. 18018 => 18.018s).
    return number / 1000.0 if number >= 1000 else number


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _redact_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
