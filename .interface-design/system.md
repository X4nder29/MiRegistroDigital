# Design system — MiRegistroDigital (DocScan Pro)

PySide6/Qt6 desktop app, Windows-only, dark-only. Web design guidance maps here through
QSS, which is a *subset* of CSS with its own painting rules — see "Qt gotchas" before
assuming a CSS technique works.

Single source of truth: `views/theme.py`. The global `STYLESHEET` is applied once in
`main.py`, so most widgets need no per-widget CSS. Add to the global sheet before
reaching for `setStyleSheet()` on an instance.

## Direction and feel

A quiet technical instrument for a registry-office operator running long scanning and
OCR sessions. Not friendly, not playful — calm, dense, and out of the way. The document
and the numbers are the content; every control is deliberately demoted so nothing
competes with the page preview.

Palette lineage: Vercel/GitHub dark. One hue, lightness-only steps.

## Tokens (`views/theme.py`)

| Token | Value | Use |
|---|---|---|
| `BG` | `#0a0a0b` | app canvas, page backgrounds |
| `SURFACE` | `#111113` | cards, menus, group boxes |
| `SURFACE2` | `#18181b` | **inset** surfaces: inputs, tab strip, compact lists |
| `SURFACE3` | `#202023` | hover fills, selection, primary button fill |
| `BORDER` | `#27272a` | all hairlines |
| `TEXT` | `#ededef` | primary text |
| `TEXT_SEC` | `#a1a1aa` | labels, secondary, control glyphs |
| `TEXT_DIM` | `#71717a` | metadata, captions, placeholders |
| `ACCENT` | `#e8e8ee` | progress fill, slider handle |
| `ACCENT2` | `#8888ff` | checked state, card hover border |
| `SUCCESS / WARNING / DANGER / INFO` | `#22c55e / #f59e0b / #ef4444 / #3b82f6` | semantic only |

Ad-hoc values that earned their place: `#2a2a2e` (pressed / primary-hover),
`#3f3f46` (disabled glyph, scrollbar hover), `#52525b` (scrollbar pressed).

**Text hierarchy is four levels** — `TEXT` / `TEXT_SEC` / `TEXT_DIM` / `#3f3f46`.
Use color + weight for hierarchy before reaching for size; the base is 10pt with
9pt for labels and 8pt for metadata.

## Depth strategy: borders-only

Committed. No drop shadows anywhere — shadows read poorly on a `#0a0a0b` canvas.
Elevation is expressed as a lightness step (`BG → SURFACE → SURFACE2 → SURFACE3`)
plus a 1px `BORDER` hairline. Inputs go *darker* than their surroundings (`SURFACE2`),
because they receive content.

Sidebars and strips share the canvas family and are separated by a hairline, never by
a different hue.

## Spacing and radius

- Base unit **4px**; layout gaps are 8 / 12 / 16 / 24.
- Page layout: `QVBoxLayout(self)` with zero margins → fixed-height header `QFrame`
  (title + actions) → content area.
- Radius scale: **4px** list/table items and menu items · **6px** inputs, buttons,
  compact lists · **8px** group boxes and pills · **12px** home tool cards.
- **Concentric radius**: a child inside a bordered parent gets `parent - border`.
  The spinbox stepper uses 5px inside the field's 6px + 1px border.

## Component patterns (measured)

- **Button** — transparent bg · 1px `BORDER` · radius 6 · padding `6px 16px` ·
  min-height 28. Hover: `SURFACE` fill + `SURFACE3` border + `TEXT`. Pressed: `SURFACE2`.
  Disabled: `TEXT_DIM`, border transparent.
  - Primary: `btn.setProperty("primary", True)` → `SURFACE3` fill, hover `#2a2a2e`.
  - Danger: `btn.setProperty("danger", True)` → `DANGER` text/border, 12% tinted hover.
  - In-panel action buttons are 32px tall; hero buttons 34–36px.
- **Text input** — `SURFACE2` · 1px `BORDER` · radius 6 · padding `6px 10px`.
  Focus: border → `INFO`. Same for `QSpinBox`/`QComboBox` at padding `4px 8px`,
  min-height 26.
- **Numeric stepper (`QSpinBox`/`QDoubleSpinBox`)** — 18px column at the right,
  **transparent** with a single `border-left: 1px solid BORDER`; no filled button, so
  it reads as part of the field. Outer corners radius 5, inner corners square.
  Hover `SURFACE3`, pressed `#2a2a2e`. Arrows are `resources/chevron_{up,down}.svg`
  (10×6, `TEXT_SEC`, 1.5 stroke, round caps); `:off` and `:disabled` swap in the
  `_dim` pair (`#3f3f46`), so the up arrow visibly dims at maximum.
  Asset paths resolve via `sys._MEIPASS`; if the SVGs are missing the whole block is
  skipped so buttons never render arrowless.
- **Group box ("isla de opciones")** — `SURFACE` · 1px `BORDER` · radius 8 ·
  `margin-top: 22px` · `padding: 20px 18px 18px 18px`; title at `left: 16px`,
  `padding: 2px 8px`, weight 600, `TEXT_SEC`. The generous top margin and padding are
  deliberate — they were added because titles collided with the box edge.
- **Pill / badge** — `pill_qss(color)`: 14% tint fill, 30% border, radius 8,
  `padding: 1px 8px`, 8pt/600. The one place color is allowed to be loud, and only for
  status.
- **West tab strip** (digitization page) — `_TAB_STRIP_W = 48`, square 48×48 tabs,
  `SURFACE2` band, emoji rasterized to `QIcon` (West tabs rotate text, not icons).
  The 3px selection border is **reserved in every state** so the icon never shifts.
  The zoom column pinned at the strip's bottom is transparent (40×32 buttons,
  15pt/500, radius 7) so it reads as one continuous strip with the tabs.
- **Home tool card** — 220×170, `SURFACE`, radius 12; hover `SURFACE2` + `ACCENT2`
  border.
- **Scrollbar** — 8px, transparent track, `BORDER` handle at radius 4, no arrows.

## Qt gotchas (learned the hard way — verified, not assumed)

- **Styling `::up-button` kills the native arrow.** Once any rule touches a spinbox
  button, Qt stops painting the arrow primitive. You must supply `image: url(...)`.
  Setting `width`/`height`/`color` on `::up-arrow` alone yields a blank stepper.
- **The CSS-triangle border trick does not work.** A 0×0 box with asymmetric borders
  renders in Qt as a filled **rectangle** — Qt doesn't miter border joins like CSS.
  Use image assets for any arrow/chevron.
- **Never add `padding-right` to a spinbox** to make room for its steppers. Qt already
  subtracts the button width from the edit rect; adding padding double-counts it and
  clips the value.
- **QSS `url()` accepts quotes** — always quote the path, install paths contain spaces.
- **`QTreeWidget.setItemWidget()` per row has non-linear cost.** 6000 rows with an
  embedded button hangs indefinitely; the same case with a context menu renders in <1s.
  Row actions use `customContextMenuRequested` + `item.setData(..., UserRole, obj)`.
- **`setCornerWidget(BottomLeftCorner)` gives zero geometry for West tabs.** Anchor an
  overlay widget parented to the `QTabWidget` and reposition it in an `eventFilter`.
- SVG in QSS works — PySide6 ships the `qsvg` image plugin. Prefer it over PNG for
  crispness at any DPI.

## Verification workflow

There are no tests and the real `MainWindow` cannot boot headlessly (EasyOCR/torch/TWAIN
init blocks). For visual work, do **not** guess — render and look:

```python
app = QApplication(sys.argv)          # no offscreen: keeps the real windows11 style
w.setStyleSheet(STYLESHEET + variant) # build candidate variants side by side
pix = w.grab()                        # works without show()
pix.scaled(w*3, h*3).save(out_png)    # upscale, then read the PNG back
```

Render candidates side by side before committing to an approach, and simulate states
(hover/pressed) by applying the pseudo-state rule unconditionally in a variant.
For fit/clipping questions, measure instead of eyeballing:
`QFontMetrics.horizontalAdvance(widest_value)` vs `spinbox.lineEdit().width() - 4`.

Then still run `python main.py` — offscreen grabs don't prove interaction.

## Known constraints

- Several spinboxes carry a `setFixedWidth`. When changing a range or suffix, re-measure:
  `ant_desde`/`ant_hasta` are 78px (max `9999`), `ocr_cores` 68px, settings fields
  80–100px. They were 55px and silently clipping.
- `fonts/JetBrainsMonoNerdFont-Regular.ttf` is optional and gitignored — the app must
  degrade to `'Segoe UI', 'Inter', sans-serif` without complaint.
- Adding a page means touching four spots in `views/main_window.py` (`_NAV`,
  `_build_ui`, `_navigate`, `_connect`). There is no page registry.
