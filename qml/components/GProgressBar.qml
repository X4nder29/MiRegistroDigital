import QtQuick 2.15
import QtQuick.Controls 2.15

ProgressBar {
    id: root
    implicitHeight: 3
    background: Rectangle { color: Theme.surface2; radius: 2 }
    contentItem: Item {
        Rectangle {
            width:  root.indeterminate ? parent.width*0.4 : parent.width * root.value
            height: parent.height
            radius: 2
            color:  Theme.accent
            Behavior on width { NumberAnimation { duration: Theme.animNormal } }
            NumberAnimation on x {
                running:  root.indeterminate
                from:     -parent.width*0.4
                to:       parent.width
                duration: 900
                loops:    Animation.Infinite
            }
        }
    }
}
