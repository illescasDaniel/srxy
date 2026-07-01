from __future__ import annotations

from unittest.mock import MagicMock, patch

from srxy.progress import ActivityUpdate, clear_activity, emit_activity, format_activity_status


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


def test_given_faster_whisper_segments_when_transcribing_then_emits_duration_progress():
	# given
	from srxy.transcribe_text import _iter_faster_whisper_segments  # pyright: ignore[reportPrivateUsage]

	segment = MagicMock(start=0.0, end=15.0, text="hello")
	info = MagicMock(duration=60.0)
	model = MagicMock()
	model.transcribe.return_value = ([segment], info)
	received: list[ActivityUpdate | None] = []

	# when
	with patch("srxy.transcribe_text._get_faster_whisper_model", return_value=model):
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
