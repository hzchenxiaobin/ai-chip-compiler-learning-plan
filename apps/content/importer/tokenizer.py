"""共享分词器（设计文档 §7.5）。

构建期与查询期使用同一套规则：
- CJK 连续片段生成二元词（bigram）；单字片段保留单字；
- 英文/数字/下划线/点/斜杠/加号/连字符组成的命令、路径、IR token 保留完整形式，
  建立小写匹配形式（mlir-opt、run_all.sh、C++ 中的 cpp 部分等）。
"""
import re

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+\\-]+")


def tokenize(text: str) -> list[str]:
    """返回小写化 token 列表（含重复，供位置统计）。

    含 / 的路径 token 同时发出 basename 段（如 code/run_all.sh → run_all.sh），
    保证按文件名检索可命中完整路径。
    """
    tokens: list[str] = []
    for match in _ASCII_TOKEN_RE.finditer(text):
        token = match.group(0).lower()
        tokens.append(token)
        if "/" in token:
            base = token.rsplit("/", 1)[-1]
            if base and base != token:
                tokens.append(base)
    for match in _CJK_RUN_RE.finditer(text):
        run = match.group(0)
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def tokenize_unique(text: str) -> list[str]:
    """去重且保持出现顺序的 token 列表。"""
    seen = set()
    result = []
    for token in tokenize(text):
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


def is_technical_token(token: str) -> bool:
    """含 - _ . / + 的 ASCII token（命令、路径、错误码样例）——精确匹配加分。"""
    return bool(token) and any(ch in token for ch in "-_./+") and not _CJK_RE.search(token)
