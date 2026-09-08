"""Centralized application configuration.

All runtime configuration lives here so the web layer, downloader and tests do
not need to know how environment variables are parsed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "sim"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} precisa ser um número inteiro.") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} precisa estar entre {minimum} e {maximum}.")
    return value


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default.resolve()
    return Path(raw).expanduser().resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings."""

    app_name: str
    app_version: str
    host: str
    port: int
    base_dir: Path
    data_dir: Path
    download_dir: Path
    log_dir: Path
    db_path: Path
    max_concurrent_downloads: int
    job_retries: int
    retention_hours: int
    socket_timeout_seconds: int
    min_free_disk_mb: int
    log_level: str
    open_browser: bool
    allow_remote: bool
    access_log: bool
    cookies_file: Path | None
    cookies_browser: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = _env_path("BAIXAI_DATA_DIR", PROJECT_ROOT / "data")
        download_dir = _env_path("BAIXAI_DOWNLOAD_DIR", data_dir / "downloads")
        log_dir = _env_path("BAIXAI_LOG_DIR", data_dir / "logs")
        cookies_raw = os.getenv("BAIXAI_COOKIES_FILE", "").strip()
        cookies_file = Path(cookies_raw).expanduser().resolve() if cookies_raw else None

        settings = cls(
            app_name="Baixaí Forge",
            app_version="1.1.0",
            host=os.getenv("BAIXAI_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_env_int("BAIXAI_PORT", 8765, 1, 65535),
            base_dir=PROJECT_ROOT,
            data_dir=data_dir,
            download_dir=download_dir,
            log_dir=log_dir,
            db_path=_env_path("BAIXAI_DB_PATH", data_dir / "baixai-forge.sqlite3"),
            max_concurrent_downloads=_env_int("BAIXAI_MAX_CONCURRENT", 2, 1, 8),
            job_retries=_env_int("BAIXAI_JOB_RETRIES", 1, 0, 5),
            retention_hours=_env_int("BAIXAI_RETENTION_HOURS", 72, 1, 24 * 365),
            socket_timeout_seconds=_env_int("BAIXAI_SOCKET_TIMEOUT", 30, 5, 300),
            min_free_disk_mb=_env_int("BAIXAI_MIN_FREE_DISK_MB", 512, 64, 1024 * 1024),
            log_level=os.getenv("BAIXAI_LOG_LEVEL", "INFO").strip().upper() or "INFO",
            open_browser=not _env_bool("BAIXAI_NO_BROWSER", False),
            allow_remote=_env_bool("BAIXAI_ALLOW_REMOTE", False),
            access_log=_env_bool("BAIXAI_ACCESS_LOG", False),
            cookies_file=cookies_file,
            cookies_browser=os.getenv("BAIXAI_COOKIES_BROWSER", "").strip() or None,
        )
        settings.validate_network_binding()
        return settings

    def validate_network_binding(self) -> None:
        """Refuse accidental public exposure unless explicitly allowed."""
        loopback = {"127.0.0.1", "localhost", "::1"}
        if self.host.lower() not in loopback and not self.allow_remote:
            raise RuntimeError(
                "Por segurança, o Baixaí Forge só inicia em localhost. "
                "Defina BAIXAI_ALLOW_REMOTE=1 conscientemente para usar outro host."
            )

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.download_dir, self.log_dir, self.db_path.parent):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings.from_env()
