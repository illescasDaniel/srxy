from __future__ import annotations

from dataclasses import asdict, dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, ProgressBar, Select, Static, TextArea

from srxy.adapters.inbound.tui.labels import (
	binary_skip_hint,
	classic_matching_hint,
	option_hint,
	option_label,
	search_options_section_how,
	search_options_section_scan,
	search_options_section_where,
	search_options_subsection_noisy,
)
from srxy.application.labels import (
	filter_label_audio_video_size,
	filter_label_document_size,
	filter_label_hits_per_file,
	filter_label_image_text_size,
	filter_label_max_results,
	filter_label_min_match,
	filter_label_speech_min,
	filter_label_visual_min,
	filter_section_limits,
	filter_section_sensitivity,
)
from srxy.application.search_filters import SearchFilters, validate_ignore_text, validate_search_filters
from srxy.application.search_options import (
	SearchOptions,
	has_search_source,
	search_source_required_message,
)
from srxy.application.settings import ScanSwitches, scan_switches_from_options
from srxy.application.size_limits import SizeLimits
from srxy.i18n import tr


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
				yield Button(tr("tui.download"), variant="primary", id="download-yes")
				yield Button(tr("common.cancel"), id="download-no")

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
			yield Label(tr("status.preparing_download"), id="download-progress-status")

	def update_progress(self, current: int, total: int, message: str):
		progress = self.query_one("#download-progress-bar", ProgressBar)
		status = self.query_one("#download-progress-status", Label)
		if total > 0:
			progress.update(total=total, progress=min(current, total))
		else:
			progress.update(total=100, progress=0)
		status.update(message or tr("gui.downloading"))


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

	HELP_TEXT_ID = "help-text"

	def compose(self) -> ComposeResult:
		from srxy.i18n import get_language, tr

		with Vertical(id="help-dialog"):
			yield Static(tr("tui.help.text"), id=self.HELP_TEXT_ID, markup=True)
			yield Static(tr("tui.language"), id="help-language-label")
			yield Select(
				(("English", "en"), ("Español", "es")),
				value=get_language(),
				id="help-language",
				allow_blank=False,
			)
			yield Button(tr("common.close"), variant="primary", id="help-close")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "help-close":
			self.dismiss(None)

	@on(Select.Changed, "#help-language")
	def _on_language_changed(self, event: Select.Changed):
		from srxy.application.settings import set_language_setting
		from srxy.i18n import get_language, set_language, tr

		value = event.value
		if value not in {"en", "es"}:
			return
		if str(value) == get_language():
			return
		set_language(str(value))
		set_language_setting(str(value))
		self.query_one(f"#{self.HELP_TEXT_ID}", Static).update(tr("tui.help.text"))
		app = self.app
		refresh = getattr(app, "_refresh_i18n", None)
		if callable(refresh):
			refresh()


@dataclass(frozen=True, slots=True)
class FiltersModalResult:
	filters: SearchFilters
	persist: bool
	scan: ScanSwitches = ScanSwitches()


class SearchFiltersModal(ModalScreen[FiltersModalResult | None]):
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

	.search-filters-subsection {
		width: 100%;
		height: auto;
		color: $text-muted;
		text-style: bold;
		margin-top: 1;
		padding-left: 1;
	}

	.search-filters-hint {
		width: 100%;
		height: auto;
		color: $text-muted;
		padding: 0 1;
		margin-bottom: 1;
		padding-left: 2;
	}

	.search-filters-noisy-option {
		padding-left: 1;
	}

	.search-filters-noisy-hint {
		padding-left: 3;
	}

	#search-filters-scroll Checkbox {
		width: 100%;
		height: auto;
		min-height: 1;
		background: $surface;
		color: $foreground;
		border: none;
		padding: 0 1;
		content-align: left middle;
	}

	#search-filters-scroll Checkbox:focus {
		background: $accent;
		color: $button-foreground;
	}

	#search-filters-scroll Checkbox.-on {
		background: $primary;
		color: $button-foreground;
		border: none;
	}

	#search-filters-scroll Checkbox:disabled {
		color: $text-muted;
		opacity: 0.6;
	}

	#sf-ignore {
		width: 100%;
		height: 6;
		margin-bottom: 1;
	}

	#sf-ignore-error {
		width: 100%;
		height: auto;
		color: $error;
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

	_SCAN_CHECKBOXES = (
		("sf-subdirs", "so-subdirs", "include_subdirectories"),
		("sf-archives", "so-archives", "include_archives"),
		("sf-hidden", "so-hidden", "include_hidden"),
		("sf-noise", "so-noise", "include_noise"),
		("sf-noise-files", "so-noise-files", "include_noise_files"),
		("sf-match-skipped-names", "so-match-skipped-names", "match_skipped_names"),
	)

	def __init__(
		self,
		initial: SearchFilters,
		persist: bool = False,
		scan: ScanSwitches | None = None,
		*,
		search_names: bool = True,
	):
		super().__init__()
		self._initial = initial
		self._persist = persist
		self._scan = scan if scan is not None else ScanSwitches()
		self._search_names = search_names

	def _compose_scan_option(
		self, checkbox_id: str, label_id: str, field: str, *, noisy: bool = False
	) -> ComposeResult:
		classes = "search-filters-noisy-option" if noisy else ""
		yield Checkbox(option_label(label_id), id=checkbox_id, value=getattr(self._scan, field), classes=classes)
		hint = option_hint(label_id)
		if hint:
			hint_classes = "search-filters-hint"
			if noisy:
				hint_classes = f"{hint_classes} search-filters-noisy-hint"
			yield Static(hint, classes=hint_classes)

	def compose(self) -> ComposeResult:
		with Vertical(id="search-filters-dialog"):
			yield Static(tr("tui.search_filters"), id="search-filters-title")
			with VerticalScroll(id="search-filters-scroll"):
				yield Static(search_options_section_scan(), classes="search-filters-section")
				yield Label(tr("tui.filters.ignore_label"), classes="search-filters-label")
				yield TextArea(id="sf-ignore", placeholder=tr("filters.ignore.placeholder"))
				yield Label("", id="sf-ignore-error")
				yield Checkbox(tr("filters.ignore.respect_gitignore"), id="sf-respect-gitignore")
				for checkbox_id, label_id, field in self._SCAN_CHECKBOXES[:2]:
					yield from self._compose_scan_option(checkbox_id, label_id, field)
				yield Static(search_options_subsection_noisy(), classes="search-filters-subsection")
				for checkbox_id, label_id, field in self._SCAN_CHECKBOXES[2:]:
					yield from self._compose_scan_option(checkbox_id, label_id, field, noisy=True)
				yield Static(binary_skip_hint(), classes="search-filters-hint")
				yield Static(filter_section_limits(), classes="search-filters-section")
				yield Label(filter_label_max_results(), classes="search-filters-label")
				yield Input(
					id="sf-top-files",
					classes="search-filters-input",
					placeholder="all",
					compact=True,
				)
				yield Label(filter_label_hits_per_file(), classes="search-filters-label")
				yield Input(id="sf-max-matches", classes="search-filters-input", compact=True)
				yield Label(filter_label_document_size(), classes="search-filters-label")
				yield Input(id="sf-size-text", classes="search-filters-input", compact=True)
				yield Label(filter_label_image_text_size(), classes="search-filters-label")
				yield Input(id="sf-size-ocr", classes="search-filters-input", compact=True)
				yield Label(filter_label_audio_video_size(), classes="search-filters-label")
				yield Input(id="sf-size-transcribe", classes="search-filters-input", compact=True)
				yield Static(filter_section_sensitivity(), classes="search-filters-section")
				yield Label(filter_label_min_match(), classes="search-filters-label")
				yield Input(id="sf-threshold", classes="search-filters-input", compact=True)
				yield Label(filter_label_visual_min(), classes="search-filters-label")
				yield Input(id="sf-semantic-image-threshold", classes="search-filters-input", compact=True)
				yield Label(filter_label_speech_min(), classes="search-filters-label")
				yield Input(id="sf-transcribe-threshold", classes="search-filters-input", compact=True)
				yield Checkbox(tr("tui.filters.persist"), id="sf-persist")
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
		self.query_one("#sf-ignore", TextArea).text = self._initial.ignore_patterns
		self.query_one("#sf-respect-gitignore", Checkbox).value = self._initial.respect_gitignore
		self.query_one("#sf-persist", Checkbox).value = self._persist
		self.query_one("#sf-match-skipped-names", Checkbox).disabled = not self._search_names

	def _current_scan(self) -> ScanSwitches:
		return ScanSwitches(
			**{
				field: self.query_one(f"#{checkbox_id}", Checkbox).value
				for checkbox_id, _l, field in self._SCAN_CHECKBOXES
			}
		)

	@on(TextArea.Changed, "#sf-ignore")
	def _on_ignore_changed(self, event: TextArea.Changed):
		message = validate_ignore_text(event.text_area.text)
		self.query_one("#sf-ignore-error", Label).update(message)
		self.query_one("#search-filters-apply", Button).disabled = bool(message)

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
			ignore_patterns=self.query_one("#sf-ignore", TextArea).text,
			respect_gitignore=self.query_one("#sf-respect-gitignore", Checkbox).value,
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
		self.dismiss(FiltersModalResult(filters, self.query_one("#sf-persist", Checkbox).value, self._current_scan()))


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
			yield Static(tr("tui.search_options"), id="search-options-title")
			with VerticalScroll(id="search-options-scroll"):
				yield Static(search_options_section_where(), classes="search-options-section")
				yield from self._compose_option("so-names", value=self._initial.search_names)
				yield from self._compose_option("so-folders", value=self._initial.search_folders)
				yield from self._compose_option("so-content", value=self._initial.search_contents)
				yield Static(search_options_section_how(), classes="search-options-section")
				yield Static(classic_matching_hint(), classes="search-options-hint")
				yield from self._compose_option("so-docs-tags", value=self._initial.search_docs_tags)
				yield from self._compose_option("so-semantic", value=self._initial.semantic)
				yield from self._compose_option("so-ocr", value=self._initial.ocr)
				yield from self._compose_option("so-transcribe", value=self._initial.transcribe)
				yield from self._compose_option("so-semantic-image", value=self._initial.semantic_image)
				yield from self._compose_option("so-enable-all", value=all_powerups)
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

	def _scan_kwargs(self) -> dict[str, bool]:
		# The scan switches are edited in the Filters modal; pass them through untouched.
		return dict(asdict(scan_switches_from_options(self._initial)))

	def _current_options(self) -> SearchOptions:
		semantic, ocr, transcribe, semantic_image = self._powerup_values()
		return SearchOptions(
			search_names=self.query_one("#so-names", Checkbox).value,
			search_folders=self.query_one("#so-folders", Checkbox).value,
			search_contents=self._content_enabled(),
			search_docs_tags=self.query_one("#so-docs-tags", Checkbox).value,
			semantic=semantic,
			semantic_image=semantic_image,
			ocr=ocr,
			transcribe=transcribe,
			**self._scan_kwargs(),
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
			error.update(search_source_required_message())
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
			yield Button(tr("common.close"), variant="primary", id="error-close")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "error-close":
			self.dismiss(None)
