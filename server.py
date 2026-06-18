#!/usr/bin/env python3
"""PP-OCRv6 OCR Server — lightweight FastAPI backend with ONNX Runtime.

Endpoints:
  POST /ocr/image   - OCR on uploaded image file
  POST /ocr/pdf     - OCR on uploaded PDF (all pages)
  POST /ocr/text    - OCR on image, plain text only
  GET  /ocr/logs    - SSE stream of structured log events (real-time progress)
  GET  /ocr/results - SSE stream of partial OCR results (real-time output)
  GET  /health      - Health check

Usage:
  python server.py                # default port 8765
  python server.py --port 8080    # custom port
"""

import io
import os
import sys
import json
import time
import asyncio
import logging
import concurrent.futures
import threading
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import numpy as np
from PIL import Image
import fitz  # PyMuPDF

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ── Use HF mirror for model downloads ───────────────────────────────
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ppocr-server")

# ── SSE Fan-Out ─────────────────────────────────────────────────────
# Two separate fan-out systems:
#   1. _log_queues    → GET /ocr/logs     (progress/status events)
#   2. _result_queues → GET /ocr/results  (partial OCR output data)
_log_queues: list[asyncio.Queue] = []
_result_queues: list[asyncio.Queue] = []

# Thread pool for CPU-bound OCR work (prevents event-loop blocking)
_ocr_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
_loop: asyncio.AbstractEventLoop | None = None  # set after event loop starts

# ── Stage labels ────────────────────────────────────────────────────
STAGE_LABELS = {
    "init":        "模型初始化",
    "preprocess":  "图像预处理",
    "detection":   "文字检测",
    "recognition": "文字识别",
    "postprocess": "后处理",
    "progress":    "进度",
    "done":        "完成",
    "error":       "错误",
}


def _now_iso() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ── Thread-safe SSE helpers ─────────────────────────────────────────
# asyncio.Queue is NOT thread-safe.  OCR runs in a thread pool, so
# queue operations must be scheduled back onto the event loop.

async def _queue_put_event(q: asyncio.Queue, data: str):
    """Push a JSON event string to a single SSE queue (runs on event loop)."""
    try:
        q.put_nowait(data)
    except asyncio.QueueFull:
        # Client is too slow — drop it
        pass


def _threadsafe_push(queues: list[asyncio.Queue], data: str):
    """Push an event to all SSE clients of a fan-out group, thread-safely."""
    if _loop is None:
        return
    # Snapshot queues; removal is handled by the SSE generator on client disconnect
    for q in queues[:]:
        asyncio.run_coroutine_threadsafe(_queue_put_event(q, data), _loop)


def _build_log_payload(
    message: str,
    level: str = "info",
    stage: str = "progress",
    detail: dict | None = None,
    progress_pct: float | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
) -> dict:
    """Build a structured log event dict (no side effects)."""
    stage_label = STAGE_LABELS.get(stage, stage)
    payload: dict = {
        "timestamp": _now_iso(),
        "level": level,
        "stage": stage,
        "stage_label": stage_label,
        "message": message,
    }
    if detail is not None:
        payload["detail"] = detail
    if progress_pct is not None:
        payload["progress_pct"] = progress_pct
    if progress_current is not None:
        payload["progress_current"] = progress_current
    if progress_total is not None:
        payload["progress_total"] = progress_total
    return payload


def broadcast_log(
    message: str,
    level: str = "info",
    stage: str = "progress",
    detail: dict | None = None,
    **kwargs,
):
    """Push a structured log event to console + all SSE log clients.

    Thread-safe: can be called from OCR worker threads.
    Console logging is inherently thread-safe; queue pushes are
    scheduled onto the event loop via run_coroutine_threadsafe.
    """
    # Console log (thread-safe)
    log_fn = getattr(logger, level, logger.info)
    stage_label = STAGE_LABELS.get(stage, stage)
    log_fn(f"[{stage_label}] {message}")

    # SSE broadcast (thread-safe via event-loop scheduling)
    payload = _build_log_payload(message, level, stage, detail, **kwargs)
    event_data = json.dumps(payload, ensure_ascii=False)
    _threadsafe_push(_log_queues, event_data)


def broadcast_result(data: dict):
    """Push a partial OCR result to all SSE result clients.

    Thread-safe — called from OCR worker threads.
    data should contain at minimum {'type': 'page'|'done'|'error', ...}
    """
    # Also log a lightweight note to the console
    rtype = data.get("type", "result")
    logger.debug(f"[result] {rtype}: {json.dumps(data, ensure_ascii=False)[:120]}")

    payload = json.dumps(data, ensure_ascii=False)
    _threadsafe_push(_result_queues, payload)


# ── Lazy OCR engine ─────────────────────────────────────────────────
_ocr = None
_ocr_lock = threading.Lock()


def _make_temp_path(prefix: str, suffix: str = ".png") -> Path:
    """Create a unique temporary path that works on Windows, WSL, and Linux."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(path)


def get_ocr():
    """Lazy-init PaddleOCR with PP-OCRv6 ONNX models. Thread-safe."""
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:  # double-check
                broadcast_log(
                    "正在加载 PP-OCRv6 模型 (ONNX Runtime)...",
                    level="info",
                    stage="init",
                )
                t0 = time.time()
                from paddleocr import PaddleOCR

                _ocr = PaddleOCR(
                    ocr_version="PP-OCRv6",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    engine="onnxruntime",
                    lang="ch",
                )
                elapsed = time.time() - t0
                broadcast_log(
                    f"模型加载完成，耗时 {elapsed:.1f}s",
                    level="info",
                    stage="init",
                    detail={
                        "elapsed_sec": round(elapsed, 1),
                        "engine": "onnxruntime",
                        "version": "PP-OCRv6",
                    },
                )
    return _ocr


# ── OCR processing (run in thread pool) ─────────────────────────────


def _ocr_image_bytes(image_bytes: bytes, filename: str = "input.png") -> list:
    """Run OCR on raw image bytes. Returns list of page dicts.

    This is called in a thread pool — broadcast_log is thread-safe.
    """
    t0 = time.time()

    # ── Preprocess ──
    broadcast_log(
        f"读取图像: {filename}", level="info", stage="preprocess"
    )
    image = Image.open(io.BytesIO(image_bytes))
    w, h = image.size
    broadcast_log(
        f"图像尺寸 {w}×{h}, 模式 {image.mode}",
        level="info",
        stage="preprocess",
        detail={"width": w, "height": h, "mode": image.mode, "filename": filename},
    )

    suffix = Path(filename).suffix or ".png"
    temp_path = _make_temp_path("ppocr_image_", suffix)
    try:
        image.save(temp_path)
        file_size = temp_path.stat().st_size
        broadcast_log(
            f"临时文件写入: {temp_path} ({file_size/1024:.1f} KB)",
            level="debug",
            stage="preprocess",
            detail={"path": str(temp_path), "size_kb": round(file_size / 1024, 1)},
        )

        # ── OCR ──
        ocr = get_ocr()
        broadcast_log("开始文字检测与识别...", level="info", stage="detection")
        results = ocr.predict(str(temp_path))

        # ── Parse results ──
        pages = []
        for res in results:
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = res.get("rec_boxes", [])

            n_regions = len(texts)
            avg_score = float(np.mean(scores)) if len(scores) > 0 else 0.0
            pages.append({
                "texts": [str(t) for t in texts],
                "scores": [float(s) for s in scores],
                "boxes": boxes.tolist() if hasattr(boxes, "tolist") else boxes,
            })

            broadcast_log(
                f"检测到 {n_regions} 个文字区域，平均置信度 {avg_score:.1%}",
                level="info",
                stage="recognition",
                detail={
                    "regions": n_regions,
                    "avg_confidence": round(avg_score, 3),
                    "texts_preview": [str(t)[:20] for t in texts[:5]],
                },
            )
    finally:
        temp_path.unlink(missing_ok=True)

    elapsed = time.time() - t0
    broadcast_log(
        f"OCR 完成，总耗时 {elapsed:.1f}s",
        level="info",
        stage="done",
        detail={
            "elapsed_sec": round(elapsed, 1),
            "regions_total": sum(len(p["texts"]) for p in pages),
        },
        progress_pct=100.0,
    )

    return pages


def _ocr_pdf_bytes(
    pdf_bytes: bytes,
    filename: str = "document.pdf",
    dpi: int = 200,
    max_pages: int = 0,
):
    """Run OCR on PDF bytes. Returns (pages_list, total_pages, processed_pages).

    This is called in a thread pool.  broadcast_log and broadcast_result
    are both thread-safe — results stream to SSE clients in real time.
    """
    t0 = time.time()

    # ── Read PDF ──
    broadcast_log(
        f"读取 PDF: {filename}", level="info", stage="preprocess"
    )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    pages_to_process = (
        min(total_pages, max_pages) if max_pages > 0 else total_pages
    )

    broadcast_log(
        f"PDF 共 {total_pages} 页，将处理 {pages_to_process} 页 @ {dpi} DPI",
        level="info",
        stage="preprocess",
        detail={
            "total_pages": total_pages,
            "pages_to_process": pages_to_process,
            "dpi": dpi,
        },
        progress_total=pages_to_process,
        progress_current=0,
    )

    ocr = get_ocr()
    all_pages = []

    for page_idx in range(pages_to_process):
        page_start = time.time()

        # ── Render ──
        broadcast_log(
            f"第 {page_idx+1}/{pages_to_process} 页 — 渲染中...",
            level="info",
            stage="preprocess",
            progress_current=page_idx,
            progress_total=pages_to_process,
            progress_pct=round(page_idx / pages_to_process * 90, 1),
        )

        page = doc[page_idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        broadcast_log(
            f"渲染完成: {pix.width}×{pix.height}",
            level="debug",
            stage="preprocess",
            detail={"page": page_idx + 1, "width": pix.width, "height": pix.height},
        )

        # ── OCR ──
        temp_path = _make_temp_path(f"ppocr_pdf_p{page_idx + 1}_", ".png")
        img.save(temp_path)

        broadcast_log(
            f"第 {page_idx+1}/{pages_to_process} 页 — 正在识别...",
            level="info",
            stage="detection",
            progress_current=page_idx,
            progress_total=pages_to_process,
            progress_pct=round(page_idx / pages_to_process * 90, 1),
        )

        try:
            results = ocr.predict(str(temp_path))
            for res in results:
                texts = res.get("rec_texts", [])
                scores = res.get("rec_scores", [])
                boxes = res.get("rec_boxes", [])

                page_entry = {
                    "page": page_idx + 1,
                    "width": pix.width,
                    "height": pix.height,
                    "texts": [str(t) for t in texts],
                    "scores": [float(s) for s in scores],
                    "boxes": boxes.tolist() if hasattr(boxes, "tolist") else boxes,
                }
                all_pages.append(page_entry)

                page_elapsed = time.time() - page_start
                avg_score = float(np.mean(scores)) if len(scores) > 0 else 0.0

                broadcast_log(
                    f"第 {page_idx+1} 页完成 — {len(texts)} 个文字区域, 耗时 {page_elapsed:.1f}s",
                    level="info",
                    stage="recognition",
                    detail={
                        "page": page_idx + 1,
                        "regions": len(texts),
                        "elapsed_sec": round(page_elapsed, 1),
                    },
                    progress_current=page_idx + 1,
                    progress_total=pages_to_process,
                    progress_pct=round((page_idx + 1) / pages_to_process * 95, 1),
                )

                # ── Stream partial result via SSE ──
                broadcast_result({
                    "type": "page",
                    "page": page_idx + 1,
                    "total_pages": total_pages,
                    "processed_pages": pages_to_process,
                    "texts": [str(t) for t in texts],
                    "scores": [float(s) for s in scores],
                    "boxes": boxes.tolist() if hasattr(boxes, "tolist") else boxes,
                    "width": pix.width,
                    "height": pix.height,
                    "regions": len(texts),
                    "avg_confidence": round(avg_score, 3),
                    "elapsed_sec": round(page_elapsed, 1),
                })
        finally:
            temp_path.unlink(missing_ok=True)

    doc.close()

    total_elapsed = time.time() - t0
    total_regions = sum(len(p["texts"]) for p in all_pages)

    broadcast_log(
        f"PDF OCR 完成 — {pages_to_process} 页, {total_regions} 个文字区域, 总耗时 {total_elapsed:.1f}s",
        level="info",
        stage="done",
        detail={
            "total_pages": total_pages,
            "processed_pages": pages_to_process,
            "total_regions": total_regions,
            "elapsed_sec": round(total_elapsed, 1),
            "dpi": dpi,
        },
        progress_pct=100.0,
        progress_current=pages_to_process,
        progress_total=pages_to_process,
    )

    # ── Signal completion on results stream ──
    broadcast_result({
        "type": "done",
        "total_pages": total_pages,
        "processed_pages": pages_to_process,
        "total_regions": total_regions,
        "elapsed_sec": round(total_elapsed, 1),
    })

    return all_pages, total_pages, pages_to_process


# ── FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    title="PP-OCRv6 OCR Server",
    description="Lightweight OCR API powered by PP-OCRv6 (ONNX Runtime)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SSE: Log Stream ─────────────────────────────────────────────────
@app.get("/ocr/logs")
async def ocr_logs(request: Request):
    """SSE stream of structured OCR log events (progress, status)."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _log_queues.append(queue)

    async def event_generator():
        try:
            init_payload = _build_log_payload(
                "日志流已连接", level="info", stage="init"
            )
            init_payload["stage_label"] = "连接"
            yield f"data: {json.dumps(init_payload, ensure_ascii=False)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _log_queues:
                _log_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── SSE: Results Stream ─────────────────────────────────────────────
@app.get("/ocr/results")
async def ocr_results(request: Request):
    """SSE stream of partial OCR results — pages stream in real time.

    Each event is a JSON object:
      {"type": "page", "page": N, "texts": [...], "scores": [...], ...}
      {"type": "done",  "total_pages": N, ...}
      {"type": "error", "message": "..."}
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _result_queues.append(queue)

    async def event_generator():
        try:
            init = json.dumps(
                {"type": "connected", "message": "结果流已连接"}, ensure_ascii=False
            )
            yield f"data: {init}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _result_queues:
                _result_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Health ──────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "engine": "onnxruntime", "model": "PP-OCRv6"}


# ── Endpoints ───────────────────────────────────────────────────────
@app.post("/ocr/image")
async def ocr_image(file: UploadFile = File(...)):
    """OCR on a single image. Returns texts, scores, and bounding boxes."""
    if not (file.content_type and file.content_type.startswith("image/")):
        raise HTTPException(400, "File must be an image")

    try:
        image_bytes = await file.read()
        loop = asyncio.get_running_loop()
        pages = await loop.run_in_executor(
            _ocr_executor,
            _ocr_image_bytes,
            image_bytes,
            file.filename or "input.png",
        )
        return {"status": "success", "pages": pages}

    except Exception as e:
        broadcast_log(
            f"OCR 失败: {str(e)}",
            level="error",
            stage="error",
            detail={"error_type": type(e).__name__},
        )
        logger.exception("OCR failed")
        raise HTTPException(500, f"OCR error: {str(e)}")


@app.post("/ocr/pdf")
async def ocr_pdf(
    file: UploadFile = File(...),
    dpi: int = Query(200, ge=72, le=600, description="Render DPI"),
    max_pages: int = Query(0, ge=0, description="Max pages (0=all)"),
):
    """OCR on a PDF. Each page is rendered at the given DPI and OCR'd.

    Results are also streamed via GET /ocr/results in real time.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF")

    try:
        pdf_bytes = await file.read()
        loop = asyncio.get_running_loop()
        all_pages, total_pages, pages_to_process = await loop.run_in_executor(
            _ocr_executor,
            _ocr_pdf_bytes,
            pdf_bytes,
            file.filename or "document.pdf",
            dpi,
            max_pages,
        )
        return {
            "status": "success",
            "total_pages": total_pages,
            "processed_pages": pages_to_process,
            "pages": all_pages,
        }

    except Exception as e:
        broadcast_log(
            f"PDF OCR 失败: {str(e)}",
            level="error",
            stage="error",
            detail={"error_type": type(e).__name__},
        )
        broadcast_result({"type": "error", "message": str(e)})
        logger.exception("PDF OCR failed")
        raise HTTPException(500, f"PDF OCR error: {str(e)}")


@app.post("/ocr/text")
async def ocr_text(file: UploadFile = File(...)):
    """OCR on an image, returning concatenated plain text."""
    result = await ocr_image(file)
    all_text = []
    for page in result.get("pages", []):
        all_text.extend(page.get("texts", []))
    return {"status": "success", "text": "\n".join(all_text)}


# ── Startup: capture event loop ─────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _loop
    _loop = asyncio.get_running_loop()
    logger.info(f"Event loop captured for thread-safe SSE broadcast")


# ── Entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PP-OCRv6 OCR Server")
    parser.add_argument(
        "--port", type=int, default=8765, help="Server port (default 8765)"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Bind address"
    )
    args = parser.parse_args()

    logger.info(f"Starting PP-OCRv6 OCR server on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
