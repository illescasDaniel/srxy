from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from srxy import SearchResult


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@dataclass(frozen=True)
class LabeledQuery:
	query: str
	expected_id: str
	min_top_score: float


@dataclass
class Product:
	name: str
	description: str = ""
	category: str = ""
	status: str = ""
	alias: str = ""
	sku: str = ""
	tags: str = ""


def load_search_corpus() -> list[dict[str, Any]]:
	path = FIXTURES_DIR / "search_corpus.json"
	return json.loads(path.read_text(encoding="utf-8"))


def load_labeled_queries() -> list[LabeledQuery]:
	path = FIXTURES_DIR / "labeled_queries.json"
	raw = json.loads(path.read_text(encoding="utf-8"))
	return [LabeledQuery(**entry) for entry in raw]


def top_k_hit_rate(results_by_query: list[list[SearchResult]], expected_ids: list[str], *, k: int) -> float:
	hits = 0
	for results, expected_id in zip(results_by_query, expected_ids, strict=True):
		top_ids = [result.item["id"] for result in results[:k]]
		if expected_id in top_ids:
			hits += 1
	return hits / len(expected_ids)


def write_pdf_with_text(path: Path, text: str):
	"""Write a minimal single-page PDF with extractable text."""
	escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
	stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
	stream_bytes = stream.encode("latin-1")
	pdf = f"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length {len(stream_bytes)}>>stream
{stream}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000313 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
403
%%EOF
"""
	path.write_bytes(pdf.encode("latin-1"))


def write_docx_with_text(path: Path, text: str):
	from docx import Document

	document = Document()
	document.add_paragraph(text)
	document.save(str(path))


def write_xlsx_with_text(path: Path, text: str):
	from openpyxl import Workbook

	workbook = Workbook()
	sheet = workbook.active
	if sheet is not None:
		sheet.title = "Summary"
		sheet["A1"] = text
	workbook.save(path)


def write_pptx_with_text(path: Path, text: str):
	from pptx import Presentation
	from pptx.util import Inches

	presentation = Presentation()
	slide = presentation.slides.add_slide(presentation.slide_layouts[6])
	textbox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
	textbox.text_frame.text = text
	presentation.save(str(path))
