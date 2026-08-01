from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, ProgressBar, Static

from srxy.adapters.inbound.tui.labels import (
	CLASSIC_MATCHING_HINT,
	FILTER_LABEL_AUDIO_VIDEO_SIZE,
	FILTER_LABEL_DOCUMENT_SIZE,
	FILTER_LABEL_HITS_PER_FILE,
	FILTER_LABEL_IMAGE_TEXT_SIZE,
	FILTER_LABEL_MAX_RESULTS,
	FILTER_LABEL_MIN_MATCH,
	FILTER_LABEL_SPEECH_MIN,
	FILTER_LABEL_VISUAL_MIN,
	FILTER_SECTION_LIMITS,
	FILTER_SECTION_SENSITIVITY,
	SEARCH_OPTIONS_SECTION_HOW,
	SEARCH_OPTIONS_SECTION_SCAN,
	SEARCH_OPTIONS_SECTION_WHERE,
	option_hint,
	option_label,
)
from srxy.application.search_filters import SearchFilters, validate_search_filters
from srxy.application.search_options import (
	SEARCH_SOURCE_REQUIRED_MESSAGE,
	SearchOptions,
	has_search_source,
)
from srxy.application.size_limits import SizeLimits


class DownloadConfirmModal(ModalScreen[bool]):
	DEFAULT_CSS = """
	DownloadConfirmModal {
		align: center middle;
	}

	#download-dialog {
		width: 72;
		height: auto;
		max-height: 80%;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}

	#download-prompt {
		width: 100%;
		height: auto;
		margin-bottom: 1;
	}

	#download-buttons {
		grid-size: 2;
		grid-gutter: 1 2;
		width: 100%;
		height: auto;
	}
	"""

	def __init__(self, prompt: str):
		super().__init__()
		self._prompt = prompt

	def compose(self) -> ComposeResult:
		with Vertical(id="download-dialog"):
			yield Static(self._prompt, id="download-prompt")
			with Grid(id="download-buttons"):
				yield Button("Download", variant="primary", id="download-yes")
				yield Button("Cancel", id="download-no")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "download-yes":
			self.dismiss(True)
		else:
			self.dismiss(False)


class DownloadProgressModal(ModalScreen[None]):
	DEFAULT_CSS = """
	DownloadProgressModal {
		align: center middle;
	}

	#download-progress-dialog {
		width: 72;
		height: auto;
		max-height: 80%;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}

	#download-progress-title {
		width: 100%;
		height: auto;
		margin-bottom: 1;
	}

	#download-progress-bar {
		width: 100%;
		height: 1;
		margin-bottom: 1;
	}

	#download-progress-status {
		width: 100%;
		height: auto;
		color: $text-muted;
	}
	"""

	def __init__(self, label: str):
		super().__init__()
		self._label = label

	def compose(self) -> ComposeResult:
		with Vertical(id="download-progress-dialog"):
			yield Static(self._label, id="download-progress-title")
			yield ProgressBar(total=100, show_eta=False, id="download-progress-bar")
			yield Label("Preparing download…", id="download-progress-status")

	def update_progress(self, current: int, total: int, message: str):
		progress = self.query_one("#download-progress-bar", ProgressBar)
		status = self.query_one("#download-progress-status", Label)
		if total > 0:
			progress.update(total=total, progress=min(current, total))
		else:
			progress.update(total=100, progress=0)
		status.update(message or "Downloading…")


class HelpModal(ModalScreen[None]):
	DEFAULT_CSS = """
	HelpModal {
		align: center middle;
	}

	#help-dialog {
		width: 64;
		height: auto;
		max-height: 80%;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}
	"""

	HELP_TEXT = """\
[bold]Srxy TUI[/]

[b]Search[/b]
  Enter / Ctrl+S   Run search
  /              Focus query input
  Orange Search  Settings changed since last run — search again

[b]Filters[/b]
  Filters            Result limits, file size caps, and match sensitivity
  Search options     Where to search, how to match, which files to scan

[b]Results[/b]
  j / k          Move selection
  o              Open selected file
  y              Copy selected file path
  m              Copy focused preview match
  M              Copy all preview matches
  Scores         Shown as match percentages (e.g. 86%)

[b]General[/b]
  ?              Show this help
  q / Ctrl+C     Quit
"""

	def compose(self) -> ComposeResult:
		with Vertical(id="help-dialog"):
			yield Static(self.HELP_TEXT, markup=True)
			yield Button("Close", variant="primary", id="help-close")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "help-close":
			self.dismiss(None)


class SearchFiltersModal(ModalScreen[SearchFilters | None]):
	DEFAULT_CSS = """
	SearchFiltersModal {
		align: center middle;
	}

	#search-filters-dialog {
		width: 60;
		height: auto;
		max-height: 80%;
		overflow: hidden;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}

	#search-filters-title {
		width: 100%;
		height: auto;
		margin-bottom: 1;
	}

	#search-filters-scroll {
		width: 100%;
		height: 1fr;
		min-height: 1;
		margin-bottom: 1;
	}

	.search-filters-section {
		width: 100%;
		height: auto;
		color: $text-muted;
		text-style: bold;
		margin-top: 1;
	}

	.search-filters-label {
		width: 100%;
		height: auto;
		color: $text-muted;
		margin-top: 1;
	}

	.search-filters-input {
		width: 100%;
		margin-bottom: 1;
		padding: 0 1;
		color: $foreground;
		background: $background;
	}

	#search-filters-error {
		width: 100%;
		height: auto;
		color: $error;
		margin-bottom: 1;
	}

	#search-filters-buttons {
		grid-size: 2;
		grid-gutter: 1 2;
		width: 100%;
		height: 1;
	}

	#search-filters-buttons Button {
		height: 1;
		min-width: 10;
		border: none;
		padding: 0 1;
		content-align: center middle;
		background: $surface;
		color: $foreground;
	}

	#search-filters-buttons Button.-primary {
		background: $primary;
		color: $button-foreground;
	}
	"""

	def __init__(self, initial: SearchFilters):
		super().__init__()
		self._initial = initial

	def compose(self) -> ComposeResult:
		with Vertical(id="search-filters-dialog"):
			yield Static("Search filters", id="search-filters-title")
			with VerticalScroll(id="search-filters-scroll"):
				yield Static(FILTER_SECTION_LIMITS, classes="search-filters-section")
				yield Label(FILTER_LABEL_MAX_RESULTS, classes="search-filters-label")
				yield Input(
					id="sf-top-files",
					classes="search-filters-input",
					placeholder="all",
					compact=True,
				)
				yield Label(FILTER_LABEL_HITS_PER_FILE, classes="search-filters-label")
				yield Input(id="sf-max-matches", classes="search-filters-input", compact=True)
				yield Label(FILTER_LABEL_DOCUMENT_SIZE, classes="search-filters-label")
				yield Input(id="sf-size-text", classes="search-filters-input", compact=True)
				yield Label(FILTER_LABEL_IMAGE_TEXT_SIZE, classes="search-filters-label")
				yield Input(id="sf-size-ocr", classes="search-filters-input", compact=True)
				yield Label(FILTER_LABEL_AUDIO_VIDEO_SIZE, classes="search-filters-label")
				yield Input(id="sf-size-transcribe", classes="search-filters-input", compact=True)
				yield Static(FILTER_SECTION_SENSITIVITY, classes="search-filters-section")
				yield Label(FILTER_LABEL_MIN_MATCH, classes="search-filters-label")
				yield Input(id="sf-threshold", classes="search-filters-input", compact=True)
				yield Label(FILTER_LABEL_VISUAL_MIN, classes="search-filters-label")
				yield Input(id="sf-semantic-image-threshold", classes="search-filters-input", compact=True)
				yield Label(FILTER_LABEL_SPEECH_MIN, classes="search-filters-label")
				yield Input(id="sf-transcribe-threshold", classes="search-filters-input", compact=True)
			yield Label("", id="search-filters-error")
			with Grid(id="search-filters-buttons"):
				yield Button("Cancel", id="search-filters-cancel")
				yield Button("Apply", variant="primary", id="search-filters-apply")

	def on_mount(self):
		self.query_one("#sf-top-files", Input).value = self._initial.top_files
		self.query_one("#sf-max-matches", Input).value = self._initial.max_matches
		self.query_one("#sf-size-text", Input).value = self._initial.size_limits.text_mib
		self.query_one("#sf-size-ocr", Input).value = self._initial.size_limits.ocr_mib
		self.query_one("#sf-size-transcribe", Input).value = self._initial.size_limits.transcribe_mib
		self.query_one("#sf-threshold", Input).value = self._initial.threshold
		self.query_one("#sf-semantic-image-threshold", Input).value = self._initial.semantic_image_threshold
		self.query_one("#sf-transcribe-threshold", Input).value = self._initial.transcribe_threshold

	def _current_filters(self) -> SearchFilters:
		return SearchFilters(
			top_files=self.query_one("#sf-top-files", Input).value,
			max_matches=self.query_one("#sf-max-matches", Input).value,
			size_limits=SizeLimits(
				text_mib=self.query_one("#sf-size-text", Input).value,
				ocr_mib=self.query_one("#sf-size-ocr", Input).value,
				transcribe_mib=self.query_one("#sf-size-transcribe", Input).value,
			),
			threshold=self.query_one("#sf-threshold", Input).value,
			semantic_image_threshold=self.query_one("#sf-semantic-image-threshold", Input).value,
			transcribe_threshold=self.query_one("#sf-transcribe-threshold", Input).value,
		)

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "search-filters-cancel":
			self.dismiss(None)
			return
		if event.button.id != "search-filters-apply":
			return
		error = self.query_one("#search-filters-error", Label)
		filters = self._current_filters()
		try:
			validate_search_filters(filters)
		except ValueError as exc:
			error.update(str(exc))
			return
		error.update("")
		self.dismiss(filters)


class SearchOptionsModal(ModalScreen[SearchOptions | None]):
	DEFAULT_CSS = """
	SearchOptionsModal {
		align: center middle;
	}

	#search-options-dialog {
		width: 64;
		height: auto;
		max-height: 80%;
		overflow: hidden;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}

	#search-options-title {
		width: 100%;
		height: auto;
		margin-bottom: 1;
	}

	#search-options-scroll {
		width: 100%;
		height: 1fr;
		min-height: 1;
		margin-bottom: 1;
	}

	.search-options-section {
		width: 100%;
		height: auto;
		color: $text-muted;
		text-style: bold;
		margin-top: 1;
	}

	.search-options-hint {
		width: 100%;
		height: auto;
		color: $text-muted;
		padding: 0 1;
		margin-bottom: 1;
	}

	.search-options-option-hint {
		margin-top: 0;
		margin-bottom: 1;
		padding-left: 2;
	}

	#search-options-scroll Checkbox {
		width: 100%;
		height: auto;
		min-height: 1;
		background: $surface;
		color: $foreground;
		border: none;
		padding: 0 1;
		content-align: left middle;
	}

	#search-options-scroll Checkbox:focus {
		background: $accent;
		color: $button-foreground;
	}

	#search-options-scroll Checkbox.-on {
		background: $primary;
		color: $button-foreground;
		border: none;
	}

	#search-options-scroll Checkbox:disabled {
		color: $text-muted;
		opacity: 0.6;
	}

	#search-options-error {
		width: 100%;
		height: auto;
		color: $error;
		margin-bottom: 1;
	}

	#search-options-buttons {
		grid-size: 2;
		grid-gutter: 1 2;
		width: 100%;
		height: 1;
	}

	#search-options-buttons Button {
		height: 1;
		min-width: 10;
		border: none;
		padding: 0 1;
		content-align: center middle;
		background: $surface;
		color: $foreground;
	}

	#search-options-buttons Button.-primary {
		background: $primary;
		color: $button-foreground;
	}
	"""

	_CONTENT_DEPENDENT_IDS = ("so-docs-tags", "so-ocr", "so-transcribe", "so-semantic-image")

	def __init__(self, initial: SearchOptions):
		super().__init__()
		self._initial = initial
		self._syncing_checkboxes = False

	def _compose_option(self, checkbox_id: str, *, value: bool) -> ComposeResult:
		yield Checkbox(option_label(checkbox_id), id=checkbox_id, value=value)
		hint = option_hint(checkbox_id)
		if hint:
			yield Static(hint, classes="search-options-hint search-options-option-hint")

	def compose(self) -> ComposeResult:
		all_powerups = (
			self._initial.semantic and self._initial.ocr and self._initial.transcribe and self._initial.semantic_image
		)
		with Vertical(id="search-options-dialog"):
			yield Static("Search options", id="search-options-title")
			with VerticalScroll(id="search-options-scroll"):
				yield Static(SEARCH_OPTIONS_SECTION_WHERE, classes="search-options-section")
				yield from self._compose_option("so-names", value=self._initial.search_names)
				yield from self._compose_option("so-content", value=self._initial.search_contents)
				yield Static(SEARCH_OPTIONS_SECTION_HOW, classes="search-options-section")
				yield Static(CLASSIC_MATCHING_HINT, classes="search-options-hint")
				yield from self._compose_option("so-docs-tags", value=self._initial.search_docs_tags)
				yield from self._compose_option("so-semantic", value=self._initial.semantic)
				yield from self._compose_option("so-ocr", value=self._initial.ocr)
				yield from self._compose_option("so-transcribe", value=self._initial.transcribe)
				yield from self._compose_option("so-semantic-image", value=self._initial.semantic_image)
				yield from self._compose_option("so-enable-all", value=all_powerups)
				yield Static(SEARCH_OPTIONS_SECTION_SCAN, classes="search-options-section")
				yield from self._compose_option("so-subdirs", value=self._initial.include_subdirectories)
				yield from self._compose_option("so-hidden", value=self._initial.include_hidden)
				yield from self._compose_option("so-noise", value=self._initial.include_noise)
				yield from self._compose_option("so-archives", value=self._initial.include_archives)
			yield Label("", id="search-options-error")
			with Grid(id="search-options-buttons"):
				yield Button("Cancel", id="search-options-cancel")
				yield Button("Apply", variant="primary", id="search-options-apply")

	def on_mount(self):
		self._sync_content_dependent_controls()

	def _content_enabled(self) -> bool:
		return self.query_one("#so-content", Checkbox).value

	def _powerup_values(self) -> tuple[bool, bool, bool, bool]:
		return (
			self.query_one("#so-semantic", Checkbox).value,
			self.query_one("#so-ocr", Checkbox).value,
			self.query_one("#so-transcribe", Checkbox).value,
			self.query_one("#so-semantic-image", Checkbox).value,
		)

	def _all_powerups_enabled(self) -> bool:
		return all(self._powerup_values())

	def _set_checkbox_value(self, checkbox_id: str, value: bool):
		checkbox = self.query_one(f"#{checkbox_id}", Checkbox)
		if checkbox.value != value:
			checkbox.value = value

	def _set_powerups(self, *, semantic: bool, ocr: bool, transcribe: bool, semantic_image: bool):
		self._syncing_checkboxes = True
		try:
			self._set_checkbox_value("so-semantic", semantic)
			self._set_checkbox_value("so-ocr", ocr)
			self._set_checkbox_value("so-transcribe", transcribe)
			self._set_checkbox_value("so-semantic-image", semantic_image)
			self._set_checkbox_value("so-enable-all", semantic and ocr and transcribe and semantic_image)
		finally:
			self._syncing_checkboxes = False

	def _sync_enable_all_from_powerups(self):
		if self._syncing_checkboxes:
			return
		self._syncing_checkboxes = True
		try:
			self._set_checkbox_value("so-enable-all", self._all_powerups_enabled())
		finally:
			self._syncing_checkboxes = False

	def _sync_content_dependent_controls(self):
		content_enabled = self._content_enabled()
		for checkbox_id in self._CONTENT_DEPENDENT_IDS:
			checkbox = self.query_one(f"#{checkbox_id}", Checkbox)
			checkbox.disabled = not content_enabled
		self._sync_enable_all_from_powerups()

	def _current_options(self) -> SearchOptions:
		semantic, ocr, transcribe, semantic_image = self._powerup_values()
		return SearchOptions(
			search_names=self.query_one("#so-names", Checkbox).value,
			search_contents=self._content_enabled(),
			search_docs_tags=self.query_one("#so-docs-tags", Checkbox).value,
			semantic=semantic,
			semantic_image=semantic_image,
			ocr=ocr,
			transcribe=transcribe,
			include_hidden=self.query_one("#so-hidden", Checkbox).value,
			include_noise=self.query_one("#so-noise", Checkbox).value,
			include_archives=self.query_one("#so-archives", Checkbox).value,
			include_subdirectories=self.query_one("#so-subdirs", Checkbox).value,
		)

	@on(Checkbox.Changed, "#so-content")
	def _on_content_changed(self):
		self._sync_content_dependent_controls()

	@on(Checkbox.Changed, "#so-enable-all")
	def _on_enable_all_changed(self, event: Checkbox.Changed):
		if self._syncing_checkboxes:
			return
		self._set_powerups(
			semantic=event.value,
			ocr=event.value,
			transcribe=event.value,
			semantic_image=event.value,
		)

	@on(Checkbox.Changed, "#so-semantic")
	@on(Checkbox.Changed, "#so-ocr")
	@on(Checkbox.Changed, "#so-transcribe")
	@on(Checkbox.Changed, "#so-semantic-image")
	def _on_powerup_changed(self):
		if self._syncing_checkboxes:
			return
		self._sync_enable_all_from_powerups()

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "search-options-cancel":
			self.dismiss(None)
			return
		if event.button.id != "search-options-apply":
			return
		error = self.query_one("#search-options-error", Label)
		options = self._current_options()
		if not has_search_source(options):
			error.update(SEARCH_SOURCE_REQUIRED_MESSAGE)
			return
		error.update("")
		self.dismiss(options)


class ErrorModal(ModalScreen[None]):
	DEFAULT_CSS = """
	ErrorModal {
		align: center middle;
	}

	#error-dialog {
		width: 72;
		height: auto;
		max-height: 80%;
		border: thick $error;
		background: $surface;
		padding: 1 2;
	}

	#error-message {
		width: 100%;
		height: auto;
		margin-bottom: 1;
		color: $error;
	}
	"""

	def __init__(self, message: str):
		super().__init__()
		self._message = message

	def compose(self) -> ComposeResult:
		with Vertical(id="error-dialog"):
			# Plain text: Rich markup would swallow pip extras like [semantic].
			yield Label(self._message, id="error-message", markup=False)
			yield Button("Close", variant="primary", id="error-close")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "error-close":
			self.dismiss(None)
