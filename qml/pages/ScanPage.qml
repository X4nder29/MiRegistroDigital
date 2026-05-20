import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3 as QtDialogs
import "../components"

Item {
    id: root

    // ── Conexiones bridge ─────────────────────────────────────────────────────
    Connections {
        target: bridge
        function onPageAdded(index, b64, src) {
            grid.addPage(index, b64, src)
            statusLabel.text = grid.pageCount + " página(s)"
        }
        function onPageUpdated(index, b64) { grid.updateThumb(index, b64) }
        function onPageDeleted(index)      { grid.removePage(index) }
        function onScanDone()              { scanBtn.enabled = true; scanBtn.text = "Escanear"; progressBar.visible = false }
        function onImportDone()            { importBusy = false; progressBar.visible = false }
        function onImportProgress(cur, tot) {
            progressBar.visible = true
            progressBar.indeterminate = false
            progressBar.value = tot > 0 ? cur/tot : 0
            statusLabel.text = "Importando " + cur + "/" + tot
        }
        function onSourcesLoaded(srcs)     { sourcesModel.clear(); for (var s of srcs) sourcesModel.append({name: s}) }
        function onCutPointChanged(idx, v) { grid.setCut(idx, v) }
        function onOcrResult(idx, serial, conf) { grid.setSerial(idx, serial, conf) }
        function onAppError(msg)           { errorBanner.show(msg) }
    }

    property bool importBusy: false
    property bool scanning:   false

    // ── Diálogos ──────────────────────────────────────────────────────────────
    QtDialogs.FileDialog {
        id: imageDialog
        title:          "Seleccionar imágenes"
        selectMultiple: true
        nameFilters:    ["Imágenes (*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.webp)", "Todos (*.*)"]
        onAccepted: bridge.importFiles(fileUrls.map(u => u.toString()))
    }
    QtDialogs.FileDialog {
        id: pdfDialog
        title:          "Seleccionar PDF"
        selectMultiple: true
        nameFilters:    ["PDF (*.pdf)", "Todos (*.*)"]
        onAccepted: bridge.importFiles(fileUrls.map(u => u.toString()))
    }

    FullscreenImageDialog { id: fsDialog }

    ListModel { id: sourcesModel }

    // ── Layout ────────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Toolbar
        Rectangle {
            Layout.fillWidth: true
            height: 52
            color:  Theme.surface
            border.color: Theme.border
            border.width: 0
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }

            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                spacing: 10

                // Escáner
                GBtn {
                    id:        scanBtn
                    text:      "Escanear"
                    primary:   true
                    iconText:  "▶"
                    onClicked: {
                        scanBtn.text    = "Escaneando…"
                        scanBtn.enabled = false
                        progressBar.visible = true
                        progressBar.indeterminate = true
                        bridge.startScan(
                            sourcesCombo.currentText,
                            parseInt(dpiField.text) || 300,
                            colorCombo.currentText.toLowerCase()
                        )
                    }
                }

                ComboBox {
                    id:        sourcesCombo
                    model:     sourcesModel
                    textRole:  "name"
                    implicitWidth: 180; implicitHeight: 32
                    background: Rectangle { color: Theme.surface2; border.color: Theme.border; border.width:1; radius: Theme.radiusMD }
                    contentItem: GLabel { text: sourcesCombo.currentText; leftPadding: 8 }
                    Component.onCompleted: bridge.loadSources()
                }

                GLabel { text: "DPI:" ; secondary: true }
                GInput { id: dpiField; text: "300"; implicitWidth: 64 }

                ComboBox {
                    id:    colorCombo
                    model: ["Color","Grises","B/N"]
                    implicitWidth: 80; implicitHeight: 32
                    background: Rectangle { color: Theme.surface2; border.color: Theme.border; border.width:1; radius: Theme.radiusMD }
                    contentItem: GLabel { text: colorCombo.currentText; leftPadding: 8 }
                }

                GDivider { vertical: true; implicitHeight: 28; implicitWidth: 1 }

                GBtn { text: "🖼 Imágenes"; onClicked: imageDialog.open() }
                GBtn { text: "📄 PDF";      onClicked: pdfDialog.open()   }

                Item { Layout.fillWidth: true }

                GBtn {
                    text: "Registros Civiles"
                    onClicked: navRail.navigate("civil")
                }
                GBtn {
                    text: "Antecedentes"
                    onClicked: navRail.navigate("antecedentes")
                }
            }
        }

        // Barra de progreso
        GProgressBar {
            id:         progressBar
            Layout.fillWidth: true
            height:     3
            visible:    false
            indeterminate: true
        }

        // Grid de páginas
        PageGrid {
            id:               grid
            Layout.fillWidth:  true
            Layout.fillHeight: true

            onPageSelected:        function(idx) { correctionPanel.pageIndex = idx }
            onCutToggled:          function(idx) { bridge.toggleCut(idx) }
            onPageDeleted:         function(idx) { bridge.deletePage(idx) }
            onFullscreenRequested: function(idx) { fsDialog.pageIndex = idx; fsDialog.open() }
        }

        // Barra de estado
        Rectangle {
            Layout.fillWidth: true
            height: 24
            color:  Theme.surface
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                GLabel { id: statusLabel; text: "Sin páginas"; secondary: true; font.pixelSize: Theme.fontXS }
                Item { Layout.fillWidth: true }
                GLabel {
                    visible:  correctionPanel.pageIndex >= 0
                    text:     "Página seleccionada: " + (correctionPanel.pageIndex + 1)
                    secondary: true; font.pixelSize: Theme.fontXS
                }
            }
        }
    }

    // ── Panel de corrección (drawer derecho) ──────────────────────────────────
    Rectangle {
        id:      correctionPanel
        property int pageIndex: -1
        property real rotAngle: 0

        anchors { top: parent.top; right: parent.right; bottom: parent.bottom; topMargin: 52 }
        width:   200
        visible: pageIndex >= 0
        color:   Theme.surface
        border.color: Theme.border; border.width: 1

        ColumnLayout {
            anchors { fill: parent; margins: 14 }
            spacing: 12

            GLabel { text: "Corrección"; font.pixelSize: Theme.fontMD; font.bold: true }
            GDivider {}

            GBtn {
                Layout.fillWidth: true
                text: "Auto perspectiva"
                onClicked: bridge.autoCorrect(correctionPanel.pageIndex)
            }

            GLabel { text: "Rotación " + Math.round(correctionPanel.rotAngle) + "°"; secondary: true }
            Slider {
                id: rotSlider
                Layout.fillWidth: true
                from: -45; to: 45; value: 0; stepSize: 1
                onValueChanged: {
                    correctionPanel.rotAngle = value
                    if (correctionPanel.pageIndex >= 0)
                        bridge.rotateManual(correctionPanel.pageIndex, value)
                }
                background: Rectangle { width: rotSlider.availableWidth; height: 3; y: (rotSlider.height-3)/2; color: Theme.surface2; radius: 2
                    Rectangle { width: rotSlider.visualPosition * parent.width; height: 3; color: Theme.accentDim; radius: 2 }
                }
                handle: Rectangle { x: rotSlider.leftPadding + rotSlider.visualPosition*(rotSlider.availableWidth-12); y: (rotSlider.height-12)/2; width:12; height:12; radius:6; color: Theme.accent; border.color: Theme.border; border.width:1 }
            }

            GBtn {
                Layout.fillWidth: true
                text: "Restablecer"
                onClicked: { bridge.resetCorrection(correctionPanel.pageIndex); rotSlider.value = 0 }
            }

            GBtn {
                Layout.fillWidth: true
                text: "Ver completa"
                onClicked: { fsDialog.pageIndex = correctionPanel.pageIndex; fsDialog.open() }
            }

            Item { Layout.fillHeight: true }

            GBtn {
                Layout.fillWidth: true
                text: "✕ Cerrar"
                onClicked: correctionPanel.pageIndex = -1
            }
        }
    }

    // ── Banner de error ───────────────────────────────────────────────────────
    Rectangle {
        id: errorBanner
        property string msg: ""
        function show(m) { msg = m; visible = true; hideTimer.restart() }
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right; bottomMargin: 12; leftMargin: 12; rightMargin: 12 }
        height: 40; radius: Theme.radiusMD; color: Theme.surface2
        border.color: Theme.danger; border.width: 1
        visible: false
        GLabel { anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12 }; text: errorBanner.msg; secondary: true }
        Timer { id: hideTimer; interval: 4000; onTriggered: errorBanner.visible = false }
    }
}
