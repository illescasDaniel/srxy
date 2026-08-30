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

	// Face / disabled colours must NOT come from ``control.palette``: we assign
	// ``palette.buttonText`` below, and any write to that group dirties the whole
	// palette — re-triggering a ``foreground`` binding that reads ``palette.*``
	// (Binding loop detected for property "foreground").
	SystemPalette {
		id: refPalette
		colorGroup: control.enabled ? SystemPalette.Active : SystemPalette.Disabled
	}

	// WCAG label colour for the styles that read it (see palette assignments):
	// onAccent when accented, contrast-on-face otherwise.
	readonly property color foreground: {
		if (!control.enabled)
			return refPalette.placeholderText
		if (control.accent)
			return (typeof srxyTheme !== "undefined" && srxyTheme) ? srxyTheme.onAccent : "#ffffff"
		const face = refPalette.button
		if (typeof srxyTheme !== "undefined" && srxyTheme)
			return srxyTheme.contrastOn(face)
		return face.hslLightness > 0.55 ? "#000000" : "#ffffff"
	}

	// The macOS DefaultButton and Fusion IconLabels draw the label with
	// ``palette.buttonText`` even when highlighted (black on the accent bevel).
	// Overriding it makes the label follow ``foreground``. Fluent/Material/
	// Universal compute their own highlighted text colours and ignore this role
	// — so their labels stay whatever the style paints, and any icon must follow
	// that same colour rather than ``foreground`` (see below).
	palette.buttonText: control.foreground

	// Icons are tinted from the IconLabel's ``defaultIconColor``, which every
	// style except Fusion/Basic sets to the exact colour it paints on the label.
	// Those two use ``palette.brightText`` while highlighted, so pin it too or a
	// glyph would disagree with the label beside it.
	palette.brightText: control.foreground

	// macOS Aqua predates ``defaultIconColor`` and leaves icons untinted, which
	// renders an alpha-only template SVG as opaque white. Everywhere else
	// ``icon.color`` must stay *unassigned*: IconLabel only falls back to
	// ``defaultIconColor`` while the role is unresolved, so even writing
	// ``"transparent"`` would strand the glyph untinted.
	Binding {
		target: control
		property: "icon.color"
		value: control.foreground
		when: Qt.platform.os === "osx"
		restoreMode: Binding.RestoreBinding
	}
}
