pragma Singleton
import QtQuick 2.15

QtObject {
    // ── Paleta (grises) ───────────────────────────────────────────────────────
    readonly property color bg:        "#111111"   // fondo principal
    readonly property color surface:   "#1a1a1a"   // tarjetas / paneles
    readonly property color surface2:  "#222222"   // inputs / rows alternas
    readonly property color border:    "#2e2e2e"   // bordes
    readonly property color border2:   "#3a3a3a"   // bordes activos
    readonly property color textPri:   "#e8e8e8"   // texto principal
    readonly property color textSec:   "#888888"   // texto secundario
    readonly property color textDim:   "#505050"   // texto deshabilitado
    readonly property color accent:    "#d0d0d0"   // acento (gris claro)
    readonly property color accentDim: "#555555"   // acento apagado
    readonly property color success:   "#909090"   // OK
    readonly property color warning:   "#a0a0a0"   // advertencia
    readonly property color danger:    "#6a6a6a"   // peligro/error
    readonly property color overlay:   "#000000c0" // modal overlay

    // ── Tipografía ────────────────────────────────────────────────────────────
    readonly property string fontFamily: "Segoe UI"
    readonly property int    fontXS:  9
    readonly property int    fontSM:  11
    readonly property int    fontMD:  13
    readonly property int    fontLG:  16
    readonly property int    fontXL:  22

    // ── Espaciado ─────────────────────────────────────────────────────────────
    readonly property int sp1: 4
    readonly property int sp2: 8
    readonly property int sp3: 12
    readonly property int sp4: 16
    readonly property int sp5: 24
    readonly property int sp6: 32

    // ── Radios ────────────────────────────────────────────────────────────────
    readonly property int radiusSM: 3
    readonly property int radiusMD: 5
    readonly property int radiusLG: 8

    // ── Animaciones ───────────────────────────────────────────────────────────
    readonly property int animFast:   100
    readonly property int animNormal: 180
}
