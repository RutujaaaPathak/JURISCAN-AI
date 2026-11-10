import threading
import time

import pytest

from app.services import ocr as ocr_module
from tests.pdf_factory import multi_page_pdf


@pytest.fixture(autouse=True)
def _reset_ocr_executor():
    ocr_module.shutdown_ocr_executor(wait=True)
    yield
    ocr_module.shutdown_ocr_executor(wait=True)


def test_ocr_renders_in_bounded_batches():
    data = multi_page_pdf([[""] for _ in range(5)])

    batches = list(
        ocr_module._iter_page_batches(data, [1, 2, 3, 4, 5], 72, 2)
    )

    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert [number for batch in batches for number, _ in batch] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert all(
        image.startswith(b"\x89PNG")
        for batch in batches
        for _, image in batch
    )


def test_ocr_releases_each_batch_before_rendering_the_next(monkeypatch):
    live = 0
    max_live = 0
    requested_batch_sizes: list[int] = []

    def fake_batches(data, page_numbers, dpi, batch_size):
        nonlocal live, max_live
        requested_batch_sizes.append(batch_size)
        for start in range(0, len(page_numbers), batch_size):
            batch = [
                (number, str(number).encode())
                for number in page_numbers[start : start + batch_size]
            ]
            batch_len = len(batch)
            live += batch_len
            max_live = max(max_live, live)
            yield batch
            live -= batch_len

    monkeypatch.setattr(ocr_module, "_iter_page_batches", fake_batches)
    monkeypatch.setattr(
        ocr_module,
        "_get_engine",
        lambda: lambda image: ([[None, image.decode()]], 0.0),
    )

    readings = ocr_module.ocr_pdf_pages(
        b"",
        [1, 2, 3, 4, 5],
        batch_size=2,
        timeout_seconds=5,
    )

    assert readings == {1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
    assert requested_batch_sizes == [2]
    assert max_live <= 2


def test_ocr_timeout_retires_executor_and_recovers(monkeypatch):
    monkeypatch.setattr(ocr_module.settings, "ocr_max_concurrent_inferences", 1)
    ocr_module.shutdown_ocr_executor(wait=True)

    def slow_engine(image):
        time.sleep(0.2)
        return ([], 0.0)

    monkeypatch.setattr(ocr_module, "_get_engine", lambda: slow_engine)
    data = multi_page_pdf([[""]])

    with pytest.raises(ocr_module.OcrTimeout):
        ocr_module.ocr_pdf_pages(
            data,
            [1],
            timeout_seconds=0.05,
            batch_size=1,
        )

    monkeypatch.setattr(
        ocr_module,
        "_get_engine",
        lambda: lambda image: ([[None, "recovered"]], 0.0),
    )
    readings = ocr_module.ocr_pdf_pages(
        data,
        [1],
        timeout_seconds=2,
        batch_size=1,
    )

    assert readings == {1: "recovered"}


def test_ocr_inference_concurrency_is_bounded(monkeypatch):
    monkeypatch.setattr(ocr_module.settings, "ocr_max_concurrent_inferences", 1)
    ocr_module.shutdown_ocr_executor(wait=True)

    active = 0
    max_active = 0
    lock = threading.Lock()

    def engine(image):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return ([[None, "ok"]], 0.0)

    monkeypatch.setattr(ocr_module, "_get_engine", lambda: engine)
    data = multi_page_pdf([[""], [""]])
    errors: list[Exception] = []

    def worker():
        try:
            ocr_module.ocr_pdf_pages(
                data,
                [1, 2],
                timeout_seconds=5,
                batch_size=1,
            )
        except Exception as exc:  # pragma: no cover - surfaced by assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert max_active == 1
