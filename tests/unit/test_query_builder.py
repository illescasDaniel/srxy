from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import normalized_svg_text
from textual.app import App, ComposeResult
from textual.css.query import NoMatches

from srxy.file_query import FileQ, build_file_query_from_rows
from srxy.tui.query_builder import QueryBuilder


pytestmark = pytest.mark.unit


class _QueryBuilderApp(App[None]):
	def __init__(self, *, initial_query: str = ""):
		super().__init__()
		self._initial_query = initial_query

	def compose(self) -> ComposeResult:
		yield QueryBuilder(id="query-builder", initial_query=self._initial_query)

	def builder(self) -> QueryBuilder:
		return self.query_one("#query-builder", QueryBuilder)


def test_given_joined_rows_when_building_file_query_then_left_associates():
	# given
	rows: list[tuple[str, str | None]] = [("foo", None), ("bar", "and"), ("baz", "or")]

	# when
	expr = build_file_query_from_rows(rows)

	# then
	assert expr == (FileQ.leaf("foo") & FileQ.leaf("bar")) | FileQ.leaf("baz")


def test_given_query_builder_when_clicking_add_term_then_mounts_second_row():
	# given
	app = _QueryBuilderApp()

	async def run():
		async with app.run_test() as pilot:
			await pilot.pause()
			builder = app.builder()
			assert builder.row_count() == 1

			# when
			await pilot.click("#add-term-button")
			await pilot.pause()

			# then
			assert builder.row_count() == 2
			builder.query_one("#query-join-1")
			builder.query_one("#query-term-1")
			builder.query_one("#query-remove-1")

	asyncio.run(run())


def test_given_two_terms_when_removing_second_row_then_keeps_first_row():
	# given
	app = _QueryBuilderApp()

	async def run():
		async with app.run_test() as pilot:
			await pilot.pause()
			builder = app.builder()
			await pilot.click("#add-term-button")
			await pilot.pause()

			# when
			await pilot.click("#query-remove-1")
			await pilot.pause()

			# then
			assert builder.row_count() == 1
			with pytest.raises(NoMatches):
				builder.query_one("#query-row-1")

	asyncio.run(run())


def test_given_two_terms_when_editing_rows_then_updates_query_string():
	# given
	app = _QueryBuilderApp()

	async def run():
		async with app.run_test() as pilot:
			await pilot.pause()
			builder = app.builder()
			await pilot.click("#add-term-button")
			await pilot.pause()
			builder.query_one("#query-term-0").value = "red"
			builder.query_one("#query-term-1").value = "blue"
			await pilot.pause()

			# when
			expr = builder.to_file_query()

			# then
			assert expr == FileQ.leaf("red") & FileQ.leaf("blue")

	asyncio.run(run())


def test_given_compound_initial_query_when_mounted_then_splits_into_rows():
	# given
	app = _QueryBuilderApp(initial_query="foo&bar")

	async def run():
		async with app.run_test() as pilot:
			await pilot.pause()
			builder = app.builder()

			# when / then
			assert builder.row_count() == 2
			assert builder.query_one("#query-term-0").value == "foo"
			assert builder.query_one("#query-term-1").value == "bar"

	asyncio.run(run())


def test_given_compound_initial_query_when_mounted_then_shows_and_join_label():
	# given
	app = _QueryBuilderApp(initial_query="foo&bar")

	async def run():
		async with app.run_test(size=(80, 12)) as pilot:
			await pilot.pause()

			# when
			svg = app.export_screenshot(title="query-builder-and")

			# then
			assert "AND" in normalized_svg_text(svg)

	asyncio.run(run())


def test_given_query_builder_when_adding_term_then_shows_and_join_label():
	# given
	app = _QueryBuilderApp()

	async def run():
		async with app.run_test(size=(80, 12)) as pilot:
			await pilot.pause()

			# when
			await pilot.click("#add-term-button")
			await pilot.pause()
			svg = app.export_screenshot(title="query-builder-add-term")

			# then
			assert "AND" in normalized_svg_text(svg)

	asyncio.run(run())


def test_given_app_with_query_builder_when_adding_term_then_does_not_crash():
	# given
	from srxy.cli import build_parser
	from srxy.tui.app import SrxyApp

	args = build_parser().parse_args(["registry", "."])

	async def run():
		app = SrxyApp(args, auto_start=False)
		async with app.run_test() as pilot:
			await pilot.pause()

			# when
			await pilot.click("#add-term-button")
			await pilot.pause()

			# then
			builder = app.query_one("#query-builder", QueryBuilder)
			assert builder.row_count() == 2

	asyncio.run(run())
