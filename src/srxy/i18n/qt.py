"""Load Qt translators for QML qsTr strings when .qm files are present."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, QTranslator


def translations_dir() -> Path:
	return Path(__file__).resolve().parent


def install_qt_translator(app: QCoreApplication, language: str) -> QTranslator | None:
	"""Install ``srxy_<lang>.qm`` if compiled; otherwise return None."""
	qm = translations_dir() / f"srxy_{language}.qm"
	if not qm.is_file():
		return None
	translator = QTranslator(app)
	if not translator.load(str(qm)):
		return None
	app.installTranslator(translator)
	QLocale.setDefault(QLocale(language))
	return translator


__all__ = [
	"install_qt_translator",
	"translations_dir",
]
