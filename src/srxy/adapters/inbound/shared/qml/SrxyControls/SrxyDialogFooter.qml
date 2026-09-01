import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Dialog action row without Material DialogButtonBox (flat + accent foreground).
// Right-aligns footer buttons and wires Return / Enter to ``defaultButton`` when set.
Pane {
	id: control

	padding: 8
	topPadding: 8
	bottomPadding: 8
	leftPadding: 8
	rightPadding: 8

	property Item defaultButton: null

	background: Rectangle {
		color: control.palette.window
	}

	RowLayout {
		anchors.fill: parent
		spacing: 8
		Item { Layout.fillWidth: true }
		RowLayout {
			id: buttonRow
			spacing: 8
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
