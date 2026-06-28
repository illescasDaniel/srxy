from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Select, Static

from srxy.file_query import FileQ, build_file_query_from_rows, format_file_query, parse_file_query
from srxy.models import QNodeType


class QueryBuilder(Vertical):
	"""Dynamic term rows with AND/OR joins between consecutive terms."""

	DEFAULT_CSS = """
	QueryBuilder {
		height: auto;
		width: 1fr;
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
	}

	QueryBuilder .query-row Button {
		width: 3;
		min-width: 3;
		height: 1;
		margin-left: 1;
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
		self._initial_rows = _rows_from_query(initial_query)

	def compose(self) -> ComposeResult:
		for index, (term, join) in enumerate(self._initial_rows):
			yield from self._compose_row(index, term=term, join=join or "and")
		with Horizontal(id="query-actions"):
			yield Button("+ Term", id="add-term-button", variant="default")
		yield Static("", id="query-preview")

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
		return build_file_query_from_rows(self._read_rows())

	def to_query_string(self) -> str:
		return format_file_query(self.to_file_query())

	def has_nonempty_term(self) -> bool:
		return any(term.strip() for term, _join in self._read_rows())

	def focus_first_term(self):
		indices = self._row_indices()
		if indices:
			self.query_one(f"#query-term-{indices[0]}", Input).focus()

	def _update_preview(self):
		preview = self.query_one("#query-preview", Static)
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

	@on(Select.Changed, ".query-row Select")
	def _on_join_changed(self, _event: Select.Changed):
		self._post_change()

	@on(Button.Pressed, "#add-term-button")
	async def _on_add_term(self, _event: Button.Pressed):
		indices = self._row_indices()
		next_index = 0 if not indices else max(indices) + 1
		row = Horizontal(classes="query-row", id=f"query-row-{next_index}")
		await self.mount(row, before="#query-actions")
		await row.mount(*self._row_widgets(next_index, join="and"))
		self.query_one(f"#query-term-{next_index}", Input).focus()
		self._post_change()

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
