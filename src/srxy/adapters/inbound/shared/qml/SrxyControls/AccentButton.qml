import QtQuick
import QtQuick.Controls

// Primary / accent CTA: system accent fill + WCAG black/white label via srxyTheme.
// Use for Search, dialog OK/Yes, installer Launch, and any future highlighted CTA.
// Bind custom contentItem colours to ``foreground`` (do not hardcode white/black).
Button {
	id: control
	// ``accent`` is used instead of ``highlighted`` because DialogButtonBox
	// clobbers ``highlighted`` on its child buttons, which would drop the accent
	// fill on dialog OK/Yes buttons.
	property bool accent: true

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

	readonly property color fillColor: {
		if (!control.enabled)
			return control.palette.button
		if (control.accent)
			return (typeof srxyTheme !== "undefined" && srxyTheme) ? srxyTheme.accent : "#1565c0"
		return control.palette.button
	}

	background: Rectangle {
		implicitWidth: 80
		implicitHeight: 32
		radius: 4
		color: control.fillColor
		opacity: control.down ? 0.85 : 1.0
		border.width: control.visualFocus ? 2 : 0
		border.color: control.palette.highlight
	}

	contentItem: Text {
		text: control.text
		font: control.font
		color: control.foreground
		horizontalAlignment: Text.AlignHCenter
		verticalAlignment: Text.AlignVCenter
		elide: Text.ElideRight
	}
}
