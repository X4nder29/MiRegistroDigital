import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3 as QtDialogs
import "../components"

Item {
    id: root

    // ── Estado ────────────────────────────────────────────────────────────────
    property bool expanded: false          // modo pantalla amplia del grid
    property int  selectedForView: -1

    Connections {
        target: bridge
        function onPageAdded(index, b64, src) {
            gridComp.addPage(index, b64, src)
            summaryLabel.text = gridComp.pageCount + " páginas · " + groupsLabel.text
        }
        function onPageUpdated(index, b64)    { gridComp.updateThumb(index, b64) }
        function onPageDeleted(index)         { gridComp.removePage(index); refreshGroups() }
        function onCutPointChanged(idx, v)    { gridComp.setCut(idx, v); refreshGroups() }
    }

    function refreshGroups() {
        var groups = bridge.getGroupsPreview()
        groupsLabel.text = groups.length + " grupo(s)"
        // Reconstruir modelo de grupos
        groupsModel.clear()
        var serial = serialSpin.value
        var pad    = paddingSpin.value
        for (var i = 0; i < groups.length; i++) {
            var pages  = groups[i]
            var label  = String(serial + i).padStart(pad, "0")
            groupsModel.append({ groupNum: i+1, pages: pages.join(", "), serial: label, count: pages.length })
        }
    }

    ListModel { id: groupsModel }

    QtDialogs.FileDialog {
        id: folderDlg; title: "Carpeta de destino"; selectFolder: true
        onAccepted: folderField.text = fileUrl.toString().replace("file:///","")
    }

    FullscreenImageDialog { id: fsDialog }

    // ── Layout raíz ───────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; height: 52; color: Theme.surface
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }; spacing: 12
                GLabel { text: "Antecedentes"; font.pixelSize: Theme.fontLG; font.bold: true }
                GLabel { id: groupsLabel; text: "0 grupo(s)"; secondary: true }
                Item { Layout.fillWidth: true }
                GBtn {
                    text: root.expanded ? "⊡  Compactar" : "⊞  Ampliar área"
                    onClicked: root.expanded = !root.expanded
                }
                GBtn {
                    text: "Limpiar cortes"
                    onClicked: { bridge.clearCuts(); refreshGroups() }
                }
            }
        }

        // ── Cuerpo principal (grid + panel derecho) ───────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Grid de páginas — se expande si expanded=true
            Item {
                Layout.fillHeight: true
                Layout.fillWidth:  true

                PageGrid {
                    id:           gridComp
                    anchors.fill: parent

                    onPageSelected: function(idx) { root.selectedForView = idx }
                    onCutToggled:   function(idx) { bridge.toggleCut(idx) }
                    onPageDeleted:  function(idx) { bridge.deletePage(idx) }
                    onFullscreenRequested: function(idx) {
                        fsDialog.pageIndex = idx; fsDialog.open()
                    }
                }

                // Hint cuando no hay páginas
                Text {
                    anchors.centerIn: parent
                    visible: gridComp.pageCount === 0
                    text: "Ve a Escanear y carga páginas primero"
                    color: Theme.textDim; font.pixelSize: Theme.fontSM
                }
            }

            // Panel lateral — se oculta en modo expanded
            Rectangle {
                visible: !root.expanded
                Layout.fillHeight: true
                width: 260
                color: Theme.surface
                border.color: Theme.border; border.width: 0
                Rectangle { anchors.left: parent.left; height: parent.height; width:1; color: Theme.border }

                ColumnLayout {
                    anchors { fill: parent; margins: 16 }
                    spacing: 14

                    // ── Vista previa de grupos ────────────────────────────────
                    GLabel { text: "Grupos"; font.pixelSize: Theme.fontMD; font.bold: true }
                    GDivider {}

                    ListView {
                        Layout.fillWidth: true
                        height: 180
                        model:  groupsModel
                        clip:   true
                        spacing: 4

                        delegate: Rectangle {
                            width: parent ? parent.width : 0
                            height: 38; radius: Theme.radiusMD
                            color: Theme.surface2; border.color: Theme.border; border.width:1
                            required property int    groupNum
                            required property string pages
                            required property string serial
                            required property int    count

                            RowLayout {
                                anchors { fill: parent; leftMargin:10; rightMargin:10 }
                                GLabel { text: "Grupo " + groupNum; font.bold: true }
                                GLabel { text: count + " pág."; secondary: true; Layout.fillWidth: true }
                                GLabel { text: serial + ".pdf"; secondary: true; font.pixelSize: Theme.fontXS }
                            }
                        }

                        Rectangle {
                            anchors.fill: parent; color: "transparent"
                            visible: groupsModel.count === 0
                            GLabel {
                                anchors.centerIn: parent
                                text: "Sin cortes definidos"
                                secondary: true; dim: true
                            }
                        }
                    }

                    GDivider {}

                    // ── Parámetros de numeración ──────────────────────────────
                    GLabel { text: "Numeración"; font.pixelSize: Theme.fontMD; font.bold: true }

                    GridLayout { columns: 2; columnSpacing: 8; rowSpacing: 8; Layout.fillWidth: true
                        GLabel { text: "Serial inicial:"; secondary: true }
                        SpinBox {
                            id: serialSpin; from: 1; to: 999999; value: 1
                            implicitWidth: 100; implicitHeight: 32
                            contentItem: TextInput { text: serialSpin.textFromValue(serialSpin.value, serialSpin.locale); color: Theme.textPri; font { family: Theme.fontFamily; pixelSize: Theme.fontSM }; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: Theme.surface2; border.color: Theme.border; border.width:1; radius: Theme.radiusMD }
                            onValueChanged: refreshGroups()
                        }

                        GLabel { text: "Dígitos:"; secondary: true }
                        SpinBox {
                            id: paddingSpin; from: 1; to: 10; value: 5
                            implicitWidth: 80; implicitHeight: 32
                            contentItem: TextInput { text: paddingSpin.textFromValue(paddingSpin.value, paddingSpin.locale); color: Theme.textPri; font { family: Theme.fontFamily; pixelSize: Theme.fontSM }; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: Theme.surface2; border.color: Theme.border; border.width:1; radius: Theme.radiusMD }
                            onValueChanged: refreshGroups()
                        }
                    }

                    // ── Rango opcional ────────────────────────────────────────
                    GLabel { text: "Rango (opcional)"; font.pixelSize: Theme.fontMD; font.bold: true }

                    RowLayout { spacing: 6
                        CheckBox {
                            id: rangeChk; text: "Activar"
                            contentItem: GLabel { text: "Activar"; leftPadding: rangeChk.indicator.width + 6 }
                            indicator: Rectangle { width:16;height:16;radius:3;border.color:Theme.border;border.width:1;color:rangeChk.checked?Theme.accentDim:Theme.surface2
                                Text { anchors.centerIn:parent; text:"✓"; color:Theme.textPri; font.pixelSize:10; visible:rangeChk.checked }
                            }
                        }
                    }
                    RowLayout { spacing: 8; enabled: rangeChk.checked; opacity: rangeChk.checked ? 1 : 0.4
                        GLabel { text: "Desde:"; secondary: true }
                        SpinBox {
                            id: desdeSpin; from:1; to:9999; value:1; implicitWidth:70; implicitHeight:28
                            contentItem: TextInput { text: desdeSpin.value; color: Theme.textPri; font.pixelSize: Theme.fontSM; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: Theme.surface2; border.color:Theme.border; border.width:1; radius:Theme.radiusMD }
                        }
                        GLabel { text: "Hasta:"; secondary: true }
                        SpinBox {
                            id: hastaSpin; from:1; to:9999; value:100; implicitWidth:70; implicitHeight:28
                            contentItem: TextInput { text: hastaSpin.value; color: Theme.textPri; font.pixelSize: Theme.fontSM; horizontalAlignment: Text.AlignHCenter }
                            background: Rectangle { color: Theme.surface2; border.color:Theme.border; border.width:1; radius:Theme.radiusMD }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    GDivider {}

                    // ── Exportar ──────────────────────────────────────────────
                    GLabel { text: "Exportar"; font.pixelSize: Theme.fontMD; font.bold: true }
                    GLabel { id: summaryLabel; text: "0 páginas · 0 grupo(s)"; secondary: true }

                    RowLayout { spacing: 6
                        GInput { id: folderField; Layout.fillWidth:true; placeholderText: "Carpeta…" }
                        GBtn { text: "…"; implicitWidth:32; onClicked: folderDlg.open() }
                    }

                    GBtn {
                        Layout.fillWidth: true; text: "Generar ZIP"; primary: true
                        onClicked: {
                            if (!folderField.text) return
                            bridge.exportAnt(
                                folderField.text,
                                serialSpin.value,
                                paddingSpin.value,
                                rangeChk.checked ? desdeSpin.value : 0,
                                rangeChk.checked ? hastaSpin.value : 0,
                                "Antecedentes"
                            )
                        }
                    }
                }
            }
        }
    }
}
