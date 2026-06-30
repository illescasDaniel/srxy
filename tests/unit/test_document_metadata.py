from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from srxy.document_text import iter_document_metadata_lines


pytestmark = pytest.mark.unit

_CORE_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:creator>Alice Example</dc:creator>
  <cp:lastModifiedBy>Bob Editor</cp:lastModifiedBy>
  <dc:title>Quarterly Report</dc:title>
</cp:coreProperties>
"""

_APP_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Microsoft Office Word</Application>
  <Company>Example Corp</Company>
</Properties>
"""


def _write_min_docx(path: Path):
	with ZipFile(path, "w") as archive:
		archive.writestr("docProps/core.xml", _CORE_XML)
		archive.writestr("docProps/app.xml", _APP_XML)
		archive.writestr("[Content_Types].xml", "<Types/>")
		archive.writestr("word/document.xml", "<w:document/>")


def test_given_office_package_metadata_when_iterating_lines_then_yields_labeled_values(tmp_path: Path):
	# given
	file_path = tmp_path / "report.docx"
	_write_min_docx(file_path)

	# when
	with (
		patch("srxy.windows_metadata.windows_metadata_supported", return_value=False),
	):
		lines = list(iter_document_metadata_lines(file_path))

	# then
	assert lines == [
		(1, "[Author] Alice Example"),
		(2, "[Last saved by] Bob Editor"),
		(3, "[Title] Quarterly Report"),
		(4, "[Program name] Microsoft Office Word"),
		(5, "[Company] Example Corp"),
	]


def test_given_non_office_file_when_iterating_document_metadata_then_yields_nothing(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("hello", encoding="utf-8")

	# then
	assert list(iter_document_metadata_lines(file_path)) == []
