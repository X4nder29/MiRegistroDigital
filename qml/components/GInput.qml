import QtQuick 2.15
import QtQuick.Controls 2.15

TextField {
    id: root
    implicitHeight: 32
    color:          Theme.textPri
    placeholderTextColor: Theme.textDim
    font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
    leftPadding: 8; rightPadding: 8
    background: Rectangle {
        radius:       Theme.radiusMD
        color:        Theme.surface2
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: 1
        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
    }
    selectionColor: Theme.accentDim
}
