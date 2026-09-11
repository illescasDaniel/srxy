from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from srxy.adapters.outbound.ocr.ocr_text import ocr_pil_image, tesseract_available


pytestmark = [pytest.mark.integration, pytest.mark.ocr]

ORIENTATION_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "file_search" / "ocr" / "orientation"

# Cardinal rotations must recover the token after OSD upright + PSM / probe selection.
_CARDINAL_CASES = [
	("ocr_document_0.jpg", "sister"),
	("ocr_document_90.jpg", "sister"),
	("ocr_document_180.jpg", "sister"),
	("ocr_document_270.jpg", "sister"),
	("no_smoking_0.jpg", "smoking"),
	("no_smoking_90.jpg", "smoking"),
	("no_smoking_180.jpg", "smoking"),
	("no_smoking_270.jpg", "smoking"),
]


@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
@pytest.mark.parametrize(("filename", "token"), _CARDINAL_CASES)
def test_given_rotated_cc_fixture_when_ocring_then_reads_token(filename: str, token: str):
	# given
	path = ORIENTATION_DIR / filename
	assert path.is_file(), f"missing fixture {path} (run scripts/build_ocr_orientation_fixtures.py)"

	# when
	with Image.open(path) as image:
		text = ocr_pil_image(image)

	# then
	assert token.lower() in text.lower(), f"{filename}: expected {token!r} in {text[:200]!r}"
