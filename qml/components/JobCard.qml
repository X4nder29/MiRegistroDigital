import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    property string jobId:    ""
    property string jobType:  "civil"
    property string jobLabel: ""
    property string status:   "running"   // queued|running|done|error|cancelled
    property int    current:  0
    property int    total:    1
    property string output:   ""
    property string errorMsg: ""

    signal removeRequested(string id)
    signal openFolder(string path)

    height: 70
    radius: Theme.radiusMD
    color:  Theme.surface
    border.color: {
        if (status === "done")  return Theme.success
        if (status === "error") return Theme.danger
        return Theme.border
    }
    border.width: 1

    RowLayout {
        anchors { fill: parent; margins: 12 }
        spacing: 12

        // Icono de tipo
        Text {
            text: root.jobType === "civil" ? "📄" : "📋"
            font.pixelSize: 20
        }

        Column {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text:  root.jobLabel
                color: Theme.textPri
                font { family: Theme.fontFamily; pixelSize: Theme.fontSM; bold: true }
                elide: Text.ElideRight
                width: parent.width
            }

            GProgressBar {
                width: parent.width
                height: 3
                value:       root.total > 0 ? root.current / root.total : 0
                indeterminate: root.status === "queued"
                visible:     root.status === "running" || root.status === "queued"
            }

            Text {
                text: {
                    if (root.status === "running") return root.current + "/" + root.total + " páginas"
                    if (root.status === "done")    return "✓ Completado"
                    if (root.status === "error")   return "✕ " + root.errorMsg
                    if (root.status === "queued")  return "En cola…"
                    return ""
                }
                color: root.status === "done"  ? Theme.success :
                       root.status === "error" ? Theme.danger  : Theme.textSec
                font { family: Theme.fontFamily; pixelSize: Theme.fontXS }
                elide: Text.ElideRight
                width: parent.width
            }
        }

        // Botones
        Column {
            spacing: 4
            visible: root.status === "done" || root.status === "error"

            GBtn {
                text: "Abrir carpeta"
                visible: root.status === "done" && root.output !== ""
                implicitHeight: 26
                onClicked: root.openFolder(root.output)
            }
            GBtn {
                text: "✕"
                implicitWidth: 30; implicitHeight: 26
                onClicked: root.removeRequested(root.jobId)
            }
        }
    }
}
