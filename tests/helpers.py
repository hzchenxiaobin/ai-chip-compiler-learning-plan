"""测试辅助：生成最小教程树。"""
import json
from pathlib import Path


def week_of(day: int) -> int:
    return (day - 1) // 7 + 1


def day_readme(day: int, title: str, *, objective=None, time_text=None,
               prerequisites=None, deliverable=None, body=None) -> str:
    objective = objective or f"完成第 {day} 天的核心练习"
    time_text = time_text or "学习 30 分钟 + 实践 45 分钟"
    prerequisites = prerequisites or "一台 Linux 机器或 WSL"
    deliverable = deliverable or f"第 {day} 天的练习产物"
    body = body or f"""
## 概念

![示意图](images/diagram.svg)

第 {day} 天的概念讲解，包含 MLIR 与 mlir-opt 命令、常量折叠与 FileCheck。

## 环境

运行环境说明与 Roofline 提示。

```bash
echo day-{day:03d}
```

## 验收

按清单检查产出。
"""
    return f"""# 第 {day} 天：{title}

> **今日目标**：{objective}
> **预计时间**：{time_text}
> **前置准备**：{prerequisites}
> **今日产出**：{deliverable}
{body}
"""


def write_day(root: Path, day: int, *, title=None, with_code=True,
              with_runall=False, with_outputs=False, with_examples=False,
              readme=None) -> Path:
    """写入一个日课目录，返回日目录路径。"""
    week = week_of(day)
    day_dir = root / "tutorials" / f"week-{week:03d}" / f"day-{day:03d}"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "README.md").write_text(
        readme or day_readme(day, title or f"测试日课 {day}"), encoding="utf-8"
    )
    images = day_dir / "images"
    images.mkdir(exist_ok=True)
    (images / "diagram.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>',
        encoding="utf-8",
    )
    if with_code:
        code = day_dir / "code"
        code.mkdir(exist_ok=True)
        (code / "main.cpp").write_text(
            f"int main() {{ return {day}; }}\n", encoding="utf-8"
        )
        if with_runall:
            (code / "run_all.sh").write_text(
                "#!/bin/bash\necho ok\n", encoding="utf-8"
            )
        if with_outputs:
            outputs = code / "outputs"
            outputs.mkdir(exist_ok=True)
            (outputs / "result.txt").write_text("PASS\n", encoding="utf-8")
    if with_examples:
        examples = day_dir / "examples"
        examples.mkdir(exist_ok=True)
        (examples / "demo.cpp").write_text("int main(){}\n", encoding="utf-8")
    return day_dir


def write_plan(root: Path) -> None:
    plan = ["# 学习计划", ""]
    for week in range(1, 25):
        plan.append(f"## 第 {week} 周：测试第 {week} 周主题")
    (root / "AI芯片编译器学习计划.md").write_text("\n".join(plan), encoding="utf-8")


def write_overrides(root: Path, days: dict | None = None) -> None:
    config_dir = root / "config" / "learning"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "days": days or {}}
    (config_dir / "day-overrides.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_tree(base: Path, day_count: int = 28, **kwargs) -> Path:
    """生成完整最小教程树（day_count 天 + 计划 + 覆盖配置）。"""
    root = base / "source"
    root.mkdir(parents=True, exist_ok=True)
    for day in range(1, day_count + 1):
        write_day(
            root, day,
            with_runall=kwargs.get("with_runall", day % 3 == 0),
            with_outputs=kwargs.get("with_outputs", day % 5 == 0),
            with_examples=kwargs.get("with_examples", False),
        )
    write_plan(root)
    write_overrides(root, kwargs.get("overrides"))
    return root
