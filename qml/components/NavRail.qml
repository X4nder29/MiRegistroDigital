import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    width:  56
    color:  Theme.surface
    property string currentPage: "scan"

    signal navigate(string page)

    Column {
        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 16 }
        spacing: 2

        // Logo
        Item { width: 40; height: 40
            Text { anchors.centerIn: parent; text: "⬛"; font.pixelSize: 18; color: Theme.textSec }
        }

        Item { height: 16; width: 1 }

        Repeater {
            model: [
                { key: "scan",         icon: "⬛", label: "Escanear" },
                { key: "civil",        icon: "◫",  label: "Registros" },
                { key: "antecedentes", icon: "⊟",  label: "Antecedentes" },
                { key: "jobs",         icon: "↻",  label: "Trabajos" },
                { key: "settings",     icon: "⚙",  label: "Ajustes" },
            ]
            delegate: Item {
                width: 48; height: 48
                required property var modelData

                Rectangle {
                    anchors.centerIn: parent
                    width: 40; height: 40; radius: Theme.radiusMD
                    color: root.currentPage === modelData.key ? Theme.surface2 : "transparent"
                    border.color: root.currentPage === modelData.key ? Theme.border2 : "transparent"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text:  modelData.icon
                        font.pixelSize: 16
                        color: root.currentPage === modelData.key ? Theme.textPri : Theme.textDim
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape:  Qt.PointingHandCursor
                        onClicked:    root.navigate(modelData.key)
                    }
                }

                // Tooltip
                ToolTip.visible: ma2.containsMouse
                ToolTip.text:   modelData.label
                ToolTip.delay:  500

                MouseArea {
                    id: ma2
                    anchors.fill: parent
                    hoverEnabled: true
                    propagateComposedEvents: true
                    onClicked: mouse.accepted = false
                }
            }
        }
    }

    // Borde derecho
    Rectangle {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 1; color: Theme.border
    }
}
