import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property int    pageIndex:  -1
    property string thumbB64:   ""
    property string serial:     ""
    property real   confidence: 0
    property bool   selected:   false
    property bool   isCut:      false

    signal clicked(int idx)
    signal cutToggled(int idx)
    signal deleteRequested(int idx)
    signal fullscreenRequested(int idx)

    width:  148
    height: 220

    Rectangle {
        anchors.fill: parent
        radius:       Theme.radiusMD
        color:        root.selected ? Theme.surface2 : Theme.surface
        border.color: root.isCut     ? Theme.accent  :
                      root.selected  ? Theme.border2  : Theme.border
        border.width: root.isCut || root.selected ? 2 : 1
        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

        Column {
            anchors { fill: parent; margins: 6 }
            spacing: 5

            // Número de página
            Text {
                width: parent.width
                text:  (root.pageIndex + 1).toString()
                color: Theme.textDim
                font { family: Theme.fontFamily; pixelSize: Theme.fontXS }
                horizontalAlignment: Text.AlignRight
            }

            // Imagen
            Item {
                width:  parent.width
                height: parent.height - 56
                Image {
                    id:               imgView
                    anchors.fill:     parent
                    source:           root.thumbB64
                    fillMode:         Image.PreserveAspectFit
                    smooth:           true
                    asynchronous:     true
                    // Mientras carga
                    Rectangle {
                        anchors.fill: parent
                        color:        Theme.surface2
                        visible:      imgView.status !== Image.Ready
                    }
                }

                // Indicador de punto de corte
                Rectangle {
                    visible: root.isCut
                    anchors { left: parent.left; top: parent.top; margins: 4 }
                    width: 20; height: 20; radius: 10
                    color: Theme.accent
                    Text {
                        anchors.centerIn: parent
                        text: "✂"; font.pixelSize: 10
                        color: Theme.bg
                    }
                }
            }

            // Serial / etiqueta
            Text {
                width:          parent.width
                text:           root.serial || "—"
                color:          root.serial ? (root.confidence >= 0.7 ? Theme.textPri : Theme.textSec) : Theme.textDim
                font { family: Theme.fontFamily; pixelSize: Theme.fontXS; bold: !!root.serial }
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }

        // Overlay hover
        Rectangle {
            anchors.fill: parent
            radius:       Theme.radiusMD
            color:        "transparent"
            visible:      ma.containsMouse

            // Botones rápidos
            Row {
                anchors { top: parent.top; right: parent.right; margins: 4 }
                spacing: 3

                // Ver a pantalla completa
                Rectangle {
                    width: 22; height: 22; radius: 4
                    color: Theme.surface
                    border.color: Theme.border; border.width: 1
                    Text { anchors.centerIn: parent; text: "⤢"; color: Theme.textSec; font.pixelSize: 11 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.fullscreenRequested(root.pageIndex)
                    }
                }

                // Corte
                Rectangle {
                    width: 22; height: 22; radius: 4
                    color: root.isCut ? Theme.accentDim : Theme.surface
                    border.color: Theme.border; border.width: 1
                    Text { anchors.centerIn: parent; text: "✂"; color: Theme.textSec; font.pixelSize: 11 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.cutToggled(root.pageIndex)
                    }
                }

                // Eliminar
                Rectangle {
                    width: 22; height: 22; radius: 4
                    color: Theme.surface
                    border.color: Theme.border; border.width: 1
                    Text { anchors.centerIn: parent; text: "✕"; color: Theme.textDim; font.pixelSize: 11 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.deleteRequested(root.pageIndex)
                    }
                }
            }
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.clicked(root.pageIndex)
        }
    }
}
