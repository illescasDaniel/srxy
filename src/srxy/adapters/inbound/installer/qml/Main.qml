import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
	id: root
	width: 720
	height: 580
	visible: true
	title: root.t("installer.window_title")
	color: palette.window

	property var c: controller
	// Which path field the folder dialog should update ("prefix" or "uninstall").
	property string browseTarget: "prefix"
	// Bump when language changes so every t() binding re-evaluates.
	property int langRev: 0
	readonly property color primaryText: palette.windowText
	readonly property color secondaryText: palette.placeholderText.a > 0
		? palette.placeholderText
		: Qt.rgba(palette.windowText.r, palette.windowText.g, palette.windowText.b, 0.65)
	readonly property bool lightTheme: palette.window.hslLightness > 0.5
	readonly property color warningText: lightTheme ? "#9a6700" : "#e0a060"
	readonly property color errorText: lightTheme ? "#c62828" : "#ff8a80"

	function t(key) {
		const _ = root.langRev
		return c ? c.i18nTr(key) : key
	}

	Connections {
		target: c
		function onLanguageChanged() {
			root.langRev++
		}
	}

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
		ToolTip.text: root.t("installer.options.info_tooltip")
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
				? root.t("installer.subtitle.uninstall")
				: root.t("installer.subtitle.install")
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
				if (c.page === "path") return 4
				if (c.page === "uninstall") return 5
				return 6
			}

			// 0 mode
			ColumnLayout {
				spacing: 12
				Label { text: root.t("installer.mode.title"); color: root.primaryText; font.pixelSize: 18 }
				RadioButton {
					text: root.t("installer.mode.install")
					checked: c.mode === "install"
					onClicked: c.setMode("install")
				}
				RadioButton {
					text: root.t("installer.mode.uninstall")
					checked: c.mode === "uninstall"
					onClicked: c.setMode("uninstall")
				}
				Label {
					text: root.t("installer.language")
					color: root.secondaryText
					Layout.topMargin: 8
				}
				ComboBox {
					objectName: "languageCombo"
					model: [root.t("menu.language.en"), root.t("menu.language.es")]
					currentIndex: c.language === "es" ? 1 : 0
					onActivated: function(index) {
						c.setLanguage(index === 1 ? "es" : "en")
					}
				}
			}

			// 1 prefix
			ColumnLayout {
				spacing: 12
				Label { text: root.t("installer.prefix.title"); color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: root.t("installer.prefix.body")
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
				RowLayout {
					Layout.fillWidth: true
					spacing: 8
					TextField {
						id: prefixField
						objectName: "prefixField"
						Layout.fillWidth: true
						text: c.prefix
						onTextChanged: c.setPrefix(text)
					}
					Button {
						objectName: "browsePrefixButton"
						text: root.t("gui.browse")
						onClicked: {
							root.browseTarget = "prefix"
							folderDialog.open()
						}
					}
				}
			}

			// 2 privacy
			ColumnLayout {
				spacing: 12
				Label { text: root.t("installer.privacy.title"); color: root.primaryText; font.pixelSize: 18 }
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
						width: Math.max(0, privacyScroll.availableWidth)
						readOnly: true
						selectByMouse: true
						wrapMode: TextEdit.Wrap
						textFormat: TextEdit.RichText
						text: c.privacyText
						color: root.primaryText
						leftPadding: 14
						rightPadding: 14
						topPadding: 12
						bottomPadding: 12
						onLinkActivated: function(link) { Qt.openUrlExternally(link) }

						HoverHandler {
							cursorShape: privacyEdit.hoveredLink !== ""
								? Qt.PointingHandCursor
								: Qt.IBeamCursor
						}
					}
				}
				CheckBox {
					text: root.t("installer.privacy.ack")
					checked: c.privacyAck
					onToggled: function() { c.setPrivacyAck(checked) }
				}
			}

			// 3 options
			ColumnLayout {
				spacing: 10
				Label { text: root.t("installer.options.title"); color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: root.t("installer.options.body")
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}

				component OptionRow: RowLayout {
					id: optionRow
					property string labelKey: ""
					property string subtitleKey: ""
					property string helpKey: ""
					property bool optionChecked: false
					property bool optionEnabled: true
					signal toggled(bool checked)

					Layout.fillWidth: true
					spacing: 8

					ColumnLayout {
						Layout.fillWidth: true
						spacing: 2
						CheckBox {
							Layout.fillWidth: true
							text: root.t(optionRow.labelKey)
							checked: optionRow.optionChecked
							enabled: optionRow.optionEnabled
							onToggled: function() { optionRow.toggled(checked) }
						}
						Label {
							text: root.t(optionRow.subtitleKey)
							wrapMode: Text.WordWrap
							color: root.secondaryText
							font.pixelSize: 12
							Layout.fillWidth: true
							Layout.leftMargin: 28
						}
					}
					InfoButton {
						helpKey: optionRow.helpKey
						enabled: true
						Layout.alignment: Qt.AlignTop
					}
				}

				OptionRow {
					labelKey: "installer.options.tesseract"
					subtitleKey: "installer.options.tesseract_sub"
					helpKey: "tesseract"
					optionChecked: c.downloadTesseract
					onToggled: function(checked) { c.setDownloadTesseract(checked) }
				}
				OptionRow {
					labelKey: "installer.options.ffmpeg"
					subtitleKey: "installer.options.ffmpeg_sub"
					helpKey: "ffmpeg"
					optionChecked: c.downloadFfmpeg
					onToggled: function(checked) { c.setDownloadFfmpeg(checked) }
				}
				OptionRow {
					labelKey: "installer.options.semantic"
					subtitleKey: "installer.options.semantic_sub"
					helpKey: "semantic"
					optionChecked: c.installSemantic
					optionEnabled: c.hasGpu
					onToggled: function(checked) { c.setInstallSemantic(checked) }
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
						ToolTip.text: root.t("installer.options.gpu_tooltip")
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
					Layout.leftMargin: 28
					spacing: 2
					opacity: c.installSemantic ? 1.0 : 0.55
					RowLayout {
						Layout.fillWidth: true
						spacing: 8
						ColumnLayout {
							Layout.fillWidth: true
							spacing: 2
							CheckBox {
								Layout.fillWidth: true
								text: root.t("installer.options.models")
								enabled: c.installSemantic
								checked: c.prefetchModels
								onToggled: function() { c.setPrefetchModels(checked) }
							}
							Label {
								text: root.t("installer.options.models_sub")
								wrapMode: Text.WordWrap
								color: root.secondaryText
								font.pixelSize: 12
								Layout.fillWidth: true
								Layout.leftMargin: 28
							}
						}
						InfoButton {
							helpKey: "models"
							enabled: true
							Layout.alignment: Qt.AlignTop
						}
					}
					Label {
						text: root.t("installer.options.models_hint")
						wrapMode: Text.WordWrap
						color: root.secondaryText
						Layout.fillWidth: true
						Layout.leftMargin: 28
					}
				}
			}

			// 4 path
			ColumnLayout {
				spacing: 12
				Label { text: root.t("installer.path.title"); color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: root.t("installer.path.body")
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
				RowLayout {
					CheckBox {
						Layout.fillWidth: true
						text: root.t("installer.path.checkbox")
						checked: c.addToPath
						onToggled: function() { c.setAddToPath(checked) }
					}
					InfoButton { helpKey: "path" }
				}
				Label {
					text: root.t("installer.path.hint")
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
			}

			// 5 uninstall
			ColumnLayout {
				spacing: 12
				Label { text: root.t("installer.uninstall.title"); color: root.primaryText; font.pixelSize: 18 }
				Label {
					text: root.t("installer.uninstall.body")
					wrapMode: Text.WordWrap
					color: root.secondaryText
					Layout.fillWidth: true
				}
				RowLayout {
					Layout.fillWidth: true
					spacing: 8
					TextField {
						id: uninstallPrefixField
						objectName: "uninstallPrefixField"
						Layout.fillWidth: true
						placeholderText: c.prefix
						text: c.uninstallPrefix
						onTextChanged: c.setUninstallPrefix(text)
					}
					Button {
						objectName: "browseUninstallButton"
						text: root.t("gui.browse")
						onClicked: {
							root.browseTarget = "uninstall"
							folderDialog.open()
						}
					}
				}
				Label {
					text: c.uninstallHint
					wrapMode: Text.WordWrap
					color: root.secondaryText
					font.pixelSize: 12
					Layout.fillWidth: true
				}
			}

			// 6 progress
			ColumnLayout {
				spacing: 12
				Label {
					text: c.busy
						? root.t("installer.progress.working")
						: (c.finished ? root.t("installer.progress.finished") : root.t("installer.progress.ready"))
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
				text: root.t("common.back")
				visible: c.page !== "mode"
				enabled: !c.busy
				onClicked: c.goBack()
			}
			Item { Layout.fillWidth: true }
			Button {
				text: root.t("common.next")
				visible: c.mode === "install" && c.page !== "path" && c.page !== "progress"
				enabled: !c.busy && (c.page !== "privacy" || c.privacyAck)
				onClicked: c.goNext()
			}
			Button {
				text: root.t("installer.button.install")
				visible: c.mode === "install" && c.page === "path"
				enabled: !c.busy && c.privacyAck
				onClicked: c.startInstall()
			}
			Button {
				text: root.t("common.next")
				visible: c.mode === "uninstall" && c.page === "mode"
				enabled: !c.busy
				onClicked: c.goNext()
			}
			Button {
				text: root.t("installer.button.uninstall")
				visible: c.mode === "uninstall" && c.page === "uninstall"
				enabled: !c.busy
				onClicked: c.startUninstall()
			}
			Button {
				text: root.t("common.close")
				visible: c.page === "progress" && !c.busy
				onClicked: Qt.quit()
			}
		}
	}

	FolderDialog {
		id: folderDialog
		title: root.browseTarget === "uninstall"
			? root.t("installer.uninstall.title")
			: root.t("installer.prefix.title")
		onAccepted: {
			if (!c)
				return
			const path = selectedFolder.toString().replace("file://", "")
			if (root.browseTarget === "uninstall")
				c.setUninstallPrefix(path)
			else
				c.setPrefix(path)
		}
	}

	Dialog {
		id: helpDialog
		title: root.t("help.option_title")
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

	Dialog {
		id: unsafePrefixDialog
		objectName: "unsafePrefixDialog"
		title: root.t("installer.confirm.unsafe_prefix_title")
		modal: true
		standardButtons: Dialog.Yes | Dialog.No
		anchors.centerIn: parent
		width: Math.min(root.width - 40, 480)
		closePolicy: Popup.NoAutoClose
		Label {
			wrapMode: Text.WordWrap
			width: parent ? parent.width : implicitWidth
			text: c ? c.unsafeConfirmMessage : ""
			color: root.primaryText
		}
		onAccepted: if (c) c.acceptUnsafeConfirm()
		onRejected: if (c) c.rejectUnsafeConfirm()
	}

	Connections {
		target: c
		function onUnsafeConfirmChanged() {
			if (c && c.unsafeConfirmOpen)
				unsafePrefixDialog.open()
			else
				unsafePrefixDialog.close()
		}
	}
}
