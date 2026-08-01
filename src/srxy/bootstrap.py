"""Wire application services and outbound adapters."""

from __future__ import annotations

from srxy.adapters.outbound.os.desktop import DesktopAdapter
from srxy.application.search_runner import FileSearchService
from srxy.application.search_session import SearchSession


def build_file_search_service() -> FileSearchService:
	return FileSearchService()


def build_search_session() -> SearchSession:
	return SearchSession()


def build_desktop() -> DesktopAdapter:
	return DesktopAdapter()
