"""确定性源码 ZIP（设计文档 §7.4）。

- 以当日 code/（或 examples/）为根；默认排除 outputs、build、缓存、VCS、
  临时文件、二进制、对象文件和疑似密钥；`source_include` 逐项声明运行必需的
  小型冻结输入；
- 条目按路径排序、固定时间戳 1980-01-01、统一压缩级别、保留 POSIX 权限
  （至少保留所有者可执行位）、显式目录项；
- 单文件 20 MiB、单日未压缩 100 MiB、2,000 条目上限；
- 构建后重读校验 CRC 与条目。
"""
import hashlib
import re
import zipfile
from pathlib import Path

from .errors import ImporterError

EXCLUDED_DIR_NAMES = {
    "outputs", "build", ".cache", ".git", "__pycache__", "node_modules",
    ".venv", "dist", ".idea", ".vscode",
}

_EXCLUDED_BASENAME_RE = [
    re.compile(p)
    for p in (
        r"^core(\.\d+)?$",
        r"\.(o|obj|a|so|dylib|dll|exe|pyc|pyo|class|dSYM|tmp|swp)$",
        r"^\.DS_Store$",
        r".*~$",
        r"^#.*#$",
        r"^\.#.*$",
    )
]

_SECRET_FILENAME_RE = re.compile(
    r"(^\.env$|\.env$|\.pem$|\.key$|^id_rsa|^id_ed25519|\.p12$|\.pfx$"
    r"|^credentials|\.token$|^service-account.*\.json$)",
    re.IGNORECASE,
)

_SECRET_CONTENT_PATTERNS = [
    (re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "私钥块"),
    (re.compile(rb"\bghp_[A-Za-z0-9]{36}\b"), "GitHub token"),
    (re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub PAT"),
    (re.compile(rb"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key"),
    (re.compile(rb"\bsk-[A-Za-z0-9]{20,}\b"), "API secret"),
    (
        re.compile(rb"(?im)^[\s]*(export\s+)?[A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*[\"'][A-Za-z0-9+/=_-]{20,}[\"']"),
        "敏感赋值",
    ),
]

ALLOWED_PLACEHOLDER = b"YOUR_TOKEN_HERE"

# 限额（设计文档 §7.4 与开发文档 01 §5.2）。
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 2000

_SNIFF_SIZE = 8192


def _is_excluded_dir(rel_parts):
    return any(part in EXCLUDED_DIR_NAMES for part in rel_parts[:-1])


def _is_excluded_basename(name):
    return any(regex.match(name) for regex in _EXCLUDED_BASENAME_RE)


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_SIZE)
    except OSError:
        return True
    return b"\x00" in head


def _secret_findings(rel: str, data: bytes):
    findings = []
    if _SECRET_FILENAME_RE.search(Path(rel).name):
        findings.append(f"文件名疑似密钥：{Path(rel).name}")
    if ALLOWED_PLACEHOLDER in data:
        return findings  # 教学占位符按设计允许。
    for pattern, label in _SECRET_CONTENT_PATTERNS:
        if pattern.search(data):
            findings.append(label)
    return findings


def _file_mode(path: Path, data: bytes) -> int:
    """优先真实 POSIX 位；不可读时退化为 shebang/扩展名推断。"""
    try:
        mode = path.stat().st_mode
        if mode & 0o111:
            return 0o755
    except OSError:
        pass
    if data.startswith(b"#!"):
        return 0o755
    if path.suffix in {".sh", ".bash"}:
        return 0o755
    return 0o644


def select_archive_files(code_dir: Path, source_include: list[str]):
    """返回 (选中文件列表[(rel, path)], 排除报告, 安全违规列表)。

    rel 以 code/（或 examples/）目录为根的 POSIX 相对路径。
    """
    if not code_dir.is_dir():
        return [], {}, []

    code_name = code_dir.name
    root_prefix = f"{code_name}/"
    include_paths = {f"{code_name}/outputs/{item}" for item in source_include}

    selected: list[tuple[str, Path]] = []
    excluded: dict[str, str] = {}
    violations: list[str] = []

    for path in sorted(code_dir.rglob("*")):
        if path.is_symlink():
            violations.append(f"拒绝符号链接：{path.relative_to(code_dir.parent)}")
            continue
        if not path.is_file():
            continue
        rel = root_prefix + path.relative_to(code_dir).as_posix()
        parts = rel.split("/")
        if rel in include_paths:
            pass  # 显式例外。
        elif _is_excluded_dir(parts):
            excluded[rel] = "排除目录（outputs/build/缓存等）"
            continue
        if _is_excluded_basename(path.name):
            excluded[rel] = "排除构建产物或临时文件"
            continue
        if _looks_binary(path):
            excluded[rel] = "排除二进制内容"
            continue
        selected.append((rel, path))

    for item in source_include:
        target = code_dir / "outputs" / item
        expected = f"{code_name}/outputs/{item}"
        if not any(rel == expected for rel, _ in selected):
            if not target.is_file() or target.is_symlink():
                violations.append(f"source_include 不是普通文件：{expected}")
            else:
                selected.append((expected, target))
                excluded.pop(expected, None)

    return selected, excluded, violations


def build_source_zip(zip_path: Path, code_dir: Path, source_include: list[str]):
    """生成确定性 ZIP。返回 (sha256, size, entry_count)；无可发布文件返回 None。"""
    selected, excluded, violations = select_archive_files(code_dir, source_include)
    if violations:
        raise ImporterError(
            "ZIP_UNSAFE_INPUT",
            "；".join(violations[:5]) + ("" if len(violations) <= 5 else " 等"),
            source=code_dir,
        )
    if not selected:
        return None

    if len(selected) > MAX_ENTRIES:
        raise ImporterError(
            "ZIP_LIMIT_EXCEEDED",
            f"条目数 {len(selected)} 超过上限 {MAX_ENTRIES}",
            source=code_dir,
        )

    entries: list[tuple[str, bytes, int]] = []
    total = 0
    for rel, path in sorted(selected, key=lambda e: e[0].encode("utf-8")):
        data = path.read_bytes()
        findings = _secret_findings(rel, data)
        if findings:
            raise ImporterError(
                "ZIP_SECRET_DETECTED",
                f"{rel}：" + "、".join(findings),
                source=code_dir,
            )
        if len(data) > MAX_FILE_BYTES:
            raise ImporterError(
                "ZIP_LIMIT_EXCEEDED",
                f"{rel} 大小 {len(data)} 超过单文件上限",
                source=code_dir,
            )
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ImporterError(
                "ZIP_LIMIT_EXCEEDED",
                "单日未压缩总量超过 100 MiB 上限",
                source=code_dir,
            )
        entries.append((rel, data, _file_mode(path, data)))

    # 显式目录项。
    dir_names = set()
    for rel, _, _ in entries:
        parts = rel.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dir_names.add("/".join(parts[:i]) + "/")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for name in sorted(dir_names, key=lambda s: s.encode("utf-8")):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o40755 << 16) | 0x10
            zf.writestr(info, b"")
        for rel, data, mode in entries:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = mode << 16
            zf.writestr(info, data)

    _verify_zip(zip_path, entries)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return digest, zip_path.stat().st_size, len(entries) + len(dir_names)


def _verify_zip(zip_path: Path, entries):
    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip() is not None:
            raise ImporterError(
                "ZIP_CRC_INVALID", "ZIP CRC 校验失败", source=zip_path
            )
        names = set(zf.namelist())
        for rel, _, mode in entries:
            if rel not in names:
                raise ImporterError(
                    "ZIP_VERIFY_FAILED", f"缺少条目：{rel}", source=zip_path
                )
            info = zf.getinfo(rel)
            if (info.external_attr >> 16) & 0o111 and not mode & 0o111:
                raise ImporterError(
                    "ZIP_VERIFY_FAILED", f"权限不一致：{rel}", source=zip_path
                )
