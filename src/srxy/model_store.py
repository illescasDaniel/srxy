from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import IO, Callable


SEMANTIC_TEXT_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEMANTIC_IMAGE_MODEL_ID = "sentence-transformers/clip-ViT-B-32"
TRANSCRIBE_FASTER_WHISPER_REPO_TEMPLATE = "Systran/faster-whisper-{model}"
TRANSCRIBE_TRANSFORMERS_MODEL_TEMPLATE = "openai/whisper-{model}"
DEFAULT_TRANSCRIBE_MODEL = "base"

_MODEL_MARKERS = ("modules.json", "config.json", "model.safetensors", "pytorch_model.bin", "model.bin")

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def default_cache_root() -> Path:
	raw = os.environ.get("SRXY_CACHE_DIR", "").strip()
	if raw:
		return Path(raw).expanduser()
	return Path.home() / ".cache" / "srxy"


def semantic_text_model_dir() -> Path:
	override = os.environ.get("SRXY_SEMANTIC_MODEL_PATH", "").strip()
	if override:
		return Path(override).expanduser()
	return default_cache_root() / "semantic-model"


def semantic_image_model_dir() -> Path:
	override = os.environ.get("SRXY_SEMANTIC_IMAGE_MODEL_PATH", "").strip()
	if override:
		return Path(override).expanduser()
	return default_cache_root() / "semantic-image-model"


def transcribe_model_name() -> str:
	raw = os.environ.get("SRXY_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL).strip()
	return raw or DEFAULT_TRANSCRIBE_MODEL


def transcribe_model_root() -> Path:
	return default_cache_root() / "transcribe-model"


def transcribe_faster_whisper_model_dir() -> Path:
	override = os.environ.get("SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH", "").strip()
	if override:
		return Path(override).expanduser()
	return transcribe_model_root() / "faster-whisper"


def transcribe_transformers_model_dir() -> Path:
	override = os.environ.get("SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH", "").strip()
	if override:
		return Path(override).expanduser()
	return transcribe_model_root() / "transformers"


def transcribe_faster_whisper_repo_id() -> str:
	return TRANSCRIBE_FASTER_WHISPER_REPO_TEMPLATE.format(model=transcribe_model_name())


def transcribe_transformers_model_id() -> str:
	return TRANSCRIBE_TRANSFORMERS_MODEL_TEMPLATE.format(model=transcribe_model_name())


def is_model_installed(path: Path) -> bool:
	if not path.is_dir():
		return False
	return any((path / marker).exists() for marker in _MODEL_MARKERS)


def huggingface_hub_installed() -> bool:
	import importlib.util

	return importlib.util.find_spec("huggingface_hub") is not None


def _auto_download_enabled() -> bool:
	value = os.environ.get("SRXY_AUTO_DOWNLOAD", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def _prompt_yes(
	prompt: str,
	*,
	stdin: IO[str] | None = None,
	stdout: IO[str] | None = None,
) -> bool:
	input_stream = stdin or sys.stdin
	output_stream = stdout or sys.stdout
	if not input_stream.isatty():
		return False
	output_stream.write(prompt)
	output_stream.flush()
	answer = input_stream.readline().strip().lower()
	return answer in {"y", "yes"}


def download_model(model_id: str, target_dir: Path):
	if not huggingface_hub_installed():
		raise RuntimeError("huggingface_hub is required to download models. Install with: pip install 'srxy[semantic]'")

	from huggingface_hub import snapshot_download  # type: ignore[import-untyped]

	target_dir.parent.mkdir(parents=True, exist_ok=True)
	if target_dir.exists():
		shutil.rmtree(target_dir)
	snapshot_download(repo_id=model_id, local_dir=str(target_dir))


def download_semantic_text_model(*, target_dir: Path | None = None):
	directory = target_dir or semantic_text_model_dir()
	print(f"Downloading {SEMANTIC_TEXT_MODEL_ID} into {directory}", file=sys.stderr)
	download_model(SEMANTIC_TEXT_MODEL_ID, directory)
	os.environ["SRXY_SEMANTIC_MODEL_PATH"] = str(directory)
	print(f"Semantic text model cached at {directory}", file=sys.stderr)


def download_semantic_image_model(*, target_dir: Path | None = None):
	directory = target_dir or semantic_image_model_dir()
	print(f"Downloading {SEMANTIC_IMAGE_MODEL_ID} into {directory}", file=sys.stderr)
	download_model(SEMANTIC_IMAGE_MODEL_ID, directory)
	os.environ["SRXY_SEMANTIC_IMAGE_MODEL_PATH"] = str(directory)
	print(f"Semantic image model cached at {directory}", file=sys.stderr)


def download_transcribe_model(*, target_dir: Path | None = None):
	from srxy.device import resolve_transcribe_device, transcribe_backend_for_device

	device = resolve_transcribe_device()
	backend = transcribe_backend_for_device(device)
	if backend == "transformers":
		directory = target_dir or transcribe_transformers_model_dir()
		model_id = transcribe_transformers_model_id()
		env_var = "SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH"
	else:
		directory = target_dir or transcribe_faster_whisper_model_dir()
		model_id = transcribe_faster_whisper_repo_id()
		env_var = "SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH"
	print(f"Downloading {model_id} into {directory}", file=sys.stderr)
	download_model(model_id, directory)
	os.environ[env_var] = str(directory)
	print(f"Transcription model cached at {directory}", file=sys.stderr)


def _ensure_model(
	*,
	label: str,
	model_id: str,
	target_dir: Path,
	env_var: str,
	size_hint: str,
	interactive: bool,
	auto_download: bool,
	stdin: IO[str] | None = None,
	stdout: IO[str] | None = None,
	prompt_yes: Callable[[str], bool] | None = None,
) -> bool:
	if is_model_installed(target_dir):
		os.environ.setdefault(env_var, str(target_dir))
		return True

	should_download = auto_download or _auto_download_enabled()
	if not should_download and interactive:
		prompt_text = f"{label} is not cached at {target_dir}.\nDownload {model_id} ({size_hint})?"
		if prompt_yes is not None:
			should_download = prompt_yes(prompt_text)
		else:
			should_download = _prompt_yes(
				f"{prompt_text} [y/N] ",
				stdin=stdin,
				stdout=stdout,
			)

	if not should_download:
		return False

	download_model(model_id, target_dir)
	os.environ[env_var] = str(target_dir)
	print(f"{label} cached at {target_dir}", file=sys.stderr)
	return True


def ensure_semantic_text_model(
	*,
	interactive: bool = True,
	auto_download: bool = False,
	stdin: IO[str] | None = None,
	stdout: IO[str] | None = None,
	prompt_yes: Callable[[str], bool] | None = None,
) -> bool:
	return _ensure_model(
		label="Semantic text model",
		model_id=SEMANTIC_TEXT_MODEL_ID,
		target_dir=semantic_text_model_dir(),
		env_var="SRXY_SEMANTIC_MODEL_PATH",
		size_hint="~470 MB",
		interactive=interactive,
		auto_download=auto_download,
		stdin=stdin,
		stdout=stdout,
		prompt_yes=prompt_yes,
	)


def ensure_semantic_image_model(
	*,
	interactive: bool = True,
	auto_download: bool = False,
	stdin: IO[str] | None = None,
	stdout: IO[str] | None = None,
	prompt_yes: Callable[[str], bool] | None = None,
) -> bool:
	return _ensure_model(
		label="Semantic image model",
		model_id=SEMANTIC_IMAGE_MODEL_ID,
		target_dir=semantic_image_model_dir(),
		env_var="SRXY_SEMANTIC_IMAGE_MODEL_PATH",
		size_hint="~600 MB",
		interactive=interactive,
		auto_download=auto_download,
		stdin=stdin,
		stdout=stdout,
		prompt_yes=prompt_yes,
	)


def semantic_text_model_missing_message() -> str:
	path = semantic_text_model_dir()
	return (
		f"Semantic text model is not cached at {path}. "
		"Run with --semantic on an interactive terminal to download it, "
		"or set SRXY_AUTO_DOWNLOAD=1."
	)


def semantic_image_model_missing_message() -> str:
	path = semantic_image_model_dir()
	return (
		f"Semantic image model is not cached at {path}. "
		"Run with --semantic-image on an interactive terminal to download it, "
		"or set SRXY_AUTO_DOWNLOAD=1."
	)


def transcribe_model_missing_message() -> str:
	path = transcribe_model_root()
	return (
		f"Transcription model is not cached at {path}. "
		"Run with --transcribe on an interactive terminal to download it, "
		"or set SRXY_AUTO_DOWNLOAD=1."
	)


def ensure_transcribe_model(
	*,
	interactive: bool = True,
	auto_download: bool = False,
	stdin: IO[str] | None = None,
	stdout: IO[str] | None = None,
	prompt_yes: Callable[[str], bool] | None = None,
) -> bool:
	from srxy.device import resolve_transcribe_device, transcribe_backend_for_device

	device = resolve_transcribe_device()
	backend = transcribe_backend_for_device(device)
	if backend == "transformers":
		return _ensure_model(
			label="Transcription model (transformers)",
			model_id=transcribe_transformers_model_id(),
			target_dir=transcribe_transformers_model_dir(),
			env_var="SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH",
			size_hint="~290 MB",
			interactive=interactive,
			auto_download=auto_download,
			stdin=stdin,
			stdout=stdout,
			prompt_yes=prompt_yes,
		)
	return _ensure_model(
		label="Transcription model (faster-whisper)",
		model_id=transcribe_faster_whisper_repo_id(),
		target_dir=transcribe_faster_whisper_model_dir(),
		env_var="SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH",
		size_hint="~150 MB",
		interactive=interactive,
		auto_download=auto_download,
		stdin=stdin,
		stdout=stdout,
		prompt_yes=prompt_yes,
	)


def _build_download_parser():
	import argparse

	parser = argparse.ArgumentParser(description="Download srxy semantic models for offline use.")
	parser.add_argument(
		"target",
		choices=("semantic-text", "semantic-image", "transcribe", "all"),
		help="Which model bundle to download into ~/.cache/srxy/",
	)
	return parser


def main(argv: list[str] | None = None) -> int:
	parser = _build_download_parser()
	args = parser.parse_args(argv)

	try:
		if args.target in {"semantic-text", "all"}:
			download_semantic_text_model()
		if args.target in {"semantic-image", "all"}:
			download_semantic_image_model()
		if args.target in {"transcribe", "all"}:
			download_transcribe_model()
	except RuntimeError as error:
		print(error, file=sys.stderr)
		return 2

	return 0


if __name__ == "__main__":
	sys.exit(main())
