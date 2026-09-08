"""CLI entry point: python -m baixai_forge"""

from __future__ import annotations

import logging
import threading
import webbrowser

import uvicorn

from .config import settings
from .logging_config import configure_logging


def _open_browser() -> None:
    if settings.open_browser:
        url = f"http://{settings.host}:{settings.port}"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()


def main() -> None:
    settings.ensure_directories()
    configure_logging(settings)
    log = logging.getLogger("baixai_forge")
    log.info("=" * 72)
    log.info("%s v%s", settings.app_name, settings.app_version)
    log.info("Interface: http://%s:%s", settings.host, settings.port)
    log.info("Downloads: %s", settings.download_dir)
    log.info("=" * 72)
    _open_browser()
    uvicorn.run(
        "baixai_forge.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
