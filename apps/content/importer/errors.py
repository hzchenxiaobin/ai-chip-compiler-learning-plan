"""导入器统一错误（设计文档 §7.1：失败版本只保留诊断）。"""


class ImporterError(Exception):
    """code + 定位信息 + 修复建议；出现即终止导入并标记 release=failed。"""

    def __init__(self, code, message, source=None, line=None):
        self.code = code
        self.message = message
        self.source = source
        self.line = line
        super().__init__(self.format())

    def format(self):
        location = ""
        if self.source:
            location = str(self.source)
            if self.line:
                location += f":{self.line}"
            location += " — "
        return f"[{self.code}] {location}{self.message}"

    def as_report(self):
        return {
            "code": self.code,
            "message": self.message,
            "source": str(self.source) if self.source else None,
            "line": self.line,
        }
