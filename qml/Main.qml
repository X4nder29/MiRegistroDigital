import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "components"
import "pages"
import "dialogs"

ApplicationWindow {
    id:      appWindow
    title:   "DocScan Pro"
    width:   1200
    height:  760
    minimumWidth:  900
    minimumHeight: 600
    visible: true
    color:   Theme.bg

    // Badge de trabajos activos en ícono de Jobs
    property int activeJobs: 0
    Connections {
        target: bridge
        function onJobCreated()  { appWindow.activeJobs++ }
        function onJobDone()     { appWindow.activeJobs = Math.max(0, appWindow.activeJobs - 1) }
        function onJobError()    { appWindow.activeJobs = Math.max(0, appWindow.activeJobs - 1) }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── NavRail ───────────────────────────────────────────────────────────
        NavRail {
            id:            navRail
            Layout.fillHeight: true
            currentPage:   stack.currentPage

            onNavigate: function(page) {
                stack.navigateTo(page)
            }
        }

        // ── Stack de páginas ──────────────────────────────────────────────────
        Item {
            Layout.fillWidth:  true
            Layout.fillHeight: true

            property string currentPage: "scan"

            function navigateTo(page) {
                currentPage = page
                navRail.currentPage = page
                if      (page === "scan")         stack.currentIndex = 0
                else if (page === "civil")        stack.currentIndex = 1
                else if (page === "antecedentes") stack.currentIndex = 2
                else if (page === "jobs")         stack.currentIndex = 3
                else if (page === "settings")     stack.currentIndex = 4
            }

            id: stack

            StackLayout {
                anchors.fill: parent
                currentIndex: 0
                id: stackLayout

                ScanPage         {}
                CivilPage        {}
                AntecedentesPage {}
                JobsPage         {}
                SettingsPage     {}
            }
        }
    }
}
