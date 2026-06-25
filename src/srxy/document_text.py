from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path


DOCUMENT_SUFFIXES = frozenset({".pdf", ".docx", ".xlsx", ".pptx"})


def is_document_path(path: Path) -> bool:
	return path.suffix.lower() in DOCUMENT_SUFFIXES


def iter_document_lines(path: Path) -> Iterator[tuple[int, str]]:
	suffix = path.suffix.lower()
	extractors: dict[str, Callable[[Path], Iterator[tuple[int, str]]]] = {
		".pdf": _iter_pdf_lines,
		".docx": _iter_docx_lines,
		".xlsx": _iter_xlsx_lines,
		".pptx": _iter_pptx_lines,
	}
	extractor = extractors.get(suffix)
	if extractor is None:
		return
	try:
		yield from extractor(path)
	except Exception:
		return


def _iter_pdf_lines(path: Path) -> Iterator[tuple[int, str]]:
	from pypdf import PdfReader

	reader = PdfReader(path)
	for page_number, page in enumerate(reader.pages, start=1):
		text = page.extract_text() or ""
		text = text.strip()
		if text:
			yield page_number, text


def _iter_docx_lines(path: Path) -> Iterator[tuple[int, str]]:
	from docx import Document

	document = Document(str(path))
	for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
		text = paragraph.text.strip()
		if text:
			yield paragraph_number, text


def _iter_xlsx_lines(path: Path) -> Iterator[tuple[int, str]]:
	from openpyxl import load_workbook

	workbook = load_workbook(path, read_only=True, data_only=True)
	try:
		line_number = 0
		for sheet in workbook.worksheets:
			for row in sheet.iter_rows(values_only=True):
				cells = [str(cell) for cell in row if cell is not None and str(cell).strip()]
				if not cells:
					continue
				line_number += 1
				yield line_number, f"[{sheet.title}] " + " ".join(cells)
	finally:
		workbook.close()


def _iter_pptx_lines(path: Path) -> Iterator[tuple[int, str]]:
	from pptx import Presentation

	presentation = Presentation(str(path))
	for slide_number, slide in enumerate(presentation.slides, start=1):
		parts: list[str] = []
		for shape in slide.shapes:
			text = shape.text.strip() if hasattr(shape, "text") else ""
			if text:
				parts.append(text)
		if parts:
			yield slide_number, " ".join(parts)
