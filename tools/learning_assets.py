#!/usr/bin/env python3
"""每日源码 ZIP 与静态资源复制（WP-02）。

对应 docs/development/01_构建与内容契约.md §5：
- 以当日 ``code/`` 为根生成 ``public/downloads/day-NNN-source.zip``
- 默认排除冻结 outputs/、build/、缓存、二进制、对象文件、疑似密钥
- ``source_include`` 显式例外逐项加入运行必需的小型冻结输入
- 确定性构建：条目排序、固定时间戳（1980-01-01）、统一压缩级别、保留 POSIX 权限
- 构建后重开 ZIP 校验路径、CRC、权限与条目数
"""

from __future__ import annotations

import re
import stat
import zipfile
from pathlib import Path

from learning_metadata import JUNK_BASENAMES, LearningError

# ---------------------------------------------------------------------------
# 排除规则
# ---------------------------------------------------------------------------

#: 默认排除的目录名（相对 code/ 根，任意层级）
EXCLUDED_DIR_NAMES = frozenset(
    {"outputs", "build", "__pycache__", ".cache", ".git", ".idea", ".vscode", "node_modules", ".dSYM", ".pytest_cache"}
)

#: 默认排除的文件后缀（对象文件、库、缓存字节码等）
EXCLUDED_FILE_SUFFIXES = frozenset(
    {".o", ".a", ".so", ".dylib", ".dll", ".exe", ".pyc", ".pyo", ".class", ".swp", ".swo", ".tmp"}
)

#: 排除的文件名（编辑器临时文件、core dump、疑似密钥文件）
EXCLUDED_FILE_NAMES = frozenset({".env", "core", "core.dump", "thermals.db"}) | set(JUNK_BASENAMES)

#: 以这些前缀命名的 core dump
CORE_PREFIX = "core."

#: 可执行/目标文件魔数（ELF、Mach-O、FAT、ar 归档、PE）；shebang 脚本不算二进制
BINARY_MAGICS = (
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xcf\xfa\xed\xbf",
    b"\xca\xfe\xba\xbe",
    b"!<arch>\n",
    b"MZ",
)

#: 高置信度密钥模式（命中即拒绝打包；占位符不会匹配这些模式）
SECRET_PATTERNS = (
    (re.compile(rb"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"), "私钥文件头"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub Token"),
    (re.compile(rb"sk-[A-Za-z0-9_-]{20,}"), "OpenAI API Key"),
    (re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack Token"),
    (re.compile(rb"AIza[0-9A-Za-z_-]{30,}"), "Google API Key"),
)

#: 大小与条目上限（初版建议值，超过即失败并评审）
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_DAY_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ENTRY_COUNT = 2000

#: 固定 ZIP 时间戳（DOS 纪元起点）
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

COMPRESSION_LEVEL = 9


def _is_core_dump(name):
    return name.startswith(CORE_PREFIX) and name[len(CORE_PREFIX) :].isdigit()


def _looks_binary(path):
    """按魔数判断是否为可执行二进制/目标文件；shebang 脚本返回 False。"""
    try:
        with path.open("rb") as handle:
            head = handle.read(8)
    except OSError:
        return True
    if head.startswith(b"#!"):
        return False
    return any(head.startswith(magic) for magic in BINARY_MAGICS)


def _scan_secrets(rel, data):
    """返回 (是否可疑, 原因)；只报告高置信度模式。"""
    for pattern, label in SECRET_PATTERNS:
        match = pattern.search(data)
        if match:
            return True, f"{label}（片段 {match.start()} 字节处）"
    return False, None


def select_archive_files(day_dir, override=None):
    """选择某日可进入源码 ZIP 的文件，返回相对 code/ 的 POSIX 路径列表。

    - 无 code/ 目录或选择结果为空 → 返回 None（不生成空 ZIP）
    - ``source_include`` 显式列出的文件绕过默认排除（仍需通过安全与大小检查）
    - 任一文件命中疑似密钥、超限或路径不安全 → 抛出 LearningError
    """
    day_dir = Path(day_dir)
    code_dir = day_dir / "code"
    if not code_dir.is_dir():
        return None
    override = override or {}
    includes = set(override.get("source_include", []))

    selected = []
    total_bytes = 0
    for path in sorted(code_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(code_dir).as_posix()
        parts = Path(rel).parts
        if ".." in parts or rel.startswith("/"):
            raise LearningError("LEARNING_E201", f"源码路径不安全：{rel}", path=code_dir)
        explicitly_included = rel in includes
        if not explicitly_included:
            if any(part in EXCLUDED_DIR_NAMES for part in parts[:-1]):
                continue
            if parts[-1] in EXCLUDED_FILE_NAMES or _is_core_dump(parts[-1]):
                continue
            if path.suffix in EXCLUDED_FILE_SUFFIXES:
                continue
            if parts[-1].endswith("~"):
                continue
            if _looks_binary(path):
                continue
        else:
            includes.discard(rel)

        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise LearningError(
                "LEARNING_E202",
                f"文件超过单文件上限 {MAX_FILE_BYTES} 字节：{rel}（{len(data)} 字节）",
                path=code_dir,
                hint="评审该文件是否应进入源码包",
            )
        suspicious, reason = _scan_secrets(rel, data)
        if suspicious:
            raise LearningError(
                "LEARNING_E203",
                f"疑似密钥：{rel} — {reason}",
                path=code_dir,
                hint="移除密钥后重试；教学占位符请显式写成 YOUR_TOKEN_HERE",
            )
        total_bytes += len(data)
        if total_bytes > MAX_DAY_UNCOMPRESSED_BYTES:
            raise LearningError("LEARNING_E204", f"单日未压缩总量超过 {MAX_DAY_UNCOMPRESSED_BYTES} 字节", path=code_dir)
        selected.append((rel, path))

    if includes:
        raise LearningError(
            "LEARNING_E205",
            f"source_include 引用了不存在或不可用的文件：{sorted(includes)}",
            path=code_dir,
            hint="只允许 code/ 下真实存在的普通文件相对路径",
        )
    if len(selected) > MAX_ENTRY_COUNT:
        raise LearningError("LEARNING_E206", f"条目数超过 {MAX_ENTRY_COUNT}：{len(selected)}", path=code_dir)
    if not selected:
        return None
    return selected


def source_zip_name(day_id):
    return f"downloads/{day_id}-source.zip"


def expected_zip_names(selected):
    """由选择结果计算 ZIP 内的完整条目名集合（文件 + 显式目录项，排序）。"""
    dir_names = set()
    for rel, _ in selected:
        parts = Path(rel).parts[:-1]
        for i in range(1, len(parts) + 1):
            dir_names.add("/".join(parts[:i]) + "/")
    return sorted([rel for rel, _ in selected] + list(dir_names), key=lambda n: n.encode("utf-8"))


def build_day_zip(day_dir, output_dir, day_id, override=None, selected=None):
    """生成并校验某日源码 ZIP，返回 (zip 路径, 条目数)。

    ``selected`` 可传入 select_archive_files() 的缓存结果避免重复遍历。
    """
    if selected is None:
        selected = select_archive_files(day_dir, override)
    if not selected:
        raise LearningError("LEARNING_E207", f"{day_id} 没有可打包文件却被请求生成 ZIP")
    output_path = Path(output_dir) / source_zip_name(day_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 显式目录项：所有文件祖先目录的去重集合
    dir_names = set()
    for rel, _ in selected:
        parts = Path(rel).parts[:-1]
        for i in range(1, len(parts) + 1):
            dir_names.add("/".join(parts[:i]) + "/")

    entries = {}
    for rel, path in selected:
        mode = path.stat().st_mode
        perm = mode & 0o777
        # 至少保留所有者可执行位给脚本；统一补全常见读权限
        if perm & 0o111:
            perm |= 0o755
        else:
            perm = 0o644
        entries[rel] = (path, (stat.S_IFREG | perm) << 16)
    for dir_name in dir_names:
        entries[dir_name] = (None, (stat.S_IFDIR | 0o755) << 16)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESSION_LEVEL) as zf:
        for name in sorted(entries, key=lambda n: n.encode("utf-8")):
            source, external_attr = entries[name]
            info = zipfile.ZipInfo(filename=name, date_time=FIXED_TIMESTAMP)
            info.external_attr = external_attr
            info.compress_type = zipfile.ZIP_DEFLATED
            if source is None:
                zf.writestr(info, b"")
            else:
                zf.writestr(info, source.read_bytes())

    verify_day_zip(output_path, expected_zip_names(selected))
    return output_path, len(selected)


def verify_day_zip(zip_path, expected_names):
    """重开 ZIP 逐项校验：条目集合、CRC（testzip）、权限与目录项。"""
    with zipfile.ZipFile(zip_path) as zf:
        actual = zf.namelist()
        if sorted(actual) != sorted(expected_names):
            raise LearningError(
                "LEARNING_E208",
                f"ZIP 条目校验失败：期望 {len(expected_names)} 项，实际 {len(actual)} 项",
                path=zip_path,
            )
        bad = zf.testzip()
        if bad is not None:
            raise LearningError("LEARNING_E209", f"ZIP CRC 校验失败：{bad}", path=zip_path)
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.date_time != FIXED_TIMESTAMP:
                raise LearningError("LEARNING_E210", f"ZIP 时间戳未固定：{info.filename}", path=zip_path)
            perm = (info.external_attr >> 16) & 0o777
            if perm == 0:
                raise LearningError("LEARNING_E211", f"ZIP 权限丢失：{info.filename}", path=zip_path)
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise LearningError("LEARNING_E212", f"ZIP 内路径不安全：{name}", path=zip_path)


def copy_learning_assets(repo_root, output_dir):
    """复制学习模块静态资源（static/css、static/js）到产物目录。

    与现有 build.py 的复制逻辑保持一致：css → public/css，
    js/learning → public/js/learning，js 其他文件由主构建复制。
    """
    import shutil

    repo_root = Path(repo_root)
    output_dir = Path(output_dir)
    (output_dir / "css").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_root / "static" / "css" / "learning.css", output_dir / "css" / "learning.css")
    learning_js = output_dir / "js" / "learning"
    if learning_js.exists():
        shutil.rmtree(learning_js)
    shutil.copytree(repo_root / "static" / "js" / "learning", learning_js)
    return output_dir
