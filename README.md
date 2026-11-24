<a id="top"></a>

# ClaraPDFPro

![Version](https://img.shields.io/badge/version-1.2.4-2b579a)
![License](https://img.shields.io/badge/license-MIT-2b579a)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**English** | [简体中文](#zh)

> **Latest release: v1.2.4** — rewritten text now keeps the original typography: edits are written back with the span's own font (embedded subset first, then the matching system font file with the same family, weight and slant), at the original size, color and baseline.
> **[→ Jump to Changelog](#changelog)**

ClaraPDFPro is a local, offline PDF toolkit for Windows. It starts as a PDF editor with an Office-style ribbon, converts PDF to and from Word / Excel, compresses PDFs to a chosen DPI or file size, organizes pages visually, exports pages as images, builds PDFs from images, and protects documents with passwords. Nothing is uploaded — every operation runs on your machine.

## Features

| Module | Capabilities |
| --- | --- |
| **Edit PDF** | The app opens directly into the editor — thumbnail strip on the left, page view on the right — with an **Office-style ribbon** (**Home / Edit / View / Tools**) for open, save, save-as, undo / redo, mode and annotation tools, OCR, page navigation, zoom and display toggles. The **Tools** tab embeds every other module in the same window — convert, compress, organize, PDF-to-image, image-to-PDF, encrypt / decrypt and About — plus a card-based toolbox home. Fill form fields, toggle checkboxes / radio buttons, edit combo and list boxes inline; **WYSIWYG text editing** — click any text to rewrite it in place, keeping position, size and color (Chinese and Latin); **annotations** — highlight, underline and sticky notes by selecting text; **OCR** — recognize the current page or all pages with the built-in Windows engine and add an invisible, searchable text layer; undo / redo, in-place incremental save and save-as; thumbnail strip, zoom, and browse / form / text / annotate modes |
| **Convert** | PDF → Word (headings, paragraphs, tables, images rebuilt), PDF → Excel (tables detected per page), Word → PDF, Excel → PDF |
| **Compress** | Compress by image DPI + JPEG quality, compress to a target file size, maximum compression by rasterizing pages |
| **Organize** | Thumbnail page manager: rotate, delete, reorder and save; extract page ranges; split every *N* pages; merge multiple PDFs |
| **PDF to Images** | Export pages as PNG / JPEG at a custom DPI with page-range support |
| **Images to PDF** | Combine images into one PDF, fitted to A4 or kept at original size |
| **Security** | AES-256 password encryption and password removal |
| **Interface** | Chinese / English UI, light / dark theme, background tasks with progress, remembered settings |

## Requirements

- Windows 10 / 11
- Python 3.10 or newer
- Microsoft Word and Excel — required only for Word/Excel → PDF conversion (uses Office COM automation)
- A Windows OCR language pack — built into Windows 10 / 11 (Chinese and English are usually installed already); OCR needs no model download and no network

## Installation

```powershell
cd C:\Users\Administrator\Desktop\GIT\ClaraPDFPro
python -m pip install -r requirements.txt
python app.py
```

Or simply double-click `run.bat` (starts silently, without a console window).

## Quick Start

1. The app opens directly in the **PDF editor** — click **Open** on the ribbon (or the button in the centre) and pick a PDF.
2. Work with the **Home / Edit / View** tabs: choose the mode and annotation tool, use OCR, navigate pages, zoom; **Ctrl+S** saves.
3. Switch to the **Tools** tab for the other modules — conversion, compression, page organization, image export/import and security — they open in the same window; **Back to document** returns to the editor.
4. In a tool, choose the source file — the output path is suggested automatically — adjust options and click the primary button.

## Project Structure

```text
ClaraPDFPro/
├── app.py                    # Application entry point
├── run.bat                   # One-click launcher
├── requirements.txt
├── LICENSE
├── README.md
└── clara_pdf/
    ├── __init__.py           # App name / version
    ├── main_window.py        # Toolbox window and navigation
    ├── pages.py              # Tool pages
    ├── page_editor.py        # Thumbnail page manager dialog
    ├── pdf_engine.py         # Page ops, merge/split, images, encryption
    ├── pdf_editor_engine.py  # Long-lived document: render, form fields, OCR, save, undo
    ├── pdf_view.py           # Page painter with inline field editors
    ├── editor_window.py      # Editor main window (Office-style ribbon, thumbnails, status bar)
    ├── ocr.py                # Windows OCR wrapper (optional EasyOCR fallback)
    ├── converter.py          # PDF ↔ Word / Excel
    ├── compressor.py         # PDF compression
    ├── tool_widgets.py       # Reusable widgets and task base
    ├── worker.py             # Background thread
    ├── i18n.py               # Chinese / English strings
    ├── theme.py              # Light / dark stylesheet
    ├── settings.py           # User preferences
    ├── fileutils.py          # Path and size helpers
    └── icons.py              # Generated application icon
```

## Versioning

Versions use a three-part number `MAJOR.MINOR.PATCH` and increase **one step per release**, with no skipped numbers:

| Situation | Rule | Example |
| --- | --- | --- |
| Normal update | `PATCH` + 1 | `1.0.0` → `1.0.1` |
| `PATCH` reaches 9 | `MINOR` + 1, `PATCH` → 0 | `1.0.9` → `1.1.0` |
| `MINOR` and `PATCH` both reach 9 | `MAJOR` + 1, `MINOR` / `PATCH` → 0 | `1.9.9` → `2.0.0` |

The version is defined in `clara_pdf/__init__.py` (`__version__`) and mirrored in the "Latest release" block above and in the changelog.

## Release & Backup Workflow

Before every release, back up the **previous** version completely:

1. Copy the whole project (excluding `backups/`, `__pycache__/`, `.venv/`) into
   `C:\Users\Administrator\Desktop\GIT\ClaraPDFPro_Backups\`.
2. Name the backup folder `<previous version>_<update summary>`,
   for example `1.0.0_Add-scan-compression` or `1.0.0_新增扫描件压缩`.
3. Bump `__version__` in `clara_pdf/__init__.py`.
4. Update the "Latest release" block at the top of this README and add a changelog entry.
5. Run the smoke tests, then release.

> v1.1.0 is archived at `ClaraPDFPro_Backups\1.1.0_模块融入功能区`. The next backup will be created when v1.1.2 is prepared.

## Roadmap

- OCR quality tuning: deskew and multi-column layout handling
- Batch conversion queue

## Changelog

<a id="changelog"></a>

### v1.2.4 — 2026-11-24 — Rewrites keep the original font, weight and color

- **New text matches the old text.** `replace_text()` no longer writes with the generic base‑14 faces (Helvetica / Times / `china‑s`). It now redacts the span and writes the new string back with the span's own font: the embedded subset when it covers every character, otherwise the matching system font file chosen by family plus the bold / italic flags (`_FONT_FILES` covers YaHei, Arial, Times, Consolas, Cascadia, Segoe UI, Calibri, Cambria, Courier, Verdana, Georgia, SimSun, SimHei, KaiTi, FangSong), keeping the original size, color and baseline `origin`
- **Verified by pixels on `README.pdf`.** Re‑writing a span with its own text gives a mean difference of 0.10/255 for CJK body text and 1.00/255 for the bold heading, with identical ink coverage (1.00); a missing family falls back by category instead of switching to a serif face (Cascadia Mono → Consolas)
- **Space characters stay searchable.** Embedding a system font makes PyMuPDF emit U+00A0 for spaces; spans now normalise it back to a regular space

### v1.2.3 — 2026-11-24 — Horizontal alignment, real font matching

- **No more left/right shift.** The editor is placed at the PDF pen origin (`origin.x`, so leading spaces and indents are honoured) minus QLineEdit's internal 2 px left padding, instead of at the bbox edge
- **No more cumulative drift.** Qt rounds every glyph advance to whole pixels and substitutes fonts, so a long line ended up several pixels short/wide. Each span now gets a `letter-spacing` correction derived from its own ink width, so the right edge lines up as well as the left. Measured on `README.pdf` (32 spans): baseline deviation ≤ 0.47 px, horizontal deviation ≤ 3.5 px, most spans within 2 px
- **English and code fonts are recognised.** `_qt_font_family()` now matches PDF names against the real `QFontDatabase` families after stripping subset prefixes and synthetic suffixes (`‑0‑400`, `‑BoldMT`), so `CascadiaMono‑0‑400` → Cascadia Mono, `SegoeUI‑Semibold` → Segoe UI Semibold; monospace/serif/sans heuristics cover fonts that are not installed
- **Letter spacing survives the theme.** Qt's style sheet rebuilds the widget font on polish and drops the correction, so the editor font is re-applied after `show()`

### v1.2.2 — 2026-11-23 — Baseline‑exact inline editor, correct bold detection

- **Text no longer drifts downward / down‑left.** The editor rectangle is now derived from the PDF baseline (`origin.y`) instead of the span bbox: height = font `ascent + descent`, top = `baseline − ascent`, with `setTextMargins(0,0,0,0)` and no extra padding. Measured deviation across 25 spans of `README.pdf`: ≤ 0.5 px
- **Bold fixed.** `_qfont_for_span` was treating PyMuPDF `flags` bit 2 (serifed) as bold. Bold is bit 4; the code now uses `1 << 4` and additionally inspects the font name (`bold` / `black` / `heavy` / `semibold` / `demi`)
- **Better font family resolution.** New `_qt_font_family()` strips subset prefixes (`ABCDEF+`), internal ids (`F1,Helv`), and style suffixes (`‑BoldMT`, `‑Semibold`, `‑Roman`), then maps PDF names to real system fonts (`MicrosoftYaHeiUI‑0‑400` → Microsoft YaHei UI, `Helv` → Arial, `ti` → Times New Roman, `china‑s` → SimSun, …), falling back to Qt substitution only when nothing matches

### v1.2.1 — 2026-11-23 — Word‑style caret when clicking text

- **No more auto‑selection.** The inline editor used to `selectAll()` on open, so a click looked like it grabbed the whole left segment. It now places a caret only and calls `deselect()`
- **Caret lands where you clicked.** `PdfEditorEngine.text_spans` now reads `rawdict` and stores each glyph's origin x (`char_x`); `_caret_index` maps the click offset (converted to PDF units via `scale`) onto those real glyph positions, so the caret does not depend on Qt font substitution
- **Font size no longer too small.** The editor point size is converted from PDF points to display points (`size × scale × 72 / logicalDpi`), matching the rendered glyph height instead of using the raw PDF point value
- **Page‑coloured mask.** The editor background is sampled from the rendered page image next to the span, so the editable text hides the original glyphs underneath instead of double‑drawing
- **Commit on click elsewhere.** `_close_editor(commit=True)` applies the pending edit when the user clicks another span / blank area or switches modes, like Word; `Esc` still cancels
- **Safe font fallback.** `_resolve_fontname` strips subset prefixes (`ABCDEF+…`) and verifies the font with `pymupdf.Font`, falling back to base‑14 when the original font file is unavailable (fixes a `need font file or buffer` error on some PDFs)

### v1.2.0 — 2026-11-23 — WYSIWYG text editing

- `PdfPageView._open_text_editor` now builds an inline `QLineEdit` that matches the PDF span font **exactly**: family (with pymupdf base‑14 → real name mapping: Helv → Helvetica, ti → Times New Roman, cour → Courier New, china‑s → SimSun, etc.), size (pointSizeF from the span, no more `× 0.75` hack), bold / italic (from pymupdf text `flags` bits), and color (raw 24‑bit int → RGB)
- **Qt pitfall fixed.** The global theme stylesheet had a catch‑all `QWidget { font-family: ...; font-size: 9pt; }` rule that silently overrode `setFont()` on every inline editor when it was shown. The editor's per‑widget stylesheet now explicitly writes `font-family`, `font-size`, `font-weight`, `font-style`, and `color` so the original PDF rendering survives
- `PdfEditorEngine.replace_text` now preserves the original `span["font"]` when redrawing text after the redaction+reinsert dance, instead of always switching to `_font_for_text`'s generic fallback
- Added `PdfPageView._qfont_for_span` and `_qcolor_for_span` static helpers that centralise font lookup / pymupdf flag decoding / color unpacking, so the same transform is used by both the UI and the engine

### v1.1.9 — 2026-11-23 — Scroll‑wheel direction, take three

- Switched `SmoothScrollArea.wheelEvent` from `sb.value() + delta` back to `sb.value() - delta`
- The Qt docs say angleDelta.y > 0 means the wheel rotated "down" (away from the user), but real end‑user machines report the sign they observe, not the documented one. The user tested, `- delta` is what feels natural on their Windows box

### v1.1.8 — 2026-11-23 — Restore your editing session on next launch

- **Session restore.** On close, the app now writes `last_path`, the current page index, dpi, and editor mode into QSettings. If the document has unsaved edits (`engine.dirty`), they are flushed into a temporary backup file in `%APPDATA%\Clara\last_edit_backup.pdf` before the engine closes
- **Restore flow.** `app.py` now calls `PdfEditorWindow.restore_session()` right after construction. It prefers the backup when one exists (so unsaved text edits, highlights, annotations, and form values survive a restart), but always keeps `engine.path` pointing back at the original file — the user's next Save goes where they expect
- **Auto‑fit skip.** Added an `auto_fit=False` flag to `_attach_engine`. Restore sessions pass it so the "fit to width" QTimer singleShot (used for fresh opens) does not clobber the dpi / zoom / page we just restored
- **Wheel direction reverted.** The `SmoothScrollArea.wheelEvent` is back to `sb.value() + delta`. The previous `sb.value() - delta` from v1.1.7 caused the scroll bar to clamp at zero at the top of the document, because on Windows `angleDelta.y() > 0` already means "scroll down" and `sb.setValue(value + delta)` is the correct direction
- **Clean‑close cleanup.** When the document is clean on close, the stale backup file is deleted so restore only uses fresh state

### v1.1.7 — 2026-11-23 — Mouse wheel direction fixed

- PySide6 on Windows reports wheel motion with the sign opposite to the user's intuition: rolling the wheel "down" (away from you) produced a positive `angleDelta.y()`, but feeding that straight into the scroll bar made the page move **up**
- Switched from `sb.setValue(sb.value() + delta)` to `sb.setValue(sb.value() - delta)`, so the direction now matches the OS (scroll down → page down, scroll up → page up)

### v1.1.6 — 2026-11-23 — Continuous vertical scrolling like Word

- `PdfPageView` now pre‑renders every page once, stacks them vertically inside a single widget (with an 8‑px gap), and `paintEvent` draws all of them in one long canvas — no more single‑page switch
- Hit‑testing computes which page segment the mouse lands in first, then resolves fields, text spans, and annotations in that page's local coordinates, so form fill, text edit, highlight, underline, and sticky notes all still work correctly
- The old `PageScrollArea` with its edge‑triggered page flipping is replaced by a thin `SmoothScrollArea` that simply translates `wheelEvent.angleDelta` into `verticalScrollBar.setValue`, because under PySide6 on Windows `super().wheelEvent()` alone does not move the scroll bar
- `_goto(idx)` now animates the scroll bar to `PdfPageView.offset_of_page(idx)` instead of rebuilding a single page; a new `_on_scroll_changed(value)` listens to the scroll bar and derives the current page from the offset table, which keeps page label, thumbnail highlight, and status bar perfectly in sync with wherever you have scrolled to

### v1.1.5 — 2026-11-23 — Mouse wheel actually drives the view

- The custom `PageScrollArea.wheelEvent` was calling `super().wheelEvent(event)` which, under Qt/PySide6 on Windows, was a no‑op: the scroll bar never moved, even though the event reached the widget
- Rewrote the wheel handler to move `verticalScrollBar.setValue(...)` directly from `angleDelta`, so rolling the wheel now actually scrolls the page contents up and down
- Kept the edge paging: when you reach the bottom of the current page and keep rolling down, it flips to the next page and resets the scroll bar to the top; conversely for going up

### v1.1.4 — 2026-11-23 — Mouse wheel scrolls across every page

- Replaced the plain QScrollArea with a `PageScrollArea` that watches wheel events
- When the wheel reaches the bottom of the current page and you keep scrolling down, the viewer flips to the next page and starts from the top
- When the wheel reaches the top and you keep scrolling up, the viewer flips back one page and shows it from the bottom
- Normal in‑page scrolling still works; first and last pages simply stop the wheel instead of overflowing

### v1.1.3 — 2026-11-23 — Language preference survives a restart

- The current language is now flushed to settings every time you switch it, and one more time on window close
- The next time you launch the app it starts in that same language — no matter whether you last chose 中文 or English

### v1.1.2 — 2026-11-23 — Ribbon corner, merged tabs, text-edit default

- Added the **light / dark theme** toggle to the ribbon corner alongside language and About; three buttons, always visible
- Removed the redundant **Settings & language** button from the Tools tab — the corner is the single home for language and theme
- Merged **Home + Edit** into a single **Home** tab: deduplicated the annotate tools and kept every unique control (file, undo, mode, annotate, OCR)
- Switched the default mode on startup to **text‑edit** instead of form‑fill, so double‑clicking text is ready to go from frame one

### v1.1.1 — 2026-11-23 — The editor view is always embedded in the main window

- Removed the separate start screen: the editor shell — **thumbnail strip on the left, page view on the right** — is shown as soon as the app starts
- Added an **Open** button directly inside the empty viewer, in addition to the ribbon's **Open** (Ctrl+O); documents open in place, never in a popup window
- While no document is open, the viewer shows a short hint and all document actions stay disabled; OCR, tools and the toolbox keep working
- Switching to the **Tools** tab and back restores the viewer exactly where it was
- Brought back the **language switch** and **About** entries — pinned to the top-right corner of the ribbon and always one click away

### v1.1.0 — 2026-11-23 — All modules back, inside the Office-style ribbon

- Added a **Tools** tab to the ribbon: **Convert**, **Compress**, **Organize**, **PDF to image**, **Image to PDF**, **Encrypt / Decrypt** and **About** all open inside the editor window — no separate toolbox window needed
- New card-based **toolbox home** inside the Tools tab, plus **Back to document** and **Toolbox home** buttons
- Tools keep their own state while you switch between the editor and a module; **Home / Edit / View** return to the PDF editor
- **Settings & language** opens the classic settings window (theme, language, About)
- Tools remain usable even without an open document; document actions stay disabled as before

### v1.0.9 — 2026-11-23 — Editor-first startup with an Office-style ribbon

- The app now opens **directly into the PDF editor**; the old editor landing page is gone
- The flat toolbar is replaced by an **Office-style ribbon** with **Home / Edit / View** tabs and labelled groups: File (Open / Save / Save as), Undo, Edit area (mode picker plus highlight / underline / note tools), OCR, Tools, Pages, Zoom and Display
- **Open** (Ctrl+O) picks a PDF from disk; without a document the window shows a centred "Open a PDF to start editing" invitation and all document actions stay disabled
- **Toolbox** opens the former main window for conversion, compression, page organization, image export and security
- Opening another document with unsaved changes asks to save first; encrypted files still prompt for a password
- All editing features (forms, text rewrite, annotations, OCR, undo / redo, save and save-as) work unchanged

### v1.0.8 — 2026-11-23 — OCR for scanned documents

- New **OCR** menu in the editor toolbar: recognize the current page or every page, with a cancellable progress dialog
- Recognition uses the built-in **Windows OCR engine** (`Windows.Media.Ocr`), so there is no model download and no network access; Chinese and English are used when their language packs are present
- Recognized lines are written back as an **invisible text layer** placed on the original text positions, making scanned pages selectable, searchable and copyable without changing how they look
- Pages that already contain text are skipped; OCR results are covered by undo / redo and are saved with the document
- If the Windows OCR components are missing, an optional **EasyOCR** fallback is used when `easyocr` is installed

### v1.0.7 — 2026-11-23 — WYSIWYG text editing and annotations

- **Edit text** mode: click any text on the page to rewrite it in place; the replacement restores the original position, font size, color and base-14 face (bold / italic / serif / monospace), and Chinese through the built-in CJK font
- **Annotate** mode: drag to select text and add a **highlight** or **underline**; place a **sticky note** anywhere
- Text and annotations are applied through redaction + rewrite and annotation APIs, so they render in any PDF viewer and are covered by undo / redo
- The mode selector now offers Browse / Fill form / Edit text / Annotate, with a dedicated annotation-tool picker

### v1.0.6 — 2026-11-23 — PDF editor with form filling

- New **Edit PDF** page opening a dedicated editor window with a thumbnail strip, zoom, page navigation and browse / form-fill modes
- Fill text fields (single-line and multi-line), combo boxes and list boxes, and toggle checkboxes / radio buttons inline on the page
- Required fields are marked with a red dot; read-only fields cannot be edited; appearance streams refresh immediately after every change
- Undo / redo backed by full-document snapshots, with in-place incremental save and save-as
- Encrypted documents prompt for a password; closing with unsaved changes asks for confirmation

### v1.0.5 — 2026-11-20 — Clear buttons for every tool

- Added a `Clear` button to Convert, Compress, PDF to Images and Security
- Added `Clear` buttons to the page-edit and split/extract sections of Organize
- Left the existing clear buttons in the multi-file lists (Organize merge, Images to PDF) unchanged

### v1.0.4 — 2026-11-20 — Silent startup

- The black console window no longer appears: `run.bat` launches with `pythonw`, and the app hides its own console when it is the only process attached
- Suppressed PyMuPDF's `pymupdf_layout` recommendation message
- Suppressed fontTools `created`/`modified` timestamp warnings emitted while building embedded fonts

### v1.0.3 — 2026-11-20 — Accurate tables, tree glyphs and line spacing

- Tightened table boundary detection so surrounding notes, headings and list items stay outside the table instead of being absorbed or duplicated inside cells
- Recovered box-drawing glyphs (│ ├ ─ └ ┌ ┐ ┘ ┤) from embedded subset fonts, so directory trees keep their branches in Word
- Measured real line pitch per page for body text and code blocks separately, with a document-wide fallback, and applied it as exact Word line spacing
- Matched the original font families (Microsoft YaHei UI / Cascadia Mono) to keep text widths and line breaks aligned
- Preserved page margins and eliminated spurious blank pages caused by spillover

### v1.0.2 — 2026-11-19 — PDF→Word style fidelity

- Preserve text color, font family (including monospace code), bold and italic for every run
- Preserve paragraph and inline background shading (code blocks, inline code, callouts)
- Keep table cell shading, drop the hard black grid, and use the original column widths
- Rebuild horizontal separators, bullet markers and hanging indents
- Use the PDF's real line heights and page margins for closer spacing

### v1.0.1 — 2026-11-19 — No green colors

- Removed all green tones from texts, backgrounds and controls
- Pinned the UI to the Fusion style with a fixed blue palette, so colors no longer follow the system accent color
- Fixed the window title bar color in both light and dark themes
- Changed the README license badge from green to Clara blue

### v1.0.0 — 2026-11-19 — Initial release

- Format conversion: PDF → Word, PDF → Excel, Word → PDF, Excel → PDF
- PDF compression by DPI, by target file size, and maximum (rasterized) mode
- Visual page manager: rotate, delete, reorder, save as
- Page extraction, split every *N* pages, PDF merging
- PDF → PNG/JPEG export with custom DPI and page ranges
- Images → PDF with A4 fit or original size
- AES-256 encryption and decryption
- Chinese / English UI, light / dark themes

[↑ Back to top](#top)

## License

Released under the [MIT License](LICENSE).

---

<a id="zh"></a>

# ClaraPDFPro（中文版）

[English](#top) | **简体中文**

> **最新版本：v1.2.4** — 改写后保持原字体：替换文字会用这段文字自己的字体写回（优先内嵌子集，其次同族同粗细同倾斜的系统字体文件），并保持原字号、颜色与基线位置，新文字与原文不再“两个样子”。
> **[→ 一键直达版本号更迭记录](#changelog-zh)**

ClaraPDFPro 是一款完全本地运行的 Windows PDF 工具箱：启动即为 PDF 编辑器（Office 风格功能区），支持 PDF 与 Word / Excel 双向转换、按 DPI 或目标体积压缩、可视化页面管理、PDF 转图片、图片转 PDF 以及密码加密。所有处理均在本机完成，文件不会上传。

## 功能

| 模块 | 能力 |
| --- | --- |
| **PDF 编辑** | 启动即进入编辑器——左侧缩略图、右侧页面视图——顶部为 **Office 风格功能区**（**开始 / 编辑 / 视图 / 工具**），提供打开、保存、另存为、撤销/重做、模式与批注工具、OCR、翻页、缩放与显示开关。**工具** 标签页把其余模块全部嵌入同一窗口——格式转换、PDF 压缩、页面管理、PDF 转图片、图片转 PDF、加密/解密与关于，并提供卡片式工具首页。可填写表单字段、勾选复选框/单选框、编辑下拉与列表框；**所见即所得文本编辑**——单击任意文字即可原位改写，保留位置、字号与颜色（中英文均支持）；**批注**——框选文字添加高亮、下划线，或放置便签；**OCR**——用 Windows 内置引擎识别当前页或全部页面，写入不可见的可检索文字层；支持撤销/重做、原地增量保存与另存为；含缩略图、缩放与浏览/填表/编辑文字/批注四种模式 |
| **格式转换** | PDF → Word（还原标题、段落、表格与图片）、PDF → Excel（逐页识别表格）、Word → PDF、Excel → PDF |
| **PDF 压缩** | 按图片 PPI + JPEG 质量压缩、按目标体积压缩、极限压缩（整页转图片） |
| **页面管理** | 缩略图管理器：旋转、删除、排序后另存；提取指定页；每 N 页拆分；多文件合并 |
| **PDF 转图片** | 按自定义 DPI 导出 PNG / JPEG，支持页码范围 |
| **图片转 PDF** | 多图合并为 PDF，可统一 A4 或保持原始尺寸 |
| **加密解密** | AES-256 加密与密码移除 |
| **界面** | 中英文切换、深浅色主题、后台任务进度、设置记忆 |

## 环境要求

- Windows 10 / 11
- Python 3.10 及以上
- Microsoft Word / Excel —— 仅 Word / Excel 转 PDF 时需要（通过 Office COM 调用）
- Windows OCR 语言包 —— Windows 10 / 11 自带（通常已含中文与英文）；OCR 无需下载模型，也不联网

## 安装

```powershell
cd C:\Users\Administrator\Desktop\GIT\ClaraPDFPro
python -m pip install -r requirements.txt
python app.py
```

也可以直接双击 `run.bat` 启动（无控制台窗口，静默运行）。

## 快速上手

1. 程序启动即为 **PDF 编辑器**——点击功能区「打开」（或窗口中央的按钮）选择 PDF。
2. 使用 **开始 / 编辑 / 视图** 三个标签页：选择模式与批注工具、执行 OCR、翻页与缩放；**Ctrl+S** 保存。
3. 切换到 **工具** 标签页使用其余模块——格式转换、压缩、页面管理、图片导入导出与加密解密，均在同一窗口打开；点「返回文档」回到编辑器。
4. 在工具页选择源文件——输出路径会自动生成——按需调整选项后点击主按钮。

## 项目结构

```text
ClaraPDFPro/
├── app.py                    # 程序入口
├── run.bat                   # 一键启动
├── requirements.txt
├── LICENSE
├── README.md
└── clara_pdf/
    ├── __init__.py           # 应用名 / 版本号
    ├── main_window.py        # 工具箱窗口与导航
    ├── pages.py              # 各工具页面
    ├── page_editor.py        # 缩略图页面管理器
    ├── pdf_engine.py         # 页面操作、合并拆分、图片、加密
    ├── pdf_editor_engine.py  # 长开文档：渲染、表单字段、OCR、保存、撤销
    ├── pdf_view.py           # 页面绘制与字段内联编辑器
    ├── editor_window.py      # 编辑器主窗口（Office 风格功能区、缩略图、状态栏）
    ├── ocr.py                # Windows OCR 封装（可选 EasyOCR 后备）
    ├── converter.py          # PDF ↔ Word / Excel
    ├── compressor.py         # PDF 压缩
    ├── tool_widgets.py       # 复用组件与任务基类
    ├── worker.py             # 后台线程
    ├── i18n.py               # 中英文文案
    ├── theme.py              # 深浅色样式
    ├── settings.py           # 用户偏好
    ├── fileutils.py          # 路径与体积工具
    └── icons.py              # 程序化生成图标
```

## 版本号规则

版本号采用 `主版本.次版本.修订号` 三段式，每次发布只进位一次，不跳号：

| 情况 | 规则 | 示例 |
| --- | --- | --- |
| 常规更新 | 修订号 + 1 | `1.0.0` → `1.0.1` |
| 修订号到达 9 | 次版本 + 1，修订号归零 | `1.0.9` → `1.1.0` |
| 次版本与修订号均为 9 | 主版本 + 1，次版本 / 修订号归零 | `1.9.9` → `2.0.0` |

版本号定义在 `clara_pdf/__init__.py` 的 `__version__`，并同步更新顶部“最新版本”与更新记录。

## 发布与备份流程

每次发布新版本前，必须完整备份**上一个版本**：

1. 将整个项目（排除 `backups/`、`__pycache__/`、`.venv/`）复制到
   `C:\Users\Administrator\Desktop\GIT\ClaraPDFPro_Backups\`。
2. 备份文件夹命名为 `<上一个版本号>_<本次更新内容>`，
   例如 `1.0.0_新增扫描件压缩`。
3. 修改 `clara_pdf/__init__.py` 中的 `__version__`。
4. 更新本 README 顶部的“最新版本”信息，并在更新记录中新增条目。
5. 运行冒烟测试后发布。

> v1.2.3 已备份至 `ClaraPDFPro_Backups\1.2.3_横向贴合与字距校正`，准备 v1.2.5 时创建下一份备份。

## 后续计划

- OCR 质量优化：倾斜校正与多栏排版处理
- 批量转换队列

## 版本号更迭记录

<a id="changelog-zh"></a>

### v1.2.4 — 2026-11-24 — 改写后保持原字体、粗细与颜色

- **新文字和原文字长得一样。** `replace_text()` 不再用通用的 base‑14 字体（Helvetica / Times / `china‑s`）写回，而是先涂黑原文字，再用这段文字自身的字体写入：内嵌子集能覆盖全部字符时直接用子集，否则按字体族 + 粗体/斜体标记挑选系统字体文件（`_FONT_FILES` 覆盖雅黑、Arial、Times、Consolas、Cascadia、Segoe UI、Calibri、Cambria、Courier、Verdana、Georgia、宋体、黑体、楷体、仿宋），保持原字号、颜色与基线 `origin`
- **在 `README.pdf` 上做了像素级验证。** 用原字体重写同一段文字后，中文正文平均差异 0.10/255、粗体标题 1.00/255，墨迹覆盖率均为 1.00；系统里没有同族字体时按类别兜底，而不是掉到衬线字体（Cascadia Mono → Consolas）
- **空格仍可检索。** 嵌入系统字体后 PyMuPDF 会把空格提取成 U+00A0，现在统一还原为普通空格

### v1.2.3 — 2026-11-24 — 横向对齐、真实字体匹配

- **不再左/右偏移。** 编辑框改按 PDF 笔位起点（`origin.x`）定位，前导空格与缩进自然参与排版，再抵消 QLineEdit 内置的 2 像素左边距，而不是贴着 bbox 边缘摆放
- **不再累积漂移。** Qt 会把每个字形步进取整、且用系统字体替换 PDF 内嵌字体，长行会出现几像素的偏窄/偏宽。现在按每段自身的墨迹宽度计算 `letter-spacing` 校正，右边缘与左边缘同时对齐。实测 `README.pdf` 32 个 span：基线偏差 ≤ 0.47 像素，横向偏差 ≤ 3.5 像素，多数在 2 像素内
- **英文与代码字体可识别。** `_qt_font_family()` 改为与真实 `QFontDatabase` 族名做紧凑匹配：剥掉子集前缀与生成器加的样式编号（`‑0‑400`、`‑BoldMT`），`CascadiaMono‑0‑400` → Cascadia Mono、`SegoeUI‑Semibold` → Segoe UI Semibold；未安装时按等宽/衬线/无衬线兜底
- **字距校正不被主题覆盖。** Qt 样式表在 polish 时会重建控件字体并丢掉字距设置，因此 `show()` 之后再设置一次编辑器字体

### v1.2.2 — 2026-11-23 — 编辑框贴合基线、粗体识别修正

- **文字不再下沉 / 左下偏。** 编辑框改为按 PDF 基线（`origin.y`）定位：高度取字体 `ascent + descent`，顶边为 `基线 − ascent`，并 `setTextMargins(0,0,0,0)`、不加额外内边距。实测 `README.pdf` 25 个 span 的基线偏差 ≤ 0.5 像素
- **粗体修正。** `_qfont_for_span` 之前把 PyMuPDF `flags` 的第 2 位（衬线）当成了粗体。粗体是第 4 位，现改为 `1 << 4`，并额外检查字体名（`bold` / `black` / `heavy` / `semibold` / `demi`）
- **字体族解析增强。** 新增 `_qt_font_family()`：去掉子集前缀（`ABCDEF+`）、内部编号（`F1,Helv`）、样式后缀（`‑BoldMT`、`‑Semibold`、`‑Roman`），再映射为系统真实字体（`MicrosoftYaHeiUI‑0‑400` → Microsoft YaHei UI、`Helv` → Arial、`ti` → Times New Roman、`china‑s` → SimSun 等），确实找不到时才交给 Qt 替换

### v1.2.1 — 2026-11-23 — 点击文字出现 Word 式光标

- **不再自动全选。** 以前打开内联编辑器时 `selectAll()`，点一下就像把左边整段文字都选中了。现在只定位光标并 `deselect()`
- **光标落在点击处。** `PdfEditorEngine.text_spans` 改用 `rawdict`，为每个字形记录起点 x（`char_x`）；`_caret_index` 把点击偏移按 `scale` 换算成 PDF 坐标后与真实字形位置比较，因此光标不依赖 Qt 的字体替换结果
- **字号不再偏小。** 编辑器点值由 PDF 点值换算为显示点值（`size × scale × 72 / 逻辑 DPI`），与渲染出的字形高度一致
- **页面底色遮罩。** 编辑器背景色从渲染页面图像中 span 旁边采样，覆盖住下方原文字，不再出现重影
- **点击别处即提交。** `_close_editor(commit=True)` 在点击其它 span / 空白处或切换模式时先提交当前修改（与 Word 一致）；`Esc` 仍然取消
- **字体安全回退。** `_resolve_fontname` 去掉子集前缀（`ABCDEF+…`）并用 `pymupdf.Font` 校验，原字体文件缺失时回退到 base-14（修复部分 PDF 报 `need font file or buffer` 的问题）

### v1.2.0 — 2026-11-23 — 文字编辑所见即所得

- `PdfPageView._open_text_editor` 现在构造一个内联 `QLineEdit`，字体**完全匹配** PDF span：字体族（pymupdf base14 名到真实字体的映射：Helv → Helvetica、ti → Times New Roman、cour → Courier New、china-s → SimSun 等）、字号（直接用 span 的 pointSizeF，不再乘 0.75 的 hack）、粗体/斜体（从 pymupdf text flags 位解码）、颜色（原始 24-bit int → RGB）
- **Qt 踩坑记录。** 全局主题样式表里有一条 `QWidget { font-family: ...; font-size: 9pt; }` 的兜底规则——每当 inline editor show() 时，Qt 重新应用样式表就把 setFont() 覆盖成 9pt。给每个 editor 写的 per-widget stylesheet 现在显式写出 font-family / font-size / font-weight / font-style / color，把主题那条全局规则挡在外面
- `PdfEditorEngine.replace_text` 在涂黑 + 重写的两步之后，现在优先用原始 `span["font"]` 重绘文字，而不是一刀切调用 `_font_for_text` 选通用 fallback
- 新增 `PdfPageView._qfont_for_span` 和 `_qcolor_for_span` 静态 helper，统一处理字体查找 / pymupdf flag 解码 / 颜色拆包，UI 和 engine 两端用同一个转换器

### v1.1.9 — 2026-11-23 — 滚轮方向再翻一次

- `SmoothScrollArea.wheelEvent` 从 `sb.value() + delta` 改回 `sb.value() - delta`
- Qt 文档说 angleDelta.y > 0 代表滚轮"向下"旋转（远离用户），但真实 Windows 机器上驱动 / 触摸板实现可能有差异。用户实际试了之后 `- delta` 才是手感正常的方向，所以以实测为准

### v1.1.8 — 2026-11-23 — 下次打开自动回到上次编辑状态

- **会话恢复。** 关闭时把 `last_path`、当前页码、dpi、编辑模式写入 QSettings；如果文档有未保存改动（`engine.dirty`），先把内存状态另存到临时备份文件 `%APPDATA%\Clara\last_edit_backup.pdf` 再关闭 engine
- **恢复流程。** `app.py` 启动时在构造 `PdfEditorWindow` 之后立刻调 `restore_session()`。优先打开临时备份（这样哪怕改了文字、高亮、批注、表单值都能跨重启保留），但 `engine.path` 始终指向原文件——下次 "保存" 还是存到用户期望的位置
- **跳过自动适应宽度。** `_attach_engine` 加了 `auto_fit=False` 参数，恢复会话时传 False，让"新开 PDF 时自适应宽度"的 QTimer 定时器不要覆盖我们刚恢复的 dpi/页码
- **滚轮方向回归正确。** `SmoothScrollArea.wheelEvent` 改回 `sb.value() + delta`。v1.1.7 里取反之后，从顶部开始滚 delta=+120 → value - 120 = -120 → 被 clamp 到 0 → 滚轮看起来完全不动；Windows 上 angleDelta.y > 0 本来就是向下推的语义，直接加就对了
- **干净关闭清理备份。** 如果文档关闭时已 clean（无未保存改动），则删除上次残留的临时备份文件

### v1.1.7 — 2026-11-23 — 滚轮方向修正

- PySide6 on Windows 的 `angleDelta.y()` 符号和用户直觉相反：滚轮向下推 `delta` 是正的，但直接加到 sb 上页面反而往上走
- 从 `sb.value() + delta` 改成 `sb.value() - delta`，方向现在符合 OS 默认（向下滚 = 页面内容向下、看更后面）

### v1.1.6 — 2026-11-23 — Word 式连续垂直滚动

- `PdfPageView` 启动时预渲染全部页面，垂直堆叠在同一个 widget 内（页间留 8 px 空隙），`paintEvent` 一次性画出整条长画布——不再按页切换
- hit-test 先算出鼠标落在哪一页段内，再用该页的局部坐标查字段、文本 span 和批注，因此表单填写、文本编辑、高亮、下划线、便签依然全部可用
- 旧的触边翻页 `PageScrollArea` 换成极简 `SmoothScrollArea`：仅把 `wheelEvent.angleDelta` 转成 `verticalScrollBar.setValue`——因为 PySide6 on Windows 下 `super().wheelEvent()` 就是 no-op
- `_goto(idx)` 现在让滚动条滚到 `PdfPageView.offset_of_page(idx)` 而不是重建单页；新增 `_on_scroll_changed(value)` 监听滚动条反向推导当前页，页码 label、缩略图高亮、状态栏全部自动同步

### v1.1.5 — 2026-11-23 — 滚轮真正驱动视图了

- 原来 `PageScrollArea.wheelEvent` 里调 `super().wheelEvent(event)` 在 Windows + PySide6 下是空操作：事件到了但滚动条没动
- 改成直接从 `angleDelta` 调 `verticalScrollBar.setValue(...)`，滚轮现在真的能把页面内容上下滚动
- 保留触边翻页：当前页到底继续向下滚 → 下一页从顶部接入；到顶继续向上滚 → 上一页从底部接入

### v1.1.4 — 2026-11-23 — 滚轮可以穿过所有页面

- 把简单 QScrollArea 换成 `PageScrollArea`，专门监听滚轮事件
- 当前页滚到底后继续向下滚 → 自动翻到下一页，并从顶部开始显示
- 当前页滚到顶后继续向上滚 → 自动翻回上一页，并从底部开始显示
- 页内正常滚动不受影响；第一页再向上滚、最后一页再向下滚时自然停住

### v1.1.3 — 2026-11-23 — 关闭时记忆中英文状态

- 每次切换语言即时写入设置，窗口关闭时再刷一次，确保无遗漏
- 下次启动时自动进入上次关闭时的语言——无论选的是「中文」还是「English」

### v1.1.2 — 2026-11-23 — 功能区右上角、标签合并、默认编辑文字

- 在功能区右上角新增 **浅色 / 深色** 主题切换按钮，与语言、关于并列，始终可见
- 从工具标签页移除重复的 **设置与语言** 按钮——语言与主题统一在右上角管理
- 将 **开始 + 编辑** 合并为一个 **开始** 标签页：批注工具去重，保留全部唯一项（文件、撤销、模式、批注、OCR）
- 启动默认模式改为 **编辑文字**，不再落在表单模式；双击文字即可改写

### v1.1.1 — 2026-11-23 — 编辑器视图常驻主窗口

- 取消独立起始页：程序启动后主窗口直接显示编辑器外壳——**左侧缩略图、右侧页面视图**
- 在空视图内直接新增 **打开** 按钮，同时保留功能区的「打开」（Ctrl+O）；文档始终在当前窗口原位打开，不再弹出新窗口
- 未打开文档时视图显示简短提示，文档相关按钮保持禁用；OCR、工具页与工具箱照常可用
- 切换到 **工具** 标签页再返回时，视图恢复到原来的位置与状态
- 恢复 **语言切换** 与 **关于** 入口，固定在功能区右上角，随时一键可达

### v1.1.0 — 2026-11-23 — 模块回归，全部融入 Office 风格功能区

- 功能区新增 **工具** 标签页：**格式转换**、**PDF 压缩**、**页面管理**、**PDF 转图片**、**图片转 PDF**、**加密 / 解密** 与 **关于** 全部在编辑器窗口内打开，无需另开工具箱窗口
- 工具标签页提供卡片式 **工具首页**，以及 **返回文档**、**工具首页** 两个导航按钮
- 编辑器与模块之间切换时各工具保留自身状态；点击 **开始 / 编辑 / 视图** 即返回 PDF 编辑器
- **设置与语言** 打开经典设置窗口（主题、语言、关于）
- 未打开文档时也可使用全部工具，文档相关按钮仍保持禁用

### v1.0.9 — 2026-11-23 — 启动即编辑器，Office 风格功能区

- 程序**启动直接进入 PDF 编辑器**，原来的编辑器入口页已移除
- 平铺工具栏改为 **Office 风格功能区**，含 **开始 / 编辑 / 视图** 三个标签页，并按组标注：文件（打开 / 保存 / 另存为）、撤销、编辑区（模式下拉与高亮 / 下划线 / 便签工具）、OCR、工具、页面、缩放、显示区
- **打开**（Ctrl+O）从磁盘选择 PDF；未打开文档时中央显示「打开 PDF 开始编辑」引导，文档相关按钮保持禁用
- **工具箱** 按钮打开原主窗口，继续提供转换、压缩、页面管理、图片导出与加密解密
- 切换文档时若有未保存更改会先询问是否保存；加密文档仍会提示输入密码
- 表单填写、文字改写、批注、OCR、撤销/重做、保存与另存为等原有功能全部保留

### v1.0.8 — 2026-11-23 — 扫描件 OCR

- 编辑器工具栏新增 **OCR** 菜单：识别当前页或全部页面，识别过程带可取消的进度条
- 识别使用 **Windows 内置 OCR 引擎**（`Windows.Media.Ocr`），无需下载模型、无需联网；系统装有中文 / 英文语言包时自动选用
- 识别结果按原始位置写回**不可见文字层**，扫描件因此可选中、可搜索、可复制，页面外观完全不变
- 已有文字层的页面自动跳过；识别结果纳入撤销 / 重做，并随文档保存
- 若系统缺少 Windows OCR 组件且已安装 `easyocr`，则自动改用 **EasyOCR** 后备

### v1.0.7 — 2026-11-23 — 所见即所得文本编辑与批注

- **编辑文字**模式：单击页面任意文字即可原位改写；替换时还原原始位置、字号、颜色与 base-14 字形（粗体/斜体/衬线/等宽），中文使用内置 CJK 字体
- **批注**模式：拖选文字添加**高亮**或**下划线**；可在任意位置放置**便签**
- 文本改写采用「涂黑 + 重写」，批注采用标准注释 API，任何 PDF 阅读器均可正常显示，且纳入撤销/重做
- 模式下拉扩为 浏览 / 填表 / 编辑文字 / 批注，并新增批注工具选择

### v1.0.6 — 2026-11-23 — 新增 PDF 编辑器与表单填写

- 新增「PDF 编辑」页面，打开独立编辑器窗口，含缩略图条、缩放、翻页以及浏览 / 填表两种模式
- 在页面上直接填写单行/多行文本框、下拉框与列表框，勾选复选框与单选框
- 必填字段标记红点；只读字段禁止编辑；每次修改后外观流即时刷新
- 基于整份文档快照的撤销 / 重做，支持原地增量保存与另存为
- 加密文档打开时提示输入密码；关闭时若有未保存更改会二次确认

### v1.0.5 — 2026-11-20 — 所有工具页新增清空按钮

- 格式转换、压缩、PDF 转图片、加密解密页新增“清空”按钮
- 页面管理的“页面编辑”和“拆分/提取”区域新增“清空”按钮
- 多文件列表（页面管理合并、图片转 PDF）原有的“清空”按钮保持不变

### v1.0.4 — 2026-11-20 — 静默启动

- 启动时不再出现黑色控制台窗口：`run.bat` 改用 `pythonw` 启动，程序也会在控制台只挂着自身时自动隐藏
- 屏蔽 PyMuPDF 的 `pymupdf_layout` 推荐提示
- 屏蔽 fontTools 在构建嵌入字体时输出的 `created`/`modified` 时间戳告警

### v1.0.3 — 2026-11-20 — 表格、目录树符号与行距还原

- 收紧表格边界识别：表格外的注意事项、标题与列表项不再被吞进单元格，也不会重复出现
- 从嵌入的子集字体中还原制表符（│ ├ ─ └ ┌ ┐ ┘ ┤），Word 中目录树的分支线完整显示
- 逐页分别统计正文与代码块的真实行距（并有全文兜底），写入 Word 固定行距
- 匹配原文字体（微软雅黑 UI / Cascadia Mono），字宽与换行位置更接近原 PDF
- 保留页边距，并消除内容溢出造成的多余空白页

### v1.0.2 — 2026-11-19 — PDF 转 Word 样式还原

- 逐段保留文字颜色、字体（含等宽代码字体）、粗体与斜体
- 保留段落与行内底色（代码块、行内代码、提示块）
- 保留表格单元格底色，去掉生硬黑框，并按原 PDF 列宽排版
- 还原横向分割线、项目符号与悬挂缩进
- 使用 PDF 实际行高与页边距，间距更接近原文

### v1.0.1 — 2026-11-19 — 去除绿色

- 移除界面中所有绿色（文字、底色与控件）
- 固定使用 Fusion 风格与自有蓝色调色板，不再跟随系统强调色
- 固定深浅色主题下的窗口标题栏颜色
- README 许可证徽章由绿色改为 Clara 蓝

### v1.0.0 — 2026-11-19 — 首个版本

- 格式转换：PDF → Word、PDF → Excel、Word → PDF、Excel → PDF
- PDF 压缩：按 PPI、按目标体积、极限压缩（转图片）
- 可视化页面管理：旋转、删除、排序、另存
- 页面提取、每 N 页拆分、PDF 合并
- PDF 转 PNG / JPEG，支持自定义 DPI 与页码范围
- 图片转 PDF，支持 A4 适应或原始尺寸
- AES-256 加密与解密
- 中英文界面、深浅色主题

[↑ 返回顶部](#top)

## 许可证

基于 [MIT License](LICENSE) 发布。
