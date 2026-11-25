"""确定性内容哈希（设计文档 §7.3）。

content_sha 输入：
1. 当日目录下全部普通文件（README、images、code/examples、冻结 outputs 等）；
2. 该日有效覆盖配置的规范 JSON。

不包含导入时间、部署域名、ZIP 本身或全局前端资源。
算法：路径（UTF-8 字节序排序）+ NUL + 十进制大小 + NUL + 单文件 SHA-256 + LF，
末尾追加覆盖 JSON，再对整个字节流取 SHA-256。
"""
import hashlib
import os
from pathlib import Path

from .errors import ImporterError

_READ_CHUNK = 1 << 20


def _iter_regular_files(day_dir: Path):
    """os.walk（不跟随符号链接），产出 (posix相对路径, 绝对路径)。"""
    for root, dirs, files in os.walk(day_dir, followlinks=False):
        root_path = Path(root)
        kept = []
        for name in sorted(dirs):
            if (root_path / name).is_symlink():
                continue
            kept.append(name)
        dirs[:] = kept
        for name in files:
            path = root_path / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(day_dir).as_posix()
            yield rel, path


def compute_content_sha(day_dir: Path, override_payload: bytes) -> str:
    digest = hashlib.sha256()
    entries = sorted(_iter_regular_files(day_dir), key=lambda e: e[0].encode("utf-8"))
    for rel, path in entries:
        stat = path.stat()
        size = stat.st_size
        file_digest = hashlib.sha256()
        read_total = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_READ_CHUNK)
                if not chunk:
                    break
                read_total += len(chunk)
                file_digest.update(chunk)
        if read_total != size:
            raise ImporterError(
                "CONTENT_HASH_RACE",
                f"文件在遍历与读取之间发生变化：{rel}",
                source=day_dir,
            )
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_digest.hexdigest().encode("ascii"))
        digest.update(b"\n")
    digest.update(override_payload)
    return digest.hexdigest()
