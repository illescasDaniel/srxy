from __future__ import annotations

import pytest
from tests.helpers import file_search_root, require_file_search_fixtures

from srxy.application.use_cases.search_files import magic_file_search


pytestmark = [pytest.mark.integration, pytest.mark.transcribe]


@pytest.mark.timeout(300)
def test_given_far_cry_query_when_searching_unrelated_audio_then_does_not_match():
	# given — single known false-positive candidate; avoid transcribing the whole corpus
	require_file_search_fixtures()
	audio = file_search_root() / "minimal.mp3"
	assert audio.is_file(), f"missing QA audio fixture: {audio}"

	# when
	results = magic_file_search(audio, "far cry", threshold=0.35, transcribe=True, limit=10)

	# then
	assert results == []
