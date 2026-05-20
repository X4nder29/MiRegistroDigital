import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

Item {
    id: root

    Connections {
        target: bridge
        function onJobCreated(id, tipo, label) {
            jobsModel.append({ jobId: id, jobType: tipo, jobLabel: label,
                               status: "running", current: 0, total: 1,
                               output: "", errorMsg: "" })
        }
        function onJobProgress(id, cur, tot) {
            for (var i = 0; i < jobsModel.count; i++) {
                if (jobsModel.get(i).jobId === id) {
                    jobsModel.setProperty(i, "current", cur)
                    jobsModel.setProperty(i, "total",   tot)
                    jobsModel.setProperty(i, "status",  "running")
                    break
                }
            }
        }
        function onJobDone(id, path) {
            for (var i = 0; i < jobsModel.count; i++) {
                if (jobsModel.get(i).jobId === id) {
                    jobsModel.setProperty(i, "status", "done")
                    jobsModel.setProperty(i, "output", path)
                    break
                }
            }
        }
        function onJobError(id, msg) {
            for (var i = 0; i < jobsModel.count; i++) {
                if (jobsModel.get(i).jobId === id) {
                    jobsModel.setProperty(i, "status",   "error")
                    jobsModel.setProperty(i, "errorMsg", msg)
                    break
                }
            }
        }
    }

    ListModel { id: jobsModel }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header
        Rectangle {
            Layout.fillWidth: true; height: 52; color: Theme.surface
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height:1; color: Theme.border }
            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }; spacing: 12
                GLabel { text: "Trabajos"; font.pixelSize: Theme.fontLG; font.bold: true }
                GLabel {
                    text: {
                        var active = 0
                        for (var i = 0; i < jobsModel.count; i++)
                            if (jobsModel.get(i).status === "running") active++
                        return active > 0 ? active + " activo(s)" : "Sin trabajos activos"
                    }
                    secondary: true
                }
                Item { Layout.fillWidth: true }
                GBtn {
                    text: "Limpiar completados"
                    onClicked: {
                        for (var i = jobsModel.count - 1; i >= 0; i--)
                            if (jobsModel.get(i).status !== "running" && jobsModel.get(i).status !== "queued") {
                                bridge.removeJob(jobsModel.get(i).jobId)
                                jobsModel.remove(i)
                            }
                    }
                }
            }
        }

        // Lista de trabajos
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            padding: 16

            Column {
                width: parent.width - 32
                spacing: 8

                Repeater {
                    model: jobsModel
                    delegate: JobCard {
                        width:    parent.width
                        jobId:    model.jobId
                        jobType:  model.jobType
                        jobLabel: model.jobLabel
                        status:   model.status
                        current:  model.current
                        total:    model.total
                        output:   model.output
                        errorMsg: model.errorMsg

                        onRemoveRequested: function(id) {
                            bridge.removeJob(id)
                            for (var i = 0; i < jobsModel.count; i++)
                                if (jobsModel.get(i).jobId === id) { jobsModel.remove(i); break }
                        }
                        onOpenFolder: function(path) {
                            // Abrir explorador de archivos
                            Qt.openUrlExternally("file:///" + path.substring(0, path.lastIndexOf("/")))
                        }
                    }
                }

                // Placeholder
                Item {
                    width:   parent.width
                    height:  200
                    visible: jobsModel.count === 0
                    Column {
                        anchors.centerIn: parent; spacing: 8
                        GLabel { text: "Sin trabajos"; font.pixelSize: Theme.fontMD; anchors.horizontalCenter: parent.horizontalCenter }
                        GLabel { text: "Los trabajos de exportación aparecerán aquí"; secondary: true; anchors.horizontalCenter: parent.horizontalCenter }
                    }
                }
            }
        }
    }
}
