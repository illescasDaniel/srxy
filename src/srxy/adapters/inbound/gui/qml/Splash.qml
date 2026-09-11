import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// Lightweight first paint while Main.qml / SearchController finish loading.
Window {
	id: splash
	objectName: "splashWindow"
	title: splashBridge ? splashBridge.appName : "srxy"
	visible: true
	width: 360
	height: 300
	color: palette.window
	modality: Qt.ApplicationModal
	flags: Qt.SplashScreen | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint

	x: Screen.width / 2 - width / 2
	y: Screen.height / 2 - height / 2

	ColumnLayout {
		anchors.centerIn: parent
		spacing: 10
		width: parent.width - 48

		Image {
			Layout.alignment: Qt.AlignHCenter
			Layout.preferredWidth: 96
			Layout.preferredHeight: 96
			source: splashIconUrl
			fillMode: Image.PreserveAspectFit
			smooth: true
			mipmap: true
			asynchronous: false
		}

		Label {
			Layout.alignment: Qt.AlignHCenter
			objectName: "splashAppName"
			text: splashBridge ? splashBridge.appName : "srxy"
			font.pixelSize: 28
			font.weight: Font.DemiBold
			color: palette.windowText
		}

		Label {
			Layout.alignment: Qt.AlignHCenter
			objectName: "splashVersion"
			text: splashBridge ? ("v" + splashBridge.version) : ""
			font.pixelSize: 13
			color: palette.placeholderText
		}

		Label {
			Layout.alignment: Qt.AlignHCenter
			objectName: "splashAuthor"
			text: splashBridge ? splashBridge.author : ""
			font.pixelSize: 12
			color: palette.placeholderText
			wrapMode: Text.WordWrap
			horizontalAlignment: Text.AlignHCenter
			Layout.fillWidth: true
		}

		Item { Layout.preferredHeight: 6 }

		BusyIndicator {
			Layout.alignment: Qt.AlignHCenter
			running: splash.visible
		}

		Label {
			Layout.alignment: Qt.AlignHCenter
			objectName: "splashStatus"
			text: splashBridge ? splashBridge.status : "Loading…"
			font.pixelSize: 13
			color: palette.windowText
			wrapMode: Text.WordWrap
			horizontalAlignment: Text.AlignHCenter
			Layout.fillWidth: true
		}
	}
}
