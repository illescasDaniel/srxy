from __future__ import annotations

import re
import threading
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path

from srxy.adapters.outbound.content.file_walker import is_names_only_path
from srxy.adapters.outbound.content.path_access import (
	PERMISSION_DENIED_REASON,
	directory_is_listable,
	is_access_denied,
	permission_skip,
)
from srxy.application.matching.composite import CompositeMatcher
from srxy.application.search_control import SearchCancelled
from srxy.application.search_defaults import (
	DEFAULT_MAX_FILE_SIZE as DEFAULT_MAX_FILE_SIZE,
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	DEFAULT_TRANSCRIBE_THRESHOLD,
	suggest_max_file_size as suggest_max_file_size,
)
from srxy.application.search_options import search_source_required_message
from srxy.application.utils import normalize_text, query_words, word_pair_match_allowed
from srxy.domain.file_query import (
	FileQ,
	coerce_file_query,
	format_file_query,
	iter_terms,
	query_is_compound,
	score_file_query,
	score_file_query_on_text,
)
from srxy.domain.models import FileSearchResult, LineMatch, SkippedFile
from srxy.domain.progress import (
	ActivityCallback,
	clear_activity,
	concurrent_activity_fan_in,
	emit_activity,
)
from srxy.ports.outbound.content import (
	ContentCachePort,
	FileWalkerPort,
	ImageSimilarityPort,
	TextExtractorPort,
)


_MIN_SEARCHABLE_WORD_LENGTH = 3
_SHORT_QUERY_PHONETIC_SKIP_LENGTH = 3
# Minimum file count before the process pool is activated for text-only searches.
# Below this threshold the process startup cost outweighs the parallelism benefit.
_MIN_PROCESS_FILES = 50
# Cap in-flight pool futures relative to max_workers so huge trees do not enqueue
# millions of Future objects while the walk continues.
_POOL_PENDING_FACTOR = 4
_LISTING_ACTIVITY_INTERVAL = 256
_SEMANTIC_WORD_MATCH_GATE = 0.5
_WORD_PATTERN = re.compile(r"[\w']+", flags=re.UNICODE)
_TOKEN_SCORING_LOCATION_KINDS = frozenset({"ocr", "tag", "transcript"})
_TEXT_MATCH_LOCATION_KINDS = frozenset({"ocr", "transcript", "line", "page", "paragraph", "row", "slide"})
_VISUAL_MATCH_PREVIEW = "(visual match)"


def _pool_pending_limit(max_workers: int | None) -> int:
	import os

	workers = max_workers if max_workers is not None else min(32, (os.cpu_count() or 1) + 4)
	return max(workers * _POOL_PENDING_FACTOR, workers)


_default_text_extractor: TextExtractorPort | None = None
_default_file_walker: FileWalkerPort | None = None
_default_image_similarity: ImageSimilarityPort | None = None
_default_content_cache: ContentCachePort | None = None


def _get_text_extractor() -> TextExtractorPort:
	global _default_text_extractor
	if _default_text_extractor is None:
		from srxy.adapters.outbound.content.text_extractor import DefaultTextExtractor

		_default_text_extractor = DefaultTextExtractor()
	return _default_text_extractor


def _get_file_walker() -> FileWalkerPort:
	global _default_file_walker
	if _default_file_walker is None:
		from srxy.adapters.outbound.content.file_walker import DefaultFileWalker

		_default_file_walker = DefaultFileWalker()
	return _default_file_walker


def _get_image_similarity() -> ImageSimilarityPort:
	global _default_image_similarity
	if _default_image_similarity is None:
		from srxy.adapters.outbound.content.image_similarity import ClipImageSimilarity

		_default_image_similarity = ClipImageSimilarity()
	return _default_image_similarity


def _get_content_cache() -> ContentCachePort:
	global _default_content_cache
	if _default_content_cache is None:
		from srxy.adapters.outbound.content.content_cache import SqliteContentCache

		_default_content_cache = SqliteContentCache()
	return _default_content_cache


def set_text_extractor(extractor: TextExtractorPort | None):
	"""Override the default text extractor (tests / composition root)."""
	global _default_text_extractor
	_default_text_extractor = extractor


def set_content_ports(
	*,
	text_extractor: TextExtractorPort | None = None,
	file_walker: FileWalkerPort | None = None,
	image_similarity: ImageSimilarityPort | None = None,
	content_cache: ContentCachePort | None = None,
):
	"""Override content ports used by file search (composition root / tests)."""
	global _default_text_extractor, _default_file_walker, _default_image_similarity, _default_content_cache
	if text_extractor is not None:
		_default_text_extractor = text_extractor
	if file_walker is not None:
		_default_file_walker = file_walker
	if image_similarity is not None:
		_default_image_similarity = image_similarity
	if content_cache is not None:
		_default_content_cache = content_cache


def _snapshot_content_ports() -> tuple[
	TextExtractorPort | None,
	FileWalkerPort | None,
	ImageSimilarityPort | None,
	ContentCachePort | None,
]:
	return (
		_default_text_extractor,
		_default_file_walker,
		_default_image_similarity,
		_default_content_cache,
	)


def _restore_content_ports(
	snapshot: tuple[
		TextExtractorPort | None,
		FileWalkerPort | None,
		ImageSimilarityPort | None,
		ContentCachePort | None,
	],
):
	global _default_text_extractor, _default_file_walker, _default_image_similarity, _default_content_cache
	(
		_default_text_extractor,
		_default_file_walker,
		_default_image_similarity,
		_default_content_cache,
	) = snapshot


def content_location_kind(path: Path) -> str:
	suffix = path.suffix.lower()
	if suffix == ".pdf":
		return "page"
	if suffix == ".docx":
		return "paragraph"
	if suffix == ".xlsx":
		return "row"
	if suffix == ".pptx":
		return "slide"
	return "line"


# Thin wrappers kept for unit-test patch targets.
def encode_semantic_image_query(query: str) -> object | None:
	return _get_image_similarity().encode_query(query)


def score_image(
	query: str,
	path: Path,
	*,
	file_hash: str | None = None,
	query_embedding: object | None = None,
) -> float:
	return _get_image_similarity().score(
		query,
		path,
		file_hash=file_hash,
		query_embedding=query_embedding,
	)


def iter_searchable_lines(
	path: Path,
	max_file_size: int | None,
	*,
	search_docs_tags: bool = True,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	skipped_files: list[SkippedFile] | None = None,
	on_activity: ActivityCallback | None = None,
) -> Iterator[tuple[int, str, str]]:
	"""Compatibility wrapper — prefer TextExtractorPort.iter_units."""
	from srxy.adapters.outbound.content.line_sources import iter_searchable_lines as _iter

	yield from _iter(
		path,
		max_file_size,
		search_docs_tags=search_docs_tags,
		ocr=ocr,
		transcribe=transcribe,
		skipped_files=skipped_files,
		on_activity=on_activity,
	)


_PREVIEW_LOCATION_KINDS = frozenset({"ocr", "transcript"})


def _tag_value_text(raw_line: str) -> str:
	if raw_line.startswith("["):
		bracket_end = raw_line.find("]")
		if bracket_end >= 0:
			return raw_line[bracket_end + 1 :].strip()
	return raw_line


def _is_meaningful_token(token: str) -> bool:
	normalized = normalize_text(token)
	if len(normalized) < _MIN_SEARCHABLE_WORD_LENGTH:
		return False
	return any(char.isalpha() for char in normalized)


def _passes_semantic_word_gate(
	query: str,
	word: str,
	breakdown: dict[str, float],
	*,
	location_kind: str | None = None,
) -> bool:
	normalized_query = normalize_text(query)
	if (
		location_kind in _TOKEN_SCORING_LOCATION_KINDS
		and len(normalized_query) <= _SHORT_QUERY_PHONETIC_SKIP_LENGTH
		and breakdown.get("phonetic", 0.0) > 0.0
		and breakdown.get("exact", 0.0) <= 0.0
		and breakdown.get("contains", 0.0) <= 0.0
		and breakdown.get("partial", 0.0) <= 0.0
	):
		return False
	if breakdown.get("exact", 0.0) > 0.0 or breakdown.get("contains", 0.0) > 0.0:
		return True
	if breakdown.get("partial", 0.0) > 0.0:
		return True
	normalized_word = normalize_text(word)
	if normalized_query and normalized_query in normalized_word.split():
		return True
	if normalized_query and normalized_query in normalized_word:
		return True
	from srxy.application.matching.registry import is_matcher_available
	from srxy.domain.models import MatchType

	if not is_matcher_available(MatchType.SEMANTIC):
		return True
	return breakdown.get("semantic", 0.0) >= _SEMANTIC_WORD_MATCH_GATE


def _score_multi_word_query(matcher: CompositeMatcher, query: str, text: str) -> float:
	terms = query_words(query)
	if len(terms) < 2:
		return 0.0
	doc_tokens = [match.group() for match in _WORD_PATTERN.finditer(text) if _is_meaningful_token(match.group())]
	if not doc_tokens:
		return 0.0
	word_scores: list[float] = []
	for query_word in terms:
		best_score = 0.0
		for doc_word in doc_tokens:
			score, breakdown = matcher.score_with_breakdown(query_word, normalize_text(doc_word))
			if word_pair_match_allowed(query_word, doc_word, breakdown, allow_semantic=False):
				best_score = max(best_score, score)
		if best_score <= 0.0:
			return 0.0
		word_scores.append(best_score)
	return min(word_scores)


def _semantic_rescue_score(score: float, breakdown: dict[str, float], *, line_threshold: float) -> float:
	"""Use semantic similarity when composite score is below threshold but embedding is strong.

	OCR/transcript tokens already admit semantic-only hits via ``_passes_semantic_word_gate``,
	but their composite score is often too low to clear the file threshold. Content lines had
	the same problem: semantic weight in ``CompositeMatcher`` is only 0.20, so related terms
	(e.g. new→recents) can embed above 0.5 while composite stays near 0.25.
	"""
	from srxy.application.matching.registry import is_matcher_available
	from srxy.domain.models import MatchType

	if not is_matcher_available(MatchType.SEMANTIC):
		return score
	semantic = breakdown.get("semantic", 0.0)
	if semantic >= _SEMANTIC_WORD_MATCH_GATE and score < line_threshold:
		return max(score, semantic)
	return score


def _score_best_word(matcher: CompositeMatcher, query: str, text: str, *, location_kind: str | None = None) -> float:
	if len(query_words(query)) >= 2:
		return _score_multi_word_query(matcher, query, text)
	best_score = 0.0
	found = False
	for match in _WORD_PATTERN.finditer(text):
		word = match.group()
		if not _is_meaningful_token(word):
			continue
		score, breakdown = matcher.score_with_breakdown(query, normalize_text(word))
		if not _passes_semantic_word_gate(query, word, breakdown, location_kind=location_kind):
			continue
		found = True
		if score > best_score:
			best_score = score
	return best_score if found else 0.0


def _score_line(
	matcher: CompositeMatcher,
	query: str,
	raw_line: str,
	location_kind: str,
	*,
	line_threshold: float,
) -> float:
	searchable = _tag_value_text(raw_line) if location_kind == "tag" else raw_line
	if len(query_words(query)) >= 2:
		return _score_multi_word_query(matcher, query, searchable)
	if location_kind in _TOKEN_SCORING_LOCATION_KINDS:
		return _score_best_word(matcher, query, searchable, location_kind=location_kind)
	score, breakdown = matcher.score_with_breakdown(query, normalize_text(searchable))
	return _semantic_rescue_score(score, breakdown, line_threshold=line_threshold)


def _score_line_expr(
	matcher: CompositeMatcher,
	expr: FileQ,
	raw_line: str,
	location_kind: str,
	*,
	line_threshold: float,
) -> float:
	def score_term(term: str, _text: str) -> float:
		return _score_line(matcher, term, raw_line, location_kind, line_threshold=line_threshold)

	return score_file_query_on_text(expr, score_term, "")


def _score_name_term(matcher: CompositeMatcher, term: str, file_path: Path, root: Path) -> float:
	try:
		relative_path = file_path.relative_to(root).as_posix()
	except ValueError:
		relative_path = file_path.as_posix()
	# Match case-insensitively: query terms are already lowercased via FileQ.leaf.
	name = normalize_text(file_path.name)
	path = normalize_text(relative_path)
	if len(query_words(term)) >= 2:
		return max(
			_score_multi_word_query(matcher, term, name),
			_score_multi_word_query(matcher, term, path),
		)
	name_score = matcher.score(term, name)
	path_score = matcher.score(term, path)
	return max(name_score, path_score)


def _score_name(matcher: CompositeMatcher, expr: FileQ, file_path: Path, root: Path) -> float:
	term_scores = {term: _score_name_term(matcher, term, file_path, root) for term in iter_terms(expr)}
	return score_file_query(expr, term_scores)


def _score_lines(
	matcher: CompositeMatcher,
	expr: FileQ,
	file_path: Path,
	max_file_size: int | None,
	line_threshold: float,
	max_matches: int,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	preview_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	*,
	search_docs_tags: bool = True,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	skipped_files: list[SkippedFile] | None = None,
	on_activity: ActivityCallback | None = None,
	text_extractor: TextExtractorPort | None = None,
) -> tuple[float, list[LineMatch], LineMatch | None, dict[str, float]]:
	matches: list[LineMatch] = []
	best_near_match: LineMatch | None = None
	term_best_scores: dict[str, float] = {term: 0.0 for term in iter_terms(expr)}
	term_best_lines: dict[str, LineMatch] = {}
	bytes_read = 0
	extractor = text_extractor if text_extractor is not None else _get_text_extractor()
	content_byte_limit = extractor.effective_max_file_size(file_path, max_file_size, ocr=ocr)

	for unit in extractor.iter_units(
		file_path,
		max_file_size,
		search_docs_tags=search_docs_tags,
		ocr=ocr,
		transcribe=transcribe,
		skipped_files=skipped_files,
		on_activity=on_activity,
	):
		line_number = unit.line_number
		raw_line = unit.text
		location_kind = unit.location_kind
		if content_byte_limit is not None and location_kind not in {"tag", "ocr", "transcript"}:
			bytes_read += len(raw_line.encode("utf-8", errors="ignore"))
			if bytes_read > content_byte_limit:
				break

		line_text = normalize_text(raw_line)
		if not line_text:
			continue

		score = _score_line_expr(matcher, expr, raw_line, location_kind, line_threshold=line_threshold)
		effective_threshold = transcribe_threshold if location_kind == "transcript" else line_threshold
		line_match = LineMatch(
			line_number=line_number,
			text=raw_line,
			score=score,
			location_kind=location_kind,
		)
		for term in iter_terms(expr):
			term_score = _score_line(matcher, term, raw_line, location_kind, line_threshold=line_threshold)
			if term_score > term_best_scores[term]:
				term_best_scores[term] = term_score
				term_best_lines[term] = LineMatch(
					line_number=line_number,
					text=raw_line,
					score=term_score,
					location_kind=location_kind,
					matched_term=term,
				)

		if score >= effective_threshold:
			matches.append(line_match)
		elif (
			score >= preview_threshold
			and location_kind in _PREVIEW_LOCATION_KINDS
			and (best_near_match is None or score > best_near_match.score)
		):
			best_near_match = line_match

	terms = list(iter_terms(expr))
	if len(terms) > 1:
		for term, line_match in term_best_lines.items():
			if term_best_scores[term] < line_threshold:
				continue
			if any(
				match.line_number == line_match.line_number and match.location_kind == line_match.location_kind
				for match in matches
			):
				continue
			matches.append(line_match)

	matches.sort(key=lambda match: match.score, reverse=True)
	seen: set[tuple[int, str]] = set()
	deduped_matches: list[LineMatch] = []
	for match in matches:
		key = (match.line_number, match.location_kind)
		if key in seen:
			continue
		seen.add(key)
		deduped_matches.append(match)
	matches = deduped_matches[:max_matches]
	content_score = matches[0].score if matches else 0.0
	return content_score, matches, best_near_match, term_best_scores


def _search_single_file(
	file_path: Path,
	*,
	matcher: CompositeMatcher,
	query_expr: FileQ,
	search_root: Path,
	search_names: bool,
	search_contents: bool,
	search_docs_tags: bool,
	threshold: float,
	max_file_size: int | None,
	effective_line_threshold: float,
	max_matches: int,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	semantic_image: bool | None = None,
	query_image_embedding: object | None = None,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	on_activity: ActivityCallback | None = None,
) -> tuple[FileSearchResult | None, list[SkippedFile]]:
	"""Search a single file and return its result plus any files skipped due to size limits.

	Each call is self-contained and thread-safe: skipped files are collected into a
	local list and returned rather than mutating a shared structure.
	"""
	local_skipped: list[SkippedFile] = []
	walker = _get_file_walker()
	extractor = _get_text_extractor()
	images = _get_image_similarity()
	cache = _get_content_cache()

	if not walker.is_searchable(file_path):
		return None, local_skipped
	archive_member = walker.is_archive_member(file_path)

	breakdown: dict[str, float] = {}
	term_bests: dict[str, float] = {term: 0.0 for term in iter_terms(query_expr)}
	term_surfaces: dict[str, dict[str, float]] = {term: {} for term in iter_terms(query_expr)}
	line_matches: list[LineMatch] = []
	near_match: LineMatch | None = None

	effective_docs_tags = search_contents and search_docs_tags
	effective_ocr = ocr if search_contents else False
	effective_transcribe = transcribe if search_contents else False
	effective_semantic_image = semantic_image if search_contents else False

	if search_names:
		name_score = _score_name(matcher, query_expr, file_path, search_root)
		breakdown["name"] = name_score
		for term in iter_terms(query_expr):
			name_term_score = _score_name_term(matcher, term, file_path, search_root)
			term_surfaces[term]["name"] = name_term_score
			term_bests[term] = max(term_bests[term], name_term_score)

	needs_line_search = (
		effective_docs_tags or extractor.ocr_active(effective_ocr) or extractor.transcribe_active(effective_transcribe)
	)
	if needs_line_search:
		content_byte_limit = extractor.effective_max_file_size(file_path, max_file_size, ocr=effective_ocr)
		exceeds_size_limit = (
			effective_docs_tags
			and content_byte_limit is not None
			and not extractor.within_size_limit(file_path, content_byte_limit)
		)
		if (
			exceeds_size_limit
			and not extractor.can_search_without_reading_body(file_path)
			and not (extractor.ocr_active(effective_ocr) or extractor.transcribe_active(effective_transcribe))
		):
			local_skipped.append(SkippedFile(path=file_path, size_bytes=extractor.size_bytes(file_path)))
		else:
			content_score, line_matches, near_match, content_term_bests = _score_lines(
				matcher,
				query_expr,
				file_path,
				max_file_size,
				effective_line_threshold,
				max_matches,
				transcribe_threshold,
				semantic_image_threshold,
				search_docs_tags=effective_docs_tags,
				ocr=effective_ocr,
				transcribe=effective_transcribe,
				skipped_files=local_skipped,
				on_activity=on_activity,
				text_extractor=extractor,
			)
			breakdown["content"] = content_score
			for term, score in content_term_bests.items():
				term_surfaces[term]["content"] = score
				term_bests[term] = max(term_bests[term], score)

	semantic_image_score = 0.0
	if not archive_member and images.is_active(effective_semantic_image) and images.is_image_path(file_path):
		emit_activity(on_activity, f"CLIP · {file_path.name}")
		try:
			file_hash = cache.get_file_content_hash(file_path)
			clip_query = " ".join(iter_terms(query_expr)) or format_file_query(query_expr)
			semantic_image_score = score_image(
				clip_query,
				file_path,
				file_hash=file_hash,
				query_embedding=query_image_embedding,
			)
		finally:
			clear_activity(on_activity)
		if semantic_image_score > 0.0:
			breakdown["semantic_image"] = semantic_image_score
			for term in iter_terms(query_expr):
				term_surfaces[term]["semantic_image"] = semantic_image_score
				term_bests[term] = max(term_bests[term], semantic_image_score)

	if not breakdown:
		return None, local_skipped

	boolean_score = score_file_query(query_expr, term_bests)
	legacy_score = max(breakdown.values())
	score = boolean_score if query_is_compound(query_expr) else legacy_score
	cutoff = threshold
	semantic_score = breakdown.get("semantic_image")
	if semantic_score is not None and semantic_score >= score:
		cutoff = semantic_image_threshold
	content_score = breakdown.get("content")
	if (
		content_score is not None
		and content_score >= score
		and line_matches
		and line_matches[0].location_kind == "transcript"
	):
		cutoff = transcribe_threshold
	if score < cutoff:
		return None, local_skipped

	semantic_image_score = breakdown.get("semantic_image", 0.0)
	clip_won = semantic_image_score > 0.0 and semantic_image_score >= score - 1e-9

	if clip_won:
		line_matches = [
			LineMatch(
				line_number=1,
				text=_VISUAL_MATCH_PREVIEW,
				score=semantic_image_score,
				location_kind="semantic_image",
			)
		]
	elif not line_matches and near_match is not None:
		line_matches = [near_match]
	elif semantic_image_score > 0.0 and not any(line.location_kind == "semantic_image" for line in line_matches):
		line_matches.append(
			LineMatch(
				line_number=1,
				text=_VISUAL_MATCH_PREVIEW,
				score=semantic_image_score,
				location_kind="semantic_image",
			)
		)
		line_matches.sort(key=lambda match: match.score, reverse=True)
		line_matches = line_matches[:max_matches]
	return (
		FileSearchResult(
			path=file_path,
			score=score,
			breakdown=breakdown,
			lines=line_matches,
			term_surfaces=term_surfaces,
		),
		local_skipped,
	)


# ---------------------------------------------------------------------------
# Process-pool worker support (large text-only searches)
# ---------------------------------------------------------------------------
# These module-level objects are used by ProcessPoolExecutor workers.  They
# must live at module scope so they are importable in spawned child processes.

# Populated once per worker by _init_proc_worker(); never written after that.
_proc_worker_matcher: CompositeMatcher | None = None


def _init_proc_worker():
	"""Pool initializer: warm up one CompositeMatcher per worker process.

	Runs once at worker startup, before any tasks are dispatched.  For
	fork-based pools (Linux default) the cost is a fresh Python object
	allocation; for spawn-based pools (macOS/Windows) it also re-imports
	the matchers, which is fast for the non-semantic case.
	"""
	global _proc_worker_matcher
	_proc_worker_matcher = CompositeMatcher()


def _proc_worker_task(
	file_path: Path,
	query_expr: FileQ,
	search_root: Path,
	search_names: bool,
	search_contents: bool,
	search_docs_tags: bool,
	threshold: float,
	max_file_size: int | None,
	effective_line_threshold: float,
	max_matches: int,
	semantic_image_threshold: float,
	transcribe_threshold: float,
) -> tuple[FileSearchResult | None, list[SkippedFile]]:
	"""Task function executed inside a worker process.

	All arguments are basic Python types (or frozen dataclasses) so they
	survive both fork and spawn pickling.  ``on_activity`` is intentionally
	omitted; cross-process callbacks are not supported and the caller's
	spinner covers the wait.
	"""
	matcher = _proc_worker_matcher
	if matcher is None:
		raise RuntimeError("_init_proc_worker was not called for this worker")
	try:
		return _search_single_file(
			file_path,
			matcher=matcher,
			query_expr=query_expr,
			search_root=search_root,
			search_names=search_names,
			search_contents=search_contents,
			search_docs_tags=search_docs_tags,
			threshold=threshold,
			max_file_size=max_file_size,
			effective_line_threshold=effective_line_threshold,
			max_matches=max_matches,
			ocr=None,
			transcribe=None,
			semantic_image=None,
			semantic_image_threshold=semantic_image_threshold,
			transcribe_threshold=transcribe_threshold,
		)
	except OSError as exc:
		if is_access_denied(exc):
			return None, [permission_skip(file_path)]
		raise


def _execute_file_search(
	path: Path | str,
	query: str | FileQ,
	*,
	search_names: bool = True,
	search_contents: bool = True,
	search_docs_tags: bool = True,
	threshold: float = 0.35,
	max_file_size: int | None = None,
	max_matches: int = 50,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
	include_archives: bool = False,
	include_subdirectories: bool = True,
	skipped_files: list[SkippedFile] | None = None,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	semantic_image: bool | None = None,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	limit: int | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: ActivityCallback | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
	max_line_matches: int | None = None,
	max_workers: int | None = None,
	cancel_check: Callable[[], bool] | None = None,
	allow_process_pool: bool = False,
) -> list[FileSearchResult]:
	if max_line_matches is not None:
		warnings.warn(
			"max_line_matches is deprecated; use max_matches instead",
			DeprecationWarning,
			stacklevel=2,
		)
		max_matches = max_line_matches
	if not search_names and not search_contents:
		raise ValueError(search_source_required_message())
	extractor = _get_text_extractor()
	images = _get_image_similarity()
	cache = _get_content_cache()
	walker = _get_file_walker()
	if search_contents and not (
		search_docs_tags
		or extractor.ocr_requested(ocr)
		or extractor.transcribe_requested(transcribe)
		or images.requested(semantic_image)
	):
		raise ValueError(search_source_required_message())

	effective_ocr = ocr if search_contents else False
	effective_transcribe = transcribe if search_contents else False
	effective_semantic_image = semantic_image if search_contents else False
	effective_docs_tags = search_docs_tags if search_contents else False

	root = Path(path).expanduser().resolve()
	query_expr = coerce_file_query(query)
	if not any(iter_terms(query_expr)):
		return []
	if not root.exists():
		raise FileNotFoundError(f"Path does not exist: {root}")

	cache.reset_run_file_hashes()
	effective_line_threshold = threshold
	search_root = root if root.is_dir() else root.parent
	resolved_search_root = search_root.resolve()
	matcher = CompositeMatcher()
	results: list[FileSearchResult] = []
	query_image_embedding: object | None = None
	clip_query = " ".join(iter_terms(query_expr)) or format_file_query(query_expr)
	from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait

	from srxy.application.matching.registry import is_matcher_available
	from srxy.domain.models import MatchType
	from srxy.i18n import tr

	# Execution strategy selection (known before the walk — do not wait for a full list):
	#
	# THREAD pool — OCR / transcribe / CLIP inference
	#   Per-file work runs outside Python for extended periods (Tesseract subprocess,
	#   Whisper inference, CLIP inference), so the GIL is fully released and threads
	#   give near-linear speedup.
	#
	# PROCESS pool — large pure-text searches (no OCR / transcribe / CLIP)
	#   Text-only matching (rapidfuzz, jellyfish, exact/partial string ops) is a mix
	#   of Python bytecode and short C-extension calls.  Threads cause heavy GIL
	#   thrashing (confirmed by benchmarks: 2-5× *slower* at all thread counts).
	#   A process pool bypasses the GIL entirely; each worker gets its own
	#   CompositeMatcher pre-warmed by the pool initializer.  Semantic-text matching
	#   (SRXY_SEMANTIC=1) is excluded because loading the ~400 MB embedding model in
	#   every worker would be prohibitively slow and memory-heavy.
	#
	#   SAFETY: only enable the process pool when ``allow_process_pool`` is set.
	#   TUI and GUI searches run on a background thread and must keep this off so
	#   fork() does not race Qt (or inherit Textual raw-mode handles in the TUI).
	#   CLI callers set the flag explicitly.
	#
	#   Paths are buffered until ``_MIN_PROCESS_FILES`` (or the walk ends). Under the
	#   threshold the buffer is searched sequentially; at/above it the pool opens and
	#   further paths are submitted while listing continues.
	#
	# SEQUENTIAL — everything else (small dirs, semantic-text, background-thread callers)
	_heavy = (
		extractor.ocr_active(effective_ocr)
		or extractor.transcribe_active(effective_transcribe)
		or images.is_active(effective_semantic_image)
	)
	_semantic_text = is_matcher_available(MatchType.SEMANTIC)
	_use_threads = max_workers != 1 and _heavy
	_may_use_processes = (
		allow_process_pool and not _use_threads and max_workers != 1 and not _heavy and not _semantic_text
	)

	# Encode CLIP once up front when semantic image search is active so image hits can
	# score as soon as they are discovered (no post-list scan for image paths).
	if images.is_active(effective_semantic_image):
		emit_activity(on_activity, tr("activity.encoding_image_query"))
		try:
			query_image_embedding = encode_semantic_image_query(clip_query)
		finally:
			clear_activity(on_activity)

	def _submit_file(
		file_path: Path,
		*,
		activity: ActivityCallback | None = None,
	) -> tuple[FileSearchResult | None, list[SkippedFile]]:
		# Captures all search parameters from the enclosing scope. Each call is
		# self-contained so no shared mutable state is touched inside the worker.
		# Concurrent thread pools pass a fan-in activity callback so per-file
		# OCR/transcribe/CLIP labels still reach the UI without stomping each other.
		names_only = is_names_only_path(
			file_path,
			search_root=search_root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			resolved_search_root=resolved_search_root,
		)
		file_search_contents = search_contents and not names_only
		try:
			return _search_single_file(
				file_path,
				matcher=matcher,
				query_expr=query_expr,
				search_root=search_root,
				search_names=search_names,
				search_contents=file_search_contents,
				search_docs_tags=effective_docs_tags if file_search_contents else False,
				threshold=threshold,
				max_file_size=max_file_size,
				effective_line_threshold=effective_line_threshold,
				max_matches=max_matches,
				ocr=effective_ocr if file_search_contents else False,
				transcribe=effective_transcribe if file_search_contents else False,
				semantic_image=effective_semantic_image if file_search_contents else False,
				query_image_embedding=query_image_embedding if file_search_contents else None,
				semantic_image_threshold=semantic_image_threshold,
				transcribe_threshold=transcribe_threshold,
				on_activity=activity,
			)
		except OSError as exc:
			if is_access_denied(exc):
				return None, _skips_for_access_denied(file_path)
			raise

	def _proc_submit(
		pool: ProcessPoolExecutor, file_path: Path
	) -> Future[tuple[FileSearchResult | None, list[SkippedFile]]]:
		names_only = is_names_only_path(
			file_path,
			search_root=search_root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			resolved_search_root=resolved_search_root,
		)
		file_search_contents = search_contents and not names_only
		return pool.submit(
			_proc_worker_task,
			file_path,
			query_expr,
			search_root,
			search_names,
			file_search_contents,
			effective_docs_tags if file_search_contents else False,
			threshold,
			max_file_size,
			effective_line_threshold,
			max_matches,
			semantic_image_threshold,
			transcribe_threshold,
		)

	# Thread-pool heavy search: merge per-worker activity into one status line.
	file_activity = on_activity
	if _use_threads and on_activity is not None:
		file_activity = concurrent_activity_fan_in(on_activity)

	emit_activity(file_activity, tr("activity.searching"))
	completed = 0
	listed = 0
	listing_done = False
	cancelled = False
	pending_limit = _pool_pending_limit(max_workers)
	denied_dir_prefixes: set[Path] = set()
	denied_lock = threading.Lock()

	def _resolve_path(path: Path) -> Path:
		try:
			return path.resolve()
		except OSError:
			return path

	def _is_under_denied(path: Path) -> bool:
		resolved = _resolve_path(path)
		with denied_lock:
			prefixes = tuple(denied_dir_prefixes)
		for prefix in prefixes:
			if resolved == prefix or prefix in resolved.parents:
				return True
		return False

	def _mark_denied_dir(directory: Path):
		resolved = _resolve_path(directory)
		with denied_lock:
			denied_dir_prefixes.add(resolved)

	def _skips_for_access_denied(path: Path) -> list[SkippedFile]:
		"""Skip the path; if its parent folder is not listable, prune that tree."""
		skips = [permission_skip(path)]
		parent = path.parent
		if parent == path:
			return skips
		if directory_is_listable(parent):
			return skips
		_mark_denied_dir(parent)
		skips.append(permission_skip(parent))
		return skips

	def _note_permission_skips(file_skipped: list[SkippedFile]):
		for skipped in file_skipped:
			if skipped.reason != PERMISSION_DENIED_REASON:
				continue
			path = skipped.path
			try:
				is_dir = path.is_dir()
			except OSError:
				is_dir = False
			if is_dir:
				_mark_denied_dir(path)
			else:
				parent = path.parent
				if not directory_is_listable(parent):
					_mark_denied_dir(parent)

	def _check_cancel():
		if cancel_check is not None and cancel_check():
			raise SearchCancelled()

	def _record_outcome(result: FileSearchResult | None, file_skipped: list[SkippedFile]):
		nonlocal completed
		completed += 1
		_note_permission_skips(file_skipped)
		if skipped_files is not None:
			skipped_files.extend(file_skipped)
		if listing_done and on_progress is not None:
			on_progress(completed, listed)
		if result is None:
			return
		results.append(result)
		if on_result is not None:
			on_result(result)

	def _emit_listing_activity():
		if listed % _LISTING_ACTIVITY_INTERVAL == 0:
			emit_activity(file_activity, tr("activity.searching"), current=listed)

	def _catch_up_progress():
		# Emit as soon as the walk finishes — including 0/N — so the UI can show
		# determinate file counts while slow OCR/transcribe workers are still running.
		if on_progress is not None and listed > 0:
			on_progress(completed, listed)

	def _drain_done(
		pending: set[Future[tuple[FileSearchResult | None, list[SkippedFile]]]],
		*,
		pool: ThreadPoolExecutor | ProcessPoolExecutor | None = None,
	) -> set[Future[tuple[FileSearchResult | None, list[SkippedFile]]]]:
		if not pending:
			return pending
		_check_cancel()
		done, still_pending = wait(pending, return_when=FIRST_COMPLETED)
		for future in done:
			if cancel_check is not None and cancel_check():
				if pool is not None:
					pool.shutdown(wait=False, cancel_futures=True)
				raise SearchCancelled()
			_record_outcome(*future.result())
		return still_pending

	def _iter_listed_paths() -> Iterator[Path]:
		nonlocal listed
		for file_path in walker.iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
			cancel_check=cancel_check,
			skipped_files=skipped_files,
		):
			if _is_under_denied(file_path):
				continue
			listed += 1
			_emit_listing_activity()
			yield file_path

	try:
		if _use_threads:
			pool = ThreadPoolExecutor(max_workers=max_workers)
			pending: set[Future[tuple[FileSearchResult | None, list[SkippedFile]]]] = set()
			try:
				for file_path in _iter_listed_paths():
					_check_cancel()
					while len(pending) >= pending_limit:
						pending = _drain_done(pending, pool=pool)
					pending.add(pool.submit(_submit_file, file_path, activity=file_activity))
				listing_done = True
				_catch_up_progress()
				while pending:
					pending = _drain_done(pending, pool=pool)
			finally:
				pool.shutdown(wait=True)
		elif _may_use_processes:
			buffer: list[Path] = []
			proc_pool: ProcessPoolExecutor | None = None
			pending = set()
			try:
				for file_path in _iter_listed_paths():
					_check_cancel()
					if proc_pool is None:
						buffer.append(file_path)
						if len(buffer) >= _MIN_PROCESS_FILES:
							proc_pool = ProcessPoolExecutor(
								max_workers=max_workers,
								initializer=_init_proc_worker,
							)
							for buffered in buffer:
								while len(pending) >= pending_limit:
									pending = _drain_done(pending, pool=proc_pool)
								pending.add(_proc_submit(proc_pool, buffered))
							buffer.clear()
						continue
					while len(pending) >= pending_limit:
						pending = _drain_done(pending, pool=proc_pool)
					pending.add(_proc_submit(proc_pool, file_path))
				listing_done = True
				if proc_pool is None:
					for buffered in buffer:
						_check_cancel()
						_record_outcome(*_submit_file(buffered, activity=file_activity))
				else:
					_catch_up_progress()
					while pending:
						pending = _drain_done(pending, pool=proc_pool)
			finally:
				if proc_pool is not None:
					proc_pool.shutdown(wait=True)
		else:
			for file_path in _iter_listed_paths():
				_check_cancel()
				_record_outcome(*_submit_file(file_path, activity=file_activity))
			listing_done = True
			_catch_up_progress()
	except SearchCancelled as error:
		cancelled = True
		if error.results or error.skipped_files:
			# Preserve any results already attached by the walker cancel path.
			if error.results and not results:
				results.extend(error.results)
			if skipped_files is not None and error.skipped_files:
				skipped_files.extend(error.skipped_files)
	finally:
		# Clear the downstream callback directly so leftover fan-in slots cannot
		# leave a stale spinner after the search ends.
		clear_activity(on_activity)

	if cancelled:
		raise SearchCancelled(results=results, skipped_files=skipped_files or [])

	results.sort(key=lambda item: item.score, reverse=True)
	if limit is not None:
		results = results[:limit]
	return results


class FileSearchUseCase:
	"""Application file-search orchestration with injectable content ports."""

	def __init__(
		self,
		*,
		text_extractor: TextExtractorPort | None = None,
		file_walker: FileWalkerPort | None = None,
		image_similarity: ImageSimilarityPort | None = None,
		content_cache: ContentCachePort | None = None,
	):
		self._text_extractor = text_extractor
		self._file_walker = file_walker
		self._image_similarity = image_similarity
		self._content_cache = content_cache

	def search(
		self,
		path: Path | str,
		query: str | FileQ,
		*,
		search_names: bool = True,
		search_contents: bool = True,
		search_docs_tags: bool = True,
		threshold: float = 0.35,
		max_file_size: int | None = None,
		max_matches: int = 50,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		skip_noise_files: bool = True,
		match_skipped_names: bool = False,
		include_archives: bool = False,
		include_subdirectories: bool = True,
		skipped_files: list[SkippedFile] | None = None,
		ocr: bool | None = None,
		transcribe: bool | None = None,
		semantic_image: bool | None = None,
		semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
		transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
		limit: int | None = None,
		on_progress: Callable[[int, int], None] | None = None,
		on_activity: ActivityCallback | None = None,
		on_result: Callable[[FileSearchResult], None] | None = None,
		max_line_matches: int | None = None,
		max_workers: int | None = None,
		cancel_check: Callable[[], bool] | None = None,
		allow_process_pool: bool = False,
	) -> list[FileSearchResult]:
		previous = _snapshot_content_ports()
		if self._text_extractor is not None:
			set_text_extractor(self._text_extractor)
		set_content_ports(
			file_walker=self._file_walker,
			image_similarity=self._image_similarity,
			content_cache=self._content_cache,
		)
		try:
			return _execute_file_search(
				path,
				query,
				search_names=search_names,
				search_contents=search_contents,
				search_docs_tags=search_docs_tags,
				threshold=threshold,
				max_file_size=max_file_size,
				max_matches=max_matches,
				skip_hidden_folders=skip_hidden_folders,
				skip_noise_folders=skip_noise_folders,
				skip_noise_files=skip_noise_files,
				match_skipped_names=match_skipped_names,
				include_archives=include_archives,
				include_subdirectories=include_subdirectories,
				skipped_files=skipped_files,
				ocr=ocr,
				transcribe=transcribe,
				semantic_image=semantic_image,
				semantic_image_threshold=semantic_image_threshold,
				transcribe_threshold=transcribe_threshold,
				limit=limit,
				on_progress=on_progress,
				on_activity=on_activity,
				on_result=on_result,
				max_line_matches=max_line_matches,
				max_workers=max_workers,
				cancel_check=cancel_check,
				allow_process_pool=allow_process_pool,
			)
		finally:
			_restore_content_ports(previous)


def magic_file_search(
	path: Path | str,
	query: str | FileQ,
	*,
	search_names: bool = True,
	search_contents: bool = True,
	search_docs_tags: bool = True,
	threshold: float = 0.35,
	max_file_size: int | None = None,
	max_matches: int = 50,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
	include_archives: bool = False,
	include_subdirectories: bool = True,
	skipped_files: list[SkippedFile] | None = None,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	semantic_image: bool | None = None,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	limit: int | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: ActivityCallback | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
	max_line_matches: int | None = None,
	max_workers: int | None = None,
	cancel_check: Callable[[], bool] | None = None,
	allow_process_pool: bool = False,
) -> list[FileSearchResult]:
	"""Public library facade — builds a default ``FileSearchUseCase``."""
	return FileSearchUseCase(text_extractor=_get_text_extractor()).search(
		path,
		query,
		search_names=search_names,
		search_contents=search_contents,
		search_docs_tags=search_docs_tags,
		threshold=threshold,
		max_file_size=max_file_size,
		max_matches=max_matches,
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_folders=skip_noise_folders,
		skip_noise_files=skip_noise_files,
		match_skipped_names=match_skipped_names,
		include_archives=include_archives,
		include_subdirectories=include_subdirectories,
		skipped_files=skipped_files,
		ocr=ocr,
		transcribe=transcribe,
		semantic_image=semantic_image,
		semantic_image_threshold=semantic_image_threshold,
		transcribe_threshold=transcribe_threshold,
		limit=limit,
		on_progress=on_progress,
		on_activity=on_activity,
		on_result=on_result,
		max_line_matches=max_line_matches,
		max_workers=max_workers,
		cancel_check=cancel_check,
		allow_process_pool=allow_process_pool,
	)
