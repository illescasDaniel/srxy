from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, Select, Static

from srxy.file_query import (
	FileQ,
	FileQueryParseError,
	build_file_query_from_rows,
	format_file_query,
	parse_file_query,
)
from srxy.models import QNodeType


class QueryBuilder(Horizontal):
	"""Dynamic term rows with AND/OR joins, or Advanced raw boolean text."""

	DEFAULT_CSS = """
	QueryBuilder {
		height: auto;
		width: 1fr;
		border: solid $accent;
		padding: 0 1;
	}

	QueryBuilder #query-label {
		width: auto;
		min-width: 8;
		height: 1;
		padding: 0 1 0 0;
		content-align: right middle;
		color: $text-muted;
	}

	QueryBuilder #query-body {
		width: 1fr;
		height: auto;
	}

	QueryBuilder .query-row {
		height: auto;
		width: 1fr;
		margin-bottom: 0;
	}

	QueryBuilder .query-row Input {
		width: 1fr;
		height: 1;
		border: none;
		padding: 0 1;
	}

	QueryBuilder .query-row Select {
		width: 8;
		height: 1;
		margin-right: 1;
		border: none;
		padding: 0 1;
		color: $foreground;
		background: $surface;
	}

	QueryBuilder .query-row Button {
		width: 3;
		min-width: 3;
		height: 1;
		margin-left: 1;
	}

	QueryBuilder #query-raw-input {
		display: none;
		width: 1fr;
		height: 1;
		border: none;
		padding: 0 1;
	}

	QueryBuilder.-advanced .query-row,
	QueryBuilder.-advanced #add-term-button {
		display: none;
	}

	QueryBuilder.-advanced #query-raw-input {
		display: block;
	}

	QueryBuilder #query-preview {
		height: 1;
		color: $text-muted;
		padding: 0 1;
	}

	QueryBuilder #query-actions {
		height: auto;
		width: 1fr;
	}
	"""

	class Changed(Message):
		pass

	def __init__(self, *, initial_query: str = "", id: str | None = None):
		super().__init__(id=id)
		self._initial_query = initial_query.strip()
		self._initial_rows = _rows_from_query(self._initial_query)
		self._advanced_mode = False

	def compose(self) -> ComposeResult:
		yield Label("Query", id="query-label")
		with Vertical(id="query-body"):
			for index, (term, join) in enumerate(self._initial_rows):
				yield from self._compose_row(index, term=term, join=join or "and")
			yield Input(
				value=self._initial_query,
				placeholder="query (|, &, parentheses)",
				id="query-raw-input",
			)
			yield Static("", id="query-preview")
			with Horizontal(id="query-actions"):
				yield Button("+ Term", id="add-term-button", variant="default")
				yield Button("Advanced", id="mode-toggle-button", variant="default")

	def on_mount(self):
		self._update_preview()

	def _row_widgets(self, index: int, *, term: str = "", join: str = "and"):
		widgets = []
		if index > 0:
			widgets.append(
				Select(
					(("AND", "and"), ("OR", "or")),
					value=join,
					id=f"query-join-{index}",
					allow_blank=False,
					compact=True,
				)
			)
		widgets.append(Input(value=term, placeholder="search term", id=f"query-term-{index}"))
		if index > 0:
			widgets.append(Button("×", id=f"query-remove-{index}", variant="default"))
		return widgets

	def _compose_row(self, index: int, *, term: str = "", join: str = "and") -> ComposeResult:
		with Horizontal(classes="query-row", id=f"query-row-{index}"):
			for widget in self._row_widgets(index, term=term, join=join):
				yield widget

	def row_count(self) -> int:
		return len(self._row_indices())

	def _row_indices(self) -> list[int]:
		indices: list[int] = []
		for child in self.query(".query-row"):
			if child.id and child.id.startswith("query-row-"):
				indices.append(int(child.id.removeprefix("query-row-")))
		return sorted(indices)

	def _raw_query_value(self) -> str:
		return self.query_one("#query-raw-input", Input).value

	def _read_rows(self) -> list[tuple[str, str | None]]:
		rows: list[tuple[str, str | None]] = []
		for index in self._row_indices():
			term_input = self.query_one(f"#query-term-{index}", Input)
			term = term_input.value
			if index == 0:
				rows.append((term, None))
				continue
			join_select = self.query_one(f"#query-join-{index}", Select)
			rows.append((term, str(join_select.value)))
		return rows

	def to_file_query(self) -> FileQ:
		if self._advanced_mode:
			return parse_file_query(self._raw_query_value())
		return build_file_query_from_rows(self._read_rows())

	def to_query_string(self) -> str:
		if self._advanced_mode:
			raw = self._raw_query_value().strip()
			if not raw:
				return ""
			return format_file_query(parse_file_query(raw))
		return format_file_query(self.to_file_query())

	def has_nonempty_term(self) -> bool:
		if self._advanced_mode:
			raw = self._raw_query_value().strip()
			if not raw:
				return False
			try:
				parse_file_query(raw)
			except FileQueryParseError:
				return False
			return True
		return any(term.strip() for term, _join in self._read_rows())

	def focus_first_term(self):
		if self._advanced_mode:
			self.query_one("#query-raw-input", Input).focus()
			return
		indices = self._row_indices()
		if indices:
			self.query_one(f"#query-term-{indices[0]}", Input).focus()

	def _update_preview(self):
		preview = self.query_one("#query-preview", Static)
		if self._advanced_mode:
			raw = self._raw_query_value().strip()
			if not raw:
				preview.update("")
				return
			try:
				preview.update(format_file_query(parse_file_query(raw)))
			except FileQueryParseError as exc:
				preview.update(f"invalid: {exc}")
			return
		try:
			preview.update(self.to_query_string())
		except ValueError:
			preview.update("")

	def _post_change(self):
		self._update_preview()
		self.post_message(self.Changed())

	@on(Input.Changed, ".query-row Input")
	def _on_term_changed(self, _event: Input.Changed):
		self._post_change()

	@on(Input.Changed, "#query-raw-input")
	def _on_raw_query_changed(self, _event: Input.Changed):
		if self._advanced_mode:
			self._post_change()

	@on(Select.Changed, ".query-row Select")
	def _on_join_changed(self, _event: Select.Changed):
		self._post_change()

	@on(Button.Pressed, "#add-term-button")
	async def _on_add_term(self, _event: Button.Pressed):
		indices = self._row_indices()
		next_index = 0 if not indices else max(indices) + 1
		row = Horizontal(classes="query-row", id=f"query-row-{next_index}")
		await self.mount(row, before="#query-raw-input")
		await row.mount(*self._row_widgets(next_index, join="and"))
		self.query_one(f"#query-term-{next_index}", Input).focus()
		self._post_change()

	@on(Button.Pressed, "#mode-toggle-button")
	def _on_mode_toggle(self, _event: Button.Pressed):
		if self._advanced_mode:
			self._switch_to_builder()
		else:
			self._switch_to_advanced()

	def _switch_to_advanced(self):
		raw_input = self.query_one("#query-raw-input", Input)
		raw_input.value = format_file_query(build_file_query_from_rows(self._read_rows()))
		self._advanced_mode = True
		self.add_class("-advanced")
		self.query_one("#mode-toggle-button", Button).label = "Builder"
		raw_input.focus()
		self._post_change()

	def _switch_to_builder(self):
		raw = self._raw_query_value().strip()
		try:
			expr = parse_file_query(raw) if raw else FileQ.leaf("")
		except FileQueryParseError:
			return
		rows: list[tuple[str, str | None]] = _rows_from_expr(expr) if raw else [("", None)]
		self._set_rows(rows)
		self._advanced_mode = False
		self.remove_class("-advanced")
		self.query_one("#mode-toggle-button", Button).label = "Advanced"
		self.focus_first_term()
		self._post_change()

	def _set_rows(self, rows: list[tuple[str, str | None]]):
		current = self._row_indices()
		for index in reversed(current):
			if index >= len(rows):
				self.query_one(f"#query-row-{index}").remove()
		for index, (term, join) in enumerate(rows):
			if index not in self._row_indices():
				row = Horizontal(classes="query-row", id=f"query-row-{index}")
				self.mount(row, before="#query-raw-input")
				row.mount(*self._row_widgets(index, term=term, join=join or "and"))
				continue
			self.query_one(f"#query-term-{index}", Input).value = term
			if index > 0:
				self.query_one(f"#query-join-{index}", Select).value = join or "and"

	@on(Button.Pressed)
	def _on_remove_term(self, event: Button.Pressed):
		if event.button.id is None or not event.button.id.startswith("query-remove-"):
			return
		index = int(event.button.id.removeprefix("query-remove-"))
		if index == 0:
			return
		self.query_one(f"#query-row-{index}").remove()
		self._post_change()


def _rows_from_query(query: str) -> list[tuple[str, str | None]]:
	text = query.strip()
	if not text:
		return [("", None)]
	try:
		expr = parse_file_query(text)
	except ValueError:
		return [(text, None)]
	return _rows_from_expr(expr)


def _rows_from_expr(expr: FileQ) -> list[tuple[str, str | None]]:
	if expr.node_type == QNodeType.LEAF:
		return [(expr.value or "", None)]
	join = "and" if expr.node_type == QNodeType.AND else "or"
	if len(expr.children) == 1:
		return _rows_from_expr(expr.children[0])
	rows = _rows_from_expr(expr.children[0])
	for child in expr.children[1:]:
		child_rows = _rows_from_expr(child)
		if len(child_rows) == 1 and child_rows[0][1] is None:
			rows.append((child_rows[0][0], join))
		else:
			rows.append((format_file_query(child), join))
	return rows
