<a id="top"></a>

# ClaraPDFPro

![Version](https://img.shields.io/badge/version-1.0.7-2b579a)
![License](https://img.shields.io/badge/license-MIT-2b579a)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**English** | [简体中文](#zh)

> **Latest release: v1.0.7** — WYSIWYG text editing plus annotations: highlight, underline and sticky notes.
> **[→ Jump to Changelog](#changelog)**

ClaraPDFPro is a local, offline PDF toolkit for Windows. It converts PDF to and from Word / Excel, compresses PDFs to a chosen DPI or file size, organizes pages visually, exports pages as images, builds PDFs from images, and protects documents with passwords. Nothing is uploaded — every operation runs on your machine.

## Features

| Module | Capabilities |
| --- | --- |
| **Edit PDF** | Fill form fields, toggle checkboxes / radio buttons, edit combo and list boxes inline; **WYSIWYG text editing** — click any text to rewrite it in place, keeping position, size and color (Chinese and Latin); **annotations** — highlight, underline and sticky notes by selecting text; undo / redo, in-place incremental save and save-as; thumbnail strip, zoom, and browse / form / text / annotate modes |
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

## Installation

```powershell
cd C:\Users\Administrator\Desktop\GIT\ClaraPDFPro
python -m pip install -r requirements.txt
python app.py
```

Or simply double-click `run.bat` (starts silently, without a console window).

## Quick Start

1. Pick a tool from the left sidebar.
2. Choose the source file — the output path is suggested automatically.
3. Adjust options (or keep the defaults).
4. Click the primary button and wait for the completion dialog.

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
    ├── main_window.py        # Main window and navigation
    ├── pages.py              # Tool pages
    ├── page_editor.py        # Thumbnail page manager dialog
    ├── pdf_engine.py         # Page ops, merge/split, images, encryption
    ├── pdf_editor_engine.py  # Long-lived document: render, form fields, save, undo
    ├── pdf_view.py           # Page painter with inline field editors
    ├── editor_window.py      # Editor main window (toolbar, thumbnails, status bar)
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

> v1.0.6 is archived at `ClaraPDFPro_Backups\1.0.6_新增PDF编辑器与表单填写`. The next backup will be created when v1.0.8 is prepared.

## Roadmap

- OCR for scanned documents — next
- Batch conversion queue

## Changelog

<a id="changelog"></a>

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

> **最新版本：v1.0.7** — 所见即所得文本编辑，以及高亮、下划线、便签三种批注。
> **[→ 一键直达版本号更迭记录](#changelog-zh)**

ClaraPDFPro 是一款完全本地运行的 Windows PDF 工具箱：支持 PDF 与 Word / Excel 双向转换、按 DPI 或目标体积压缩、可视化页面管理、PDF 转图片、图片转 PDF 以及密码加密。所有处理均在本机完成，文件不会上传。

## 功能

| 模块 | 能力 |
| --- | --- |
| **PDF 编辑** | 填写表单字段、勾选复选框/单选框、编辑下拉与列表框；**所见即所得文本编辑**——单击任意文字即可原位改写，保留位置、字号与颜色（中英文均支持）；**批注**——框选文字添加高亮、下划线，或放置便签；支持撤销/重做、原地增量保存与另存为；含缩略图、缩放与浏览/填表/编辑文字/批注四种模式 |
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

## 安装

```powershell
cd C:\Users\Administrator\Desktop\GIT\ClaraPDFPro
python -m pip install -r requirements.txt
python app.py
```

也可以直接双击 `run.bat` 启动（无控制台窗口，静默运行）。

## 快速上手

1. 在左侧选择工具。
2. 选择源文件——输出路径会自动生成。
3. 按需调整选项（或保持默认）。
4. 点击主按钮，等待完成提示。

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
    ├── main_window.py        # 主窗口与导航
    ├── pages.py              # 各工具页面
    ├── page_editor.py        # 缩略图页面管理器
    ├── pdf_engine.py         # 页面操作、合并拆分、图片、加密
    ├── pdf_editor_engine.py  # 长开文档：渲染、表单字段、保存、撤销
    ├── pdf_view.py           # 页面绘制与字段内联编辑器
    ├── editor_window.py      # 编辑器主窗口（工具栏、缩略图、状态栏）
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

> v1.0.6 已备份至 `ClaraPDFPro_Backups\1.0.6_新增PDF编辑器与表单填写`，准备 v1.0.8 时创建下一份备份。

## 后续计划

- 扫描件 OCR —— 下一版本
- 批量转换队列

## 版本号更迭记录

<a id="changelog-zh"></a>

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
