"""import_tutorial：从指定 commit 导入并激活内容版本（设计文档 §8.1）。

用法：
    python manage.py import_tutorial --commit HEAD
    python manage.py import_tutorial --commit <40位哈希> --no-activate
    python manage.py import_tutorial --commit local --source-dir /path/to/snapshot
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.content.importer.importer import import_release, resolve_commit
from apps.content.importer.errors import ImporterError


class Command(BaseCommand):
    help = "从指定 Git 提交导入 168 天教程并激活内容版本"

    def add_arguments(self, parser):
        parser.add_argument("--commit", required=True,
                            help="40 位提交哈希，或 HEAD/分支名（解析为提交）")
        parser.add_argument("--config-version", type=int, default=1)
        parser.add_argument("--no-activate", action="store_true",
                            help="仅导入并校验，不切换 active_release")
        parser.add_argument("--source-dir", default=None,
                            help="直接使用指定快照目录（测试用；commit 仍须有效）")
        parser.add_argument("--expected-days", type=int, default=168)

    def handle(self, *args, **options):
        repo_root = Path(settings.BASE_DIR)
        commit_arg = options["commit"]
        if commit_arg == "local":
            if not options["source_dir"]:
                raise CommandError("--commit local 需要同时提供 --source-dir")
            commit = "0" * 40  # 测试快照：显式伪提交。
        else:
            commit = resolve_commit(repo_root, commit_arg)
        self.stdout.write(f"目标提交：{commit}")

        try:
            release = import_release(
                content_commit=commit,
                config_version=options["config_version"],
                source_root=Path(options["source_dir"]) if options["source_dir"] else None,
                repo_root=repo_root,
                expected_days=options["expected_days"],
                activate=not options["no_activate"],
                logger=lambda msg: self.stdout.write(msg),
            )
        except ImporterError as exc:
            raise CommandError(exc.format()) from exc

        self.stdout.write(self.style.SUCCESS(
            f"导入完成：{release.day_count} 天 / {release.chunk_count} 分片 / "
            f"状态 {release.status} / checksum {release.checksum[:16]}…"
        ))
