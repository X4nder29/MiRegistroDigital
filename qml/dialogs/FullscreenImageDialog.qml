import QtQuick 2.15
import QtQuick.Controls 2.15

Popup {
    id: root
    property int pageIndex: -1
    property string imageB64: ""

    modal:    true
    anchors.centerIn: Overlay.overlay
    width:    Overlay.overlay ? Overlay.overlay.width  : 800
    height:   Overlay.overlay ? Overlay.overlay.height : 600
    padding:  0

    background: Rectangle { color: Theme.overlay }

    onPageIndexChanged: {
        if (root.visible && pageIndex >= 0)
            imageB64 = bridge.getPageImageB64(pageIndex)
    }

    onVisibleChanged: {
        if (root.visible && pageIndex >= 0)
            imageB64 = bridge.getPageImageB64(pageIndex)
    }

    Rectangle {
        anchors.fill:   parent
        color:          Theme.bg

        // Cerrar
        Rectangle {
            anchors { top: parent.top; right: parent.right; margins: 12 }
            width: 32; height: 32; radius: 16
            color: Theme.surface2; border.color: Theme.border; border.width: 1
            Text { anchors.centerIn: parent; text: "✕"; color: Theme.textSec; font.pixelSize: 14 }
            MouseArea { anchors.fill: parent; onClicked: root.close() }
        }

        // Flecha izq
        Rectangle {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 12 }
            width: 36; height: 36; radius: 18
            color: Theme.surface2; border.color: Theme.border; border.width: 1
            visible: root.pageIndex > 0
            Text { anchors.centerIn: parent; text: "‹"; color: Theme.textPri; font.pixelSize: 22 }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    root.pageIndex = Math.max(0, root.pageIndex - 1)
                }
            }
        }

        // Flecha der
        Rectangle {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 12 }
            width: 36; height: 36; radius: 18
            color: Theme.surface2; border.color: Theme.border; border.width: 1
            visible: root.pageIndex < bridge.pageCount - 1
            Text { anchors.centerIn: parent; text: "›"; color: Theme.textPri; font.pixelSize: 22 }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    root.pageIndex = Math.min(bridge.pageCount - 1, root.pageIndex + 1)
                }
            }
        }

        // Imagen
        Image {
            anchors {
                fill:    parent
                margins: 60
            }
            source:   root.imageB64
            fillMode: Image.PreserveAspectFit
            smooth:   true
            asynchronous: true
        }

        // Número de página
        Text {
            anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 14 }
            text:  "Página " + (root.pageIndex + 1)
            color: Theme.textSec
            font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
        }
    }
}
