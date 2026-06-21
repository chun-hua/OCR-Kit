"""Windows desktop launcher for the packaged OCR-Kit application."""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from app_config import apply_runtime_environment, load_config, save_config

_redirected_stream = None


def _redirect_packaged_streams(project_dir: str) -> None:
    """Give windowed builds a valid stream for third-party progress output."""
    global _redirected_stream
    if not getattr(sys, "frozen", False):
        return
    log_dir = Path(project_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _redirected_stream = open(
        log_dir / "runtime-output.log",
        "a",
        encoding="utf-8",
        buffering=1,
    )
    sys.stdout = _redirected_stream
    sys.stderr = _redirected_stream


def _configure_logging(project_dir: str) -> None:
    log_dir = Path(project_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "ocr-kit.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def _is_ocr_kit_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            return response.status == 200 and b"OCR-Kit" in response.read()
    except Exception:
        return False


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _open_when_ready(url: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(0.25)


def main() -> None:
    config = load_config()
    config = save_config(config)
    apply_runtime_environment(config)
    _redirect_packaged_streams(config["project_dir"])
    _configure_logging(config["project_dir"])

    port = int(config["server_port"])
    url = f"http://127.0.0.1:{port}"
    if _is_ocr_kit_running(port):
        webbrowser.open(url)
        return
    if not _port_available(port):
        raise RuntimeError(
            f"端口 {port} 已被其他程序占用。请在配置文件中修改 server_port："
            f"{config['config_path'] if 'config_path' in config else ''}"
        )

    if config.get("open_browser", True):
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    import uvicorn
    from server import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
