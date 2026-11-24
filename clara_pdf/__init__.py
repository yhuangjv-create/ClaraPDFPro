"""ClaraPDFPro 应用包。

PDF 编辑、格式互转、压缩、页面管理工具。
"""

import logging
import os

# 关闭 PyMuPDF 的 pymupdf_layout 推荐提示，避免污染控制台
os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")
# fontTools 编译字体表时的时间戳告警与本应用无关
logging.getLogger("fontTools").setLevel(logging.ERROR)

APP_NAME = "ClaraPDFPro"
ORG_NAME = "Clara"
__version__ = "1.2.4"
