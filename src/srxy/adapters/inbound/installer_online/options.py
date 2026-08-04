"""Build InstallOptions for the online one-click installer."""

from __future__ import annotations

from pathlib import Path

from srxy.adapters.inbound.installer.catalog import vendor_downloads_supported
from srxy.adapters.inbound.installer.gpu import has_accelerated_gpu
from srxy.adapters.inbound.installer.install import InstallOptions
from srxy.adapters.inbound.installer.package_spec import resolve_pypi_install_spec
from srxy.application.install_paths import default_install_prefix


def build_online_install_options(
	*,
	prefix: Path | None = None,
	fetch_pypi: bool = True,
) -> InstallOptions:
	"""Fixed auto choices: PATH + tesseract + ffmpeg; semantic iff GPU; no model prefetch."""
	has_gpu = has_accelerated_gpu()
	vendors_ok = vendor_downloads_supported()
	return InstallOptions(
		prefix=(prefix or default_install_prefix()).expanduser().resolve(),
		download_tesseract=vendors_ok,
		download_ffmpeg=vendors_ok,
		install_semantic=has_gpu,
		prefetch_models=False,
		add_to_path=True,
		srxy_spec=resolve_pypi_install_spec(fetch_pypi=fetch_pypi),
	)


__all__ = ["build_online_install_options"]
