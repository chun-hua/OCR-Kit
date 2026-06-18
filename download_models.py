#!/usr/bin/env python3
"""Download PP-OCRv6 ONNX models from HuggingFace (via hf-mirror.com for China)."""

import os
import sys
from pathlib import Path

# Use HF mirror for faster download in China
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

MODELS_DIR = Path(__file__).parent / "models"
MODELS = {
    "det": "PaddlePaddle/PP-OCRv6_tiny_det_onnx",
    "rec": "PaddlePaddle/PP-OCRv6_tiny_rec_onnx",
}


def download_model(repo_id: str, local_dir: Path):
    from huggingface_hub import snapshot_download

    print(f"Downloading {repo_id} -> {local_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    # List downloaded files
    for f in sorted(local_dir.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(MODELS_DIR)} ({f.stat().st_size / 1024:.1f} KB)")


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, repo_id in MODELS.items():
        local_dir = MODELS_DIR / name
        local_dir.mkdir(parents=True, exist_ok=True)
        download_model(repo_id, local_dir)
    print("\nAll models downloaded successfully!")


if __name__ == "__main__":
    main()
