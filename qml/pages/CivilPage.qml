import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3 as QtDialogs
import "../components"

Item {
    id: root

    Connections {
        target: bridge
        function onPageAdded(index, b64, src) {
            tableModel.append({ idx: index, serial: "", conf: 0.0, status: "pendiente" })
        }
        function onOcrResult(index, serial, conf) {
            for (var i = 0; i < tableModel.count; i++) {
                if (tableModel.get(i).idx === index) {
                    tableModel.setProperty(i, "serial",  serial)
                    tableModel.setProperty(i, "conf",    conf)
                    tableModel.setProperty(i, "status",  serial ? (conf >= 0.7 ? "ok" : "bajo") : "sin_serial")
                }
            }
            updateSummary()
        }
        function onOcrAllDone()   { ocrBtn.enabled = true; ocrBtn.text = "OCR a todas las páginas"; updateSummary() }
        function onOcrError(idx, msg) {
            for (var i = 0; i < tableModel.count; i++)
                if (tableModel.get(i).idx === idx) { tableModel.setProperty(i, "status", "error"); break }
        }
        function onPageDeleted(index) {
            for (var i = tableModel.count-1; i >= 0; i--)
                if (tableModel.get(i).idx === index) { tableModel.remove(i); break }
            // Reindexar
            for (var j = 0; j < tableModel.count; j++) tableModel.setProperty(j, "idx", j)
            updateSummary()
        }
    }

    function updateSummary() {
        var ok = 0, pend = 0
        for (var i = 0; i < tableModel.count; i++) {
            var s = tableModel.get(i).status
            if (s === "ok") ok++; else pend++
        }
        summaryLabel.text = tableModel.count + " páginas · " + ok + " OK · " + pend + " pendientes"
    }

    ListModel { id: tableModel }

    QtDialogs.FileDialog {
        id: folderDlg
        title:        "Carpeta de destino"
        selectFolder: true
        onAccepted: folderField.text = fileUrl.toString().replace("file:///","")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header
        Rectangle {
            Layout.fillWidth: true; height: 52; color: Theme.surface
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }; spacing: 12
                GLabel { text: "Registros Civiles"; font.pixelSize: Theme.fontLG; font.bold: true }
                Item { Layout.fillWidth: true }
                GBtn {
                    id:      ocrBtn
                    text:    "OCR a todas las páginas"
                    primary: true
                    onClicked: {
                        ocrBtn.enabled = false
                        ocrBtn.text    = "Procesando…"
                        bridge.runOcrAll()
                    }
                }
            }
        }

        // Tabla
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            color: Theme.bg

            ListView {
                id: listView
                anchors { fill: parent; margins: 0 }
                model: tableModel
                clip:  true

                // Cabecera
                header: Rectangle {
                    width: listView.width; height: 32; color: Theme.surface
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border }
                    Row {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                        GLabel { width: 60;  text: "Página";    secondary: true; font.pixelSize: Theme.fontXS }
                        GLabel { width: 160; text: "Serial OCR"; secondary: true; font.pixelSize: Theme.fontXS }
                        GLabel { width: 80;  text: "Confianza"; secondary: true; font.pixelSize: Theme.fontXS }
                        GLabel {             text: "Estado";     secondary: true; font.pixelSize: Theme.fontXS }
                    }
                }

                delegate: Rectangle {
                    width: listView.width; height: 40
                    color: index % 2 === 0 ? Theme.bg : Theme.surface
                    required property int    idx
                    required property string serial
                    required property real   conf
                    required property string status
                    required property int    index

                    Row {
                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 12; right: parent.right; rightMargin: 12 }
                        spacing: 0

                        GLabel { width: 60;  text: (idx+1).toString(); secondary: true }

                        // Serial editable
                        TextInput {
                            width: 160
                            text:  serial
                            color: Theme.textPri
                            font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
                            selectByMouse: true
                            onEditingFinished: bridge.overrideSerial(idx, text)
                        }

                        GLabel {
                            width: 80
                            text: conf > 0 ? Math.round(conf*100) + "%" : "—"
                            color: conf >= 0.7 ? Theme.textPri : Theme.textSec
                        }

                        Text {
                            text: {
                                if (status === "ok")         return "✓ OK"
                                if (status === "bajo")       return "⚠ Baja confianza"
                                if (status === "sin_serial") return "✕ Sin serial"
                                if (status === "error")      return "✕ Error"
                                return "— Pendiente"
                            }
                            color: {
                                if (status === "ok")    return Theme.success
                                if (status === "error" || status === "sin_serial") return Theme.danger
                                return Theme.textSec
                            }
                            font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Item { width: 20 }

                        GBtn {
                            text: "OCR"
                            implicitHeight: 26; implicitWidth: 50
                            anchors.verticalCenter: parent.verticalCenter
                            onClicked: bridge.runOcrPage(idx)
                        }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border; opacity: 0.4 }
                }
            }
        }

        // Panel de exportación
        Rectangle {
            Layout.fillWidth: true; height: 60; color: Theme.surface
            Rectangle { anchors.top: parent.top; width: parent.width; height:1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }; spacing: 10
                GLabel { id: summaryLabel; text: "0 páginas"; secondary: true }
                Item { Layout.fillWidth: true }
                GLabel { text: "Carpeta:"; secondary: true }
                GInput { id: folderField; implicitWidth: 280; placeholderText: "Seleccionar carpeta…" }
                GBtn { text: "…"; implicitWidth: 32; onClicked: folderDlg.open() }
                GBtn {
                    text: "Generar ZIP"
                    primary: true
                    onClicked: {
                        if (!folderField.text) return
                        bridge.exportCivil(folderField.text, "Civil")
                    }
                }
            }
        }
    }
}
