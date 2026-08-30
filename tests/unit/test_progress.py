from __future__ import annotations

from unittest.mock import MagicMock, patch

from srxy.domain.progress import (
	ActivityUpdate,
	clear_activity,
	emit_activity,
	format_activity_status,
	format_activity_status_body,
)


def test_given_activity_update_when_determinate_then_reports_progress():
	# given
	update = ActivityUpdate(label="Transcribe · audio.mp3", current=12, total=30)

	# then
	assert update.determinate is True
	assert update.indeterminate is False


def test_given_activity_update_when_label_only_then_is_indeterminate():
	# given
	update = ActivityUpdate(label="OCR · photo.png")

	# then
	assert update.indeterminate is True
	assert update.determinate is False


def test_given_callback_when_emit_activity_then_passes_update():
	# given
	received: list[ActivityUpdate | None] = []

	# when
	emit_activity(received.append, "Scanning · notes.txt", current=2, total=10)

	# then
	assert len(received) == 1
	assert received[0] == ActivityUpdate(label="Scanning · notes.txt", current=2, total=10)


def test_given_callback_when_clear_activity_then_passes_none():
	# given
	received: list[ActivityUpdate | None] = []

	# when
	clear_activity(received.append)

	# then
	assert received == [None]


def test_given_determinate_activity_when_formatting_status_then_includes_percent():
	# given
	update = ActivityUpdate(label="Transcribe · speech.mp3", current=15, total=60)

	# when / then
	assert format_activity_status(update, spinner_frame="⠋") == "⠋ 25% Transcribe · speech.mp3"


def test_given_indeterminate_activity_when_formatting_status_then_omits_percent():
	# given
	update = ActivityUpdate(label="OCR · photo.png")

	# when / then
	assert format_activity_status(update, spinner_frame="⠙") == "⠙ OCR · photo.png"
	assert format_activity_status_body(update) == "OCR · photo.png"
	assert format_activity_status(update, spinner_frame="") == "OCR · photo.png"


def test_given_determinate_activity_when_formatting_body_then_omits_spinner():
	update = ActivityUpdate(label="Transcribe · speech.mp3", current=15, total=60)
	assert format_activity_status_body(update) == "25% Transcribe · speech.mp3"


def test_given_searching_label_when_checking_generic_then_yields_to_scanning():
	from srxy.domain.progress import is_generic_searching_activity

	assert is_generic_searching_activity(None, searching_label="Searching…") is True
	assert is_generic_searching_activity(ActivityUpdate(label="Searching…"), searching_label="Searching…") is True
	assert is_generic_searching_activity(ActivityUpdate(label="OCR · photo.png"), searching_label="Searching…") is False


def test_given_concurrent_fan_in_when_two_threads_emit_then_clear_keeps_other_label():
	import threading

	from srxy.domain.progress import concurrent_activity_fan_in, emit_activity

	received: list[ActivityUpdate | None] = []
	fan_in = concurrent_activity_fan_in(received.append)
	ready = threading.Barrier(2)
	hold = threading.Event()

	def worker_a():
		emit_activity(fan_in, "OCR · a.png")
		ready.wait()
		hold.wait(timeout=5)
		fan_in(None)

	def worker_b():
		ready.wait()
		emit_activity(fan_in, "OCR · b.png")
		hold.set()
		fan_in(None)

	threads = [threading.Thread(target=worker_a), threading.Thread(target=worker_b)]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=5)

	labels = [update.label if update is not None else None for update in received]
	assert "OCR · a.png" in labels
	assert "OCR · b.png" in labels
	assert labels[-1] is None


def test_given_faster_whisper_segments_when_transcribing_then_emits_duration_progress():
	# given
	from srxy.adapters.outbound.transcribe.transcribe_text import (
		_iter_faster_whisper_segments,  # pyright: ignore[reportPrivateUsage]
	)

	segment = MagicMock(start=0.0, end=15.0, text="hello")
	info = MagicMock(duration=60.0)
	model = MagicMock()
	model.transcribe.return_value = ([segment], info)
	received: list[ActivityUpdate | None] = []

	# when
	with patch("srxy.adapters.outbound.transcribe.transcribe_text._get_faster_whisper_model", return_value=model):
		segments = list(
			_iter_faster_whisper_segments(
				__import__("pathlib").Path("audio.wav"),
				"cpu",
				on_activity=received.append,
				label="Transcribe · audio.wav",
			)
		)

	# then
	assert segments == [(0, "hello")]
	assert any(
		update is not None and update.determinate and update.current == 15 and update.total == 60 for update in received
	)
