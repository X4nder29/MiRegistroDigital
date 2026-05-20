import QtQuick 2.15
Rectangle {
    property bool vertical: false
    width:  vertical ? 1 : parent.width
    height: vertical ? parent.height : 1
    color:  Theme.border
}
