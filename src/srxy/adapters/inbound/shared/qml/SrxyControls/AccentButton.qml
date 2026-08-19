import QtQuick
import QtQuick.Controls

// Primary / accent CTA: native button chrome, recoloured via the style's own
// accent switch. `highlighted` is the native accent on every style we use —
// Material (Material.accent), Universal (Universal.accent), FluentWinUI3
// (palette.accent), Fusion (palette.highlight), macOS/Windows (native default
// button). There is no custom background/contentItem, so hover/press/focus/
// ripple/size all follow the active style.
//
// Qt 6.11's DialogButtonBox forcibly calls setHighlighted() on every child on
// each layout pass, so a QML ``highlighted`` binding is unreliable inside a
// box: the box only keeps it true for its defaultButton. We still bind
// ``highlighted`` to ``accent`` so non-box usages (Search, installer Launch)
// get the native accent; dialog OK/Yes buttons set the box's defaultButton.
Button {
	id: control
	property bool accent: true

	highlighted: control.accent

	// Used only by custom contentItems (the Search button's icon+text Row).
	// Plain dialog/launch buttons render their label through the style's own
	// highlighted text colour instead.
	readonly property color foreground: {
		if (!control.enabled)
			return control.palette.placeholderText
		if (control.accent)
			return (typeof srxyTheme !== "undefined" && srxyTheme) ? srxyTheme.onAccent : "#ffffff"
		const face = control.palette.button
		if (typeof srxyTheme !== "undefined" && srxyTheme)
			return srxyTheme.contrastOn(face)
		return face.hslLightness > 0.55 ? "#000000" : "#ffffff"
	}
}
