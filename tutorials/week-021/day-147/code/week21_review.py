#!/usr/bin/env python3
"""第 147 天：第 21 周复盘——删代码日＋每周模板账本。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

LEDGER = """第 21 周账本（每周模板）

本周目标：扩展方向——块循环 Tiling 的 minic 化（「动态 Shape＋自动
          调度」轻量组合的最后一块，future F-01）。

本周可运行产出：gen_block_v2 生成器（~300 行：块循环壳＋参数校验）；
          四个集成点打通（tile 端到端/(shape,tile) 分发 key/fuzz 扩容/
          全管道数值）；正式验收 10/10（正 5/负 3/边 2）＋D141 标准 5/5。

新增测试数量：10 例正式＋30 组 fuzz＋3 极端＋5 负例＝48 项新增判定。

最重要的一个技术问题：扩展是否真正增强了项目主线——还是增加了
          无关复杂度？

问题根因：扩展的诱惑是"顺便多做点"——范围失控是第一死因；判断的
          标准是"它让已有能力更强还是让系统更乱"。

如何验证修复：主线检验三问——块循环让 minic 的能力更强了吗
          （tile 从空变量变真参数——是）；它依赖/破坏了已有功能吗
          （tile=None 零变化——没有）；删掉它项目会缺什么
          （性能差异的可测性——D153 的实验基础）。

一个优化前后对照：D125 时空变量（tile 不影响产物）→ 今天 tile 改变
          产物（phi 7 vs 4）＋数值全对＋分发可用——--tile 参数从
          装饰变成功能。

能脱稿回答的问题：选型判据（衔接＞相关性＞成本）；蓝图先行（形态
          合法才施工）；幂等论证的正确前提（每块独立算同值——k0 bug
          的教训）；组合是新的失败面；5/3/2 三面验收；标准先行。

仍然讲不清楚的问题：块内边界完整版的 min 钳制 IR 表达（教学边界）；
          tile 的自动搜索接入（D106~D111 与 minic 的接口）；
          双缓冲在 CPU 教学版的可测性（L1 全命中——测不出收益）。

下周唯一核心目标：性能归因（D148~D154）——选择慢用例、建立基线、
          拆解编译/运行开销、Roofline 瓶颈分析、有依据的优化、
          跨 Shape 验证、构造反例、完整性能报告——块循环 Tiling
          正好是第 22 周的实验素材。
"""

CLEANUP = """删代码日清单（计划条目："删除未被使用的实验分支和临时代码"）

检查对象：第 21 周的四个代码目录（D143~D146）
检查标准：文件被 README/测试引用＝保留；否则＝删除候选

保留（被引用）：
  · block_tile.py（D143 生成器 v1——README 5.2 引用）
  · constraints.py（v2 生成器＋校验——D145/146 复用）
  · integrate.py / accept.py（集成与验收——D146 的主产出）

结论：第 21 周无实验分支残留——每天都是"完成即验收"的节奏，
      没有留下半成品。（诚实声明：这是节奏红利不是设计必然——
      D142 的"先窄后宽"纪律直接避免了分支累积。）
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "week-ledger.txt"), "w").write(LEDGER)
    open(os.path.join(OUT, "cleanup.txt"), "w").write(CLEANUP)
    checks = [
        ("账本 10 问", LEDGER.count("：") >= 10),
        ("主线检验三问", "主线检验三问" in LEDGER),
        ("删代码清单", len(CLEANUP) > 100),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
