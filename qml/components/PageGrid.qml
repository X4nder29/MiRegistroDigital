import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property int   selectedIndex: -1
    property bool  cutMode:       false    // cuando true, clic activa corte

    signal pageSelected(int idx)
    signal cutToggled(int idx)
    signal pageDeleted(int idx)
    signal fullscreenRequested(int idx)

    // ── Modelo interno ────────────────────────────────────────────────────────
    ListModel { id: pageModel }

    function addPage(index, b64, src) {
        pageModel.append({ pageIndex: index, thumb: b64, serial: "", confidence: 0, isCut: false })
    }
    function updateThumb(index, b64) {
        for (var i = 0; i < pageModel.count; i++)
            if (pageModel.get(i).pageIndex === index) { pageModel.setProperty(i, "thumb", b64); return }
    }
    function setSerial(index, serial, conf) {
        for (var i = 0; i < pageModel.count; i++)
            if (pageModel.get(i).pageIndex === index) {
                pageModel.setProperty(i, "serial", serial)
                pageModel.setProperty(i, "confidence", conf)
                return
            }
    }
    function setCut(index, isCut) {
        for (var i = 0; i < pageModel.count; i++)
            if (pageModel.get(i).pageIndex === index) { pageModel.setProperty(i, "isCut", isCut); return }
    }
    function removePage(index) {
        for (var i = pageModel.count-1; i >= 0; i--)
            if (pageModel.get(i).pageIndex === index) { pageModel.remove(i); break }
        // Reindexar
        for (var j = 0; j < pageModel.count; j++) pageModel.setProperty(j, "pageIndex", j)
    }
    function clearAll() { pageModel.clear(); root.selectedIndex = -1 }

    // ── Vista ─────────────────────────────────────────────────────────────────
    ScrollView {
        anchors.fill: parent
        contentWidth:  grid.implicitWidth
        contentHeight: grid.implicitHeight
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AsNeeded
        ScrollBar.vertical.policy:   ScrollBar.AsNeeded

        GridView {
            id: grid
            width:       root.width
            implicitHeight: Math.ceil(count / Math.max(1, Math.floor(root.width / 164))) * 236
            cellWidth:   164
            cellHeight:  236
            model:       pageModel
            clip:        true

            delegate: ThumbnailCard {
                pageIndex:  model.pageIndex
                thumbB64:   model.thumb
                serial:     model.serial
                confidence: model.confidence
                selected:   model.pageIndex === root.selectedIndex
                isCut:      model.isCut

                onClicked: function(idx) {
                    root.selectedIndex = idx
                    root.pageSelected(idx)
                }
                onCutToggled:         function(idx) { root.cutToggled(idx) }
                onDeleteRequested:    function(idx) { root.pageDeleted(idx) }
                onFullscreenRequested: function(idx) { root.fullscreenRequested(idx) }
            }
        }
    }

    // Placeholder vacío
    Column {
        anchors.centerIn: parent
        visible: pageModel.count === 0
        spacing: Theme.sp3
        Text { text: "Sin páginas"; color: Theme.textDim; font.pixelSize: Theme.fontMD; anchors.horizontalCenter: parent.horizontalCenter }
        Text { text: "Escanea o importa archivos para comenzar"; color: Theme.textDim; font.pixelSize: Theme.fontSM; anchors.horizontalCenter: parent.horizontalCenter }
    }
}
