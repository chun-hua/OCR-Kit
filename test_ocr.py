#!/usr/bin/env python3
"""Test PP-OCRv6 on a local PDF or image file."""

import os
import sys
import tempfile
from pathlib import Path

# Use HF mirror for model downloads
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from paddleocr import PaddleOCR


def test_image(image_path: str):
    print(f"Testing OCR on image: {image_path}")
    ocr = PaddleOCR(
        ocr_version="PP-OCRv6",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="onnxruntime",
        lang="ch",
    )
    results = ocr.predict(image_path)
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])
        for text, score in zip(texts, scores):
            print(f"  [{float(score):.3f}] {text}")


def test_pdf(pdf_path: str, dpi: int = 200):
    import fitz
    from PIL import Image

    print(f"Testing OCR on PDF: {pdf_path} (DPI={dpi})")

    ocr = PaddleOCR(
        ocr_version="PP-OCRv6",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="onnxruntime",
        lang="ch",
    )

    doc = fitz.open(pdf_path)
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        fd, temp_name = tempfile.mkstemp(
            prefix=f"ppocr_test_p{page_idx + 1}_",
            suffix=".png",
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            img.save(temp_path)
            results = ocr.predict(str(temp_path))
            for res in results:
                texts = res.get("rec_texts", [])
                print(f"\n--- Page {page_idx+1} ---")
                for text in texts:
                    print(f"  {text}")
        finally:
            temp_path.unlink(missing_ok=True)

    doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default: test on PDF in current directory
        pdfs = list(Path(".").glob("*.pdf"))
        if pdfs:
            test_pdf(str(pdfs[0]))
        else:
            print("Usage: python test_ocr.py <image_or_pdf_path>")
    else:
        path = sys.argv[1]
        if path.lower().endswith(".pdf"):
            test_pdf(path)
        else:
            test_image(path)
