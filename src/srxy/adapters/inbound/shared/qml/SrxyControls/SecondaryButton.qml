import QtQuick
import QtQuick.Controls

// Neutral secondary CTA: contained (non-flat) button chrome matching Options/Filter.
// Material DialogButtonBox forces flat delegates and accent foreground on footer
// children; ``flat: false`` restores the gray elevated surface. Label colour
// follows ``palette.buttonText`` (body text) on every style we ship.
Button {
	id: control

	flat: false
	highlighted: false

	SystemPalette {
		id: refPalette
		colorGroup: control.enabled ? SystemPalette.Active : SystemPalette.Disabled
	}

	readonly property color foreground: control.enabled
		? refPalette.buttonText
		: refPalette.placeholderText

	palette.buttonText: control.foreground
	palette.brightText: control.foreground

	Binding {
		target: control
		property: "icon.color"
		value: control.foreground
		when: Qt.platform.os === "osx"
		restoreMode: Binding.RestoreBinding
	}
}
