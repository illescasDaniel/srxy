import QtQuick
import QtQuick.Controls
import QtQuick.Templates as T

// Selected automatically on macOS via QFileSelector (+macos / +macOS).
// Prefer Popup.Native so Cocoa hosts the window (real shadow / sheet chrome)
// instead of Qt's Fusion-copied macOS Dialog.qml. Fall back chrome below is only
// for Popup.Item (offscreen tests / platforms without native popups).
T.Dialog {
	id: control

	// Offscreen GUI tests set srxyUseNativeAlerts=false and need overlay Item
	// popups (findChild + synthetic clicks). Interactive macOS uses Native.
	popupType: (typeof srxyUseNativeAlerts === "boolean" && srxyUseNativeAlerts === false)
		? Popup.Item
		: Popup.Native
	padding: 20
	spacing: 14
	topPadding: _overlaySheet && control.title.length > 0 ? 8 : 20
	bottomPadding: 16
	leftPadding: 20
	rightPadding: 20

	readonly property bool _overlaySheet: control.popupType === Popup.Item

	background: Rectangle {
		implicitWidth: 320
		implicitHeight: 96
		color: control.palette.window
		radius: control._overlaySheet ? 12 : 0
		border.width: control._overlaySheet ? 1 : 0
		border.color: Qt.rgba(
			0, 0, 0,
			control.palette.window.hslLightness > 0.5 ? 0.12 : 0.50
		)
	}

	// Overlay sheets need an in-content title; Native/Window use the system title bar.
	header: Item {
		visible: control._overlaySheet && control.title.length > 0
		height: visible ? titleLabel.implicitHeight + 16 : 0
		implicitWidth: control.availableWidth
		implicitHeight: height

		Label {
			id: titleLabel
			text: control.title
			anchors.horizontalCenter: parent.horizontalCenter
			anchors.top: parent.top
			anchors.topMargin: 4
			font.bold: true
			font.pixelSize: 13
			elide: Text.ElideRight
			width: Math.min(implicitWidth, parent.width - 24)
			horizontalAlignment: Text.AlignHCenter
		}

		Rectangle {
			anchors.left: parent.left
			anchors.right: parent.right
			anchors.bottom: parent.bottom
			height: 1
			color: Qt.rgba(
				0, 0, 0,
				control.palette.window.hslLightness > 0.5 ? 0.10 : 0.35
			)
		}
	}

	T.Overlay.modal: Rectangle {
		color: Qt.rgba(0, 0, 0, control.palette.window.hslLightness > 0.5 ? 0.18 : 0.40)
	}
}
