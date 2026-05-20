import QtQuick 2.15
import QtQuick.Dialogs 1.3 as QtDialogs

QtDialogs.FileDialog {
    id: root
    selectFolder: true
    title: "Seleccionar carpeta de destino"
    property var onAcceptedCallback: null
    onAccepted: {
        if (root.onAcceptedCallback)
            root.onAcceptedCallback(fileUrl.toString())
    }
}
