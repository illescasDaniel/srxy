import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
	id: root
	width: 1200
	height: 800
	visible: true
	title: "srxy"
	objectName: "mainWindow"

	property bool syncingOptions: false
	property bool syncingFilters: false

	ListModel { id: termModel }

	function syncTermRows() {
		if (!controller)
			return
		const rows = []
		for (let i = 0; i < termModel.count; i++) {
			const item = termModel.get(i)
			rows.push({ term: item.term, join: i === 0 ? "" : (item.join || "or") })
		}
		controller.termRowsJson = JSON.stringify(rows)
	}

	function applyDemoMultiTerms(termsJson) {
		const terms = JSON.parse(termsJson)
		modeBox.currentIndex = 1
		termModel.clear()
		for (let i = 0; i < terms.length; i++)
			termModel.append({ term: terms[i], join: i === 0 ? "" : "or" })
		syncTermRows()
	}

	function loadOptionsFromController() {
		if (!controller)
			return
		syncingOptions = true
		const draft = JSON.parse(controller.optionsJson())
		optNames.checked = !!draft.search_names
		optContents.checked = !!draft.search_contents
		optDocsTags.checked = draft.search_docs_tags !== false
		optSemantic.checked = !!draft.semantic
		optOcr.checked = !!draft.ocr
		optTranscribe.checked = !!draft.transcribe
		optSemanticImage.checked = !!draft.semantic_image
		optHidden.checked = !!draft.include_hidden
		optNoise.checked = !!draft.include_noise
		optNoiseFiles.checked = !!draft.include_noise_files
		optMatchSkippedNames.checked = !!draft.match_skipped_names
		optArchives.checked = !!draft.include_archives
		optSubdirs.checked = draft.include_subdirectories !== false
		syncContentDependentOptions()
		syncingOptions = false
	}

	function syncContentDependentOptions() {
		const contentOn = optContents.checked
		optDocsTags.enabled = contentOn
		optOcr.enabled = contentOn && (controller ? controller.isFeatureEnabled("ocr") : false)
		optTranscribe.enabled = contentOn && (controller ? controller.isFeatureEnabled("transcribe") : false)
		optSemanticImage.enabled = contentOn && (controller ? controller.isFeatureEnabled("semantic_image") : false)
		optMatchSkippedNames.enabled = optNames.checked
	}

	function pushOptionsToController() {
		if (!controller || syncingOptions)
			return ""
		return controller.applyOptionsJson(JSON.stringify({
			search_names: optNames.checked,
			search_contents: optContents.checked,
			search_docs_tags: optDocsTags.checked,
			semantic: optSemantic.checked && controller.isFeatureEnabled("semantic"),
			ocr: optOcr.checked && controller.isFeatureEnabled("ocr"),
			transcribe: optTranscribe.checked && controller.isFeatureEnabled("transcribe"),
			semantic_image: optSemanticImage.checked && controller.isFeatureEnabled("semantic_image"),
			include_hidden: optHidden.checked,
			include_noise: optNoise.checked,
			include_noise_files: optNoiseFiles.checked,
			match_skipped_names: optMatchSkippedNames.checked,
			include_archives: optArchives.checked,
			include_subdirectories: optSubdirs.checked
		}))
	}

	function loadFiltersFromController() {
		if (!controller)
			return
		syncingFilters = true
		const draft = JSON.parse(controller.filtersJson())
		fltTopFiles.text = draft.top_files ?? ""
		fltMaxMatches.text = draft.max_matches ?? "50"
		fltThreshold.text = draft.threshold ?? "35"
		fltVisualMin.text = draft.semantic_image_threshold ?? "18"
		fltSpeechMin.text = draft.transcribe_threshold ?? "25"
		fltDocSize.text = draft.size_limits ? draft.size_limits.text_mib : "100"
		fltOcrSize.text = draft.size_limits ? draft.size_limits.ocr_mib : "50"
		fltMediaSize.text = draft.size_limits ? draft.size_limits.transcribe_mib : "500"
		syncingFilters = false
	}

	function pushFiltersToController() {
		if (!controller || syncingFilters)
			return
		controller.applyFiltersJson(JSON.stringify({
			top_files: fltTopFiles.text,
			max_matches: fltMaxMatches.text,
			threshold: fltThreshold.text,
			semantic_image_threshold: fltVisualMin.text,
			transcribe_threshold: fltSpeechMin.text,
			size_limits: {
				text_mib: fltDocSize.text,
				ocr_mib: fltOcrSize.text,
				transcribe_mib: fltMediaSize.text
			}
		}))
	}

	function showHelp(key) {
		helpTitle.text = key
		helpBody.text = controller ? controller.helpText(key) : ""
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
		ToolTip.text: "About this setting"
		onClicked: showHelp(helpKey)
	}

	FolderDialog {
		id: folderDialog
		onAccepted: {
			if (controller)
				controller.path = selectedFolder.toString().replace("file://", "")
		}
	}

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 8
		spacing: 8

		GroupBox {
			title: "Where to search"
			Layout.fillWidth: true
			RowLayout {
				anchors.fill: parent
				Button {
					objectName: "browseButton"
					text: "Browse…"
					onClicked: folderDialog.open()
				}
				TextField {
					id: pathField
					objectName: "pathField"
					Layout.fillWidth: true
					placeholderText: "Path"
					text: controller ? controller.path : "."
					onTextChanged: if (controller) controller.path = text
					Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
				}
				ToolButton {
					objectName: "pathIssueButton"
					text: "⚠"
					flat: true
					visible: controller && controller.pathIssue.length > 0
					implicitWidth: 28
					implicitHeight: 28
					ToolTip.visible: hovered
					ToolTip.text: controller ? controller.pathIssue : ""
				}
			}
		}

		GroupBox {
			title: "What to search"
			Layout.fillWidth: true
			ColumnLayout {
				anchors.fill: parent
				spacing: 8
				RowLayout {
					TextField {
						id: simpleQuery
						objectName: "simpleQueryField"
						Layout.fillWidth: true
						placeholderText: "Search…"
						visible: modeBox.currentIndex === 0
						text: controller ? controller.simpleQuery : ""
						onTextChanged: if (controller) controller.simpleQuery = text
						Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
					}
					ColumnLayout {
						Layout.fillWidth: true
						visible: modeBox.currentIndex === 1
						spacing: 4
						Repeater {
							id: termRepeater
							model: termModel
							delegate: RowLayout {
								required property int index
								required property string term
								required property string join
								ComboBox {
									visible: index > 0
									model: ["or", "and"]
									currentIndex: join === "and" ? 1 : 0
									onActivated: {
										termModel.setProperty(index, "join", currentText)
										syncTermRows()
									}
								}
								TextField {
									Layout.fillWidth: true
									text: term
									placeholderText: "Term"
									onTextChanged: {
										termModel.setProperty(index, "term", text)
										syncTermRows()
									}
									Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
								}
								Button {
									text: "−"
									visible: termModel.count > 1
									onClicked: {
										termModel.remove(index)
										syncTermRows()
									}
								}
							}
						}
						Button {
							text: "Add term"
							onClicked: {
								termModel.append({ term: "", join: "or" })
								syncTermRows()
							}
						}
					}
					TextField {
						id: advancedQuery
						objectName: "advancedQueryField"
						Layout.fillWidth: true
						placeholderText: "e.g. revenue | amphibian & person"
						visible: modeBox.currentIndex === 2
						text: controller ? controller.advancedQuery : ""
						onTextChanged: if (controller) controller.advancedQuery = text
						Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
					}
					ComboBox {
						id: modeBox
						objectName: "queryModeBox"
						model: ["Simple", "Multi-term", "Advanced"]
						implicitWidth: 120
						Layout.alignment: Qt.AlignTop
						onCurrentIndexChanged: {
							const modes = ["simple", "multi", "advanced"]
							if (controller)
								controller.queryMode = modes[currentIndex]
						}
					}
				}
				Label {
					objectName: "queryPreview"
					visible: modeBox.currentIndex !== 0
					text: controller ? controller.queryPreview : ""
					opacity: 0.7
					wrapMode: Text.Wrap
					Layout.fillWidth: true
				}
			}
		}

		GroupBox {
			title: "How to search"
			Layout.fillWidth: true
			ColumnLayout {
				anchors.fill: parent
				spacing: 8

				RowLayout {
					Button {
						id: optionsButton
						objectName: "optionsButton"
						text: "Options"
						onClicked: {
							loadOptionsFromController()
							optionsDialog.open()
						}
					}
					Label {
						text: controller ? controller.optionsSummary : ""
						opacity: 0.7
						elide: Text.ElideRight
						Layout.fillWidth: true
					}
				}
				RowLayout {
					Button {
						id: filtersButton
						objectName: "filtersButton"
						text: "Filters"
						onClicked: {
							loadFiltersFromController()
							filtersDialog.open()
						}
					}
					Label {
						text: controller ? controller.filtersSummary : ""
						opacity: 0.7
						elide: Text.ElideRight
						Layout.fillWidth: true
					}
				}
			}
		}

		GroupBox {
			title: "Search"
			Layout.fillWidth: true
			RowLayout {
				Button {
					id: searchButton
					objectName: "searchButton"
					text: "Search"
					highlighted: controller ? controller.stale : true
					implicitWidth: 160
					enabled: controller !== null && controller !== undefined && controller.canSearch
					onClicked: if (controller) controller.startSearch()
				}
				ToolButton {
					objectName: "queryIssueButton"
					text: "⚠"
					flat: true
					visible: controller && controller.queryIssue.length > 0
					implicitWidth: 28
					implicitHeight: 28
					ToolTip.visible: hovered
					ToolTip.text: controller ? controller.queryIssue : ""
				}
			}
		}

		GroupBox {
			title: "Search Results"
			Layout.fillWidth: true
			Layout.fillHeight: true
			enabled: controller ? controller.hasSearched : false
			opacity: enabled ? 1.0 : 0.45
			SplitView {
				anchors.fill: parent
				orientation: Qt.Horizontal

				Frame {
					SplitView.preferredWidth: 380
					SplitView.minimumWidth: 240
					ColumnLayout {
						anchors.fill: parent
						Label { text: "Results"; font.bold: true }
						RowLayout {
							Layout.fillWidth: true
							spacing: 0
							Label { text: "#"; font.bold: true; Layout.preferredWidth: 36; padding: 6 }
							Label { text: "Match"; font.bold: true; Layout.preferredWidth: 56; padding: 6 }
							Label { text: "Path"; font.bold: true; Layout.fillWidth: true; padding: 6 }
							Label { text: "Matched"; font.bold: true; Layout.preferredWidth: 88; padding: 6 }
						}
						Item {
							Layout.fillWidth: true
							Layout.fillHeight: true
							ListView {
								id: resultsView
								objectName: "resultsView"
								anchors.fill: parent
								clip: true
								model: controller ? controller.resultsModel : null
								delegate: Item {
									id: resultRow
									required property int index
									required property string score
									required property string path
									required property string labels
									width: resultsView.width
									height: resultRowLayout.implicitHeight
									Rectangle {
										anchors.fill: parent
										color: resultRow.index % 2 === 0
											? (palette.alternateBase && palette.alternateBase !== palette.base
												? palette.alternateBase
												: Qt.rgba(palette.base.r, palette.base.g, palette.base.b, 0.85))
											: palette.base
										opacity: resultsView.currentIndex === resultRow.index ? 0.65 : 1
									}
									RowLayout {
										id: resultRowLayout
										anchors.fill: parent
										spacing: 0
										Label { text: String(resultRow.index + 1); Layout.preferredWidth: 36; padding: 6; elide: Text.ElideRight }
										Label { text: resultRow.score; Layout.preferredWidth: 56; padding: 6; elide: Text.ElideRight }
										Label { text: resultRow.path; Layout.fillWidth: true; padding: 6; elide: Text.ElideMiddle }
										Label { text: resultRow.labels; Layout.preferredWidth: 88; padding: 6; elide: Text.ElideRight }
									}
									MouseArea {
										anchors.fill: parent
										acceptedButtons: Qt.LeftButton | Qt.RightButton
										onClicked: (mouse) => {
											resultsView.currentIndex = resultRow.index
											controller.selectResult(resultRow.index)
											if (mouse.button === Qt.RightButton)
												resultMenu.popup()
										}
										onDoubleClicked: controller.openResult(resultRow.index)
									}
									Menu {
										id: resultMenu
										MenuItem { text: "Open file"; onTriggered: controller.openResult(resultRow.index) }
										MenuItem { text: "Copy path"; onTriggered: controller.copyResultPath(resultRow.index) }
										MenuItem { text: "Copy all matches"; onTriggered: controller.copyAllMatches(resultRow.index) }
									}
								}
							}
							Label {
								anchors.centerIn: parent
								width: parent.width - 32
								horizontalAlignment: Text.AlignHCenter
								wrapMode: Text.WordWrap
								opacity: 0.65
								visible: controller && controller.resultsEmptyHint.length > 0
								text: controller ? controller.resultsEmptyHint : ""
							}
						}
					}
				}

				SplitView {
					orientation: Qt.Vertical
					SplitView.fillWidth: true
					Frame {
						id: matchesFrame
						visible: matchesView.count > 0
						SplitView.preferredHeight: visible ? 180 : 0
						SplitView.minimumHeight: visible ? 60 : 0
						SplitView.maximumHeight: visible ? 10000 : 0
						ColumnLayout {
							anchors.fill: parent
							Label { text: "Matches in file"; font.bold: true }
							RowLayout {
								Layout.fillWidth: true
								spacing: 0
								Label { text: "#"; font.bold: true; Layout.preferredWidth: 36; padding: 6 }
								Label { text: "Match"; font.bold: true; Layout.preferredWidth: 56; padding: 6 }
								Label { text: "Location"; font.bold: true; Layout.preferredWidth: 120; padding: 6 }
								Label { text: "Text"; font.bold: true; Layout.fillWidth: true; padding: 6 }
							}
							ListView {
								id: matchesView
								objectName: "matchesView"
								Layout.fillWidth: true
								Layout.fillHeight: true
								clip: true
								model: controller ? controller.matchesModel : null
								delegate: Item {
									id: matchRow
									required property int index
									required property string score
									required property string location
									required property string text
									width: matchesView.width
									height: matchRowLayout.implicitHeight
									Rectangle {
										anchors.fill: parent
										color: matchRow.index % 2 === 0
											? (palette.alternateBase && palette.alternateBase !== palette.base
												? palette.alternateBase
												: Qt.rgba(palette.base.r, palette.base.g, palette.base.b, 0.85))
											: palette.base
									}
									RowLayout {
										id: matchRowLayout
										anchors.fill: parent
										spacing: 0
										Label { text: String(matchRow.index + 1); Layout.preferredWidth: 36; padding: 6; elide: Text.ElideRight }
										Label { text: matchRow.score; Layout.preferredWidth: 56; padding: 6; elide: Text.ElideRight }
										Label { text: matchRow.location; Layout.preferredWidth: 120; padding: 6; elide: Text.ElideRight }
										Label {
											text: matchRow.text
											textFormat: Text.RichText
											font.family: "monospace"
											Layout.fillWidth: true
											padding: 6
											elide: Text.ElideRight
											wrapMode: Text.NoWrap
										}
									}
									MouseArea {
										anchors.fill: parent
										acceptedButtons: Qt.RightButton
										onClicked: matchMenu.popup()
									}
									Menu {
										id: matchMenu
										MenuItem { text: "Copy line"; onTriggered: controller.copyMatchLine(matchRow.index) }
										MenuItem { text: "Copy location"; onTriggered: controller.copyMatchLocation(matchRow.index) }
									}
								}
							}
						}
					}
					Frame {
						SplitView.fillHeight: true
						ColumnLayout {
							anchors.fill: parent
							Label {
								objectName: "previewHeader"
								text: controller ? controller.previewHeader : ""
								wrapMode: Text.Wrap
							}
							ScrollView {
								Layout.fillWidth: true
								Layout.fillHeight: true
								TextArea {
									objectName: "previewText"
									readOnly: true
									wrapMode: TextEdit.Wrap
									textFormat: TextEdit.RichText
									font.family: "monospace"
									text: controller ? controller.previewText : ""
									selectByMouse: true
								}
							}
						}
					}
				}
			}
		}

		GroupBox {
			title: "Search progress"
			Layout.fillWidth: true
			enabled: controller ? controller.hasSearched : false
			opacity: enabled ? 1.0 : 0.45
			RowLayout {
				anchors.fill: parent
				ProgressBar {
					id: progressBar
					objectName: "progressBar"
					Layout.fillWidth: true
					from: 0
					to: 100
					value: controller ? controller.progress : 0
				}
				Label {
					objectName: "progressPercent"
					text: (controller ? Math.round(controller.progress) : 0) + "%"
					Layout.preferredWidth: 48
					horizontalAlignment: Text.AlignRight
				}
				Label {
					objectName: "statusLabel"
					text: controller ? controller.status : ""
					Layout.preferredWidth: 280
					elide: Text.ElideRight
				}
				Button {
					text: "Cancel"
					visible: controller && controller.searching
					onClicked: controller.cancelSearch()
				}
			}
		}
	}

	Dialog {
		id: optionsDialog
		objectName: "optionsDialog"
		title: "Search options"
		modal: true
		anchors.centerIn: parent
		width: 520
		implicitWidth: 520
		onAboutToShow: {
			optionsError.text = ""
			optionsError.visible = false
			loadOptionsFromController()
		}
		footer: DialogButtonBox {
			Button {
				text: qsTr("Cancel")
				DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
				onClicked: optionsDialog.reject()
			}
			Button {
				text: qsTr("OK")
				highlighted: true
				onClicked: {
					const err = pushOptionsToController()
					if (err) {
						optionsError.text = err
						optionsError.visible = true
						return
					}
					optionsError.visible = false
					optionsDialog.accept()
				}
			}
		}

		ScrollView {
			clip: true
			ColumnLayout {
				spacing: 6
				width: optionsDialog.availableWidth - 24

				Label {
					id: optionsError
					objectName: "optionsError"
					visible: false
					color: "#c62828"
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}

				Label {
					text: "Where to search"
					font.bold: true
				}
				RowLayout {
					CheckBox {
						id: optNames
						text: "File names"
						checked: true
						onCheckedChanged: if (!syncingOptions) syncContentDependentOptions()
					}
					InfoButton { helpKey: "search_names" }
				}
				RowLayout {
					CheckBox {
						id: optContents
						text: "File contents"
						checked: true
						onCheckedChanged: if (!syncingOptions) syncContentDependentOptions()
					}
					InfoButton { helpKey: "search_contents" }
				}

				Label {
					text: "How to match"
					font.bold: true
					Layout.topMargin: 8
				}
				Label {
					text: "Fuzzy, phonetic, and substring matching (always on)"
					opacity: 0.7
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
				RowLayout {
					CheckBox {
						id: optDocsTags
						text: "Docs, tags & metadata (recommended ON)"
						checked: true
					}
					InfoButton { helpKey: "search_docs_tags" }
				}
				RowLayout {
					CheckBox {
						id: optSemantic
						text: "Similar meaning"
						enabled: controller ? controller.isFeatureEnabled("semantic") : false
					}
					InfoButton { helpKey: "semantic"; enabled: true }
				}
				RowLayout {
					CheckBox {
						id: optOcr
						text: "Text in images"
						enabled: controller ? controller.isFeatureEnabled("ocr") : false
					}
					InfoButton { helpKey: "ocr"; enabled: true }
				}
				RowLayout {
					CheckBox {
						id: optTranscribe
						text: "Spoken words"
						enabled: controller ? controller.isFeatureEnabled("transcribe") : false
					}
					InfoButton { helpKey: "transcribe"; enabled: true }
				}
				RowLayout {
					CheckBox {
						id: optSemanticImage
						text: "Visual description"
						enabled: controller ? controller.isFeatureEnabled("semantic_image") : false
					}
					InfoButton { helpKey: "semantic_image"; enabled: true }
				}

				Label {
					text: "Which files to scan"
					font.bold: true
					Layout.topMargin: 8
				}
				RowLayout {
					CheckBox { id: optSubdirs; text: "Include subdirectories"; checked: true }
					InfoButton { helpKey: "include_subdirectories" }
				}
				RowLayout {
					CheckBox { id: optArchives; text: "Inside zip/tar files" }
					InfoButton { helpKey: "include_archives" }
				}
				Label {
					text: "Noisy files"
					font.bold: true
					Layout.leftMargin: 12
					Layout.topMargin: 4
					opacity: 0.75
				}
				RowLayout {
					Layout.leftMargin: 12
					CheckBox { id: optHidden; text: "Hidden files & folders" }
					InfoButton { helpKey: "include_hidden" }
				}
				RowLayout {
					Layout.leftMargin: 12
					CheckBox { id: optNoise; text: "Cache & vendor folders" }
					InfoButton { helpKey: "include_noise" }
				}
				RowLayout {
					Layout.leftMargin: 12
					CheckBox { id: optNoiseFiles; text: "Junk & lock files" }
					InfoButton { helpKey: "include_noise_files" }
				}
				RowLayout {
					Layout.leftMargin: 12
					CheckBox { id: optMatchSkippedNames; text: "Skipped file names" }
					InfoButton { helpKey: "match_skipped_names" }
				}
				Label {
					text: "Binary-looking files (null byte in first 8 KiB) skip body text; names can still match"
					wrapMode: Text.WordWrap
					opacity: 0.7
					Layout.fillWidth: true
					Layout.topMargin: 4
				}
			}
		}
	}

	Dialog {
		id: filtersDialog
		objectName: "filtersDialog"
		title: "Filters"
		modal: true
		standardButtons: Dialog.Ok | Dialog.Cancel
		anchors.centerIn: parent
		width: 480
		implicitWidth: 480
		onAboutToShow: loadFiltersFromController()
		onAccepted: pushFiltersToController()

		GridLayout {
			columns: 3
			columnSpacing: 8
			rowSpacing: 6

			Label { text: "Max results" }
			TextField { id: fltTopFiles; placeholderText: "all"; Layout.fillWidth: true }
			InfoButton { helpKey: "top_files" }

			Label { text: "Hits per file" }
			TextField { id: fltMaxMatches; text: "50"; Layout.fillWidth: true }
			InfoButton { helpKey: "max_matches" }

			Label { text: "Minimum match %" }
			TextField { id: fltThreshold; text: "35"; Layout.fillWidth: true }
			InfoButton { helpKey: "threshold" }

			Label { text: "Visual min %" }
			TextField { id: fltVisualMin; text: "18"; Layout.fillWidth: true }
			InfoButton { helpKey: "semantic_image_threshold" }

			Label { text: "Speech min %" }
			TextField { id: fltSpeechMin; text: "25"; Layout.fillWidth: true }
			InfoButton { helpKey: "transcribe_threshold" }

			Label { text: "Document MiB" }
			TextField { id: fltDocSize; text: "100"; Layout.fillWidth: true }
			InfoButton { helpKey: "text_mib" }

			Label { text: "Image text MiB" }
			TextField { id: fltOcrSize; text: "50"; Layout.fillWidth: true }
			InfoButton { helpKey: "ocr_mib" }

			Label { text: "Audio/video MiB" }
			TextField { id: fltMediaSize; text: "500"; Layout.fillWidth: true }
			InfoButton { helpKey: "transcribe_mib" }
		}
	}

	Dialog {
		id: helpDialog
		objectName: "helpDialog"
		title: "About this setting"
		modal: true
		standardButtons: Dialog.Ok
		anchors.centerIn: parent
		width: 460
		implicitWidth: 460
		ColumnLayout {
			Label { id: helpTitle; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true }
			Label { id: helpBody; wrapMode: Text.Wrap; Layout.fillWidth: true }
		}
	}

	Dialog {
		id: downloadConfirmDialog
		objectName: "downloadConfirmDialog"
		title: "Download model"
		modal: true
		standardButtons: Dialog.Yes | Dialog.No
		anchors.centerIn: parent
		width: 480
		implicitWidth: 480
		closePolicy: Popup.NoAutoClose
		Label {
			wrapMode: Text.Wrap
			text: controller ? controller.downloadConfirmMessage : ""
		}
		onAccepted: if (controller) controller.acceptDownloadConfirm()
		onRejected: if (controller) controller.rejectDownloadConfirm()
	}

	Dialog {
		id: downloadProgressDialog
		objectName: "downloadProgressDialog"
		title: "Downloading…"
		modal: true
		anchors.centerIn: parent
		width: 420
		implicitWidth: 420
		closePolicy: Popup.NoAutoClose
		standardButtons: Dialog.Cancel
		ColumnLayout {
			Label {
				text: controller ? controller.downloadStatus : ""
				wrapMode: Text.Wrap
				Layout.fillWidth: true
			}
			ProgressBar {
				from: 0
				to: 100
				value: controller ? controller.downloadProgress : 0
				Layout.fillWidth: true
			}
		}
		onRejected: if (controller) controller.cancelDownload()
	}

	Dialog {
		id: errorDialog
		objectName: "errorDialog"
		title: "Error"
		modal: true
		standardButtons: Dialog.Ok
		anchors.centerIn: parent
		width: 420
		implicitWidth: 420
		Label {
			id: errorLabel
			wrapMode: Text.Wrap
			width: errorDialog.availableWidth - 24
		}
	}

	Connections {
		target: controller
		function onErrorOccurred(message) {
			errorLabel.text = message
			errorDialog.open()
		}
		function onDownloadConfirmChanged() {
			if (controller && controller.downloadConfirmOpen)
				downloadConfirmDialog.open()
			else
				downloadConfirmDialog.close()
		}
		function onDownloadProgressUiChanged() {
			if (controller && controller.downloadProgressOpen)
				downloadProgressDialog.open()
			else
				downloadProgressDialog.close()
		}
		function onCapabilitiesChanged() {
			loadOptionsFromController()
		}
	}

	Component.onCompleted: {
		termModel.clear()
		const initialTerm = controller ? controller.simpleQuery : ""
		termModel.append({ term: initialTerm, join: "" })
		if (controller) {
			syncTermRows()
			loadOptionsFromController()
			loadFiltersFromController()
			controller.refreshCapabilities()
		}
	}
}
