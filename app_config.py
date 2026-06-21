"""Persistent desktop configuration and hardware recommendations for OCR-Kit."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "OCR-Kit"
CONFIG_VERSION = 1

PERFORMANCE_PROFILES: dict[str, dict[str, Any]] = {
    "compatible": {
        "label": "兼容模式",
        "description": "适合 4–8 GB 内存或较老的双核/四核电脑，优先稳定和低占用。",
        "model": "tiny",
        "cpu_threads": 2,
        "ocr_workers": 1,
        "device": "cpu",
    },
    "balanced": {
        "label": "均衡模式",
        "description": "适合 8 GB 以上内存和主流四核以上处理器，推荐大多数电脑使用。",
        "model": "small",
        "cpu_threads": 6,
        "ocr_workers": 1,
        "device": "cpu",
    },
    "performance": {
        "label": "高性能 CPU",
        "description": "适合 16 GB 以上内存和八核以上处理器，使用更多线程并默认选择高精度模型。",
        "model": "medium",
        "cpu_threads": 10,
        "ocr_workers": 1,
        "device": "cpu",
    },
    "cuda": {
        "label": "NVIDIA CUDA",
        "description": "仅适用于包含 CUDA Runtime 的 GPU 发行版，并要求兼容的 NVIDIA 驱动。",
        "model": "medium",
        "cpu_threads": 4,
        "ocr_workers": 1,
        "device": "gpu",
    },
}


def _default_user_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"


def get_config_path() -> Path:
    explicit = os.environ.get("PPOCR_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\{APP_NAME}") as key:
                value, _ = winreg.QueryValueEx(key, "ConfigPath")
                if value:
                    return Path(value).expanduser().resolve()
        except (OSError, ValueError):
            pass

    return _default_user_root() / "config.json"


def default_config() -> dict[str, Any]:
    root = _default_user_root()
    profile = deepcopy(PERFORMANCE_PROFILES["balanced"])
    return {
        "version": CONFIG_VERSION,
        "model_dir": str(root / "models"),
        "project_dir": str(Path.home() / "Documents" / APP_NAME),
        "performance_profile": "balanced",
        "device": profile["device"],
        "cpu_threads": profile["cpu_threads"],
        "ocr_workers": profile["ocr_workers"],
        "default_model": profile["model"],
        "open_browser": True,
        "server_port": 8765,
    }


def _normalize(config: dict[str, Any]) -> dict[str, Any]:
    merged = default_config()
    merged.update(config)

    profile_id = str(merged.get("performance_profile", "balanced")).lower()
    if profile_id not in PERFORMANCE_PROFILES:
        profile_id = "balanced"
    merged["performance_profile"] = profile_id

    merged["device"] = "gpu" if str(merged.get("device")).lower() == "gpu" else "cpu"
    merged["cpu_threads"] = max(1, min(int(merged.get("cpu_threads", 4)), 64))
    merged["ocr_workers"] = max(1, min(int(merged.get("ocr_workers", 1)), 4))
    merged["server_port"] = max(1024, min(int(merged.get("server_port", 8765)), 65535))
    merged["default_model"] = (
        merged["default_model"]
        if merged.get("default_model") in {"tiny", "small", "medium"}
        else PERFORMANCE_PROFILES[profile_id]["model"]
    )
    merged["model_dir"] = str(Path(merged["model_dir"]).expanduser().resolve())
    merged["project_dir"] = str(Path(merged["project_dir"]).expanduser().resolve())
    merged["version"] = CONFIG_VERSION
    merged["open_browser"] = bool(merged.get("open_browser", True))
    return merged


def load_config() -> dict[str, Any]:
    path = get_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be an object")
        return _normalize(data)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return _normalize({})


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize(config)
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)
    Path(normalized["model_dir"]).mkdir(parents=True, exist_ok=True)
    Path(normalized["project_dir"]).mkdir(parents=True, exist_ok=True)
    return normalized


def apply_runtime_environment(config: dict[str, Any]) -> None:
    model_dir = Path(config["model_dir"])
    project_dir = Path(config["project_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    os.environ["PADDLE_PDX_CACHE_HOME"] = str(model_dir)
    os.environ["HF_HOME"] = str(model_dir / "huggingface")
    os.environ["PPOCR_MODEL"] = str(config["default_model"])
    os.environ["OMP_NUM_THREADS"] = str(config["cpu_threads"])
    os.environ["MKL_NUM_THREADS"] = str(config["cpu_threads"])


def _windows_gpu_names() -> list[str]:
    if os.name != "nt":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-CimInstance Win32_VideoController | "
            "Where-Object {$_.Name} | Select-Object -ExpandProperty Name"
        ),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def detect_hardware() -> dict[str, Any]:
    logical_cpus = os.cpu_count() or 1
    memory_gb: float | None = None
    try:
        import psutil

        memory_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        if os.name == "nt":
            try:
                import ctypes

                class MemoryStatus(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                status = MemoryStatus()
                status.dwLength = ctypes.sizeof(MemoryStatus)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
                memory_gb = round(status.ullTotalPhys / (1024**3), 1)
            except (AttributeError, OSError):
                pass

    providers: list[str] = []
    try:
        import onnxruntime as ort

        providers = list(ort.get_available_providers())
    except (ImportError, OSError, AttributeError):
        pass

    gpu_names = _windows_gpu_names()
    cuda_available = "CUDAExecutionProvider" in providers
    if cuda_available:
        recommended = "cuda"
        reason = "检测到可用的 ONNX Runtime CUDA 执行提供程序。"
    elif memory_gb is not None and memory_gb >= 16 and logical_cpus >= 8:
        recommended = "performance"
        reason = "内存不少于 16 GB 且逻辑处理器不少于 8 个。"
    elif memory_gb is not None and memory_gb < 8:
        recommended = "compatible"
        reason = "可用物理内存配置低于 8 GB，建议控制模型和线程占用。"
    else:
        recommended = "balanced"
        reason = "当前硬件适合默认的速度与资源占用平衡配置。"

    return {
        "os": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "logical_cpus": logical_cpus,
        "memory_gb": memory_gb,
        "gpus": gpu_names,
        "onnx_providers": providers,
        "cuda_available": cuda_available,
        "recommended_profile": recommended,
        "recommendation_reason": reason,
    }


def public_settings(config: dict[str, Any]) -> dict[str, Any]:
    return {
        **config,
        "config_path": str(get_config_path()),
        "profiles": [
            {"id": key, **value} for key, value in PERFORMANCE_PROFILES.items()
        ],
    }
