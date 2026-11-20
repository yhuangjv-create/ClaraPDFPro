"""各工具页面的界面实现。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from . import compressor, converter, pdf_engine
from .fileutils import default_output, human_size
from .page_editor import PageManagerDialog
from .settings import Settings
from .tool_widgets import FileRow, MultiFileRow, ToolPage, error_box, result_box


def _field(label: str, widget: QWidget, align_top: bool = False) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    tag = QLabel(label)
    tag.setObjectName("FieldLabel")
    tag.setFixedWidth(96)
    tag.setAlignment(Qt.AlignLeft | (Qt.AlignTop if align_top else Qt.AlignVCenter))
    layout.addWidget(tag)
    layout.addWidget(widget, 1)
    return row


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def _button_row(*buttons: QWidget, stretch: bool = True) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for btn in buttons:
        layout.addWidget(btn)
    if stretch:
        layout.addStretch(1)
    return row


class ConvertPage(ToolPage):
    _MODES = ("pdf2docx", "pdf2xlsx", "docx2pdf", "xlsx2pdf")
    _INPUT_FILTER = {
        "pdf2docx": "filter.pdf",
        "pdf2xlsx": "filter.pdf",
        "docx2pdf": "filter.docx",
        "xlsx2pdf": "filter.xlsx",
    }
    _INPUT_EXT = {
        "pdf2docx": ".pdf",
        "pdf2xlsx": ".pdf",
        "docx2pdf": ".docx",
        "xlsx2pdf": ".xlsx",
    }
    _OUTPUT_EXT = {
        "pdf2docx": ".docx",
        "pdf2xlsx": ".xlsx",
        "docx2pdf": ".pdf",
        "xlsx2pdf": ".pdf",
    }

    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "convert.title", "convert.desc", parent)

        card = self.add_card()
        self.mode_combo = QComboBox()
        for mode in self._MODES:
            self.mode_combo.addItem(i18n.t(f"convert.mode.{mode}"), mode)

        self.input = FileRow(i18n, "filter.pdf")
        self.output = FileRow(i18n, "filter.docx", save_mode=True)

        card.add(_field(i18n.t("convert.direction"), self.mode_combo))
        card.add(_field(i18n.t("common.input"), self.input))
        card.add(_field(i18n.t("common.output"), self.output))
        self.hint = _hint("")
        card.add(self.hint)

        self.start_btn = QPushButton(i18n.t("convert.start"))
        self.start_btn.setObjectName("PrimaryButton")
        self.clear_btn = QPushButton(i18n.t("common.clear"))
        card.add(_button_row(self.start_btn, self.clear_btn))

        self.mode_combo.currentIndexChanged.connect(self._apply_mode)
        self.input.changed.connect(self._on_input)
        self.start_btn.clicked.connect(self._start)
        self.clear_btn.clicked.connect(self._clear)
        self._apply_mode()

    # ---------------- 交互 ----------------
    def _mode(self) -> str:
        return self.mode_combo.currentData()

    def _apply_mode(self) -> None:
        mode = self._mode()
        self.input.set_filter(self._INPUT_FILTER[mode])
        self.output.set_filter(
            {"pdf2docx": "filter.docx", "pdf2xlsx": "filter.xlsx"}.get(mode, "filter.pdf")
        )
        self.hint.setText(self.i18n.t(
            "convert.hint.pdf2docx" if mode == "pdf2docx"
            else "convert.hint.pdf2xlsx" if mode == "pdf2xlsx"
            else "convert.hint.office2pdf"
        ))
        src = self.input.path()
        if src and Path(src).suffix.lower() != self._INPUT_EXT[mode]:
            self.input.set_path("")
            self.output.set_path("")
        self._on_input()

    def _on_input(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            return
        mode = self._mode()
        tag = "converted" if mode in ("pdf2docx", "pdf2xlsx") else ""
        self.output.set_path(default_output(src, self._OUTPUT_EXT[mode], tag))

    def _clear(self) -> None:
        if self.is_busy():
            return
        self.input.set_path("")
        self.output.set_path("")

    def _start(self) -> None:
        mode = self._mode()
        src = self.input.path()
        out = self.output.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        if not out:
            out = str(default_output(src, self._OUTPUT_EXT[mode]))
            self.output.set_path(out)
        out = str(Path(out))

        def task(log, progress):
            if mode == "pdf2docx":
                return converter.pdf_to_docx(src, out, progress, log)
            if mode == "pdf2xlsx":
                return converter.pdf_to_xlsx(src, out, progress, log)
            kind = "word" if mode == "docx2pdf" else "excel"
            if not converter.office_available(kind):
                raise RuntimeError(self.i18n.t("convert.need_office"))
            return converter.office_to_pdf(src, out, kind, progress, log)

        def done(result) -> None:
            Settings().last_dir = str(Path(result).parent)
            result_box(self, self.i18n,
                       self.i18n.t("convert.success", path=Path(result).name), result)

        self.run_task(task, done, self.start_btn)


class CompressPage(ToolPage):
    _MODES = ("ppi", "target", "raster")

    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "compress.title", "compress.desc", parent)

        card = self.add_card()
        self.input = FileRow(i18n, "filter.pdf")
        self.info = _hint("—")
        self.output = FileRow(i18n, "filter.pdf", save_mode=True)
        self.mode_combo = QComboBox()
        for mode in self._MODES:
            self.mode_combo.addItem(i18n.t(f"compress.mode.{mode}"), mode)

        card.add(_field(i18n.t("common.input"), self.input))
        card.add(_field("", self.info))
        card.add(_field(i18n.t("compress.mode"), self.mode_combo))

        self.options = QStackedWidget()

        ppi_page = QWidget()
        ppi_layout = QVBoxLayout(ppi_page)
        ppi_layout.setContentsMargins(0, 0, 0, 0)
        ppi_layout.setSpacing(8)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 300)
        self.dpi_spin.setSingleStep(10)
        self.dpi_spin.setValue(150)
        self.dpi_spin.setSuffix(" PPI")
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(30, 95)
        self.quality_spin.setValue(70)
        self.quality_spin.setSuffix(" %")
        ppi_layout.addWidget(_field(i18n.t("common.dpi"), self.dpi_spin))
        ppi_layout.addWidget(_field(i18n.t("common.quality"), self.quality_spin))
        ppi_layout.addWidget(_hint(i18n.t("compress.hint.ppi")))

        target_page = QWidget()
        target_layout = QVBoxLayout(target_page)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(8)
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.1, 500.0)
        self.target_spin.setSingleStep(0.5)
        self.target_spin.setDecimals(1)
        self.target_spin.setValue(2.0)
        self.target_spin.setSuffix(" MB")
        target_layout.addWidget(_field(i18n.t("compress.target_mb"), self.target_spin))
        target_layout.addWidget(_hint(i18n.t("compress.hint.target")))

        raster_page = QWidget()
        raster_layout = QVBoxLayout(raster_page)
        raster_layout.setContentsMargins(0, 0, 0, 0)
        raster_layout.setSpacing(8)
        self.raster_dpi = QSpinBox()
        self.raster_dpi.setRange(50, 200)
        self.raster_dpi.setSingleStep(10)
        self.raster_dpi.setValue(110)
        self.raster_dpi.setSuffix(" PPI")
        self.raster_quality = QSpinBox()
        self.raster_quality.setRange(20, 90)
        self.raster_quality.setValue(55)
        self.raster_quality.setSuffix(" %")
        raster_layout.addWidget(_field(i18n.t("common.dpi"), self.raster_dpi))
        raster_layout.addWidget(_field(i18n.t("common.quality"), self.raster_quality))
        raster_layout.addWidget(_hint(i18n.t("compress.hint.raster")))

        for page in (ppi_page, target_page, raster_page):
            self.options.addWidget(page)
        card.add(self.options)
        card.add(_field(i18n.t("common.output"), self.output))

        self.result = _hint("")
        card.add(self.result)

        self.start_btn = QPushButton(i18n.t("compress.start"))
        self.start_btn.setObjectName("PrimaryButton")
        self.clear_btn = QPushButton(i18n.t("common.clear"))
        card.add(_button_row(self.start_btn, self.clear_btn))

        self.input.changed.connect(self._on_input)
        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        self.start_btn.clicked.connect(self._start)
        self.clear_btn.clicked.connect(self._clear)
        self._on_mode()

    def _on_mode(self) -> None:
        self.options.setCurrentIndex(self.mode_combo.currentIndex())
        src = self.input.path()
        if src and Path(src).exists():
            self.output.set_path(default_output(src, ".pdf", "compressed"))

    def _on_input(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            self.info.setText("—")
            return
        info = pdf_engine.pdf_info(src)
        if info["error"]:
            self.info.setText(info["error"])
        else:
            self.info.setText(self.i18n.t(
                "status.file_info",
                name=Path(src).name,
                pages=info["pages"],
                size=human_size(info["size"]),
            ))
        self.output.set_path(default_output(src, ".pdf", "compressed"))

    def _clear(self) -> None:
        if self.is_busy():
            return
        self.input.set_path("")
        self.output.set_path("")
        self.info.setText("—")
        self.result.setText("")

    def _start(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        out = self.output.path() or str(default_output(src, ".pdf", "compressed"))
        mode = self.mode_combo.currentData()

        if mode == "ppi":
            fn = lambda log, p: compressor.compress_pdf(  # noqa: E731
                src, out, "ppi", self.dpi_spin.value(), self.quality_spin.value(),
                progress=p, log=log)
        elif mode == "target":
            fn = lambda log, p: compressor.compress_pdf(  # noqa: E731
                src, out, "target", target_mb=self.target_spin.value(),
                progress=p, log=log)
        else:
            fn = lambda log, p: compressor.compress_pdf(  # noqa: E731
                src, out, "raster", self.raster_dpi.value(), self.raster_quality.value(),
                progress=p, log=log)

        def done(result: dict) -> None:
            before = human_size(result["before"])
            after = human_size(result["after"])
            percent = result["percent"]
            if percent < 1:
                text = self.i18n.t("compress.result_bigger", before=before, after=after)
            else:
                text = self.i18n.t("compress.result", before=before, after=after, percent=percent)
            self.result.setText(text)
            Settings().last_dir = str(Path(result["output"]).parent)
            result_box(self, self.i18n, text, result["output"])

        self.run_task(fn, done, self.start_btn)


class OrganizePage(ToolPage):
    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "organize.title", "organize.desc", parent)

        # ---- 页面编辑 ----
        card = self.add_card()
        self.input = FileRow(i18n, "filter.pdf")
        self.info = _hint(i18n.t("organize.manager_hint"))
        self.manager_btn = QPushButton(i18n.t("organize.open_manager"))
        self.clear_input_btn = QPushButton(i18n.t("common.clear"))
        card.add(_field(i18n.t("common.input"), self.input))
        card.add(_field("", self.info))
        card.add(_button_row(self.manager_btn, self.clear_input_btn))

        # ---- 拆分 / 提取 ----
        split_card = self.add_card(i18n.t("organize.split_title"), i18n.t("organize.split_desc"))
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText(i18n.t("common.page_range_hint"))
        self.per_spin = QSpinBox()
        self.per_spin.setRange(1, 999)
        self.per_spin.setValue(1)
        split_card.add(_field(i18n.t("common.page_range"), self.range_edit))
        split_row = QWidget()
        split_layout = QHBoxLayout(split_row)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(8)
        tag = QLabel(i18n.t("organize.split_every"))
        tag.setObjectName("FieldLabel")
        split_layout.addWidget(tag)
        split_layout.addWidget(self.per_spin)
        split_layout.addWidget(QLabel(i18n.t("organize.split_unit")))
        split_layout.addStretch(1)
        split_card.add(_field("", split_row))
        self.extract_btn = QPushButton(i18n.t("organize.extract"))
        self.split_btn = QPushButton(i18n.t("organize.split_btn"))
        self.clear_split_btn = QPushButton(i18n.t("common.clear"))
        split_card.add(_button_row(self.extract_btn, self.split_btn, self.clear_split_btn))

        # ---- 合并 ----
        merge_card = self.add_card(i18n.t("organize.merge_title"), i18n.t("organize.merge_desc"))
        self.merge_files = MultiFileRow(i18n, "filter.pdf")
        self.merge_out = FileRow(i18n, "filter.pdf", save_mode=True)
        self.merge_btn = QPushButton(i18n.t("organize.merge_btn"))
        merge_card.add(_field(i18n.t("common.files"), self.merge_files, align_top=True))
        merge_card.add(_field(i18n.t("common.output"), self.merge_out))
        merge_card.add(_button_row(self.merge_btn))

        self.input.changed.connect(self._on_input)
        self.manager_btn.clicked.connect(self._open_manager)
        self.clear_input_btn.clicked.connect(self._clear_input)
        self.extract_btn.clicked.connect(self._extract)
        self.split_btn.clicked.connect(self._split)
        self.clear_split_btn.clicked.connect(self._clear_split)
        self.merge_files.changed.connect(self._on_merge_files)
        self.merge_btn.clicked.connect(self._merge)

    # ---------------- 页面管理 ----------------
    def _on_input(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            self.info.setText(self.i18n.t("organize.manager_hint"))
            return
        info = pdf_engine.pdf_info(src)
        self.info.setText(self.i18n.t(
            "status.file_info",
            name=Path(src).name,
            pages=info["pages"],
            size=human_size(info["size"]),
        ))

    def _clear_input(self) -> None:
        if self.is_busy():
            return
        self.input.set_path("")
        self.info.setText(self.i18n.t("organize.manager_hint"))

    def _clear_split(self) -> None:
        if self.is_busy():
            return
        self.range_edit.clear()
        self.per_spin.setValue(1)

    def _open_manager(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        dialog = PageManagerDialog(self.i18n, src, self)
        if dialog.exec() and dialog.saved_path:
            Settings().last_dir = str(Path(dialog.saved_path).parent)
            result_box(self, self.i18n,
                       self.i18n.t("organize.saved", path=Path(dialog.saved_path).name),
                       dialog.saved_path)

    # ---------------- 拆分 / 提取 ----------------
    def _extract(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        start = default_output(src, ".pdf", "pages")
        chosen, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("organize.extract"), str(start), self.i18n.t("filter.pdf"))
        if not chosen:
            return
        if not chosen.lower().endswith(".pdf"):
            chosen += ".pdf"
        pages_text = self.range_edit.text()
        self.run_task(
            lambda log, p: pdf_engine.extract_pages(src, chosen, pages_text, p),
            lambda result: result_box(self, self.i18n,
                                      self.i18n.t("organize.saved", path=Path(result).name),
                                      result),
            self.extract_btn,
        )

    def _split(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        directory = QFileDialog.getExistingDirectory(
            self, self.i18n.t("organize.choose_dir"), Settings().last_dir)
        if not directory:
            return
        per_file = self.per_spin.value()
        self.run_task(
            lambda log, p: pdf_engine.split_by_count(src, directory, per_file, p, log),
            lambda result: result_box(
                self, self.i18n,
                self.i18n.t("organize.split_done", n=len(result), dir=directory), directory),
            self.split_btn,
        )

    # ---------------- 合并 ----------------
    def _on_merge_files(self) -> None:
        paths = self.merge_files.paths()
        if paths:
            self.merge_out.set_path(default_output(paths[0], ".pdf", "merged"))

    def _merge(self) -> None:
        paths = self.merge_files.paths()
        if len(paths) < 2:
            error_box(self, self.i18n, self.i18n.t("common.no_files"))
            return
        out = self.merge_out.path() or str(default_output(paths[0], ".pdf", "merged"))
        self.run_task(
            lambda log, p: pdf_engine.merge_pdfs(paths, out, p, log),
            lambda result: result_box(self, self.i18n,
                                      self.i18n.t("organize.saved", path=Path(result).name),
                                      result),
            self.merge_btn,
        )


class PdfToImagesPage(ToolPage):
    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "pdf2img.title", "pdf2img.desc", parent)

        card = self.add_card()
        self.input = FileRow(i18n, "filter.pdf")
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 400)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setValue(150)
        self.dpi_spin.setSuffix(" PPI")
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG", "png")
        self.format_combo.addItem("JPEG", "jpeg")
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText(i18n.t("common.page_range_hint"))
        self.outdir = QLineEdit()
        self.outdir.setReadOnly(True)
        self.outdir_btn = QPushButton(i18n.t("common.browse"))
        outdir_row = QWidget()
        outdir_layout = QHBoxLayout(outdir_row)
        outdir_layout.setContentsMargins(0, 0, 0, 0)
        outdir_layout.setSpacing(8)
        outdir_layout.addWidget(self.outdir, 1)
        outdir_layout.addWidget(self.outdir_btn)

        card.add(_field(i18n.t("common.input"), self.input))
        card.add(_field(i18n.t("common.dpi"), self.dpi_spin))
        card.add(_field(i18n.t("pdf2img.format"), self.format_combo))
        card.add(_field(i18n.t("common.page_range"), self.range_edit))
        card.add(_field(i18n.t("pdf2img.outdir"), outdir_row))

        self.start_btn = QPushButton(i18n.t("pdf2img.start"))
        self.start_btn.setObjectName("PrimaryButton")
        self.clear_btn = QPushButton(i18n.t("common.clear"))
        card.add(_button_row(self.start_btn, self.clear_btn))

        self.input.changed.connect(self._on_input)
        self.outdir_btn.clicked.connect(self._browse_dir)
        self.start_btn.clicked.connect(self._start)
        self.clear_btn.clicked.connect(self._clear)

    def _on_input(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            return
        self.outdir.setText(str(Path(src).parent / f"{Path(src).stem}_images"))

    def _clear(self) -> None:
        if self.is_busy():
            return
        self.input.set_path("")
        self.outdir.clear()
        self.range_edit.clear()

    def _browse_dir(self) -> None:
        start = self.outdir.text() or Settings().last_dir
        directory = QFileDialog.getExistingDirectory(
            self, self.i18n.t("pdf2img.outdir"), start)
        if directory:
            self.outdir.setText(directory)

    def _start(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        out_dir = self.outdir.text() or str(Path(src).parent / f"{Path(src).stem}_images")
        dpi = self.dpi_spin.value()
        fmt = self.format_combo.currentData()
        pages_text = self.range_edit.text()

        def done(result) -> None:
            directory = out_dir if Path(out_dir).is_dir() else str(Path(result[0]).parent)
            Settings().last_dir = directory
            result_box(self, self.i18n,
                       self.i18n.t("pdf2img.done", n=len(result), dir=directory), directory)

        self.run_task(
            lambda log, p: pdf_engine.pdf_to_images(src, out_dir, dpi, fmt, pages_text, p, log),
            done, self.start_btn)


class ImagesToPdfPage(ToolPage):
    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "img2pdf.title", "img2pdf.desc", parent)

        card = self.add_card()
        self.files = MultiFileRow(i18n, "filter.images")
        self.fit_combo = QComboBox()
        self.fit_combo.addItem(i18n.t("img2pdf.fit.a4"), "a4")
        self.fit_combo.addItem(i18n.t("img2pdf.fit.original"), "original")
        self.output = FileRow(i18n, "filter.pdf", save_mode=True)

        card.add(_field(i18n.t("common.files"), self.files, align_top=True))
        card.add(_field(i18n.t("img2pdf.fit"), self.fit_combo))
        card.add(_field(i18n.t("common.output"), self.output))

        self.start_btn = QPushButton(i18n.t("img2pdf.start"))
        self.start_btn.setObjectName("PrimaryButton")
        card.add(_button_row(self.start_btn))

        self.files.changed.connect(self._on_files)
        self.start_btn.clicked.connect(self._start)

    def _on_files(self) -> None:
        paths = self.files.paths()
        if paths:
            self.output.set_path(default_output(paths[0], ".pdf", "images"))

    def _start(self) -> None:
        paths = self.files.paths()
        if not paths:
            error_box(self, self.i18n, self.i18n.t("common.no_files"))
            return
        out = self.output.path() or str(default_output(paths[0], ".pdf", "images"))
        fit = self.fit_combo.currentData()
        self.run_task(
            lambda log, p: pdf_engine.images_to_pdf(paths, out, fit, p, log),
            lambda result: result_box(
                self, self.i18n, self.i18n.t("img2pdf.done", path=Path(result).name), result),
            self.start_btn,
        )


class SecurityPage(ToolPage):
    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "security.title", "security.desc", parent)

        card = self.add_card()
        self.input = FileRow(i18n, "filter.pdf")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(i18n.t("security.mode.encrypt"), "encrypt")
        self.mode_combo.addItem(i18n.t("security.mode.decrypt"), "decrypt")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.owner = QLineEdit()
        self.owner.setEchoMode(QLineEdit.Password)
        self.owner_row = _field(i18n.t("common.owner_password"), self.owner)
        self.output = FileRow(i18n, "filter.pdf", save_mode=True)

        card.add(_field(i18n.t("common.input"), self.input))
        card.add(_field(i18n.t("security.mode"), self.mode_combo))
        card.add(_field(i18n.t("common.password"), self.password))
        card.add(self.owner_row)
        card.add(_field(i18n.t("common.output"), self.output))
        self.hint = _hint(i18n.t("security.password_hint"))
        card.add(self.hint)

        self.start_btn = QPushButton(i18n.t("common.start"))
        self.start_btn.setObjectName("PrimaryButton")
        self.clear_btn = QPushButton(i18n.t("common.clear"))
        card.add(_button_row(self.start_btn, self.clear_btn))

        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        self.input.changed.connect(self._on_input)
        self.start_btn.clicked.connect(self._start)
        self.clear_btn.clicked.connect(self._clear)
        self._on_mode()

    def _on_mode(self) -> None:
        encrypt = self.mode_combo.currentData() == "encrypt"
        self.owner_row.setVisible(encrypt)
        self.hint.setText(self.i18n.t(
            "security.password_hint" if encrypt else "security.need_password"))
        src = self.input.path()
        if src and Path(src).exists():
            self.output.set_path(default_output(
                src, ".pdf", "encrypted" if encrypt else "decrypted"))

    def _on_input(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            return
        encrypt = self.mode_combo.currentData() == "encrypt"
        self.output.set_path(default_output(src, ".pdf", "encrypted" if encrypt else "decrypted"))

    def _clear(self) -> None:
        if self.is_busy():
            return
        self.input.set_path("")
        self.output.set_path("")
        self.password.clear()
        self.owner.clear()

    def _start(self) -> None:
        src = self.input.path()
        if not src or not Path(src).exists():
            error_box(self, self.i18n, self.i18n.t("common.select_file"))
            return
        password = self.password.text()
        if not password:
            error_box(self, self.i18n, self.i18n.t("security.need_password"))
            return
        mode = self.mode_combo.currentData()
        out = self.output.path() or str(default_output(src, ".pdf", mode))
        owner = self.owner.text()

        if mode == "encrypt":
            fn = lambda log, p: pdf_engine.encrypt_pdf(src, out, password, owner)  # noqa: E731
        else:
            fn = lambda log, p: pdf_engine.decrypt_pdf(src, out, password)  # noqa: E731

        self.run_task(
            fn,
            lambda result: result_box(self, self.i18n,
                                      self.i18n.t("security.done", path=Path(result).name),
                                      result),
            self.start_btn,
        )


class AboutPage(ToolPage):
    def __init__(self, i18n, parent=None) -> None:
        super().__init__(i18n, "about.title", "about.desc", parent)

        card = self.add_card()
        card.add(_hint(f"{i18n.t('common.version')} {__version__}"))
        card.add(_hint(i18n.t("about.feature_list")))

        tech = self.add_card(i18n.t("about.tech"))
        tech.add(_hint("Python · PySide6 · PyMuPDF · pypdf · python-docx · openpyxl · Microsoft Office"))
        body = QLabel(
            "PDF 渲染与压缩：PyMuPDF\n"
            "PDF 读写与加密：pypdf\n"
            "Word 生成：python-docx\n"
            "Excel 生成：openpyxl\n"
            "Office 转 PDF：Microsoft Office (COM)"
        )
        body.setObjectName("Hint")
        tech.add(body)
        tech.add(_hint(i18n.t("about.desc")))
