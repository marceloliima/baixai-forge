"""Download job orchestration, cancellation, retries and maintenance."""

from __future__ import annotations

import asyncio
import logging
import shutil
import threading
import time
import uuid

from .config import Settings
from .downloader import DownloadCancelled, DownloadExecutionError, DownloadService
from .models import DownloadRequest, JobRecord, JobStatus
from .platforms import detect_platform
from .storage import JobStore

logger = logging.getLogger("baixai_forge.jobs")


class JobConflictError(RuntimeError):
    pass


class JobManager:
    def __init__(self, settings: Settings, store: JobStore):
        self.settings = settings
        self.store = store
        self.downloader = DownloadService(settings)
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._maintenance_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        interrupted = self.store.mark_active_as_interrupted()
        if interrupted:
            logger.warning("%s job(s) ativos foram marcados como interrompidos após reinício.", interrupted)
        self._maintenance_task = asyncio.create_task(self._maintenance_loop(), name="baixai-maintenance")

    async def shutdown(self) -> None:
        for event in self._cancel_events.values():
            event.set()
        if self._maintenance_task:
            self._maintenance_task.cancel()
        active = list(self._tasks.values())
        if active:
            try:
                await asyncio.wait(active, timeout=3.0)
            except Exception:
                logger.exception("Falha aguardando encerramento dos jobs.")

    def submit(self, request: DownloadRequest) -> JobRecord:
        platform = detect_platform(request.url)
        now = time.time()
        job = JobRecord(
            id=uuid.uuid4().hex,
            url=request.url,
            platform=platform.slug,
            platform_name=platform.name,
            media_type=request.media_type,
            quality=request.quality,
            status=JobStatus.QUEUED,
            message="Na fila...",
            created_at=now,
            updated_at=now,
        )
        self.store.create(job)
        self._launch(job)
        return job

    def retry(self, job_id: str) -> JobRecord:
        old = self.store.get(job_id)
        if old is None:
            raise KeyError(job_id)
        if not old.status.terminal:
            raise JobConflictError("Aguarde o job atual terminar ou cancele-o primeiro.")
        request = DownloadRequest(url=old.url, media_type=old.media_type, quality=old.quality)
        return self.submit(request)

    def cancel(self, job_id: str) -> JobRecord:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status.terminal:
            return job
        event = self._cancel_events.get(job_id)
        if event:
            event.set()
        return self.store.update(
            job_id,
            status=JobStatus.CANCELLING,
            message="Cancelando com segurança...",
        ) or job

    def delete(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if not job.status.terminal:
            raise JobConflictError("Cancele o download antes de removê-lo.")
        self._delete_job_files(job)
        self.store.delete(job_id)

    def _launch(self, job: JobRecord) -> None:
        cancel_event = threading.Event()
        self._cancel_events[job.id] = cancel_event
        task = asyncio.create_task(self._run(job.id, cancel_event), name=f"download-{job.id[:8]}")
        self._tasks[job.id] = task
        task.add_done_callback(lambda _task, job_id=job.id: self._forget(job_id))

    def _forget(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)
        self._cancel_events.pop(job_id, None)

    async def _run(self, job_id: str, cancel_event: threading.Event) -> None:
        async with self._semaphore:
            job = self.store.get(job_id)
            if job is None:
                return
            if cancel_event.is_set():
                self._finish_cancelled(job_id)
                return

            max_attempts = self.settings.job_retries + 1
            for attempt in range(1, max_attempts + 1):
                if cancel_event.is_set():
                    self._finish_cancelled(job_id)
                    return

                self.store.update(
                    job_id,
                    status=JobStatus.DOWNLOADING,
                    message="Preparando download..." if attempt == 1 else f"Nova tentativa {attempt}/{max_attempts}...",
                    attempts=attempt,
                    error_code=None,
                    error_message=None,
                )

                def progress(payload: dict[str, object | None]) -> None:
                    status_value = payload.pop("status", None)
                    status = JobStatus(status_value) if status_value in {item.value for item in JobStatus} else None
                    fields = dict(payload)
                    if status:
                        fields["status"] = status
                    try:
                        self.store.update(job_id, **fields)
                    except Exception:
                        logger.exception("Falha registrando progresso do job %s", job_id)

                try:
                    outcome = await self.downloader.download(
                        job_id=job_id,
                        url=job.url,
                        platform=job.platform,
                        media_type=job.media_type,
                        quality=job.quality,
                        progress_callback=progress,
                        cancel_event=cancel_event,
                    )
                except DownloadCancelled:
                    self._finish_cancelled(job_id)
                    return
                except DownloadExecutionError as exc:
                    if cancel_event.is_set():
                        self._finish_cancelled(job_id)
                        return
                    if exc.retryable and attempt < max_attempts:
                        self.store.update(
                            job_id,
                            status=JobStatus.RETRYING,
                            message=f"Falha temporária. Nova tentativa em {2 ** attempt}s...",
                            error_code=exc.code,
                            error_message=exc.public_message,
                        )
                        await asyncio.sleep(2 ** attempt)
                        continue
                    self.store.update(
                        job_id,
                        status=JobStatus.ERROR,
                        message="Não foi possível concluir.",
                        error_code=exc.code,
                        error_message=exc.public_message,
                        finished_at=time.time(),
                    )
                    return
                except Exception:
                    logger.exception("Erro não tratado no job %s", job_id)
                    self.store.update(
                        job_id,
                        status=JobStatus.ERROR,
                        message="Não foi possível concluir.",
                        error_code="UNEXPECTED_ERROR",
                        error_message="Ocorreu um erro inesperado. Consulte o arquivo de log.",
                        finished_at=time.time(),
                    )
                    return

                result_relpath = str(outcome.path.resolve().relative_to(self.settings.download_dir.resolve()))
                self.store.update(
                    job_id,
                    status=JobStatus.DONE,
                    message="Pronto para salvar no computador.",
                    progress=100.0,
                    title=outcome.title,
                    uploader=outcome.uploader,
                    duration=outcome.duration,
                    result_relpath=result_relpath,
                    result_size=outcome.path.stat().st_size,
                    finished_at=time.time(),
                    eta=0,
                    error_code=None,
                    error_message=None,
                )
                return

    def _finish_cancelled(self, job_id: str) -> None:
        self.store.update(
            job_id,
            status=JobStatus.CANCELLED,
            message="Cancelado.",
            error_code="CANCELLED_BY_USER",
            error_message=None,
            finished_at=time.time(),
        )

    def _delete_job_files(self, job: JobRecord) -> None:
        job_dir = (self.settings.download_dir / job.id).resolve()
        try:
            job_dir.relative_to(self.settings.download_dir.resolve())
        except ValueError:
            logger.error("Recusado delete fora da pasta de downloads: %s", job_dir)
            return
        shutil.rmtree(job_dir, ignore_errors=True)

    async def _maintenance_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(30 * 60)
                self.cleanup_old_jobs()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Falha na manutenção automática.")

    def cleanup_old_jobs(self) -> int:
        cutoff = time.time() - self.settings.retention_hours * 3600
        jobs = self.store.old_terminal_jobs(cutoff)
        for job in jobs:
            self._delete_job_files(job)
            self.store.delete(job.id)
        if jobs:
            logger.info("Manutenção removeu %s job(s) antigos.", len(jobs))
        return len(jobs)
