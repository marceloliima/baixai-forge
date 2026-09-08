import time

from baixai_forge.models import JobRecord, JobStatus
from baixai_forge.storage import JobStore


def make_job(job_id="abc"):
    now = time.time()
    return JobRecord(
        id=job_id,
        url="https://youtube.com/watch?v=x",
        platform="youtube",
        platform_name="YouTube",
        media_type="video",
        quality="720",
        status=JobStatus.QUEUED,
        message="Na fila...",
        created_at=now,
        updated_at=now,
    )


def test_crud_and_restart_recovery(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create(make_job())
    assert store.get("abc").status == JobStatus.QUEUED

    store.update("abc", status=JobStatus.DOWNLOADING, progress=42.5)
    assert store.get("abc").progress == 42.5

    assert store.mark_active_as_interrupted() == 1
    recovered = store.get("abc")
    assert recovered.status == JobStatus.INTERRUPTED
    assert recovered.error_code == "APP_RESTARTED"

    assert store.delete("abc") is True
    assert store.get("abc") is None
    store.close()
