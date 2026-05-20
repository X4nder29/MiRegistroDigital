import QtQuick 2.15
import QtQuick.Controls 2.15

Button {
    id: root
    property color  bgColor:   Theme.surface2
    property color  fgColor:   Theme.textPri
    property bool   primary:   false
    property bool   danger:    false
    property string iconText:  ""

    implicitHeight: 34
    implicitWidth:  contentItem.implicitWidth + 28

    background: Rectangle {
        radius:  Theme.radiusMD
        color: {
            if (!root.enabled)     return Theme.surface
            if (root.hovered)      return root.primary ? Theme.accent : Theme.border2
            if (root.pressed)      return Theme.border
            if (root.primary)      return Theme.accentDim
            if (root.danger)       return "#3a2222"
            return root.bgColor
        }
        border.color: root.primary ? Theme.accent : Theme.border
        border.width: 1
        Behavior on color { ColorAnimation { duration: Theme.animFast } }
    }

    contentItem: Row {
        spacing: 5
        anchors.centerIn: parent
        Text {
            visible: root.iconText !== ""
            text:    root.iconText
            font.pixelSize: Theme.fontMD
            color:   root.enabled ? root.fgColor : Theme.textDim
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text:  root.text
            font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
            color: root.enabled ? root.fgColor : Theme.textDim
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
