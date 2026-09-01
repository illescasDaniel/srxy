import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import SrxyControls

ApplicationWindow {
	id: root
	width: 1200
	height: 800
	// run_gui shows this after Splash.qml + controller are ready (avoids empty flash).
	// Direct engine.load in tests should set visible: true after load when needed.
	visible: false
	title: "srxy"
	objectName: "mainWindow"

	property bool syncingOptions: false
	property bool syncingFilters: false
	property bool filtersDraftValid: true
	readonly property bool lightTheme: palette.window.hslLightness > 0.5
	// Bump when language changes so every t() / privacy binding re-evaluates.
	property int langRev: 0
	property int settingsRev: 0
	property var settingsData: ({
		models: [],
		cache: { path: "", present: false, statusText: "", pathLabel: "" },
		preferences: { path: "", present: false, statusText: "", pathLabel: "" },
		busy: false
	})

	// Keep platform-native checkbox rendering (especially on macOS).
	component StyledCheckBox: CheckBox {}

	component SettingsModelRow: RowLayout {
		required property string kind
		readonly property var row: root.settingsModelRow(kind)
		readonly property bool settingsLoading: !!(root.settingsData && root.settingsData.loading)
		readonly property bool busy: settingsLoading || !!(root.settingsData && root.settingsData.busy)
		spacing: 8
		ColumnLayout {
			Layout.fillWidth: true
			spacing: 2
			Label {
				text: row.label
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
			}
			Label {
				text: row.statusText
				opacity: 0.75
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
			}
		}
		SecondaryButton {
			objectName: "settingsClear_" + kind
			text: kind === "all"
				? root.t("settings.action.clear_all")
				: root.t("settings.action.clear")
			enabled: !!row.installed && !busy
			onClicked: if (controller) controller.confirmClearModel(kind)
		}
		SecondaryButton {
			objectName: "settingsRedownload_" + kind
			text: kind === "all"
				? root.t("settings.action.redownload_all")
				: (row.installed
					? root.t("settings.action.redownload")
					: root.t("settings.action.download"))
			enabled: !busy
			onClicked: if (controller) controller.redownloadModel(kind)
		}
	}

	function t(key) {
		const _ = root.langRev
		return controller ? controller.i18nTr(key) : key
	}

	function reloadSettingsData() {
		const _ = root.settingsRev
		if (!controller)
			return
		try {
			root.settingsData = JSON.parse(controller.settingsJson)
		} catch (e) {
			root.settingsData = {
				loading: false,
				models: [],
				cache: { path: "", present: false, statusText: "", pathLabel: "" },
				preferences: { path: "", present: false, statusText: "", pathLabel: "" },
				busy: false
			}
		}
	}

	function settingsModelRow(kind) {
		const data = root.settingsData
		const models = data && data.models ? data.models : []
		for (let i = 0; i < models.length; i++) {
			if (models[i].kind === kind)
				return models[i]
		}
		return { kind: kind, label: kind, installed: false, statusText: "", path: "" }
	}

	Connections {
		target: controller
		function onLanguageChanged() {
			root.langRev++
		}
		function onSettingsUiChanged() {
			root.settingsRev++
			root.reloadSettingsData()
		}
	}

	onLightThemeChanged: if (controller) controller.setPreviewTheme(root.lightTheme)
	menuBar: MenuBar {
		objectName: "helpMenuBar"
		Menu {
			title: root.t("menu.settings")
			objectName: "settingsMenu"
			Action {
				objectName: "downloadAllModelsAction"
				text: root.t("menu.settings.download_all")
				onTriggered: if (controller) controller.confirmDownloadAllModels()
			}
			Action {
				objectName: "resetCacheAction"
				text: root.t("menu.settings.reset_cache")
				onTriggered: if (controller) controller.confirmClearCache()
			}
			Action {
				objectName: "resetPreferencesAction"
				text: root.t("menu.settings.reset_preferences")
				onTriggered: if (controller) controller.confirmResetPreferences()
			}
			MenuSeparator {}
			Action {
				objectName: "settingsAction"
				text: root.t("menu.settings.open")
				onTriggered: if (controller) controller.openSettings()
			}
		}
		Menu {
			title: root.t("menu.help")
			objectName: "helpMenu"
			Action {
				objectName: "aboutAction"
				text: root.t("menu.about")
				onTriggered: if (controller) controller.openAbout()
			}
			Action {
				objectName: "checkUpdatesAction"
				text: root.t("menu.check_updates")
				onTriggered: if (controller) controller.checkForUpdates()
			}
			Menu {
				title: root.t("menu.language")
				objectName: "languageMenu"
				Action {
					text: root.t("menu.language.en")
					checkable: true
					checked: controller && controller.language === "en"
					onTriggered: if (controller) controller.setLanguage("en")
				}
				Action {
					text: root.t("menu.language.es")
					checkable: true
					checked: controller && controller.language === "es"
					onTriggered: if (controller) controller.setLanguage("es")
				}
			}
		}
	}

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
		optPersist.checked = !!draft.persist_options
		syncContentDependentOptions()
		syncingOptions = false
	}

	function resetOptionsDraft() {
		if (!controller)
			return
		syncingOptions = true
		const draft = JSON.parse(controller.defaultOptionsJson())
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
		// OCR / transcribe / semantic_image enabled bindings also watch capabilitiesJson.
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
			include_subdirectories: optSubdirs.checked,
			persist_options: optPersist.checked
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
		fltPersist.checked = !!draft.persist_filters
		syncingFilters = false
		validateFiltersDraft()
	}

	function resetFiltersDraft() {
		if (!controller)
			return
		syncingFilters = true
		const draft = JSON.parse(controller.defaultFiltersJson())
		fltTopFiles.text = draft.top_files ?? ""
		fltMaxMatches.text = draft.max_matches ?? "50"
		fltThreshold.text = draft.threshold ?? "35"
		fltVisualMin.text = draft.semantic_image_threshold ?? "18"
		fltSpeechMin.text = draft.transcribe_threshold ?? "25"
		fltDocSize.text = draft.size_limits ? draft.size_limits.text_mib : "100"
		fltOcrSize.text = draft.size_limits ? draft.size_limits.ocr_mib : "50"
		fltMediaSize.text = draft.size_limits ? draft.size_limits.transcribe_mib : "500"
		syncingFilters = false
		validateFiltersDraft()
	}

	function filtersDraftPayload() {
		return JSON.stringify({
			top_files: fltTopFiles.text,
			max_matches: fltMaxMatches.text,
			threshold: fltThreshold.text,
			semantic_image_threshold: fltVisualMin.text,
			transcribe_threshold: fltSpeechMin.text,
			size_limits: {
				text_mib: fltDocSize.text,
				ocr_mib: fltOcrSize.text,
				transcribe_mib: fltMediaSize.text
			},
			persist_filters: fltPersist.checked
		})
	}

	function validateFiltersDraft() {
		if (!controller || syncingFilters || !filtersError)
			return
		const err = controller.validateFiltersJson(filtersDraftPayload())
		if (err) {
			filtersError.text = err
			filtersError.visible = true
			filtersDraftValid = false
		} else {
			filtersError.text = ""
			filtersError.visible = false
			filtersDraftValid = true
		}
	}

	function pushFiltersToController() {
		if (!controller || syncingFilters)
			return ""
		return controller.applyFiltersJson(filtersDraftPayload())
	}

	function showHelp(key) {
		helpTitle.text = key
		helpBody.text = controller ? controller.helpText(key) : ""
		helpDialog.title = root.t("help.dialog_title")
		helpDialog.open()
	}

	function showUnavailable(key) {
		helpTitle.text = key
		helpBody.text = controller ? controller.unavailableReason(key) : ""
		helpDialog.title = root.t("options.unavailable_title")
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
		ToolTip.text: root.t("gui.about_setting")
		onClicked: showHelp(helpKey)
	}

	component WarningButton: ToolButton {
		property string featureKey: ""
		text: "!"
		flat: true
		implicitWidth: 28
		implicitHeight: 28
		font.bold: true
		// Depend on capabilitiesJson so visibility refreshes after async probe.
		visible: controller && featureKey.length > 0 && controller.capabilitiesJson.length > 0
			&& !controller.isFeatureEnabled(featureKey)
		palette.buttonText: root.lightTheme ? "#9a6700" : "#e0a060"
		ToolTip.visible: hovered
		ToolTip.text: root.t("options.unavailable_tooltip")
		onClicked: showUnavailable(featureKey)
	}

	component TermRow: RowLayout {
		property int termIndex: 0
		property real trailingReserve: 0
		property real sideInset: 8
		// Capture ApplicationWindow before Repeater teardown; `root` is
		// undefined while a removed delegate is destroyed.
		readonly property var appWindow: root
		readonly property var termRow: termIndex >= 0 && termIndex < termModel.count
			? termModel.get(termIndex) : null
		spacing: 4
		ComboBox {
			visible: termIndex > 0
			model: 2
			currentIndex: termRow && termRow.join === "and" ? 1 : 0
			displayText: appWindow.t(currentIndex === 1 ? "gui.join.and" : "gui.join.or")
			delegate: ItemDelegate {
				required property int index
				width: parent ? parent.width : 80
				text: appWindow.t(index === 1 ? "gui.join.and" : "gui.join.or")
			}
			onActivated: {
				if (!termRow)
					return
				termModel.setProperty(termIndex, "join", currentIndex === 1 ? "and" : "or")
				appWindow.syncTermRows()
			}
		}
		TextField {
			id: termField
			Layout.fillWidth: true
			text: termRow ? termRow.term : ""
			placeholderText: appWindow.t("gui.term_placeholder")
			leftPadding: sideInset
			rightPadding: sideInset + trailingReserve
			onTextChanged: {
				if (!termRow)
					return
				termModel.setProperty(termIndex, "term", text)
				appWindow.syncTermRows()
			}
			Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
		}
		readonly property real fieldHeight: termField.height
		SecondaryButton {
			text: "−"
			visible: termModel.count > 1
			onClicked: {
				const idx = termIndex
				if (idx < 0 || idx >= termModel.count)
					return
				const sync = appWindow.syncTermRows
				termModel.remove(idx)
				Qt.callLater(sync)
			}
		}
	}

	FolderDialog {
		id: folderDialog
		onAccepted: {
			if (controller) {
				// QUrl.toString() returns "file:///C:/path" on Windows and
				// "file:///home/user" on Unix.  Strip the scheme correctly so
				// the result is always a native absolute path.
				var raw = selectedFolder.toString()
				// Windows: file:///C:/... → C:/...
				var path = raw.replace(/^file:\/\/\/([A-Za-z]:)/, "$1")
				// Unix absolute: file:///home/... → /home/...
				path = path.replace(/^file:\/\//, "")
				controller.path = path
			}
		}
	}

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 8
		spacing: 8

		ScrollView {
			id: mainScroll
			Layout.fillWidth: true
			Layout.fillHeight: true
			clip: true
			ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
			readonly property bool scrollNeeded: contentHeight > height + 1
			ScrollBar.vertical.policy: scrollNeeded ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff

			ColumnLayout {
				id: mainContent
				width: mainScroll.availableWidth
				height: Math.max(implicitHeight, mainScroll.availableHeight)
				spacing: 8

				GroupBox {
					title: root.t("gui.section.where")
					Layout.fillWidth: true
					RowLayout {
						anchors.fill: parent
						SecondaryButton {
							objectName: "browseButton"
							text: root.t("gui.browse")
							onClicked: folderDialog.open()
						}
						TextField {
							id: pathField
							objectName: "pathField"
							Layout.fillWidth: true
							placeholderText: root.t("gui.path_placeholder")
							text: controller ? controller.path : ""
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

				RowLayout {
					id: whatHowRow
					Layout.fillWidth: true
					Layout.alignment: Qt.AlignTop
					spacing: 8

					// Wrapper owns Layout width/height so Material GroupBox
					// implicitWidth (content ↔ chrome) cannot loop.
					Item {
						id: whatWrapper
						Layout.fillWidth: true
						Layout.preferredWidth: 1
						Layout.alignment: Qt.AlignTop
						readonly property real maxBodyHeight: 220
						readonly property real chromeHeight: whatGroup.topPadding + whatGroup.bottomPadding
						readonly property real desiredHeight: Math.min(
							maxBodyHeight + chromeHeight,
							whatBody.implicitHeight + chromeHeight
						)
						Layout.maximumHeight: maxBodyHeight + chromeHeight
						Layout.preferredHeight: desiredHeight
						implicitWidth: 100
						implicitHeight: desiredHeight

						GroupBox {
							id: whatGroup
							title: root.t("gui.section.what")
							anchors.fill: parent
							// Material computes implicitWidth from fill-anchored
							// content (loops). Actual size comes from whatWrapper.
							implicitWidth: 1
							implicitHeight: 1
							ScrollView {
								id: whatScroll
								anchors.fill: parent
								// Only clip when scrolling — otherwise Material's
								// outlined floating label gets cut by the viewport.
								clip: contentHeight > height + 1
								ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
								ScrollBar.vertical.policy: contentHeight > height + 1
									? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
								contentWidth: width
								ColumnLayout {
									id: whatBody
									width: whatScroll.width
									spacing: 4
									// Breathing room for Material outlined TextField
									// floating labels / focus rings.
									readonly property real fieldInset: 10
									RowLayout {
										Layout.fillWidth: true
										Layout.leftMargin: whatBody.fieldInset
										Layout.rightMargin: whatBody.fieldInset
										Layout.topMargin: 12
										Layout.bottomMargin: 4
										spacing: 4
										StackLayout {
											id: queryModeStack
											Layout.fillWidth: true
											Layout.fillHeight: false
											currentIndex: modeBox.currentIndex
											Layout.preferredHeight: currentIndex === 0
												? simpleQuery.implicitHeight
												: (currentIndex === 1 ? multiTermColumn.implicitHeight : advancedQuery.implicitHeight)
											TextField {
												id: simpleQuery
												objectName: "simpleQueryField"
												Layout.fillWidth: true
												Layout.fillHeight: false
												Layout.preferredHeight: implicitHeight
												placeholderText: root.t("gui.search_placeholder")
												text: controller ? controller.simpleQuery : ""
												onTextChanged: if (controller) controller.simpleQuery = text
												Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
											}
											ColumnLayout {
												id: multiTermColumn
												spacing: 2
												width: parent.width
												Repeater {
													id: multiTermRepeater
													model: termModel.count
													delegate: TermRow {
														termIndex: index
														Layout.fillWidth: true
														width: parent.width
													}
												}
												SecondaryButton {
													text: root.t("gui.add_term")
													onClicked: {
														termModel.append({ term: "", join: "or" })
														root.syncTermRows()
													}
												}
											}
											TextField {
												id: advancedQuery
												objectName: "advancedQueryField"
												Layout.fillWidth: true
												Layout.fillHeight: false
												Layout.preferredHeight: implicitHeight
												placeholderText: root.t("gui.advanced_placeholder")
												text: controller ? controller.advancedQuery : ""
												onTextChanged: if (controller) controller.advancedQuery = text
												Keys.onReturnPressed: if (controller && controller.canSearch) controller.startSearch()
											}
										}
										AccentButton {
											id: searchButton
											objectName: "searchButton"
											// Stretch-to-field is a Fluent/Windows look. On macOS (and
											// Linux Material) the native button is taller than the field;
											// forcing matchHeight clips the bevel and mis-centres the label.
											readonly property bool stretchToField: Qt.platform.os === "windows"
											readonly property real matchHeight: {
												if (modeBox.currentIndex === 0)
													return simpleQuery.implicitHeight
												if (modeBox.currentIndex === 2)
													return advancedQuery.implicitHeight
												const row = multiTermRepeater.itemAt(0)
												return row && row.fieldHeight > 0 ? row.fieldHeight : simpleQuery.implicitHeight
											}
											Layout.alignment: stretchToField ? Qt.AlignTop : Qt.AlignVCenter
											Binding {
												target: searchButton
												property: "implicitHeight"
												value: searchButton.matchHeight
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "Layout.preferredHeight"
												value: searchButton.matchHeight
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "Layout.minimumHeight"
												value: searchButton.matchHeight
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "Layout.maximumHeight"
												value: searchButton.matchHeight
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "leftPadding"
												value: 12
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "rightPadding"
												value: 14
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "topPadding"
												value: 0
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											Binding {
												target: searchButton
												property: "bottomPadding"
												value: 0
												when: searchButton.stretchToField
												restoreMode: Binding.RestoreBinding
											}
											spacing: 8
											accent: controller ? controller.stale : true
											enabled: controller !== null && controller !== undefined && controller.canSearch
											focusPolicy: Qt.NoFocus
											text: root.t("gui.search")
											// Keep the style's own IconLabel: it paints the label, and
											// AccentButton leaves ``icon.color`` unassigned so the glyph
											// follows ``defaultIconColor`` (same colour as the dialogs' OK).
											icon.source: "images/search.svg"
											icon.width: 16
											icon.height: 16
											onClicked: if (controller) controller.startSearch()
										}
										ToolButton {
											objectName: "queryIssueButton"
											text: "⚠"
											flat: true
											visible: controller && controller.queryIssue.length > 0
											implicitWidth: 28
											implicitHeight: 28
											Layout.alignment: searchButton.stretchToField ? Qt.AlignTop : Qt.AlignVCenter
											ToolTip.visible: hovered
											ToolTip.text: controller ? controller.queryIssue : ""
										}
										ToolButton {
											objectName: "searchWarningsButton"
											text: "⚠"
											flat: true
											visible: controller && controller.hasSearchWarnings
											implicitWidth: 28
											implicitHeight: 28
											Layout.alignment: searchButton.stretchToField ? Qt.AlignTop : Qt.AlignVCenter
											ToolTip.visible: hovered
											ToolTip.text: root.t("gui.search_warnings.tooltip")
											onClicked: searchWarningsDialog.open()
										}
									}
									Label {
										objectName: "queryPreview"
										visible: modeBox.currentIndex !== 0
										text: controller ? controller.queryPreview : ""
										opacity: 0.7
										wrapMode: Text.Wrap
										Layout.fillWidth: true
										Layout.leftMargin: whatBody.fieldInset
										Layout.rightMargin: whatBody.fieldInset
									}
								}
							}
						}
					}

					GroupBox {
						id: howGroup
						title: root.t("gui.section.how")
						Layout.fillWidth: false
						Layout.alignment: Qt.AlignTop
						ColumnLayout {
							id: howBody
							spacing: 4
							ComboBox {
								id: modeBox
								objectName: "queryModeBox"
								Layout.fillWidth: true
								implicitWidth: 140
								model: 3
								displayText: root.t(
									["gui.mode.simple", "gui.mode.multi", "gui.mode.advanced"][currentIndex]
								)
								delegate: ItemDelegate {
									required property int index
									width: modeBox.width
									text: root.t(
										["gui.mode.simple", "gui.mode.multi", "gui.mode.advanced"][index]
									)
								}
								onCurrentIndexChanged: {
									const modes = ["simple", "multi", "advanced"]
									if (controller)
										controller.queryMode = modes[currentIndex]
								}
							}
							RowLayout {
								id: howButtonRow
								spacing: 4
								readonly property real sharedButtonWidth: Math.max(
									optionsButton.implicitWidth,
									filtersButton.implicitWidth
								)
								SecondaryButton {
									id: optionsButton
									objectName: "optionsButton"
									text: root.t("gui.options")
									Layout.preferredWidth: howButtonRow.sharedButtonWidth
									ToolTip.visible: hovered && controller && controller.optionsSummary.length > 0
									ToolTip.text: controller ? controller.optionsSummary : ""
									onClicked: {
										loadOptionsFromController()
										optionsDialog.open()
									}
								}
								SecondaryButton {
									id: filtersButton
									objectName: "filtersButton"
									text: root.t("gui.filters")
									Layout.preferredWidth: howButtonRow.sharedButtonWidth
									ToolTip.visible: hovered && controller && controller.filtersSummary.length > 0
									ToolTip.text: controller ? controller.filtersSummary : ""
									onClicked: {
										loadFiltersFromController()
										filtersDialog.open()
									}
								}
							}
						}
					}
				}

		GroupBox {
			title: root.t("gui.section.results")
			Layout.fillWidth: true
			Layout.fillHeight: true
			Layout.minimumHeight: 280
			ColumnLayout {
				anchors.fill: parent
				spacing: 8
				Item {
					Layout.fillWidth: true
					Layout.fillHeight: true
					Layout.minimumHeight: 240
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
						Label { text: root.t("gui.results"); font.bold: true }
						RowLayout {
							Layout.fillWidth: true
							spacing: 0
							Label { text: root.t("gui.col.hash"); font.bold: true; Layout.preferredWidth: 36; padding: 6 }
							Label { text: root.t("gui.col.match"); font.bold: true; Layout.preferredWidth: 56; padding: 6 }
							Label { text: root.t("gui.col.path"); font.bold: true; Layout.fillWidth: true; padding: 6 }
							Label { text: root.t("gui.col.matched"); font.bold: true; Layout.preferredWidth: 88; padding: 6 }
						}
						Item {
							Layout.fillWidth: true
							Layout.fillHeight: true
							property int contextResultRow: -1
							ListView {
								id: resultsView
								objectName: "resultsView"
								anchors.fill: parent
								clip: true
								reuseItems: true
								cacheBuffer: 200
								model: controller ? controller.resultsModel : null
								currentIndex: controller ? controller.selectedResult : -1
								ScrollBar.vertical: ScrollBar {
									objectName: "resultsScrollBar"
									policy: ScrollBar.AlwaysOn
									visible: resultsView.count > 0
										&& resultsView.contentHeight > resultsView.height + 1
								}
								delegate: Item {
									id: resultRow
									required property int index
									required property string score
									required property string path
									required property string labels
									width: resultsView.width
									// Fixed height avoids per-row implicitHeight measure storms while streaming.
									height: 28
									Rectangle {
										anchors.fill: parent
										color: resultsView.currentIndex === resultRow.index
											? palette.highlight
											: (resultRow.index % 2 === 0
												? (palette.alternateBase && palette.alternateBase !== palette.base
													? palette.alternateBase
													: Qt.rgba(palette.base.r, palette.base.g, palette.base.b, 0.85))
												: palette.base)
									}
									RowLayout {
										id: resultRowLayout
										anchors.fill: parent
										spacing: 0
										Label {
											text: String(resultRow.index + 1)
											Layout.preferredWidth: 36
											padding: 6
											elide: Text.ElideRight
											color: resultsView.currentIndex === resultRow.index ? palette.highlightedText : palette.text
										}
										Label {
											text: resultRow.score
											Layout.preferredWidth: 56
											padding: 6
											elide: Text.ElideRight
											color: resultsView.currentIndex === resultRow.index ? palette.highlightedText : palette.text
										}
										Label {
											text: resultRow.path
											Layout.fillWidth: true
											padding: 6
											elide: Text.ElideMiddle
											color: resultsView.currentIndex === resultRow.index ? palette.highlightedText : palette.text
										}
										Label {
											text: resultRow.labels
											Layout.preferredWidth: 88
											padding: 6
											elide: Text.ElideRight
											color: resultsView.currentIndex === resultRow.index ? palette.highlightedText : palette.text
										}
									}
									MouseArea {
										anchors.fill: parent
										acceptedButtons: Qt.LeftButton | Qt.RightButton
										onClicked: (mouse) => {
											controller.selectResult(resultRow.index)
											if (mouse.button === Qt.RightButton) {
												resultsView.parent.contextResultRow = resultRow.index
												resultContextMenu.popup()
											}
										}
										onDoubleClicked: controller.openResult(resultRow.index)
									}
								}
							}
							Menu {
								id: resultContextMenu
								MenuItem {
									text: root.t("gui.menu.open_file")
									onTriggered: controller.openResult(resultsView.parent.contextResultRow)
								}
								MenuItem {
									text: root.t("gui.menu.open_containing_folder")
									onTriggered: controller.openResultFolder(resultsView.parent.contextResultRow)
								}
								MenuItem {
									text: root.t("gui.menu.copy_path")
									onTriggered: controller.copyResultPath(resultsView.parent.contextResultRow)
								}
								MenuItem {
									text: root.t("gui.menu.copy_all_matches")
									onTriggered: controller.copyAllMatches(resultsView.parent.contextResultRow)
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
							Label { text: root.t("gui.matches_in_file"); font.bold: true }
							Item {
								Layout.fillWidth: true
								height: matchesHeader.implicitHeight
								clip: true
								RowLayout {
									id: matchesHeader
									x: -matchesView.contentX
									width: matchesView.contentWidth
									spacing: 0
									Label { text: root.t("gui.col.hash"); font.bold: true; Layout.preferredWidth: 36; padding: 6 }
									Label { text: root.t("gui.col.match"); font.bold: true; Layout.preferredWidth: 56; padding: 6 }
									Label { text: root.t("gui.col.location"); font.bold: true; Layout.preferredWidth: 120; padding: 6 }
									Label { text: root.t("gui.col.text"); font.bold: true; Layout.fillWidth: true; padding: 6 }
								}
							}
							TextMetrics {
								id: matchCharMetrics
								font.family: Qt.platform.os === "windows"
									? "Consolas"
									: (Qt.platform.os === "osx" ? "Menlo" : "monospace")
								text: "0"
							}
							ListView {
								id: matchesView
								objectName: "matchesView"
								Layout.fillWidth: true
								Layout.fillHeight: true
								clip: true
								cacheBuffer: 400
								flickableDirection: Flickable.HorizontalAndVerticalFlick
								model: controller ? controller.matchesModel : null
								readonly property int fixedColumnsWidth: 212
								readonly property int textPadding: 12
								contentWidth: Math.max(
									width,
									fixedColumnsWidth
										+ (controller && controller.matchesModel
											? matchCharMetrics.advanceWidth * controller.matchesModel.maxTextLength
											: 0)
										+ textPadding)
								ScrollBar.vertical: ScrollBar {
									objectName: "matchesScrollBar"
									policy: ScrollBar.AlwaysOn
									visible: matchesView.count > 0
										&& matchesView.contentHeight > matchesView.height + 1
								}
								ScrollBar.horizontal: ScrollBar {
									objectName: "matchesHScrollBar"
									policy: ScrollBar.AsNeeded
									visible: matchesView.count > 0
										&& matchesView.contentWidth > matchesView.width + 1
								}
								delegate: Item {
									id: matchRow
									required property int index
									required property string score
									required property string location
									required property string text
									required property int lineNumber
									width: matchesView.contentWidth
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
											font.family: Qt.platform.os === "windows"
												? "Consolas"
												: (Qt.platform.os === "osx" ? "Menlo" : "monospace")
											Layout.fillWidth: true
											padding: 6
											wrapMode: Text.NoWrap
										}
									}
									MouseArea {
										anchors.fill: parent
										acceptedButtons: Qt.LeftButton | Qt.RightButton
										onClicked: (mouse) => {
											if (mouse.button === Qt.RightButton)
												matchMenu.popup()
											else if (matchRow.lineNumber > 0 && controller)
												controller.revealPreviewLine(matchRow.lineNumber)
										}
									}
									Menu {
										id: matchMenu
										MenuItem { text: root.t("gui.menu.copy_line"); onTriggered: controller.copyMatchLine(matchRow.index) }
										MenuItem { text: root.t("gui.menu.copy_location"); onTriggered: controller.copyMatchLocation(matchRow.index) }
									}
								}
							}
						}
					}
					Frame {
						SplitView.fillHeight: true
						objectName: "previewFrame"
						function scrollPreviewToLine(line) {
							if (line <= 0)
								return
							var flick = previewScroll.contentItem
							if (!flick)
								return
							var lineHeight = controller && controller.previewLineHeight > 0
								? controller.previewLineHeight
								: previewTextArea.font.pixelSize
							flick.contentY = Math.max(0, (line - 1) * lineHeight)
						}
						Connections {
							target: controller
							function onPreviewScrollLineChanged() {
								scrollPreviewToLine(controller.previewScrollLine)
							}
						}
					Shortcut {
						sequences: [StandardKey.Find]
						enabled: controller ? controller.previewHasFile : false
						onActivated: controller.openPreviewFind()
					}
						Shortcut {
							sequence: "F3"
							enabled: controller ? controller.previewFindOpen : false
							onActivated: controller.previewFindNext()
						}
						Shortcut {
							sequence: "Shift+F3"
							enabled: controller ? controller.previewFindOpen : false
							onActivated: controller.previewFindPrevious()
						}
						ColumnLayout {
							anchors.fill: parent
							RowLayout {
								Layout.fillWidth: true
								spacing: 6
								Label {
									id: previewFilePathLabel
									objectName: "previewFilePath"
									text: controller ? controller.previewFilePath : ""
									elide: Text.ElideRight
									wrapMode: Text.NoWrap
									Layout.fillWidth: true
									ToolTip.visible: previewFilePathHover.hovered && (controller ? controller.previewFilePath.length > 0 : false)
									ToolTip.text: controller ? controller.previewFilePath : ""
									HoverHandler {
										id: previewFilePathHover
									}
								}
								Label {
									objectName: "previewContentType"
									visible: controller && controller.previewContentType.length > 0
									text: controller ? controller.previewContentType : ""
									elide: Text.ElideRight
									wrapMode: Text.NoWrap
									opacity: 0.85
									ToolTip.visible: previewContentTypeHover.hovered && visible
									ToolTip.text: root.t("gui.preview.content_type")
									HoverHandler {
										id: previewContentTypeHover
									}
								}
								Label {
									objectName: "previewHeader"
									text: controller ? controller.previewHeader : ""
									elide: Text.ElideRight
									wrapMode: Text.NoWrap
								}
							}
							RowLayout {
								id: findBar
								visible: controller ? controller.previewFindOpen : false
								onVisibleChanged: if (visible) findField.forceActiveFocus()
								TextField {
									id: findField
									Layout.fillWidth: true
									placeholderText: root.t("gui.preview.find_placeholder")
									text: controller ? controller.previewFindQuery : ""
									onTextEdited: if (controller) controller.setPreviewFindQuery(text)
									onAccepted: if (controller) controller.previewFindNext()
									Keys.onEscapePressed: if (controller) controller.closePreviewFind()
								}
								CheckBox {
									text: root.t("gui.preview.find_approximate")
									checked: controller ? controller.previewFindApproximate : false
									onToggled: if (controller) controller.setPreviewFindApproximate(checked)
								}
								ToolButton {
									text: root.t("gui.preview.find_previous")
									onClicked: if (controller) controller.previewFindPrevious()
								}
								ToolButton {
									text: root.t("gui.preview.find_next")
									onClicked: if (controller) controller.previewFindNext()
								}
								Label {
									text: controller ? controller.previewFindStatus : ""
									Layout.preferredWidth: 70
									elide: Text.ElideRight
								}
								ToolButton {
									text: root.t("gui.preview.find_close")
									onClicked: if (controller) controller.closePreviewFind()
								}
							}
							RowLayout {
								Layout.fillWidth: true
								Layout.fillHeight: true
								spacing: 0
								Item {
									id: gutter
									objectName: "previewGutter"
									visible: controller && controller.previewLineCount > 0
									Layout.fillHeight: true
									Layout.preferredWidth: gutterText.implicitWidth + 12
									clip: true
									readonly property var flick: previewScroll.contentItem
									Text {
										id: gutterText
										objectName: "previewGutterText"
										width: gutter.width - 12
										y: gutter.flick ? previewTextArea.topPadding - gutter.flick.contentY : 0
										font: previewTextArea.font
										color: controller ? controller.previewGutterColor : palette.text
										horizontalAlignment: Text.AlignRight
										text: controller ? controller.previewGutterText : ""
									}
									WheelHandler {
										onWheel: (event) => {
											if (!gutter.flick || !controller)
												return
											const step = Math.max(1, controller.previewLineHeight) * 3 * (event.angleDelta.y / 120)
											const maxY = Math.max(0, gutter.flick.contentHeight - gutter.flick.height)
											gutter.flick.contentY = Math.max(0, Math.min(maxY, gutter.flick.contentY - step))
										}
									}
								}
								ScrollView {
									id: previewScroll
									objectName: "previewScroll"
									Layout.fillWidth: true
									Layout.fillHeight: true
									clip: true
									// Keep the *default* attached bars (correctly anchored). Replacing
									// ScrollBar.vertical with a bare ScrollBar {} drops Qt's anchors and
									// parks the bar at (0,0) — looking "misplaced" over the text/gutter.
									readonly property bool needsVScroll: previewTextArea.length > 0
										&& previewTextArea.contentHeight > previewScroll.availableHeight + 1
									readonly property bool needsHScroll: previewTextArea.length > 0
										&& previewTextArea.contentWidth > previewScroll.availableWidth + 1
									ScrollBar.vertical.policy: needsVScroll ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
									ScrollBar.horizontal.policy: needsHScroll ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
									TextArea {
										id: previewTextArea
										objectName: "previewText"
										readOnly: true
										verticalAlignment: TextEdit.AlignTop
										wrapMode: TextEdit.NoWrap
										textFormat: TextEdit.PlainText
										font.family: Qt.platform.os === "windows"
											? "Consolas"
											: (Qt.platform.os === "osx" ? "Menlo" : "monospace")
										// Content is owned by Python via attachPreviewDocument / setPlainText.
										selectByMouse: true
										Component.onCompleted: if (controller) controller.attachPreviewDocument(previewTextArea.textDocument)
										MouseArea {
											anchors.fill: parent
											acceptedButtons: Qt.RightButton
											onClicked: previewMenu.popup()
										}
									}
								}
							}
							Label {
								objectName: "previewFooter"
								visible: controller && controller.previewFooter.length > 0
								text: controller ? controller.previewFooter : ""
								opacity: 0.75
								Layout.fillWidth: true
								wrapMode: Text.WordWrap
							}
							Menu {
								id: previewMenu
								MenuItem { text: root.t("gui.menu.open_file"); enabled: controller ? controller.previewHasFile : false; onTriggered: controller.openPreviewFile() }
								MenuItem { text: root.t("gui.menu.open_containing_folder"); enabled: controller ? controller.previewHasFile : false; onTriggered: controller.openPreviewFolder() }
								MenuSeparator {}
								MenuItem { text: root.t("gui.menu.copy"); enabled: previewTextArea.selectedText.length > 0; onTriggered: previewTextArea.copy() }
								MenuItem { text: root.t("gui.menu.select_all"); onTriggered: previewTextArea.selectAll() }
								MenuItem { text: root.t("gui.menu.find"); onTriggered: controller.openPreviewFind() }
							}
						}
					}
				}
			}
		}
		}
		}

		GroupBox {
			title: root.t("gui.section.progress")
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
					indeterminate: controller ? controller.progressIndeterminate : false
					value: controller ? controller.progress : 0
				}
				Label {
					objectName: "progressPercent"
					visible: controller && !controller.progressIndeterminate
					text: (controller ? Math.round(controller.progress) : 0) + "%"
					Layout.preferredWidth: 48
					horizontalAlignment: Text.AlignRight
				}
				Label {
					objectName: "progressCount"
					visible: controller && controller.progressCount.length > 0
					text: controller ? controller.progressCount : ""
					Layout.preferredWidth: 88
					elide: Text.ElideRight
					horizontalAlignment: Text.AlignRight
				}
				Label {
					objectName: "statusLabel"
					text: {
						if (!controller)
							return ""
						var spin = controller.activitySpinner
						return spin.length > 0 ? (spin + " " + controller.status) : controller.status
					}
					Layout.preferredWidth: 280
					elide: Text.ElideRight
				}
				SecondaryButton {
					objectName: "cancelSearchButton"
					text: root.t("gui.cancel")
					visible: controller && controller.searching
					onClicked: controller.cancelSearch()
				}
			}
		}
			}
		}
	}

	Dialog {
		id: optionsDialog
		objectName: "optionsDialog"
		title: root.t("gui.options.title")
		modal: true
		anchors.centerIn: parent
		width: 520
		implicitWidth: 520
		height: Math.min(620, parent.height - 40)
		onAboutToShow: {
			optionsError.text = ""
			optionsError.visible = false
			if (controller)
				controller.refreshCapabilities()
			loadOptionsFromController()
		}
		footer: SrxyDialogFooter {
			defaultButton: optionsOkButton
			SecondaryButton {
				text: root.t("common.cancel")
				onClicked: optionsDialog.reject()
			}
			AccentButton {
				id: optionsOkButton
				objectName: "optionsOkButton"
				text: root.t("common.ok")
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
			anchors.fill: parent
			clip: true
			ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
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
					text: root.t("gui.options.where")
					font.bold: true
				}
			RowLayout {
				StyledCheckBox {
					id: optNames
					objectName: "optNames"
					text: root.t("gui.options.file_names")
					checked: true
					onCheckedChanged: if (!syncingOptions) syncContentDependentOptions()
				}
				InfoButton { helpKey: "search_names" }
			}
			RowLayout {
				StyledCheckBox {
					id: optContents
					objectName: "optContents"
					text: root.t("gui.options.file_contents")
					checked: true
					onCheckedChanged: if (!syncingOptions) syncContentDependentOptions()
				}
				InfoButton { helpKey: "search_contents" }
			}

				Label {
					text: root.t("gui.options.how")
					font.bold: true
					Layout.topMargin: 8
				}
				Label {
					text: root.t("gui.options.classic_hint")
					opacity: 0.7
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
			RowLayout {
				StyledCheckBox {
					id: optDocsTags
					text: root.t("gui.options.docs_tags")
					checked: true
				}
				InfoButton { helpKey: "search_docs_tags" }
			}
			RowLayout {
				StyledCheckBox {
					id: optSemantic
					text: root.t("gui.options.semantic")
					enabled: !!(controller && controller.capabilitiesJson)
						&& controller.isFeatureEnabled("semantic")
				}
				WarningButton { featureKey: "semantic" }
				InfoButton { helpKey: "semantic"; enabled: true }
			}
			RowLayout {
				StyledCheckBox {
					id: optOcr
					objectName: "optOcr"
					text: root.t("gui.options.ocr")
					enabled: optContents.checked
						&& !!(controller && controller.capabilitiesJson)
						&& controller.isFeatureEnabled("ocr")
				}
				WarningButton { featureKey: "ocr" }
				InfoButton { helpKey: "ocr"; enabled: true }
			}
			RowLayout {
				StyledCheckBox {
					id: optTranscribe
					text: root.t("gui.options.transcribe")
					enabled: optContents.checked
						&& !!(controller && controller.capabilitiesJson)
						&& controller.isFeatureEnabled("transcribe")
				}
				WarningButton { featureKey: "transcribe" }
				InfoButton { helpKey: "transcribe"; enabled: true }
			}
			RowLayout {
				StyledCheckBox {
					id: optSemanticImage
					text: root.t("gui.options.semantic_image")
					enabled: optContents.checked
						&& !!(controller && controller.capabilitiesJson)
						&& controller.isFeatureEnabled("semantic_image")
				}
				WarningButton { featureKey: "semantic_image" }
				InfoButton { helpKey: "semantic_image"; enabled: true }
			}

				Label {
					text: root.t("gui.options.which_files")
					font.bold: true
					Layout.topMargin: 8
				}
			RowLayout {
				StyledCheckBox { id: optSubdirs; text: root.t("gui.options.subdirs"); checked: true }
				InfoButton { helpKey: "include_subdirectories" }
			}
			RowLayout {
				StyledCheckBox { id: optArchives; text: root.t("gui.options.archives") }
				InfoButton { helpKey: "include_archives" }
			}
				Label {
					text: root.t("gui.options.noisy")
					font.bold: true
					Layout.leftMargin: 12
					Layout.topMargin: 4
					opacity: 0.75
				}
			RowLayout {
				Layout.leftMargin: 12
				StyledCheckBox { id: optHidden; text: root.t("gui.options.hidden") }
				InfoButton { helpKey: "include_hidden" }
			}
			RowLayout {
				Layout.leftMargin: 12
				StyledCheckBox { id: optNoise; text: root.t("gui.options.noise") }
				InfoButton { helpKey: "include_noise" }
			}
			RowLayout {
				Layout.leftMargin: 12
				StyledCheckBox { id: optNoiseFiles; text: root.t("gui.options.noise_files") }
				InfoButton { helpKey: "include_noise_files" }
			}
			RowLayout {
				Layout.leftMargin: 12
				StyledCheckBox { id: optMatchSkippedNames; text: root.t("gui.options.match_skipped") }
				InfoButton { helpKey: "match_skipped_names" }
			}
				Label {
					text: root.t("gui.options.binary_hint")
					wrapMode: Text.WordWrap
					opacity: 0.7
					Layout.fillWidth: true
					Layout.topMargin: 4
				}
				StyledCheckBox {
					id: optPersist
					objectName: "optPersist"
					text: root.t("gui.options.persist")
					Layout.topMargin: 12
				}
				SecondaryButton {
					id: optReset
					objectName: "optReset"
					text: root.t("gui.options.reset")
					onClicked: resetOptionsDraft()
				}
			}
		}
	}

	Dialog {
		id: filtersDialog
		objectName: "filtersDialog"
		title: root.t("gui.filters.title")
		modal: true
		anchors.centerIn: parent
		width: 480
		implicitWidth: 480
		onAboutToShow: {
			filtersError.text = ""
			filtersError.visible = false
			loadFiltersFromController()
		}
		footer: SrxyDialogFooter {
			defaultButton: filtersOkButton
			SecondaryButton {
				text: root.t("common.cancel")
				onClicked: filtersDialog.reject()
			}
			AccentButton {
				id: filtersOkButton
				objectName: "filtersOkButton"
				text: root.t("common.ok")
				enabled: root.filtersDraftValid
				onClicked: {
					if (!root.filtersDraftValid)
						return
					const err = pushFiltersToController()
					if (err) {
						filtersError.text = err
						filtersError.visible = true
						root.filtersDraftValid = false
						return
					}
					filtersError.visible = false
					filtersDialog.accept()
				}
			}
		}

		ColumnLayout {
			width: filtersDialog.availableWidth - 24
			spacing: 6

			Label {
				id: filtersError
				objectName: "filtersError"
				visible: false
				color: "#c62828"
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
			}

		GridLayout {
			columns: 3
			columnSpacing: 8
			rowSpacing: 6
			Layout.fillWidth: true

			Label { text: root.t("gui.filters.max_results") }
			TextField {
				id: fltTopFiles
				objectName: "fltTopFiles"
				placeholderText: root.t("gui.filters.max_results_ph")
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "top_files" }

			Label { text: root.t("gui.filters.hits_per_file") }
			TextField {
				id: fltMaxMatches
				objectName: "fltMaxMatches"
				text: "50"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "max_matches" }

			Label { text: root.t("gui.filters.min_match") }
			TextField {
				id: fltThreshold
				objectName: "fltThreshold"
				text: "35"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "threshold" }

			Label { text: root.t("gui.filters.visual_min") }
			TextField {
				id: fltVisualMin
				objectName: "fltVisualMin"
				text: "18"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "semantic_image_threshold" }

			Label { text: root.t("gui.filters.speech_min") }
			TextField {
				id: fltSpeechMin
				objectName: "fltSpeechMin"
				text: "25"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "transcribe_threshold" }

			Label { text: root.t("gui.filters.doc_mib") }
			TextField {
				id: fltDocSize
				objectName: "fltDocSize"
				text: "100"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "text_mib" }

			Label { text: root.t("gui.filters.ocr_mib") }
			TextField {
				id: fltOcrSize
				objectName: "fltOcrSize"
				text: "50"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "ocr_mib" }

			Label { text: root.t("gui.filters.media_mib") }
			TextField {
				id: fltMediaSize
				objectName: "fltMediaSize"
				text: "500"
				Layout.fillWidth: true
				onTextChanged: validateFiltersDraft()
			}
			InfoButton { helpKey: "transcribe_mib" }
		}
			StyledCheckBox {
				id: fltPersist
				objectName: "fltPersist"
				text: root.t("gui.filters.persist")
				Layout.topMargin: 12
			}
			SecondaryButton {
				id: fltReset
				objectName: "fltReset"
				text: root.t("gui.filters.reset")
				onClicked: resetFiltersDraft()
			}
		}
	}

	Dialog {
		id: helpDialog
		objectName: "helpDialog"
		title: root.t("help.dialog_title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(520, parent.width - 40)
		implicitWidth: 520
		contentWidth: availableWidth
		footer: SrxyDialogFooter {
			AccentButton {
				text: root.t("common.ok")
				onClicked: helpDialog.accept()
			}
		}
		ColumnLayout {
			width: helpDialog.availableWidth > 0 ? helpDialog.availableWidth - 24 : 480
			spacing: 8
			Label {
				id: helpTitle
				font.bold: true
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
				Layout.maximumWidth: helpDialog.availableWidth - 24
			}
			Label {
				id: helpBody
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
				Layout.maximumWidth: helpDialog.availableWidth - 24
				textFormat: Text.PlainText
			}
		}
	}

	Dialog {
		id: updateDialog
		objectName: "updateDialog"
		title: root.t("update.title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(520, parent.width - 40)
		// Drive open/close via Connections (not visible binding) — avoids macOS Dialog loops.
		closePolicy: controller && controller.updateBusy ? Popup.NoAutoClose : Popup.CloseOnEscape
		onClosed: if (controller) controller.closeUpdateDialog()
		footer: SrxyDialogFooter {
			defaultButton: updateYesButton
			SecondaryButton {
				text: root.t("common.cancel")
				visible: controller && controller.updateDialogMode === "prompt"
				onClicked: updateDialog.reject()
			}
			AccentButton {
				id: updateYesButton
				text: root.t("update.yes")
				visible: controller && controller.updateCanApply
				onClicked: if (controller) controller.applyUpdate()
			}
			SecondaryButton {
				text: root.t("update.ok")
				visible: controller && controller.updateDialogMode === "info"
				onClicked: updateDialog.accept()
			}
		}
		Label {
			wrapMode: Text.WordWrap
			width: parent ? parent.width : 480
			text: controller ? controller.updateMessage : ""
		}
	}

	Dialog {
		id: settingsDialog
		objectName: "settingsDialog"
		title: root.t("settings.title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(640, parent.width - 40)
		height: Math.min(560, parent.height - 40)
		// Drive open/close via Connections (not visible binding) — avoids macOS Dialog loops.
		onOpened: root.reloadSettingsData()
		onClosed: if (controller) controller.closeSettings()
		footer: SrxyDialogFooter {
			SecondaryButton {
				text: root.t("common.close")
				onClicked: settingsDialog.accept()
			}
		}
		BusyIndicator {
			objectName: "settingsBusyIndicator"
			anchors.centerIn: parent
			running: !!(root.settingsData && root.settingsData.loading)
			visible: running
		}
		ScrollView {
			anchors.fill: parent
			clip: true
			visible: !(root.settingsData && root.settingsData.loading)
			ColumnLayout {
				width: settingsDialog.availableWidth - 24
				spacing: 12

				Label {
					text: root.t("settings.section.models")
					font.bold: true
					Layout.fillWidth: true
				}

				SettingsModelRow {
					kind: "semantic_text"
					Layout.fillWidth: true
				}
				SettingsModelRow {
					kind: "semantic_image"
					Layout.fillWidth: true
				}
				SettingsModelRow {
					kind: "transcribe"
					Layout.fillWidth: true
				}
				SettingsModelRow {
					kind: "all"
					Layout.fillWidth: true
				}

				Label {
					text: root.t("settings.section.cache")
					font.bold: true
					Layout.topMargin: 8
					Layout.fillWidth: true
				}

				Label {
					text: root.settingsData && root.settingsData.cache
						? root.settingsData.cache.pathLabel
						: ""
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
				Label {
					text: root.settingsData && root.settingsData.cache
						? root.settingsData.cache.statusText
						: ""
					opacity: 0.75
					Layout.fillWidth: true
				}
				SecondaryButton {
					objectName: "settingsClearCache"
					text: root.t("settings.action.clear_cache")
					enabled: !!(root.settingsData && root.settingsData.cache
						&& root.settingsData.cache.present
						&& !root.settingsData.busy
						&& !root.settingsData.loading)
					Layout.alignment: Qt.AlignLeft
					onClicked: if (controller) controller.confirmClearCache()
				}

				Label {
					text: root.t("settings.section.preferences")
					font.bold: true
					Layout.topMargin: 8
					Layout.fillWidth: true
				}
				Label {
					text: root.settingsData && root.settingsData.preferences
						? root.settingsData.preferences.pathLabel
						: ""
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
				Label {
					text: root.settingsData && root.settingsData.preferences
						? root.settingsData.preferences.statusText
						: ""
					opacity: 0.75
					Layout.fillWidth: true
				}
				SecondaryButton {
					objectName: "settingsResetPreferences"
					text: root.t("settings.action.reset_preferences")
					enabled: !!(root.settingsData && root.settingsData.preferences
						&& root.settingsData.preferences.present
						&& !root.settingsData.loading)
					Layout.alignment: Qt.AlignLeft
					onClicked: if (controller) controller.confirmResetPreferences()
				}
			}
		}
	}

	Dialog {
		id: settingsConfirmDialog
		objectName: "settingsConfirmDialog"
		title: controller && controller.settingsConfirmTitle
			? controller.settingsConfirmTitle
			: root.t("settings.confirm.title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(480, parent.width - 40)
		closePolicy: Popup.NoAutoClose
		footer: SrxyDialogFooter {
			defaultButton: settingsConfirmAccept
			SecondaryButton {
				text: root.t("common.cancel")
				onClicked: settingsConfirmDialog.reject()
			}
			AccentButton {
				id: settingsConfirmAccept
				text: controller ? controller.settingsConfirmAcceptLabel : ""
				onClicked: settingsConfirmDialog.accept()
			}
		}
		Label {
			wrapMode: Text.WordWrap
			width: settingsConfirmDialog.availableWidth > 0
				? settingsConfirmDialog.availableWidth - 24
				: 456
			text: controller ? controller.settingsConfirmMessage : ""
		}
		onAccepted: if (controller) controller.acceptSettingsConfirm()
		onRejected: if (controller) controller.rejectSettingsConfirm()
	}

	Dialog {
		id: aboutDialog
		objectName: "aboutDialog"
		title: root.t("about.title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(560, parent.width - 40)
		height: Math.min(520, parent.height - 40)
		// Drive open/close via Connections (not visible binding) — avoids macOS Dialog loops.
		onClosed: if (controller) controller.closeAbout()
		footer: SrxyDialogFooter {
			AccentButton {
				text: root.t("common.ok")
				onClicked: aboutDialog.accept()
			}
		}
		ScrollView {
			anchors.fill: parent
			clip: true
			ColumnLayout {
				width: aboutDialog.availableWidth - 24
				spacing: 10
				Label {
					text: "srxy"
					font.pixelSize: 22
					font.bold: true
				}
				Label {
					text: controller
						? root.t("about.version").replace("{version}", controller.appVersion)
						: ""
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
				Label {
					text: root.t("about.license")
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
				}
				Label {
					text: root.t("about.links")
					font.bold: true
				}
				Label {
					textFormat: Text.RichText
					wrapMode: Text.WordWrap
					Layout.fillWidth: true
					text: controller
						? ("<a href=\"" + controller.pypiUrl + "\">" + root.t("about.pypi") + "</a> · "
							+ "<a href=\"" + controller.githubUrl + "\">" + root.t("about.github") + "</a> · "
							+ "<a href=\"" + controller.websiteUrl + "\">" + root.t("about.website") + "</a>")
						: ""
					onLinkActivated: function(link) { Qt.openUrlExternally(link) }
					HoverHandler {
						cursorShape: parent.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
					}
				}
				Label {
					text: root.t("about.privacy_heading")
					font.bold: true
					Layout.topMargin: 8
				}
				TextEdit {
					readOnly: true
					selectByMouse: true
					wrapMode: TextEdit.Wrap
					textFormat: TextEdit.RichText
					text: controller ? controller.aboutPrivacyHtml : ""
					Layout.fillWidth: true
					color: palette.windowText
					onLinkActivated: function(link) { Qt.openUrlExternally(link) }
					HoverHandler {
						cursorShape: parent.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor
					}
				}
			}
		}
	}

	Dialog {
		id: downloadConfirmDialog
		objectName: "downloadConfirmDialog"
		title: root.t("gui.download_model")
		modal: true
		anchors.centerIn: parent
		width: Math.min(480, parent.width - 40)
		implicitWidth: 480
		contentWidth: availableWidth
		closePolicy: Popup.NoAutoClose
		footer: SrxyDialogFooter {
			defaultButton: downloadConfirmAccept
			SecondaryButton {
				text: root.t("common.cancel")
				onClicked: downloadConfirmDialog.reject()
			}
			AccentButton {
				id: downloadConfirmAccept
				text: root.t("settings.action.download")
				onClicked: downloadConfirmDialog.accept()
			}
		}
		Label {
			wrapMode: Text.WordWrap
			width: downloadConfirmDialog.availableWidth > 0
				? downloadConfirmDialog.availableWidth - 24
				: 456
			text: controller ? controller.downloadConfirmMessage : ""
		}
		onAccepted: if (controller) controller.acceptDownloadConfirm()
		onRejected: if (controller) controller.rejectDownloadConfirm()
	}

	Dialog {
		id: downloadProgressDialog
		objectName: "downloadProgressDialog"
		title: root.t("gui.downloading")
		modal: true
		anchors.centerIn: parent
		width: Math.min(420, parent.width - 40)
		implicitWidth: 420
		contentWidth: availableWidth
		closePolicy: Popup.NoAutoClose
		footer: SrxyDialogFooter {
			SecondaryButton {
				text: root.t("common.cancel")
				onClicked: downloadProgressDialog.reject()
			}
		}
		ColumnLayout {
			width: downloadProgressDialog.availableWidth > 0
				? downloadProgressDialog.availableWidth - 24
				: 396
			Label {
				text: controller ? controller.downloadStatus : ""
				wrapMode: Text.WordWrap
				Layout.fillWidth: true
				Layout.maximumWidth: downloadProgressDialog.availableWidth - 24
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
		id: searchWarningsDialog
		objectName: "searchWarningsDialog"
		title: root.t("gui.search_warnings.title")
		modal: true
		anchors.centerIn: parent
		width: Math.min(560, parent.width - 40)
		footer: SrxyDialogFooter {
			AccentButton {
				text: root.t("common.ok")
				onClicked: searchWarningsDialog.accept()
			}
		}
		ScrollView {
			anchors.fill: parent
			clip: true
			ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
			Label {
				wrapMode: Text.Wrap
				width: searchWarningsDialog.availableWidth - 24
				text: controller ? controller.searchWarnings : ""
			}
		}
	}

	Dialog {
		id: errorDialog
		objectName: "errorDialog"
		title: root.t("gui.error")
		modal: true
		anchors.centerIn: parent
		width: 420
		implicitWidth: 420
		footer: SrxyDialogFooter {
			AccentButton {
				text: root.t("common.ok")
				onClicked: errorDialog.accept()
			}
		}
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
		function onSettingsUiChanged() {
			if (controller && controller.settingsOpen)
				settingsDialog.open()
			else
				settingsDialog.close()
		}
		function onSettingsConfirmChanged() {
			if (controller && controller.settingsConfirmOpen)
				settingsConfirmDialog.open()
			else
				settingsConfirmDialog.close()
		}
		function onAboutUiChanged() {
			if (controller && controller.aboutOpen)
				aboutDialog.open()
			else
				aboutDialog.close()
		}
		function onUpdateUiChanged() {
			if (controller && controller.updateDialogOpen)
				updateDialog.open()
			else
				updateDialog.close()
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
			controller.setPreviewTheme(root.lightTheme)
			syncTermRows()
			loadOptionsFromController()
			loadFiltersFromController()
		}
	}
}
