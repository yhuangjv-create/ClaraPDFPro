<a id="top"></a>

# ClaraPDFPro

![Version](https://img.shields.io/badge/version-1.0.0-2b579a)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**English** | [简体中文](#zh)

> **Latest release: v1.0.0** — Initial public release.
> **[→ Jump to Changelog](#changelog)**

ClaraPDFPro is a local, offline PDF toolkit for Windows. It converts PDF to and from Word / Excel, compresses PDFs to a chosen DPI or file size, organizes pages visually, exports pages as images, builds PDFs from images, and protects documents with passwords. Nothing is uploaded — every operation runs on your machine.

## Features

| Module | Capabilities |
| --- | --- |
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

Or simply double-click `run.bat`.

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

> The current release v1.0.0 is the first version, so no backup exists yet. The first backup will be created when v1.0.1 is prepared.

## Roadmap

- Direct PDF text editing and annotation (highlight, note, underline)
- Form filling
- OCR for scanned documents
- Batch conversion queue

## Changelog

<a id="changelog"></a>

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

> **最新版本：v1.0.0** — 首个正式版本。
> **[→ 一键直达版本号更迭记录](#changelog-zh)**

ClaraPDFPro 是一款完全本地运行的 Windows PDF 工具箱：支持 PDF 与 Word / Excel 双向转换、按 DPI 或目标体积压缩、可视化页面管理、PDF 转图片、图片转 PDF 以及密码加密。所有处理均在本机完成，文件不会上传。

## 功能

| 模块 | 能力 |
| --- | --- |
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

也可以直接双击 `run.bat` 启动。

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

> 当前 v1.0.0 为首个版本，暂无历史版本可备份。准备 v1.0.1 时将创建第一份备份。

## 后续计划

- PDF 文本直接编辑与批注（高亮、便签、下划线）
- 表单填写
- 扫描件 OCR
- 批量转换队列

## 版本号更迭记录

<a id="changelog-zh"></a>

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
