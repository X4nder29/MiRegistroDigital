import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3 as QtDialogs
import "../components"

Item {
    id: root

    Component.onCompleted: loadValues()

    function loadValues() {
        dpiField.text       = bridge.cfgGet("scanner",      "dpi")             || "300"
        marginField.text    = Math.round((bridge.cfgGet("ocr","margin_right_pct") || 0.15) * 100)
        confField.text      = Math.round((bridge.cfgGet("ocr","confidence_threshold") || 0.4) * 100)
        outFolderField.text = bridge.cfgGet("output",       "default_folder")   || ""
        pdfDpiField.text    = bridge.cfgGet("output",       "pdf_dpi")          || "200"
        serialField.text    = bridge.cfgGet("antecedentes", "serial_inicial")   || "1"
        padField.text       = bridge.cfgGet("antecedentes", "serial_padding")   || "5"
        autoPerspChk.checked = bridge.cfgGet("correction",  "auto_perspective") !== false
        autoRotChk.checked   = bridge.cfgGet("correction",  "auto_rotation")    !== false
        gpuChk.checked       = bridge.cfgGet("ocr",         "gpu")             === true
    }

    function saveValues() {
        bridge.cfgSet("scanner",      "dpi",                  parseInt(dpiField.text)    || 300)
        bridge.cfgSet("ocr",          "margin_right_pct",     (parseInt(marginField.text)||15)/100)
        bridge.cfgSet("ocr",          "confidence_threshold", (parseInt(confField.text)||40)/100)
        bridge.cfgSet("output",       "default_folder",       outFolderField.text)
        bridge.cfgSet("output",       "pdf_dpi",              parseInt(pdfDpiField.text) || 200)
        bridge.cfgSet("antecedentes", "serial_inicial",       parseInt(serialField.text) || 1)
        bridge.cfgSet("antecedentes", "serial_padding",       parseInt(padField.text)    || 5)
        bridge.cfgSet("correction",   "auto_perspective",     autoPerspChk.checked)
        bridge.cfgSet("correction",   "auto_rotation",        autoRotChk.checked)
        bridge.cfgSet("ocr",          "gpu",                  gpuChk.checked)
        bridge.cfgSave()
        savedBanner.visible = true
        savedTimer.restart()
    }

    QtDialogs.FileDialog {
        id: outDlg; title: "Carpeta por defecto"; selectFolder: true
        onAccepted: outFolderField.text = fileUrl.toString().replace("file:///","")
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 0

        // Header
        Rectangle {
            Layout.fillWidth: true; height: 52; color: Theme.surface
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin:16; rightMargin:16 }; spacing:12
                GLabel { text: "Configuración"; font.pixelSize: Theme.fontLG; font.bold: true }
                Item { Layout.fillWidth: true }
                GBtn { text: "Guardar"; primary: true; onClicked: saveValues() }
            }
        }

        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true; padding: 24

            ColumnLayout {
                width: parent.width - 48; spacing: 24

                // ── Escáner ───────────────────────────────────────────────────
                GLabel { text: "Escáner"; font.pixelSize: Theme.fontMD; font.bold: true }
                GDivider {}

                GridLayout { columns: 2; columnSpacing: 16; rowSpacing: 10
                    GLabel { text: "Resolución por defecto:"; secondary: true }
                    RowLayout { GInput { id: dpiField; implicitWidth: 80 }; GLabel { text: "DPI"; secondary: true } }

                    GLabel { text: "Corr. perspectiva auto:"; secondary: true }
                    CheckBox {
                        id: autoPerspChk
                        indicator: Rectangle { width:16;height:16;radius:3;border.color:Theme.border;border.width:1;color:autoPerspChk.checked?Theme.accentDim:Theme.surface2
                            Text { anchors.centerIn:parent; text:"✓"; color:Theme.textPri; font.pixelSize:10; visible:autoPerspChk.checked }
                        }
                        contentItem: Item {}
                    }

                    GLabel { text: "Corr. rotación auto:"; secondary: true }
                    CheckBox {
                        id: autoRotChk
                        indicator: Rectangle { width:16;height:16;radius:3;border.color:Theme.border;border.width:1;color:autoRotChk.checked?Theme.accentDim:Theme.surface2
                            Text { anchors.centerIn:parent; text:"✓"; color:Theme.textPri; font.pixelSize:10; visible:autoRotChk.checked }
                        }
                        contentItem: Item {}
                    }
                }

                // ── OCR ───────────────────────────────────────────────────────
                GLabel { text: "OCR"; font.pixelSize: Theme.fontMD; font.bold: true }
                GDivider {}

                GridLayout { columns: 2; columnSpacing: 16; rowSpacing: 10
                    GLabel { text: "Margen derecho OCR:"; secondary: true }
                    RowLayout { GInput { id: marginField; implicitWidth: 60 }; GLabel { text: "%"; secondary: true } }

                    GLabel { text: "Umbral de confianza:"; secondary: true }
                    RowLayout { GInput { id: confField; implicitWidth: 60 }; GLabel { text: "%"; secondary: true } }

                    GLabel { text: "Usar GPU (CUDA):"; secondary: true }
                    CheckBox {
                        id: gpuChk
                        indicator: Rectangle { width:16;height:16;radius:3;border.color:Theme.border;border.width:1;color:gpuChk.checked?Theme.accentDim:Theme.surface2
                            Text { anchors.centerIn:parent; text:"✓"; color:Theme.textPri; font.pixelSize:10; visible:gpuChk.checked }
                        }
                        contentItem: Item {}
                    }
                }

                // ── Salida ────────────────────────────────────────────────────
                GLabel { text: "Salida"; font.pixelSize: Theme.fontMD; font.bold: true }
                GDivider {}

                GridLayout { columns: 2; columnSpacing: 16; rowSpacing: 10
                    GLabel { text: "Carpeta por defecto:"; secondary: true }
                    RowLayout {
                        GInput { id: outFolderField; implicitWidth: 280; placeholderText: "Ruta…" }
                        GBtn { text: "…"; implicitWidth: 32; onClicked: outDlg.open() }
                    }
                    GLabel { text: "DPI de PDFs generados:"; secondary: true }
                    RowLayout { GInput { id: pdfDpiField; implicitWidth: 80 }; GLabel { text: "DPI"; secondary: true } }
                }

                // ── Antecedentes ──────────────────────────────────────────────
                GLabel { text: "Antecedentes (por defecto)"; font.pixelSize: Theme.fontMD; font.bold: true }
                GDivider {}

                GridLayout { columns: 2; columnSpacing: 16; rowSpacing: 10
                    GLabel { text: "Serial inicial:"; secondary: true }
                    GInput { id: serialField; implicitWidth: 100 }
                    GLabel { text: "Dígitos (relleno):"; secondary: true }
                    GInput { id: padField; implicitWidth: 60 }
                }

                Item { height: 40 }
            }
        }
    }

    // Banner guardado
    Rectangle {
        id:           savedBanner
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 16 }
        width: 220; height: 36; radius: Theme.radiusMD
        color: Theme.surface; border.color: Theme.success; border.width: 1
        visible: false
        GLabel { anchors.centerIn: parent; text: "✓ Configuración guardada" }
        Timer { id: savedTimer; interval: 2500; onTriggered: savedBanner.visible = false }
    }
}
