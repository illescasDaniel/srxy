from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, ProgressBar, Static

from srxy.tui.search_options import SearchOptions
from srxy.tui.size_limits import SizeLimits, validate_size_limits


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
  Top files          Max matched files (empty = all)
  Per file           Max matches per file (lines, OCR, transcript, …)
  Size limits        Max file sizes for text, OCR, and transcribe (MiB)
  Advanced           Search modes (names, content, semantic, archives, …)

[b]Results[/b]
  j / k          Move selection
  o              Open selected file
  y              Copy selected file path
  m              Copy focused preview match
  M              Copy all preview matches
  Path/Match/All Bottom-right copy buttons
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


class SizeLimitsModal(ModalScreen[SizeLimits | None]):
	DEFAULT_CSS = """
	SizeLimitsModal {
		align: center middle;
	}

	#size-limits-dialog {
		width: 56;
		height: auto;
		max-height: 80%;
		border: thick $accent;
		background: $surface;
		padding: 1 2;
	}

	#size-limits-title {
		width: 100%;
		height: auto;
		margin-bottom: 1;
	}

	.size-limits-label {
		width: 100%;
		height: auto;
		color: $text-muted;
		margin-top: 1;
	}

	.size-limits-input {
		width: 100%;
		height: 1;
		margin-bottom: 1;
		border: none;
		padding: 0 1;
		background: $background;
	}

	#size-limits-error {
		width: 100%;
		height: auto;
		color: $error;
		margin-bottom: 1;
	}

	#size-limits-buttons {
		grid-size: 2;
		grid-gutter: 1 2;
		width: 100%;
		height: auto;
		margin-top: 1;
	}
	"""

	def __init__(self, initial: SizeLimits):
		super().__init__()
		self._initial = initial

	def compose(self) -> ComposeResult:
		with Vertical(id="size-limits-dialog"):
			yield Static("File size limits (MiB)", id="size-limits-title")
			yield Label("Text & documents (0 = unlimited)", classes="size-limits-label")
			yield Input(id="size-limit-text", classes="size-limits-input")
			yield Label("OCR", classes="size-limits-label")
			yield Input(id="size-limit-ocr", classes="size-limits-input")
			yield Label("Transcribe", classes="size-limits-label")
			yield Input(id="size-limit-transcribe", classes="size-limits-input")
			yield Label("", id="size-limits-error")
			with Grid(id="size-limits-buttons"):
				yield Button("Apply", variant="primary", id="size-limits-apply")
				yield Button("Cancel", id="size-limits-cancel")

	def on_mount(self):
		self.query_one("#size-limit-text", Input).value = self._initial.text_mib
		self.query_one("#size-limit-ocr", Input).value = self._initial.ocr_mib
		self.query_one("#size-limit-transcribe", Input).value = self._initial.transcribe_mib

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "size-limits-cancel":
			self.dismiss(None)
			return
		if event.button.id != "size-limits-apply":
			return
		error = self.query_one("#size-limits-error", Label)
		limits = SizeLimits(
			text_mib=self.query_one("#size-limit-text", Input).value,
			ocr_mib=self.query_one("#size-limit-ocr", Input).value,
			transcribe_mib=self.query_one("#size-limit-transcribe", Input).value,
		)
		try:
			validate_size_limits(limits)
		except ValueError as exc:
			error.update(str(exc))
			return
		error.update("")
		self.dismiss(limits)


class SearchOptionsModal(ModalScreen[SearchOptions | None]):
	DEFAULT_CSS = """
	SearchOptionsModal {
		align: center middle;
	}

	#search-options-dialog {
		width: 48;
		height: auto;
		max-height: 80%;
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
		height: auto;
		max-height: 18;
		margin-bottom: 1;
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

	#search-options-buttons {
		grid-size: 2;
		grid-gutter: 1 2;
		width: 100%;
		height: auto;
	}
	"""

	def __init__(self, initial: SearchOptions):
		super().__init__()
		self._initial = initial

	def compose(self) -> ComposeResult:
		with Vertical(id="search-options-dialog"):
			yield Static("Search options", id="search-options-title")
			with VerticalScroll(id="search-options-scroll"):
				yield Checkbox("Names", id="so-names", value=self._initial.search_names)
				yield Checkbox("Content", id="so-content", value=self._initial.search_contents)
				yield Checkbox("Semantic", id="so-semantic", value=self._initial.semantic)
				yield Checkbox("Image semantic", id="so-semantic-image", value=self._initial.semantic_image)
				yield Checkbox("OCR", id="so-ocr", value=self._initial.ocr)
				yield Checkbox("Transcribe", id="so-transcribe", value=self._initial.transcribe)
				yield Checkbox("Hidden", id="so-hidden", value=self._initial.include_hidden)
				yield Checkbox("Noise", id="so-noise", value=self._initial.include_noise)
				yield Checkbox("Archives", id="so-archives", value=self._initial.include_archives)
			with Grid(id="search-options-buttons"):
				yield Button("Apply", variant="primary", id="search-options-apply")
				yield Button("Cancel", id="search-options-cancel")

	def _current_options(self) -> SearchOptions:
		return SearchOptions(
			search_names=self.query_one("#so-names", Checkbox).value,
			search_contents=self.query_one("#so-content", Checkbox).value,
			semantic=self.query_one("#so-semantic", Checkbox).value,
			semantic_image=self.query_one("#so-semantic-image", Checkbox).value,
			ocr=self.query_one("#so-ocr", Checkbox).value,
			transcribe=self.query_one("#so-transcribe", Checkbox).value,
			include_hidden=self.query_one("#so-hidden", Checkbox).value,
			include_noise=self.query_one("#so-noise", Checkbox).value,
			include_archives=self.query_one("#so-archives", Checkbox).value,
		)

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "search-options-cancel":
			self.dismiss(None)
			return
		if event.button.id == "search-options-apply":
			self.dismiss(self._current_options())


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
			yield Label(self._message, id="error-message")
			yield Button("Close", variant="primary", id="error-close")

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "error-close":
			self.dismiss(None)
