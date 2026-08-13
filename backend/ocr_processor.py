"""
ocr_processor.py

Step 7 (stretch goal) of the build: extract text from an image of a
prescription/medication list (e.g. a photo or scanned document), then
reuse extractor.py's vocabulary-based drug detection on the OCR'd text.

Deliberately uses pytesseract (a thin wrapper around the Tesseract OCR
engine) instead of an ML-based OCR library like EasyOCR, because EasyOCR
depends on torch — which is blocked on this machine by a Windows
Application Control / WDAC policy (see extractor.py for the same issue
we hit with BioBERT). Tesseract is a standalone binary with no such
dependency.

Requires:
  1. pip install pytesseract pillow
  2. The Tesseract OCR *engine* installed separately (not a pip package):
     - Windows: https://github.com/UB-Mannheim/tesseract/wiki
       (install, then set TESSERACT_CMD below to the install path, e.g.
       "C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
     - Mac: brew install tesseract
     - Linux: apt install tesseract-ocr
"""

import os

from PIL import Image, ImageFilter, ImageOps
import pytesseract

from extractor import extract_drug_mentions, extract_and_normalize

# On Windows, pytesseract can't find the tesseract binary automatically
# unless it's on PATH. If you installed it but get a "tesseract is not
# installed" error, uncomment and set this to your actual install path:
#
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_env_cmd = os.environ.get("TESSERACT_CMD")
if _env_cmd:
    pytesseract.pytesseract.tesseract_cmd = _env_cmd


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Basic preprocessing to improve OCR accuracy on photographed (not
    scanned) prescriptions: convert to grayscale, boost contrast a bit,
    and lightly sharpen. Cheap operations, no ML involved."""
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    sharpened = gray.filter(ImageFilter.SHARPEN)
    return sharpened


def extract_text_from_image(image_path: str) -> str:
    """Run OCR on an image file and return the raw extracted text."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = Image.open(image_path)
    processed = _preprocess_image(image)

    try:
        text = pytesseract.image_to_string(processed)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract OCR engine not found. Install it separately (it's not "
            "a pip package) — see the module docstring in ocr_processor.py "
            "for instructions, then set TESSERACT_CMD if needed."
        ) from e

    return text


def extract_drugs_from_image(image_path: str) -> list:
    """Full pipeline: image -> OCR text -> raw drug mentions (via
    extractor.py's vocabulary matcher). Returns raw strings, not yet
    normalized."""
    text = extract_text_from_image(image_path)
    return extract_drug_mentions(text)


def extract_and_normalize_from_image(image_path: str) -> list:
    """Full pipeline: image -> OCR text -> normalized drugs. Returns
    NormalizedDrug objects, same as extractor.py's text-based version, so
    main.py can plug this into the same interactions.py flow."""
    text = extract_text_from_image(image_path)
    return extract_and_normalize(text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ocr_processor.py <path_to_image>")
        print("(No test image bundled — pass a photo of a prescription/med list.)")
        sys.exit(1)

    image_path = sys.argv[1]

    print(f"Running OCR on: {image_path}\n")
    raw_text = extract_text_from_image(image_path)
    print("=== Raw OCR text ===")
    print(raw_text)
    print()

    mentions = extract_drug_mentions(raw_text)
    print("=== Extracted drug mentions ===")
    print(mentions)
    print()

    normalized = extract_and_normalize(raw_text)
    print("=== Normalized ===")
    for nd in normalized:
        print(f"{nd.original!r:20} -> {nd.normalized!r:25} "
              f"match_type={nd.match_type:15} is_class={nd.is_class}")