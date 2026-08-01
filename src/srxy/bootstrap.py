"""Wire application services and outbound adapters."""

from __future__ import annotations

from dataclasses import dataclass

from srxy.adapters.outbound.content.content_cache import SqliteContentCache
from srxy.adapters.outbound.content.file_walker import DefaultFileWalker
from srxy.adapters.outbound.content.image_similarity import ClipImageSimilarity
from srxy.adapters.outbound.content.text_extractor import DefaultTextExtractor
from srxy.adapters.outbound.os.desktop import OsDesktopAdapter
from srxy.application.search_runner import FileSearchService
from srxy.application.search_runner_adapter import AdaptiveSearchRunner
from srxy.application.search_session import SearchSession
from srxy.ports.inbound.file_search import FileSearchPort
from srxy.ports.inbound.search_runner import SearchRunnerPort
from srxy.ports.outbound.content import (
	ContentCachePort,
	FileWalkerPort,
	ImageSimilarityPort,
	TextExtractorPort,
)
from srxy.ports.outbound.desktop import DesktopPort


@dataclass(frozen=True, slots=True)
class AppServices:
	file_search: FileSearchPort
	search_session: SearchSession
	search_runner: SearchRunnerPort
	desktop: DesktopPort
	text_extractor: TextExtractorPort
	file_walker: FileWalkerPort
	image_similarity: ImageSimilarityPort
	content_cache: ContentCachePort


def build_app_services(*, desktop: DesktopPort | None = None) -> AppServices:
	text_extractor: TextExtractorPort = DefaultTextExtractor()
	file_walker: FileWalkerPort = DefaultFileWalker()
	image_similarity: ImageSimilarityPort = ClipImageSimilarity()
	content_cache: ContentCachePort = SqliteContentCache()
	from srxy.application.use_cases.search_files import set_content_ports, set_text_extractor

	set_text_extractor(text_extractor)
	set_content_ports(
		text_extractor=text_extractor,
		file_walker=file_walker,
		image_similarity=image_similarity,
		content_cache=content_cache,
	)
	file_search: FileSearchPort = FileSearchService()
	search_session = SearchSession(file_search)
	search_runner: SearchRunnerPort = AdaptiveSearchRunner(search_session)
	return AppServices(
		file_search=file_search,
		search_session=search_session,
		search_runner=search_runner,
		desktop=desktop if desktop is not None else OsDesktopAdapter(),
		text_extractor=text_extractor,
		file_walker=file_walker,
		image_similarity=image_similarity,
		content_cache=content_cache,
	)


def build_worker_services() -> AppServices:
	"""Composition root for the search worker subprocess."""
	return build_app_services()
