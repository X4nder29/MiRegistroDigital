import QtQuick 2.15

Text {
    property bool secondary: false
    property bool dim:       false
    color:          dim ? Theme.textDim : (secondary ? Theme.textSec : Theme.textPri)
    font { family: Theme.fontFamily; pixelSize: Theme.fontSM }
    elide: Text.ElideRight
}
