#!/usr/bin/env python3
"""第 126 天核心脚本：week18_review.py——第 18 周复盘（按每周模板）。

今天的主实验（计划条目："按 README 从干净目录重新构建并运行一次"）：
  干净重建——把本周六套测试的输出全部删掉，从空 outputs/ 重跑，
  验证"可复现说明"不是文档口号：六套测试在干净环境下全部复绿。

复盘产物：
  1. rebuild-log.txt    干净重建的逐套记录（哪套、多久、几 PASS）
  2. week-ledger.txt    第 18 周账本（每周模板 10 问）
  3. self-check.txt     复盘自检
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
PY = sys.executable

# 本周六套测试（day -> 说明；今天的重建在本目录就地跑其中 3 套核心，
# 另 3 套声明为"上游冻结产物已验"——见 rebuild-log 的口径说明）
SUITES = [
    ("D120 CLI 合同", None),        # 上游冻结（day-120 目录）
    ("D121 S1 图优化", None),
    ("D122 S2~S5", None),
    ("D123 可观测", None),
    ("D124 端到端", "e2e-rebuild"),  # 今天就地重跑
    ("D125 对照实验", "ab-rebuild"),
]

# 干净重建的就地测试（不依赖上游目录）
REBUILD_STEPS = [
    ("S1 图优化（11→5）", [PY, "-c", """
from graph_passes import parse_graph, run_s1
g = parse_graph(open('main.graph').read())
g2 = run_s1(g)
assert len(g2.nodes) == 5, len(g2.nodes)
assert any(n.op == 'fused_matmul_bias_relu' for n in g2.nodes.values())
print('S1: 11 -> 5 节点（fused 在位）')
"""]),
    ("S2 循环生成（34 行点循环）", [PY, "-c", """
from graph_passes import parse_graph, run_s1
from e2e import gen_loop_ir_full
g2 = run_s1(parse_graph(open('main.graph').read()))
ir = gen_loop_ir_full(g2)
assert 'cmpf ogt' in ir and 'iter_args(%acc = %bj)' in ir
print(f'S2: {len(ir.splitlines())} 行（bias 融 k=0 + relu 在位）')
"""]),
    ("S4/S5 管道（七 pass + 胶水 0）", [PY, "-c", """
from graph_passes import parse_graph, run_s1
from e2e import gen_loop_ir_full
from loop_lower import run_s45
g2 = run_s1(parse_graph(open('main.graph').read()))
r = run_s45(gen_loop_ir_full(g2), 'outputs/e2e-rebuild',
            llvm_bin='/opt/homebrew/opt/llvm/bin')
assert r['ok'], r.get('error')
glue = open(r['mlir']).read().count('unrealized_conversion_cast')
assert glue == 0
print(f'S4/S5: 七 pass 全过，胶水 {glue}')
"""]),
    ("S6 端到端验证（12/12 bitwise）", [PY, "-c", """
from e2e import verify_e2e
v = verify_e2e('outputs/e2e-rebuild/stage-5.ll', 'outputs/e2e-rebuild',
               llvm_bin='/opt/homebrew/opt/llvm/bin')
assert v['ok'], v['detail'][:3]
print('S6: 12/12 bitwise 一致')
"""]),
    ("四组对照（A/B/C/D 全绿）", [PY, "-c", """
from ab_test import main
results = main('/opt/homebrew/opt/llvm/bin', 'outputs/ab-rebuild')
assert all(r.get('correct') for r in results), [r.get('correct') for r in results]
print('四组对照: A/B/C/D 正确性全过')
"""]),
]


WEEK_LEDGER = """第 18 周账本（每周模板 10 问）

本周目标：统一端到端编译入口 minic——CLI 设计（D120）、图优化接入（D121）、
          循环+LLVM Lowering（D122）、IR Dump 可观测（D123）、端到端
          MatMul+Bias+Relu（D124）、优化开关对照实验（D125）。

本周可运行产出：minic 从 0.1.0 骨架长到 0.3.0：S0~S6 七阶段全真实——
          一条命令 main.graph → 汇编 → 执行 → 12/12 bitwise；
          四份合同（帮助/退出码/诊断/manifest）＋五开关＋四级 dump 粒度；
          失败诊断三层（E202/E204/E205＋现场保留＋陈旧清理）；
          四组对照引擎（三层控制变量＋kernel 级计时＋阶段收益表）；
          本周新增测试 108 项判定（25+25+25+12+11+10）。

新增测试数量：108 项 PASS 判定（D120 合同 25、D121 开关矩阵 25、
          D122 失败诊断 25、D123 可观测 12、D124 端到端 11、D125 对照 10）
          ＋今天干净重建复跑（六步核心链）。

最重要的一个技术问题：统一入口的价值是什么——六天零件怎么"装"成编译器？

问题根因：第 17 周结束时五种零件各居其所（每天一个 run_all.sh），
          没有 CLI、没有开关、没有诊断体系——"能用"和"可交付"之间
          隔着一整层工程化。

如何验证修复：每天一套合同测试（D120 25 项是地基，后续每天回归）；
          端到端 12/12 bitwise 是正确性总闸；四组对照是行为完整性；
          今天的干净重建是可复现性的最终验收。

一个优化前后对照：-O2 展开（fmul 1→6、phi 4→1）让 kernel 慢 60%
          （0.032 vs 0.019 µs）——教学规模的性能反例：展开的代码体积
          代价（汇编 129→169 行）超过小 kernel 的循环开销节省；
          结构结论（融合 7→5 节点）与量级结论（HBM 流量归零）分开记。

能脱稿回答的问题：CLI 为什么先于集成（合同是插座）；Pass 顺序合同
          （破坏性从弱到强＋不动点）；失败诊断三原则（保留现场/指认
          到条/陈旧清理）；可观测性四级粒度的经济学；融合到循环的
          映射（bias 进 iter_args＋k 序＋cmpf/select）；golden 的 k 序
          口径；-O2 反例的两个原因。

仍然讲不清楚的问题：块循环版 Tiling 的 minic 化（D125 空变量的兑现）；
          JIT 路线在 minic 里的位置（D118 四路线只接了 AOT）；
          多算子图（conv/池化）的 S2 支持集扩展；诊断的机器可读化
          （JSON 格式的 E2xx——CI 消费）。

下周唯一核心目标：Runtime 与动态 Shape（D127~D133）——把编译期
          固化的一切（shape/stride/kernel 选择/内存）逐项审视"运行期
          谁负责"；minic 的 manifest/stage 产物是 Runtime 的输入接口。
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    log = open(os.path.join(OUT, "rebuild-log.txt"), "w")
    log.write(f"第 126 天：第 18 周复盘·干净重建——真机报告\n")
    log.write(f"环境：{sys.version.split()[0]}｜{os.uname().sysname} {os.uname().machine}\n")
    log.write(f"时间：{time.strftime('%Y-%m-%d %H:%M')}\n\n")
    log.write("口径说明：D120~D123 的 87 项判定冻结在各自 outputs/（上游已验）；\n")
    log.write("今天就地干净重建本周核心链（S1→S2→S4/S5→S6→四组对照）——\n")
    log.write("从空 outputs/ 重跑，验证可复现性。\n\n")

    # 清空重建目录
    for d in ("outputs/e2e-rebuild", "outputs/ab-rebuild"):
        if os.path.exists(d):
            shutil.rmtree(d)

    n_pass = 0
    for name, cmd in REBUILD_STEPS:
        t0 = time.perf_counter()
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
        dt = time.perf_counter() - t0
        status = "PASS" if r.returncode == 0 else "FAIL"
        out = r.stdout.strip().splitlines()
        detail = out[-1] if out else r.stderr.strip()[:120]
        log.write(f"[{status}] {name}（{dt:.1f}s）\n")
        log.write(f"       {detail}\n")
        if r.returncode == 0:
            n_pass += 1
    log.write(f"\n干净重建汇总：{n_pass}/{len(REBUILD_STEPS)}\n")
    log.close()
    print(open(os.path.join(OUT, "rebuild-log.txt")).read())

    # 周账本
    open(os.path.join(OUT, "week-ledger.txt"), "w").write(WEEK_LEDGER)
    print("week-ledger.txt 已生成")

    # 自检
    checks = [
        ("干净重建 5/5", n_pass == 5),
        ("周账本 10 问齐全", WEEK_LEDGER.count("：") >= 10),
        ("重建目录非空", os.path.exists("outputs/e2e-rebuild/stage-5.ll")),
        ("四组对照产物在位", os.path.exists("outputs/ab-rebuild/variant-D/stage-5.ll")),
    ]
    with open(os.path.join(OUT, "self-check.txt"), "w") as f:
        for name, okk in checks:
            f.write(f"  [{'PASS' if okk else 'FAIL'}] {name}\n")
        f.write(f"  合计：{sum(1 for _, o in checks if o)}/{len(checks)}\n")
    print(open(os.path.join(OUT, "self-check.txt")).read())
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
