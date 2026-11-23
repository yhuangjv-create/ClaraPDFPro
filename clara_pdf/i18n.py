"""中英文界面文案。

所有界面文字集中在此字典中，键名被界面代码引用；
新增文字时只需在 STRINGS 中补一条 (中文, English) 元组。
"""

from __future__ import annotations

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

LANG_ZH = "zh"
LANG_EN = "en"

_qt_translator: QTranslator | None = None


def install_qt_translator(lang: str) -> None:
    """加载 Qt 标准控件（对话框按钮、右键菜单）的中文翻译。"""
    global _qt_translator
    app = QApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if lang != LANG_ZH:
        return
    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_zh_CN", path):
        app.installTranslator(translator)
        _qt_translator = translator


# key: (中文, English)
STRINGS: dict[str, tuple[str, str]] = {
    # ---------- 通用 ----------
    "app.name": ("ClaraPDFPro", "ClaraPDFPro"),
    "app.slogan": ("PDF 工具箱", "PDF Toolkit"),
    "common.ok": ("确定", "OK"),
    "common.cancel": ("取消", "Cancel"),
    "common.browse": ("浏览…", "Browse…"),
    "common.open_file": ("打开文件", "Open file"),
    "common.open_folder": ("打开文件夹", "Open folder"),
    "common.add": ("添加文件…", "Add files…"),
    "common.remove": ("移除", "Remove"),
    "common.clear": ("清空", "Clear"),
    "common.up": ("上移", "Move up"),
    "common.down": ("下移", "Move down"),
    "common.start": ("开始处理", "Start"),
    "common.working": ("正在处理，请稍候…", "Working…"),
    "common.ready": ("就绪", "Ready"),
    "common.done": ("处理完成", "Done"),
    "common.failed": ("处理失败", "Failed"),
    "common.error": ("错误", "Error"),
    "common.info": ("提示", "Info"),
    "common.input": ("源文件", "Source file"),
    "common.output": ("输出文件", "Output file"),
    "common.files": ("文件列表", "File list"),
    "common.optional": ("可选", "optional"),
    "common.close": ("关闭", "Close"),
    "common.reset": ("还原", "Reset"),
    "common.dpi": ("图片清晰度 (PPI)", "Image DPI"),
    "common.quality": ("图片质量", "Image quality"),
    "common.page_range": ("页码范围", "Page range"),
    "common.page_range_hint": ("留空表示全部，例：1-3,5,7-8", "Empty = all, e.g. 1-3,5,7-8"),
    "common.password": ("密码", "Password"),
    "common.owner_password": ("所有者密码", "Owner password"),
    "common.select_file": ("请先选择文件。", "Please select a file."),
    "common.no_files": ("请先添加文件。", "Please add files first."),
    "common.pages": ("页", "pages"),
    "common.unknown": ("未知", "unknown"),
    "common.version": ("版本", "Version"),
    "common.dark": ("深色", "Dark"),
    "common.light": ("浅色", "Light"),
    "common.lang": ("English", "中文"),

    # ---------- 导航 ----------
    "nav.convert": ("格式转换", "Convert"),
    "nav.compress": ("PDF 压缩", "Compress"),
    "nav.organize": ("页面管理", "Organize"),
    "nav.pdf2img": ("PDF 转图片", "PDF to Images"),
    "nav.img2pdf": ("图片转 PDF", "Images to PDF"),
    "nav.security": ("加密 / 解密", "Security"),
    "nav.editor": ("PDF 编辑", "Edit PDF"),
    "nav.about": ("关于", "About"),
    "nav.section_tools": ("工具", "TOOLS"),

    # ---------- 格式转换 ----------
    "convert.title": ("格式转换", "Format Conversion"),
    "convert.desc": (
        "PDF、Word、Excel 双向互转，保留文字与表格结构。",
        "Convert between PDF, Word and Excel while keeping text and tables.",
    ),
    "convert.direction": ("转换方向", "Direction"),
    "convert.mode.pdf2docx": ("PDF → Word", "PDF → Word"),
    "convert.mode.pdf2xlsx": ("PDF → Excel", "PDF → Excel"),
    "convert.mode.docx2pdf": ("Word → PDF", "Word → PDF"),
    "convert.mode.xlsx2pdf": ("Excel → PDF", "Excel → PDF"),
    "convert.hint.pdf2docx": (
        "提取文字与图片并按段落重建 Word；扫描件需先 OCR。",
        "Rebuilds a Word document from text and images; scans need OCR first.",
    ),
    "convert.hint.pdf2xlsx": (
        "识别 PDF 中的表格并写入 Excel，每个页面一个工作表。",
        "Detects tables in each PDF page and writes them to worksheets.",
    ),
    "convert.hint.office2pdf": (
        "调用本机 Microsoft Office 进行高保真转换。",
        "Uses local Microsoft Office for high-fidelity conversion.",
    ),
    "convert.start": ("开始转换", "Convert"),
    "convert.success": ("转换完成：{path}", "Converted: {path}"),
    "convert.need_office": (
        "未检测到可用的 Microsoft Word / Excel，Office 转 PDF 需要本机安装 Office。",
        "Microsoft Word / Excel was not found. Office-to-PDF requires local Office.",
    ),
    "convert.pdf_no_text": (
        "该 PDF 没有可提取的文字，可能是扫描件。",
        "No extractable text found; this PDF may be a scan.",
    ),

    # ---------- 压缩 ----------
    "compress.title": ("PDF 压缩", "PDF Compression"),
    "compress.desc": (
        "减小文件体积：可按 PPI 压缩图片，也可指定目标大小。",
        "Shrink PDFs by resampling images at a chosen DPI or hitting a target size.",
    ),
    "compress.mode": ("压缩方式", "Mode"),
    "compress.mode.ppi": ("按 PPI 压缩", "By image DPI"),
    "compress.mode.target": ("按目标体积", "To target size"),
    "compress.mode.raster": ("极限压缩（转图片）", "Maximum (rasterize)"),
    "compress.target_mb": ("目标体积 (MB)", "Target size (MB)"),
    "compress.start": ("开始压缩", "Compress"),
    "compress.hint.ppi": (
        "将高于设定 PPI 的图片重采样，适合扫描件与含大图的 PDF。",
        "Downsamples images above the chosen DPI; good for scans and photo-heavy PDFs.",
    ),
    "compress.hint.target": (
        "自动尝试多组参数，尽量接近目标体积。",
        "Tries multiple settings to approach the target size.",
    ),
    "compress.hint.raster": (
        "将每页渲染为图片重新封装，压缩率最高，但文字将不可选中。",
        "Rasterizes every page; smallest files but text is no longer selectable.",
    ),
    "compress.result": (
        "压缩完成：{before} → {after}（减少 {percent}%）",
        "Compressed: {before} → {after} ({percent}% smaller)",
    ),
    "compress.result_bigger": (
        "压缩完成：{before} → {after}（该文件已高度优化，体积未明显减小）",
        "Done: {before} → {after} (file was already well optimized)",
    ),
    "compress.progress": ("正在压缩第 {i}/{n} 轮…", "Compression pass {i}/{n}…"),

    # ---------- 页面管理 ----------
    "organize.title": ("页面管理", "Page Organizer"),
    "organize.desc": (
        "可视化重排页面：旋转、删除、调整顺序，并支持拆分、提取与合并。",
        "Reorder pages visually — rotate, delete, move — plus split, extract and merge.",
    ),
    "organize.open_manager": ("打开页面管理器…", "Open page manager…"),
    "organize.manager_hint": (
        "先选择 PDF，再打开页面管理器进行可视化编辑。",
        "Choose a PDF, then open the page manager to edit visually.",
    ),
    "organize.split_title": ("拆分 / 提取页面", "Split / Extract"),
    "organize.split_desc": (
        "提取指定页面另存为新 PDF，或按每 N 页拆分成多个文件。",
        "Save selected pages as a new PDF, or split every N pages.",
    ),
    "organize.extract": ("提取页面", "Extract pages"),
    "organize.split_every": ("每", "Every"),
    "organize.split_unit": ("页拆分为多个文件", "pages per file"),
    "organize.split_btn": ("开始拆分", "Split"),
    "organize.merge_title": ("合并 PDF", "Merge PDFs"),
    "organize.merge_desc": (
        "按列表顺序合并多个 PDF 文件。",
        "Merge multiple PDFs in the order listed.",
    ),
    "organize.merge_btn": ("合并为一个 PDF", "Merge into one PDF"),
    "organize.choose_dir": ("选择输出文件夹", "Choose output folder"),
    "organize.saved": ("已保存：{path}", "Saved: {path}"),
    "organize.split_done": ("已生成 {n} 个文件：{dir}", "Created {n} file(s) in {dir}"),
    "organize.range_invalid": ("页码范围无效：{err}", "Invalid page range: {err}"),

    # ---------- 页面管理器对话框 ----------
    "pm.title": ("页面管理器 — {name}", "Page Manager — {name}"),
    "pm.thumb_note": (
        "拖动或使用按钮调整页面；保存时按当前顺序输出。",
        "Drag or use the buttons to arrange pages; saving uses the current order.",
    ),
    "pm.page": ("第 {n} 页", "Page {n}"),
    "pm.rotate_left": ("左转 90°", "Rotate left"),
    "pm.rotate_right": ("右转 90°", "Rotate right"),
    "pm.delete": ("删除页面", "Delete page"),
    "pm.save": ("另存为…", "Save as…"),
    "pm.too_many": (
        "该 PDF 共 {n} 页，缩略图加载可能较慢，是否继续？",
        "This PDF has {n} pages; thumbnails may load slowly. Continue?",
    ),
    "pm.thumb_failed": ("缩略图生成失败，仍可进行页面操作。", "Thumbnail rendering failed; page operations still work."),

    # ---------- PDF 转图片 ----------
    "pdf2img.title": ("PDF 转图片", "PDF to Images"),
    "pdf2img.desc": (
        "把 PDF 每页导出为 PNG / JPEG 图片。",
        "Export each PDF page as a PNG / JPEG image.",
    ),
    "pdf2img.format": ("图片格式", "Image format"),
    "pdf2img.outdir": ("输出文件夹", "Output folder"),
    "pdf2img.start": ("开始导出", "Export"),
    "pdf2img.done": ("已导出 {n} 张图片到：{dir}", "Exported {n} image(s) to: {dir}"),

    # ---------- 图片转 PDF ----------
    "img2pdf.title": ("图片转 PDF", "Images to PDF"),
    "img2pdf.desc": (
        "把多张图片合并为一个 PDF，可统一为 A4 页面。",
        "Combine images into one PDF, optionally fitting each to A4.",
    ),
    "img2pdf.fit": ("页面设置", "Page layout"),
    "img2pdf.fit.a4": ("A4 居中适应", "Fit to A4"),
    "img2pdf.fit.original": ("保持原始尺寸", "Original size"),
    "img2pdf.start": ("生成 PDF", "Create PDF"),
    "img2pdf.done": ("已生成 PDF：{path}", "PDF created: {path}"),

    # ---------- 加密 / 解密 ----------
    "security.title": ("加密 / 解密", "Encrypt / Decrypt"),
    "security.desc": (
        "为 PDF 设置打开密码，或移除已有密码。",
        "Add an open password to a PDF, or remove an existing one.",
    ),
    "security.mode": ("操作", "Action"),
    "security.mode.encrypt": ("加密 PDF", "Encrypt"),
    "security.mode.decrypt": ("解密 PDF", "Decrypt"),
    "security.password_hint": ("设置打开文档所需的密码", "Password required to open the document"),
    "security.owner_hint": (
        "可选：权限密码，留空则与打开密码相同",
        "Optional: owner password, defaults to the open password",
    ),
    "security.need_password": ("请输入密码。", "Please enter a password."),
    "security.wrong_password": ("密码错误，无法解密。", "Wrong password; cannot decrypt."),
    "security.done": ("已完成：{path}", "Done: {path}"),

    # ---------- PDF 编辑器 ----------
    "editor.title": ("PDF 编辑器", "PDF Editor"),
    "editor.desc": (
        "直接编辑 PDF：填写表单、勾选复选框，支持撤销 / 重做与原地保存；还能对扫描件做 OCR，生成可复制检索的文字层。",
        "Edit PDFs directly: fill forms, toggle checkboxes, with undo / redo and in-place save; OCR scanned pages to add a searchable text layer.",
    ),
    "editor.open_btn": ("打开编辑器…", "Open editor…"),
    "editor.window_title": ("{name} — PDF 编辑器", "{name} — PDF Editor"),
    "editor.field_readonly": ("该字段为只读，无法编辑。", "This field is read-only."),
    "editor.save": ("保存", "Save"),
    "editor.save_as": ("另存为", "Save as"),
    "editor.undo": ("撤销", "Undo"),
    "editor.redo": ("重做", "Redo"),
    "editor.prev_page": ("上一页", "Previous"),
    "editor.next_page": ("下一页", "Next"),
    "editor.page_n": ("第 {n} / {total} 页", "Page {n} / {total}"),
    "editor.zoom_in": ("放大", "Zoom in"),
    "editor.zoom_out": ("缩小", "Zoom out"),
    "editor.fit_width": ("适合宽度", "Fit width"),
    "editor.fit_page": ("适合页面", "Fit page"),
    "editor.zoom_pct": ("{pct}%", "{pct}%"),
    "editor.mode_browse": ("浏览", "Browse"),
    "editor.mode_form": ("填表", "Fill form"),
    "editor.mode_text": ("编辑文字", "Edit text"),
    "editor.mode_annot": ("批注", "Annotate"),
    "editor.annot_highlight": ("高亮", "Highlight"),
    "editor.annot_underline": ("下划线", "Underline"),
    "editor.annot_note": ("便签", "Note"),
    "editor.note_prompt": ("便签内容：", "Note text:"),
    "editor.no_text": (
        "该页未检测到可编辑文字。",
        "No editable text found on this page.",
    ),
    "editor.toggle_annots": ("显示批注", "Show annotations"),
    "editor.toggle_fields": ("高亮字段", "Highlight fields"),
    "editor.no_form": (
        "该 PDF 未检测到可填写的表单字段，可切换到「浏览」模式查看。",
        "No fillable form fields detected. Switch to Browse mode to view.",
    ),
    "editor.unsaved_title": ("未保存的更改", "Unsaved changes"),
    "editor.unsaved": ("文档有未保存的更改，是否在关闭前保存？", "Save changes before closing?"),
    "editor.discard": ("不保存", "Don't save"),
    "editor.saved": ("已保存：{path}", "Saved: {path}"),
    "editor.save_failed": ("保存失败：{err}", "Save failed: {err}"),
    "editor.need_password": ("请输入文档密码", "Please enter the document password"),
    "editor.open_error": ("无法打开 PDF：{err}", "Cannot open PDF: {err}"),
    "editor.status_fields": ("{n} 个字段", "{n} fields"),
    "editor.thumb_title": ("页面", "Pages"),
    "editor.ocr": ("OCR 文字识别", "OCR"),
    "editor.ocr_page": ("识别当前页", "Recognize this page"),
    "editor.ocr_all": ("识别全部页面", "Recognize all pages"),
    "editor.ocr_running": ("正在识别文字…", "Recognizing text…"),
    "editor.ocr_progress": (
        "正在识别第 {n} / {total} 页…", "Recognizing page {n} / {total}…"),
    "editor.ocr_done": (
        "OCR 完成：{pages} 页，写入 {lines} 行文字。",
        "OCR finished: {pages} page(s), {lines} text line(s) added."),
    "editor.ocr_skip": (
        "这些页面已包含文字层，无需识别。",
        "These pages already contain text; nothing to recognize."),
    "editor.ocr_empty": ("未识别到文字。", "No text was recognized."),
    "editor.ocr_unavailable": (
        "未找到可用的 OCR 组件。请确认 Windows 已安装 OCR 语言包，"
        "或执行：pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
        "winrt-Windows.Storage.Streams winrt-Windows.Globalization",
        "No OCR engine is available. Make sure a Windows OCR language pack is installed, "
        "or run: pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
        "winrt-Windows.Storage.Streams winrt-Windows.Globalization"),

    # ---------- 关于 ----------
    "about.title": ("关于 ClaraPDFPro", "About ClaraPDFPro"),
    "about.desc": (
        "一款轻量的本地 PDF 工具箱，所有处理均在本机完成，文件不会上传。",
        "A lightweight local PDF toolkit. Everything runs on your machine — nothing is uploaded.",
    ),
    "about.features": ("功能", "Features"),
    "about.tech": ("技术栈", "Built with"),
    "about.feature_list": (
        "PDF ↔ Word / Excel 互转 · PDF 压缩 · 页面重排 / 拆分 / 合并 · PDF 转图片 · 图片转 PDF · 加密解密 · 表单填写与批注 · OCR 文字识别",
        "PDF ↔ Word / Excel · Compression · Page organize / split / merge · PDF to images · Images to PDF · Encryption · Form filling & annotations · OCR",
    ),

    # ---------- 状态栏 ----------
    "status.file_info": ("{name} · {pages} 页 · {size}", "{name} · {pages} pages · {size}"),
    "status.task_done": ("完成", "Done"),

    # ---------- 文件过滤器 ----------
    "filter.pdf": ("PDF 文件 (*.pdf)", "PDF files (*.pdf)"),
    "filter.docx": ("Word 文档 (*.docx)", "Word documents (*.docx)"),
    "filter.xlsx": ("Excel 工作簿 (*.xlsx)", "Excel workbooks (*.xlsx)"),
    "filter.images": (
        "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)",
        "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)",
    ),
    "filter.all": ("所有文件 (*.*)", "All files (*.*)"),
}


class I18n:
    """极简界面翻译器。"""

    def __init__(self, lang: str = LANG_ZH) -> None:
        self.lang = lang if lang in (LANG_ZH, LANG_EN) else LANG_ZH

    def set_lang(self, lang: str) -> None:
        self.lang = LANG_ZH if lang == LANG_ZH else LANG_EN

    def toggle(self) -> str:
        self.lang = LANG_EN if self.lang == LANG_ZH else LANG_ZH
        return self.lang

    def t(self, key: str, **fmt) -> str:
        pair = STRINGS.get(key)
        if pair is None:
            return key
        text = pair[0] if self.lang == LANG_ZH else pair[1]
        return text.format(**fmt) if fmt else text
