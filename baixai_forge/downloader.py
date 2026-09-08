"""yt-dlp integration isolated from the web/API layer."""

from __future__ import annotations

import logging
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Settings
from .shopee import ShopeeResolutionError, ShopeeResolver

logger = logging.getLogger("baixai_forge.downloader")


class DownloadCancelled(Exception):
    """Internal signal used by progress hooks to stop a download."""


class DownloadExecutionError(Exception):
    def __init__(self, public_message: str, *, code: str = "DOWNLOAD_FAILED", retryable: bool = False):
        super().__init__(public_message)
        self.public_message = public_message
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class DownloadOutcome:
    path: Path
    title: str | None
    uploader: str | None
    duration: float | None


ProgressCallback = Callable[[dict[str, object | None]], None]


class _YTDLPLogger:
    """Bridge yt-dlp messages into our rotating application log."""

    def debug(self, message: str) -> None:
        if message.startswith("[debug] "):
            logger.debug("yt-dlp | %s", message[8:])
        else:
            logger.debug("yt-dlp | %s", message)

    def info(self, message: str) -> None:
        logger.info("yt-dlp | %s", message)

    def warning(self, message: str) -> None:
        logger.warning("yt-dlp | %s", message)

    def error(self, message: str) -> None:
        logger.error("yt-dlp | %s", message)


class DownloadService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def download(
        self,
        *,
        job_id: str,
        url: str,
        platform: str,
        media_type: str,
        quality: str,
        progress_callback: ProgressCallback,
        cancel_event: threading.Event,
    ) -> DownloadOutcome:
        import asyncio

        return await asyncio.to_thread(
            self._download_sync,
            job_id,
            url,
            platform,
            media_type,
            quality,
            progress_callback,
            cancel_event,
        )

    def _download_sync(
        self,
        job_id: str,
        url: str,
        platform: str,
        media_type: str,
        quality: str,
        progress_callback: ProgressCallback,
        cancel_event: threading.Event,
    ) -> DownloadOutcome:
        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError as YTDLPDownloadError
        except ImportError as exc:
            raise DownloadExecutionError(
                "yt-dlp não está instalado. Execute INSTALAR.bat novamente.",
                code="YTDLP_MISSING",
            ) from exc

        self._assert_disk_space()

        resolved_title: str | None = None
        resolved_uploader: str | None = None
        resolved_duration: float | None = None
        source_headers: dict[str, str] = {}
        source_url = url
        fallback_source_url: str | None = None

        if platform == "shopee":
            progress_callback(
                {
                    "status": "processing",
                    "message": "Resolvendo link da Shopee...",
                    "progress": 0.0,
                }
            )
            try:
                resolved = ShopeeResolver(self.settings).resolve(url, cancel_event)
            except ShopeeResolutionError as exc:
                if cancel_event.is_set():
                    raise DownloadCancelled() from exc
                raise DownloadExecutionError(
                    exc.public_message,
                    code=exc.code,
                    retryable=exc.retryable,
                ) from exc
            source_url = resolved.media_url
            fallback_source_url = (
                resolved.original_media_url
                if resolved.clean_variant and resolved.original_media_url != resolved.media_url
                else None
            )
            source_headers = resolved.headers
            resolved_title = resolved.title
            resolved_uploader = resolved.uploader
            resolved_duration = resolved.duration
            progress_callback(
                {
                    "status": "downloading",
                    "message": "Vídeo da Shopee localizado. Iniciando download...",
                    "progress": 0.0,
                }
            )
            logger.info(
                "Shopee resolvida para mídia direta (%s)",
                "variante limpa" if resolved.clean_variant else "URL do payload",
            )

        job_dir = (self.settings.download_dir / job_id).resolve()
        temp_dir = job_dir / ".tmp"
        job_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        last_progress_write = 0.0

        def emit_progress(data: dict) -> None:
            nonlocal last_progress_write
            if cancel_event.is_set():
                raise DownloadCancelled()

            status = data.get("status")
            now = time.monotonic()
            if status == "downloading" and now - last_progress_write < 0.45:
                return
            last_progress_write = now

            downloaded = _as_int(data.get("downloaded_bytes"))
            total = _as_int(data.get("total_bytes")) or _as_int(data.get("total_bytes_estimate"))
            percent = 0.0
            if downloaded is not None and total:
                percent = min(99.5, downloaded * 100.0 / total)
            elif status == "finished":
                percent = 99.5

            progress_callback(
                {
                    "progress": percent,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed": _as_float(data.get("speed")),
                    "eta": _as_int(data.get("eta")),
                    "status": "processing" if status == "finished" else "downloading",
                    "message": "Processando arquivo..." if status == "finished" else "Baixando...",
                }
            )

        def postprocessor_hook(data: dict) -> None:
            if cancel_event.is_set():
                raise DownloadCancelled()
            progress_callback(
                {
                    "status": "processing",
                    "message": "Convertendo e finalizando...",
                    "progress": 99.5,
                }
            )

        opts: dict[str, object] = {
            "outtmpl": str(job_dir / "%(title).180B [%(id)s].%(ext)s"),
            "paths": {"home": str(job_dir), "temp": str(temp_dir)},
            "noplaylist": True,
            "continuedl": True,
            "overwrites": False,
            "retries": 4,
            "fragment_retries": 4,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "socket_timeout": self.settings.socket_timeout_seconds,
            "concurrent_fragment_downloads": 2,
            "quiet": True,
            "no_warnings": False,
            "logger": _YTDLPLogger(),
            "progress_hooks": [emit_progress],
            "postprocessor_hooks": [postprocessor_hook],
        }
        opts.update(self._format_options(media_type, quality))
        opts.update(self._cookie_options())
        if source_headers:
            opts["http_headers"] = source_headers

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(source_url, download=True)
                except YTDLPDownloadError:
                    if not fallback_source_url or cancel_event.is_set():
                        raise
                    logger.warning(
                        "Variante limpa da Shopee falhou no download; tentando URL original do payload."
                    )
                    self._remove_partial_files(job_dir)
                    progress_callback(
                        {
                            "status": "downloading",
                            "message": "Tentando a URL alternativa da Shopee...",
                            "progress": 0.0,
                        }
                    )
                    with yt_dlp.YoutubeDL(opts) as fallback_ydl:
                        info = fallback_ydl.extract_info(fallback_source_url, download=True)
        except DownloadCancelled:
            self._remove_partial_files(job_dir)
            raise
        except KeyboardInterrupt as exc:
            self._remove_partial_files(job_dir)
            raise DownloadCancelled() from exc
        except YTDLPDownloadError as exc:
            if cancel_event.is_set():
                self._remove_partial_files(job_dir)
                raise DownloadCancelled() from exc
            public, code, retryable = classify_error(str(exc))
            logger.warning("Download %s falhou: %s", job_id, exc)
            raise DownloadExecutionError(public, code=code, retryable=retryable) from exc
        except OSError as exc:
            if cancel_event.is_set():
                self._remove_partial_files(job_dir)
                raise DownloadCancelled() from exc
            public, code, retryable = classify_error(str(exc))
            logger.exception("Erro de sistema no download %s", job_id)
            raise DownloadExecutionError(public, code=code, retryable=retryable) from exc
        except Exception as exc:
            if cancel_event.is_set():
                self._remove_partial_files(job_dir)
                raise DownloadCancelled() from exc
            logger.exception("Erro inesperado no download %s", job_id)
            raise DownloadExecutionError(
                "O download falhou por um erro inesperado. Consulte o log para detalhes.",
                code="UNEXPECTED_ERROR",
            ) from exc

        if cancel_event.is_set():
            self._remove_partial_files(job_dir)
            raise DownloadCancelled()

        path = self._find_result_file(job_dir)
        if path is None:
            raise DownloadExecutionError(
                "O processamento terminou, mas nenhum arquivo final válido foi encontrado.",
                code="RESULT_NOT_FOUND",
            )

        progress_callback(
            {
                "status": "done",
                "message": "Concluído.",
                "progress": 100.0,
                "downloaded_bytes": path.stat().st_size,
                "total_bytes": path.stat().st_size,
                "speed": None,
                "eta": 0,
            }
        )
        return DownloadOutcome(
            path=path,
            title=resolved_title or (_text(info.get("title")) if isinstance(info, dict) else None),
            uploader=resolved_uploader or (_text(info.get("uploader")) if isinstance(info, dict) else None),
            duration=resolved_duration or (_as_float(info.get("duration")) if isinstance(info, dict) else None),
        )

    def _format_options(self, media_type: str, quality: str) -> dict[str, object]:
        if media_type == "mp3":
            if not shutil.which("ffmpeg"):
                raise DownloadExecutionError(
                    "FFmpeg não foi encontrado. Ele é obrigatório para converter áudio em MP3.",
                    code="FFMPEG_MISSING",
                )
            return {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": quality,
                    }
                ],
            }

        if quality == "best":
            format_selector = "bv*+ba/b"
        else:
            height = int(quality)
            format_selector = f"bv*[height<={height}]+ba/b[height<={height}]/b"
        return {
            "format": format_selector,
            "merge_output_format": "mp4",
        }

    def _cookie_options(self) -> dict[str, object]:
        if self.settings.cookies_file:
            if not self.settings.cookies_file.is_file():
                raise DownloadExecutionError(
                    "BAIXAI_COOKIES_FILE aponta para um arquivo que não existe.",
                    code="COOKIES_FILE_MISSING",
                )
            return {"cookiefile": str(self.settings.cookies_file)}
        if self.settings.cookies_browser:
            return {"cookiesfrombrowser": parse_browser_cookie_spec(self.settings.cookies_browser)}
        return {}

    def _assert_disk_space(self) -> None:
        free_mb = shutil.disk_usage(self.settings.download_dir).free // (1024 * 1024)
        if free_mb < self.settings.min_free_disk_mb:
            raise DownloadExecutionError(
                f"Espaço em disco insuficiente. Mantenha pelo menos {self.settings.min_free_disk_mb} MB livres.",
                code="LOW_DISK_SPACE",
            )

    @staticmethod
    def _find_result_file(job_dir: Path) -> Path | None:
        ignored_suffixes = {".part", ".ytdl", ".tmp", ".json", ".description"}
        candidates = [
            path
            for path in job_dir.rglob("*")
            if path.is_file()
            and ".tmp" not in path.parts
            and path.suffix.lower() not in ignored_suffixes
            and not path.name.endswith(".part-Frag0")
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item.stat().st_mtime, item.stat().st_size))

    @staticmethod
    def _remove_partial_files(job_dir: Path) -> None:
        for path in job_dir.rglob("*"):
            if path.is_file() and (path.suffix.lower() in {".part", ".ytdl", ".tmp"} or ".tmp" in path.parts):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.debug("Não foi possível remover parcial: %s", path)


def parse_browser_cookie_spec(spec: str) -> tuple[str, str | None, str | None, str | None]:
    """Parse yt-dlp's BROWSER[+KEYRING][:PROFILE][::CONTAINER] syntax."""
    pattern = re.compile(
        r"^(?P<name>[^+:]+)(?:\+(?P<keyring>[^:]+))?(?::(?!:)(?P<profile>.*?))?(?:::(?P<container>.*))?$"
    )
    match = pattern.fullmatch(spec.strip())
    if not match:
        raise DownloadExecutionError("Configuração de cookies do navegador inválida.", code="COOKIES_BROWSER_INVALID")
    name = match.group("name").strip().lower()
    profile = (match.group("profile") or "").strip() or None
    keyring = (match.group("keyring") or "").strip().upper() or None
    container = (match.group("container") or "").strip() or None
    return name, profile, keyring, container


def classify_error(message: str) -> tuple[str, str, bool]:
    text = message.lower()
    if "no space left" in text or "disk full" in text or "espaço insuficiente" in text:
        return "O disco ficou sem espaço durante o download.", "DISK_FULL", False
    if "ffmpeg" in text and ("not found" in text or "not installed" in text):
        return "FFmpeg não foi encontrado. Instale-o e tente novamente.", "FFMPEG_MISSING", False
    if any(token in text for token in ("sign in", "login", "cookies", "private video", "age-restricted")):
        return (
            "Esse conteúdo exige autenticação. Configure cookies da sua própria sessão e tente novamente.",
            "AUTH_REQUIRED",
            False,
        )
    if "unsupported url" in text or "no suitable extractor" in text:
        return "Esse link não é suportado pelo extrator atual.", "UNSUPPORTED_URL", False
    if any(token in text for token in ("404", "not available", "unavailable", "removed")):
        return "O conteúdo não está disponível ou foi removido.", "CONTENT_UNAVAILABLE", False
    if any(token in text for token in ("429", "too many requests", "rate limit")):
        return "A plataforma limitou temporariamente as requisições. Tente novamente mais tarde.", "RATE_LIMITED", True
    if any(token in text for token in ("403", "forbidden")):
        return "A plataforma recusou o acesso ao arquivo. Atualize o yt-dlp e tente novamente.", "ACCESS_DENIED", True
    if any(token in text for token in ("timed out", "timeout", "connection reset", "temporary failure", "network")):
        return "Falha temporária de conexão. O sistema tentará novamente automaticamente.", "NETWORK_ERROR", True
    return "Não foi possível concluir o download. Consulte o log para detalhes.", "DOWNLOAD_FAILED", False


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
