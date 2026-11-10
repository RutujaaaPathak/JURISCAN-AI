import asyncio
import threading

from app.services import processing as processing_module


def test_process_upload_async_runs_worker_off_the_event_loop(monkeypatch):
    seen_thread: list[threading.Thread] = []

    def fake_worker(**kwargs):
        seen_thread.append(threading.current_thread())
        return 42

    monkeypatch.setattr(processing_module, "_process_upload_worker", fake_worker)
    processing_module.shutdown_processing_executor(wait=True)

    async def run():
        return await processing_module.process_upload_async(
            user_id=1,
            data=b"content",
            filename="file.txt",
            content_type="text/plain",
            title=None,
            max_size_bytes=1024,
            force=False,
        )

    try:
        assert asyncio.run(run()) == 42
    finally:
        processing_module.shutdown_processing_executor(wait=True)

    assert seen_thread
    assert seen_thread[0] is not threading.main_thread()
