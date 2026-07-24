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
| `SURFACE` | `#131316` | cards, menus, group boxes |
| `SURFACE2` | `#1b1b1f` | **inset** surfaces: inputs, button fill, tab strip |
| `SURFACE3` | `#26262c` | hover fills, selection |
| `BORDER` | `#303038` | dividers, hairlines |
| `BORDER_STRONG` | `#3a3a43` | control boundaries: inputs, buttons, checkboxes |
| `TEXT` | `#f2f2f4` | primary text — 17.7:1 |
| `TEXT_SEC` | `#adadb8` | labels, secondary, control glyphs — 8.9:1 |
| `TEXT_DIM` | `#8f8f9a` | metadata, captions, placeholders — 6.2:1 |
| `DISABLED` | `#5f5f6b` | inactive text and glyphs |
| `POPUP` | `#212127` | floating surfaces: menus, dropdowns, tooltips |
| `POPUP_SEL` | `#33333d` | highlighted row inside a popup |
| `ACCENT` | `#e8e8ee` | **primary button fill**, progress fill, slider handle |
| `ACCENT2` | `#8888ff` | checked state, card hover border |
| `SUCCESS / WARNING / DANGER / INFO` | `#22c55e / #f59e0b / #ef4444 / #3b82f6` | semantic only |

Ad-hoc values that earned their place: `#2f2f36` (pressed), `#4a4a55` (button
hover border), `#55555f` / `#6b6b76` (scrollbar hover / pressed), `#ffffff` and
`#d4d4dc` (primary hover / pressed).

**Text hierarchy is four levels** — `TEXT` / `TEXT_SEC` / `TEXT_DIM` / `DISABLED`.
Use color + weight for hierarchy before reaching for size; the base is 10pt with
9pt for labels and 8pt for metadata.

## Contrast: which metric applies where

Use **WCAG ratio for text** and **CIE L\* delta for adjacent dark surfaces**.
Near black the WCAG formula's `+0.05` term dominates and every ratio compresses
toward 1.0, so it stops describing what the eye sees — chasing 3:1 between two
dark greys would wreck the direction rather than help. Rule of thumb for dL\*:
~2 is just noticeable on a large area, 4–6 reads clearly, >10 reads as separate
zones.

Calibrated against real dark UIs (measured, not assumed):

| | dL\* surface | dL\* border | muted text | body text |
|---|---|---|---|---|
| GitHub dark | 4.6 | 17.4 | 6.15:1 | 16.0:1 |
| Vercel dark | 2.7 | 21.2 | 8.13:1 | 17.9:1 |
| Linear dark | 4.6 | 13.8 | 5.86:1 | 17.9:1 |
| **this app (before)** | 2.4 | 13.0 | **4.09:1** | 16.9:1 |
| **this app (now)** | 3.2 | 17.4 | 6.19:1 | 17.7:1 |

Muted text at 4.09:1 was the real outlier — below AA and darker than every
reference. All text now passes AA; hover/selection separation went from dL\* 4.0
to 5.5, and the control boundary from dL\* 13 to 22.

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

- **Button** — `SURFACE2` fill · 1px `BORDER_STRONG` · radius 6 · padding
  `5px 16px` · min-height 20 (**= 32px tall**). A button carries its own fill, not
  just a border: transparent-with-a-1.3:1-border read as a floating label, not an
  object. Hover: `SURFACE3` + `#4a4a55` border. Pressed: `#2f2f36`. Disabled:
  `SURFACE` fill, `DISABLED` text, `BORDER`.
  - Primary: `btn.setProperty("primary", True)` → `ACCENT` fill with `BG` text,
    weight 600. It wins by **inverting value** (16:1 against the canvas), not by
    being one grey lighter. Exactly one primary is visible per view — the four in
    the digitization page are one-per-tab plus the empty state.
  - Danger: `btn.setProperty("danger", True)` → `DANGER` text/border, 12% tinted hover.
  - Default height is 32px; hero buttons set 34–36px explicitly.
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
- **Floating surfaces (menus, dropdowns, tooltips)** — `POPUP` fill, 1px
  `BORDER_STRONG`, radius 6, 4px padding; rows at `padding: 6px 10px` radius 4,
  `TEXT_SEC` at rest and `POPUP_SEL` + `TEXT` when highlighted; `outline: none`
  on the dropdown view to kill the dotted focus rect. A popup **must** sit a
  level above whatever it covers: they previously used `SURFACE`, which is
  dL\* 0.0 against a `SURFACE` island — the menu had literally no separation
  from the panel behind it.
- **West tab strip** (digitization page) — `_TAB_STRIP_W = 48`, square 48×48 cells
  painted by `VerticalTabBar` (see Qt gotchas). The band is **one uniform
  `SURFACE2` for the whole column**, painted by `#digitRightPanel` (the panel is
  the bottom-most layer and always paints); `QTabWidget` is `transparent` and the
  pane paints `BG` over the content area. The cells paint **no background** and
  every icon draws at **full opacity**; the only state marker is the 3px
  `ACCENT2` indicator.
  Three things that each broke this and must not come back: a `BG` fill on the
  selected cell (7.2 dL\* darker than the band — a black hole), a lighter
  `SURFACE3` fill (still reads as a block stuck on the strip), and dimming
  inactive icons by opacity (they just look switched off).
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
- **A stylesheet set on a container propagates to its children and beats the app
  stylesheet.** `header.setStyleSheet("background:#131316; border:none;")` flattened
  every button inside that header — the Settings "Guardar" primary rendered as a
  dark, borderless label. Always scope container rules with an id selector:
  `w.setObjectName("x"); w.setStyleSheet("#x { … }")`. This bit seven containers
  across the app (page headers, toolbars, the top nav bar, the home root).
  Leaf `QLabel`s with inline rules are harmless — they have no children.
- **A West `QTabBar` cannot centre an icon via QSS.** Qt reserves the tab's text
  slot even with an empty label, which measured as a fixed **16px of phantom
  space at the top** of every cell: `top gap = padding-top + 16`,
  `bottom gap = padding-bottom`, `cell height = icon + top + bottom + 16`.
  For a 48px square cell that solves to `padding-top = -3.2px` — impossible.
  A reserved `border-right` also shifts the icon left, since it shrinks the
  content box on one side only. The fix is `VerticalTabBar`: override
  `tabSizeHint` and `paintEvent`, and place the icon with integer arithmetic
  (`(48-22)//2`). Use explicit maths, not `QRect.center()` — on an even-sized
  rect `center()` lands half a pixel low/left and reintroduces a 1px shift.
  Icons painted this way are **not** rotated by Qt, so they must not be
  pre-rotated (`_emoji_icon` used to compensate for a rotation that no longer
  happens). Verified at 0.00px deviation across 5 tabs × 5 selection states.
- **`QTabWidget` does not reliably paint its own background.** It draws the pane
  and the tab bar; the leftover strip column below the last tab is painted by
  nobody and falls through to the global `QWidget { background-color: BG }`,
  giving a two-tone strip. Put the band on the parent panel (a plain `QWidget`
  always paints its background) and set the `QTabWidget` transparent.
- **Grabbing a widget directly can hide a background bug.** `tabs.grab()` forces
  that widget to paint its own background, so the strip measured perfectly
  uniform while the running app showed two tones. Grab the **parent** (or the
  window) when verifying anything about background layering.
- **Unscoped container stylesheets also leak into popups**, not just child
  widgets: a host with `setStyleSheet("background:#0a0a0b")` forced a combo box's
  dropdown to paint on `BG`. Another reason to always use an id selector.
- **QSS `min-height` overrides `setFixedHeight()`.** With `min-height: 28px` plus
  `6px` padding, every button had a 42px floor, so *every* `setFixedHeight(32)` in
  the codebase was silently ignored and buttons overflowed 44px toolbars. Keep the
  QSS floor at or below the smallest height any call site asks for.
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
