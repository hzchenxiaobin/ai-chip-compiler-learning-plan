#!/usr/bin/env python3
"""第 159 天：整理性能材料——数据汇总＋图表引用＋结论摘要。"""
from __future__ import annotations
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "outputs")


def main():
    os.makedirs(OUT, exist_ok=True)
    # 引用上游数据
    summary = {"标题": "minic 性能材料汇总", "数据源": []}
    sources = [
        ("基线", "day-148/outputs/baseline.json"),
        ("拆解", "day-149/outputs/breakdown.json"),
        ("Roofline", "day-150/outputs/roofline.json"),
        ("优化", "day-151/outputs/optimize.json"),
        ("分布", "day-152/outputs/cross-shape.json"),
        ("反例", "day-153/outputs/counterexample.json"),
    ]
    for name, rel in sources:
        # 兼容两种位置：day-XXX/outputs 与 day-XXX/code/outputs
        p = os.path.join(ROOT, "tutorials", rel)
        if not os.path.exists(p):
            p = os.path.join(ROOT, "tutorials", rel.replace("/outputs/", "/code/outputs/"))
        if os.path.exists(p):
            data = json.load(open(p))
            summary["数据源"].append({"name": name, "path": rel,
                                      "keys": list(data.keys())[:6] if isinstance(data, dict) else f"list[{len(data)}]"})
        else:
            summary["数据源"].append({"name": name, "path": rel, "status": "缺失"})

    # 结论摘要（五步一句话版）
    summary["结论"] = (
        "160³ 朴素 kernel 基线 20.9ms/0.39GF（离峰值百倍）；"
        "稳态执行占 100%（嫌疑唯一）；Roofline 两屋顶都远（执行效率瓶颈）；"
        "O2 展开 8.4×（H1 成立）、tile 0.3×（H2 证伪）；"
        "跨 7 shape 分布 1.7~14.1×；反例是环境函数（LLVM 18 vs 23）。"
    )
    summary["口径声明"] = {
        "基线五要素": "shape 160³/朴素 O0/7×3 中位/arm64 Darwin/复现命令",
        "统计": "中位数抗离群＋P90 尾部（D138 口径）",
        "环境戳": "所有结论带版本/平台声明（D153 教训）",
    }

    json.dump(summary, open(os.path.join(OUT, "perf-summary.json"), "w"),
              ensure_ascii=False, indent=2)
    n_ok = sum(1 for s in summary["数据源"] if s.get("keys"))
    print(f"数据源：{n_ok}/6 在位")
    print(f"结论：{summary['结论'][:60]}...")
    ok = n_ok >= 5
    print(f"判定：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
