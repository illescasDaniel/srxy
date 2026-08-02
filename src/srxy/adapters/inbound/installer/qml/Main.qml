import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
	id: root
	width: 720
	height: 580
	visible: true
	title: "srxy installer"
	color: palette.window

	property var c: controller
	readonly property color primaryText: palette.windowText
	readonly property color secondaryText: palette.placeholderText.a > 0
		? palette.placeholderText
		: Qt.rgba(palette.windowText.r, palette.windowText.g, palette.windowText.b, 0.65)
	readonly property bool lightTheme: palette.window.hslLightness > 0.5
	readonly property color warningText: lightTheme ? "#9a6700" : "#e0a060"
	readonly property color errorText: lightTheme ? "#c62828" : "#ff8a80"

	function showHelp(key) {
		helpTitle.text = key
		helpBody.text = c ? c.helpText(key) : ""
		helpDialog.open()
	}

	component InfoButton: ToolButton {
		property string helpKey: ""
		text: "i"
		flat: true
		implicitWidth: 28
		implicitHeight: 28
		font.bold: true
		ToolTip.visible: hovered
		ToolTip.text: "About this option"
		onClicked: showHelp(helpKey)
	}

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 20
		spacing: 12

		Label {
			text: "srxy"
			font.pixelSize: 28
			font.bold: true
			color: root.primaryText
		}
		Label {
			visible: c.page !== "mode"
			text: c.mode === "uninstall"
				? "Remove srxy on this computer"
				: "Install srxy on this computer"
			color: root.secondaryText
		}

		StackLayout {
			Layout.fillWidth: true
			Layout.fillHeight: true
			currentIndex: {
				if (c.page === "mode") return 0
				if (c.page === "prefix") return 1
				if (c.page === "privacy") return 2
				if (c.page === "options") return 3
				if (c.page === "uninstall") return 4
				return 5
			}

			// 0 mode
			ColumnLayout {
				spacing: 12
				Label { text: "What do you want to do?"; color: root.primaryText; font.pixelSize: 18 }
				RadioButton {
					text: "Install srxy"
					checked: c.mode === "install"
					onClicked: c.setMode("install")
				}
				RadioButton {
					text: "Uninstall srxy"
					checked: c.mode === "uninstall"
					onClicked: c.setMode("uninstall")
				}
			}

			// 1 prefix
			ColumnLayout {
				spacing: 12
				Label { text: "Where should srxy live?"; color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: "Default is your Applications folder. Tools, AI models, and cache stay in this folder."
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
				TextField {
					Layout.fillWidth: true
					text: c.prefix
					onTextChanged: c.setPrefix(text)
				}
			}

			// 2 privacy
			ColumnLayout {
				spacing: 12
				Label { text: "Privacy & downloads notice"; color: root.primaryText; font.pixelSize: 18 }
				ScrollView {
					id: privacyScroll
					Layout.fillWidth: true
					Layout.fillHeight: true
					clip: true
					background: Rectangle {
						color: root.palette.base
						border.color: root.palette.mid
						radius: 2
					}

					TextEdit {
						id: privacyEdit
						width: privacyScroll.availableWidth
						readOnly: true
						selectByMouse: true
						wrapMode: TextEdit.Wrap
						textFormat: TextEdit.RichText
						text: c.privacyText
						color: root.primaryText
						onLinkActivated: function(link) { Qt.openUrlExternally(link) }

						HoverHandler {
							cursorShape: privacyEdit.hoveredLink !== ""
								? Qt.PointingHandCursor
								: Qt.IBeamCursor
						}
					}
				}
				CheckBox {
					text: "I understand and want to continue"
					checked: c.privacyAck
					onToggled: c.setPrivacyAck(checked)
				}
			}

			// 3 options
			ColumnLayout {
				spacing: 10
				Label { text: "Optional extras"; color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: "Turn on what you need. Tap (i) for a plain-language explanation."
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}

				RowLayout {
					CheckBox {
						Layout.fillWidth: true
						text: "Text in images"
						checked: c.downloadTesseract
						onToggled: c.setDownloadTesseract(checked)
					}
					InfoButton { helpKey: "tesseract" }
				}
				RowLayout {
					CheckBox {
						Layout.fillWidth: true
						text: "Spoken words helper"
						checked: c.downloadFfmpeg
						onToggled: c.setDownloadFfmpeg(checked)
					}
					InfoButton { helpKey: "ffmpeg" }
				}
				RowLayout {
					CheckBox {
						Layout.fillWidth: true
						text: "AI search extras"
						enabled: c.hasGpu
						checked: c.installSemantic
						onToggled: c.setInstallSemantic(checked)
					}
					InfoButton { helpKey: "semantic"; enabled: true }
				}
				RowLayout {
					visible: !c.hasGpu
					Layout.fillWidth: true
					spacing: 8
					ToolButton {
						text: "!"
						flat: true
						implicitWidth: 28
						implicitHeight: 28
						font.bold: true
						palette.buttonText: root.warningText
						ToolTip.visible: hovered
						ToolTip.text: "Why AI extras are unavailable"
						onClicked: showHelp("no_gpu")
					}
					Label {
						text: c.noGpuMessage
						wrapMode: Text.WordWrap
						color: root.warningText
						Layout.fillWidth: true
					}
				}
				ColumnLayout {
					Layout.fillWidth: true
					spacing: 4
					RowLayout {
						Layout.fillWidth: true
						CheckBox {
							Layout.fillWidth: true
							text: "Download AI models now"
							enabled: c.installSemantic
							checked: c.prefetchModels
							onToggled: c.setPrefetchModels(checked)
						}
						InfoButton { helpKey: "models"; enabled: true }
					}
					Label {
						text: "If you skip this, srxy can later install the models when needed."
						wrapMode: Text.WordWrap
						color: root.secondaryText
						Layout.fillWidth: true
						Layout.leftMargin: 28
					}
				}
			}

			// 4 uninstall
			ColumnLayout {
				spacing: 12
				Label { text: "Remove srxy"; color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: "Leave blank to use the usual Applications folder when srxy is installed there."
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
				TextField {
					Layout.fillWidth: true
					placeholderText: c.prefix
					text: c.uninstallPrefix
					onTextChanged: c.setUninstallPrefix(text)
				}
				Label {
					text: c.uninstallHint
					wrapMode: Text.WordWrap
					color: root.secondaryText
					font.pixelSize: 12
					Layout.fillWidth: true
				}
			}

			// 5 progress
			ColumnLayout {
				spacing: 12
				Label {
					text: c.busy ? "Working…" : (c.finished ? "Finished" : "Ready")
					color: root.primaryText
					font.pixelSize: 18
				}
				Label { text: c.status; color: root.primaryText; wrapMode: Text.WordWrap; Layout.fillWidth: true }
				Label { text: c.progressLabel; color: root.secondaryText; visible: c.progressLabel.length > 0 }
				ProgressBar {
					Layout.fillWidth: true
					value: c.progressValue
					from: 0
					to: 1
					indeterminate: c.busy && c.progressValue <= 0
				}
				Label {
					visible: c.error.length > 0
					text: c.error
					color: root.errorText
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
			}
		}

		Label {
			visible: c.error.length > 0 && c.page !== "progress"
			text: c.error
			color: root.errorText
			wrapMode: Text.WordWrap
			Layout.fillWidth: true
		}

		RowLayout {
			Layout.fillWidth: true
			Button {
				text: "Back"
				enabled: !c.busy && c.page !== "mode"
				onClicked: c.goBack()
			}
			Item { Layout.fillWidth: true }
			Button {
				text: "Next"
				visible: c.mode === "install" && c.page !== "options" && c.page !== "progress"
				enabled: !c.busy && (c.page !== "privacy" || c.privacyAck)
				onClicked: c.goNext()
			}
			Button {
				text: "Install"
				visible: c.mode === "install" && c.page === "options"
				enabled: !c.busy && c.privacyAck
				onClicked: c.startInstall()
			}
			Button {
				text: "Next"
				visible: c.mode === "uninstall" && c.page === "mode"
				enabled: !c.busy
				onClicked: c.goNext()
			}
			Button {
				text: "Uninstall"
				visible: c.mode === "uninstall" && c.page === "uninstall"
				enabled: !c.busy
				onClicked: c.startUninstall()
			}
			Button {
				text: "Close"
				visible: c.page === "progress" && !c.busy
				onClicked: Qt.quit()
			}
		}
	}

	Dialog {
		id: helpDialog
		title: "About this option"
		modal: true
		standardButtons: Dialog.Ok
		anchors.centerIn: parent
		width: Math.min(root.width - 40, 480)

		ColumnLayout {
			anchors.fill: parent
			spacing: 8
			Label {
				id: helpTitle
				visible: false
			}
			Label {
				id: helpBody
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
				color: root.primaryText
			}
		}
	}
}
