import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Dialog action row without Material DialogButtonBox (flat + accent foreground).
// Right-aligns footer buttons and wires Return / Enter to ``defaultButton`` when set.
Pane {
	id: control

	readonly property bool _macos: Qt.platform.os === "osx"

	// macOS Native popups: keep Cancel/OK off the window edge and opaque so
	// scrolling form content cannot show through the footer strip.
	padding: _macos ? 0 : 8
	topPadding: _macos ? 14 : 8
	bottomPadding: _macos ? 16 : 8
	leftPadding: _macos ? 16 : 8
	rightPadding: _macos ? 16 : 8

	property Item defaultButton: null

	background: Rectangle {
		color: control.palette.window
		Rectangle {
			anchors.left: parent.left
			anchors.right: parent.right
			anchors.top: parent.top
			height: 1
			visible: control._macos
			color: Qt.rgba(
				0, 0, 0,
				control.palette.window.hslLightness > 0.5 ? 0.10 : 0.35
			)
		}
	}

	RowLayout {
		anchors.fill: parent
		spacing: 8
		Item { Layout.fillWidth: true }
		RowLayout {
			id: buttonRow
			spacing: control._macos ? 12 : 8
		}
	}

	default property alias buttons: buttonRow.children

	Shortcut {
		sequences: [StandardKey.Ok, StandardKey.Save, "Return"]
		enabled: control.visible
			&& control.defaultButton
			&& control.defaultButton.enabled
		onActivated: {
			if (control.defaultButton && control.defaultButton.enabled)
				control.defaultButton.clicked()
		}
	}
}
