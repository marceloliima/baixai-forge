"""FastAPI application factory for Baixaí Forge."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .config import Settings, settings
from .jobs import JobConflictError, JobManager
from .logging_config import configure_logging
from .models import AUDIO_QUALITIES, VIDEO_QUALITIES, DownloadRequest, JobStatus
from .platforms import PLATFORMS, InvalidMediaUrl
from .storage import JobStore

logger = logging.getLogger("baixai_forge.web")


def _safe_attachment_name(path: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9À-ÿ._()\- \[\]]+", "_", path.name, flags=re.UNICODE)
    return (name[:220] or "download").strip()


def _yt_dlp_version() -> str | None:
    try:
        import yt_dlp

        return yt_dlp.version.__version__
    except Exception:
        return None


def create_app(app_settings: Settings = settings) -> FastAPI:
    app_settings.ensure_directories()
    configure_logging(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = JobStore(app_settings.db_path)
        manager = JobManager(app_settings, store)
        app.state.store = store
        app.state.manager = manager
        manager.start()
        manager.cleanup_old_jobs()
        logger.info("%s v%s iniciado.", app_settings.app_name, __version__)
        try:
            yield
        finally:
            await manager.shutdown()
            store.close()
            logger.info("%s encerrado.", app_settings.app_name)

    app = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        description="Downloader local com fila, persistência, progresso e diagnóstico.",
        lifespan=lifespan,
    )

    static_dir = app_settings.base_dir / "baixai_forge" / "static"
    template_dir = app_settings.base_dir / "baixai_forge" / "templates"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=template_dir)

    @app.middleware("http")
    async def security_and_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Erro HTTP não tratado | request_id=%s | path=%s", request_id, request.url.path)
            return JSONResponse(
                {"detail": "Erro interno. Consulte os logs.", "request_id": request_id},
                status_code=500,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else None
        message = first.get("msg", "Dados inválidos.") if first else "Dados inválidos."
        message = str(message).removeprefix("Value error, ")
        return JSONResponse({"detail": message}, status_code=422)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": app_settings.app_name, "version": __version__},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    @app.get("/api/health")
    async def health(request: Request):
        manager: JobManager = request.app.state.manager
        free = shutil.disk_usage(app_settings.download_dir).free
        warnings: list[str] = []
        if not shutil.which("ffmpeg"):
            warnings.append("FFmpeg não encontrado: MP3 e alguns merges de vídeo podem falhar.")
        if _yt_dlp_version() is None:
            warnings.append("yt-dlp não está instalado.")
        js_runtime = next((name for name in ("deno", "node", "bun") if shutil.which(name)), None)
        if not js_runtime:
            warnings.append("Runtime JavaScript não detectado; o suporte completo ao YouTube pode exigir Deno ou Node.js.")
        if app_settings.cookies_file and not app_settings.cookies_file.is_file():
            warnings.append("BAIXAI_COOKIES_FILE foi configurado, mas o arquivo não existe.")
        return {
            "ok": _yt_dlp_version() is not None,
            "app": app_settings.app_name,
            "version": __version__,
            "yt_dlp": _yt_dlp_version(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")),
            "javascript_runtime": js_runtime,
            "download_dir": str(app_settings.download_dir),
            "free_disk_bytes": free,
            "active_jobs": len([job for job in manager.store.list_recent(100) if not job.status.terminal]),
            "max_concurrent": app_settings.max_concurrent_downloads,
            "warnings": warnings,
        }

    @app.get("/api/platforms")
    async def platforms():
        return {
            "platforms": [{"slug": p.slug, "name": p.name, "domains": p.domains} for p in PLATFORMS],
            "video_qualities": VIDEO_QUALITIES,
            "audio_qualities": AUDIO_QUALITIES,
        }

    @app.get("/api/jobs")
    async def list_jobs(request: Request, limit: int = Query(default=25, ge=1, le=100)):
        store: JobStore = request.app.state.store
        return {"jobs": [job.public() for job in store.list_recent(limit)]}

    @app.post("/api/jobs", status_code=202)
    async def create_job(payload: DownloadRequest, request: Request):
        manager: JobManager = request.app.state.manager
        try:
            job = manager.submit(payload)
        except InvalidMediaUrl as exc:
            raise HTTPException(400, str(exc)) from exc
        return job.public()

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str, request: Request):
        store: JobStore = request.app.state.store
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Download não encontrado.")
        return job.public()

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str, request: Request):
        manager: JobManager = request.app.state.manager
        try:
            return manager.cancel(job_id).public()
        except KeyError as exc:
            raise HTTPException(404, "Download não encontrado.") from exc

    @app.post("/api/jobs/{job_id}/retry", status_code=202)
    async def retry_job(job_id: str, request: Request):
        manager: JobManager = request.app.state.manager
        try:
            return manager.retry(job_id).public()
        except KeyError as exc:
            raise HTTPException(404, "Download não encontrado.") from exc
        except JobConflictError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request):
        manager: JobManager = request.app.state.manager
        try:
            manager.delete(job_id)
        except KeyError as exc:
            raise HTTPException(404, "Download não encontrado.") from exc
        except JobConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True}

    @app.get("/api/files/{job_id}")
    async def get_file(job_id: str, request: Request):
        store: JobStore = request.app.state.store
        job = store.get(job_id)
        if not job or job.status != JobStatus.DONE or not job.result_relpath:
            raise HTTPException(404, "Arquivo ainda não está disponível.")

        root = app_settings.download_dir.resolve()
        path = (root / job.result_relpath).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            logger.error("Tentativa de acesso fora do diretório de downloads: %s", path)
            raise HTTPException(403, "Caminho de arquivo inválido.") from exc
        if not path.is_file():
            raise HTTPException(410, "O arquivo não existe mais no disco.")
        return FileResponse(
            path,
            filename=_safe_attachment_name(path),
            media_type="application/octet-stream",
        )

    return app


app = create_app()
