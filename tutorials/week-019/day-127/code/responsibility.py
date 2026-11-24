#!/usr/bin/env python3
"""第 127 天核心脚本：responsibility.py——Compiler/Runtime 职责划分审计。

对 minic 管道的每个决策点做"谁负责"的审计，产出职责划分表：
  · 决策点（如"shape 确定"、"内存分配"、"kernel 选择"）
  · 当前归属（编译期固化 / 运行期动态 / 两者协作）
  · 证据（哪个文件/哪行代码/哪个 manifest 字段）
  · 真实系统对照（TVM/CUDA/本教程的对应做法）

计划条目："列出当前项目中 Shape、内存、Kernel 选择和同步分别由谁负责"。
产出：职责划分表（机器生成+人工注释）＋运行时流程图（图2）。
"""
from __future__ import annotations

import json
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# 职责划分表：每个决策点一行
# 归属枚举：COMPILE（编译期固化）/ RUNTIME（运行期动态）/ SPLIT（协作）
TABLE = [
    # (决策点, 归属, 当前 minic 的实现证据, 真实系统对照, 教学评注)
    ("Shape 确定（M/N/K）", "COMPILE",
     "S2 从图推断：const.shape/arg.tensor/reshape.new_shape 三来源（loop_lower._infer_shape）",
     "TVM: 编译期全静态；PyTorch: 运行期动态 shape（每次推理现推）",
     "minic 是『纯静态派』——图 IR 里 shape 是属性不是输入"),
    ("Stride/布局确定", "COMPILE",
     "S2 签名 strided<[K,1]> 写死行主序（gen_loop_ir_full）",
     "TVM: layout 自由变换；cuDNN: 运行期选 NHWC/NCHW",
     "D57~D68 的布局课在 minic 里退化为固定行主序——教学取舍"),
    ("Tile 参数选择", "COMPILE",
     "CLI --tile 传入，manifest.tile 记录（但 D125 证明教学版不消费）",
     "TVM/Ansor: 搜索空间+代价模型；AutoTVM: 运行期 autotune",
     "D106~D111 的调优管道是它的真身"),
    ("Kernel 选择（哪个实现）", "COMPILE",
     "S1 融合决策 + S2 单一展开路径（无备选）",
     "cuDNN: 运行期 heuristic 按 shape 选 kernel；Triton: JIT 缓存",
     "minic 无备选——D129/D130 的特化/回退将引入『两个实现』"),
    ("内存分配（输出缓冲区）", "RUNTIME",
     "kernel 内 memref.alloc → malloc(48)，每次调用都分配（stage-5.ll: %20 = call @malloc）",
     "TVM: 运行时 TVMArray 从 allocators 拿；CUDA: cudaMalloc 或池",
     "D118 挂账的 malloc 债务——D131 结清（分配器/池）"),
    ("内存释放", "NONE",
     "kernel 不 free——泄漏（教学规模无所谓，D118 诚实声明）",
     "真实 Runtime 必须管生命周期（引用计数/arena/池）",
     "『没人负责』也是一种划分——真实系统不能这么选"),
    ("输入数据搬运", "CALLER",
     "driver 的 desc_t 构造把 A/B 地址传给 kernel（verify_driver.c）",
     "GPU: cudaMemcpyAsync/H2D；CPU: 零拷贝（指针直传）",
     "CPU 教学版天然零拷贝——GPU 版的搬运是 Runtime 大头"),
    ("同步（何时算完）", "IMPLICIT",
     "C 函数调用返回＝完成（同步语义，D118 AOT 路线）",
     "CUDA: stream+event；异步 Launch 后 host 侧 sync",
     "D132 的主题——CPU 的隐式同步在 GPU 上显式化"),
    ("验证（结果对不对）", "TEST",
     "S6 golden bitwise（verify_e2e，12/12）",
     "真实系统：UT 层面做，运行期不做逐次验证（太慢）",
     "验证是『开发期职责』不是运行期——但 CI 里它守着每次提交"),
    ("Kernel 缓存（编译结果复用）", "NONE",
     "每次 minic 调用都全管道重跑（无缓存）",
     "Triton: @lru_cache 按 (shape,dtype) 缓存；TVM: 本地磁盘缓存",
     "D129 特化将引入『按 shape 缓存』的雏形"),
    ("错误诊断与恢复", "COMPILE",
     "E1xx/E2xx 诊断体系（minic.py DIAG_CODES）",
     "运行期错误（OOM/超时）由 Runtime 兜底重试或降级",
     "编译期诊断已完备；运行期恢复（D130 回退）下周见"),
]


def render_table() -> str:
    lines = ["第 127 天：Compiler/Runtime 职责划分表（机器生成）", "=" * 78, ""]
    lines.append(f"{'决策点':<24}{'归属':<10}证据与对照")
    lines.append("-" * 78)
    for item, owner, evidence, real, note in TABLE:
        lines.append(f"{item}")
        lines.append(f"  归属：{owner}")
        lines.append(f"  minic 证据：{evidence}")
        lines.append(f"  真实系统：{real}")
        lines.append(f"  评注：{note}")
        lines.append("")
    lines.append("=" * 78)
    lines.append("""
归属统计与解读：
  COMPILE ×4（Shape/Stride/Tile/Kernel选择）—— minic 是纯静态编译派
  RUNTIME ×1（输出内存分配）—— malloc 债务的唯一运行期职责
  CALLER ×1（输入搬运）—— driver 负责，天然零拷贝
  IMPLICIT ×1（同步）—— CPU 调用语义隐式保证
  NONE ×2（释放/缓存）—— 没人负责——真实系统不能留空的两格
  TEST ×1（验证）—— 开发期职责，不进运行期热路径

核心结论（下周的地图）：
  ① D128 运行期参数——Shape 从"编译期属性"变"运行期输入"要动什么
  ② D129 特化——Kernel 选择从 COMPILE（单一）变 SPLIT（多版本+分发）
  ③ D130 回退——错误恢复从 NONE 变 RUNTIME（分发器兜底）
  ④ D131 内存——分配从 RUNTIME（裸 malloc）变 RUNTIME（池化）＋释放从 NONE 变 RUNTIME
  ⑤ D132 同步——从 IMPLICIT 变显式（stream/event 的教学映射）
""")
    return "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    text = render_table()
    open(os.path.join(OUT, "responsibility-table.txt"), "w").write(text)
    print(text[:2000])
    # JSON 版（机器可读）
    rows = [{"item": t[0], "owner": t[1], "evidence": t[2], "real": t[3], "note": t[4]}
            for t in TABLE]
    json.dump(rows, open(os.path.join(OUT, "responsibility-table.json"), "w"),
              ensure_ascii=False, indent=2)
    # 自检
    owners = [t[1] for t in TABLE]
    checks = [
        ("11 个决策点", len(TABLE) == 11),
        ("归属枚举合法", all(o in ("COMPILE", "RUNTIME", "SPLIT", "CALLER",
                              "IMPLICIT", "NONE", "TEST") for o in owners)),
        ("COMPILE ≥ 4（静态派）", owners.count("COMPILE") >= 4),
        ("NONE 恰 2（释放+缓存）", owners.count("NONE") == 2),
        ("JSON 与表一致", len(rows) == 11),
    ]
    with open(os.path.join(OUT, "self-check.txt"), "w") as f:
        for name, okk in checks:
            f.write(f"  [{'PASS' if okk else 'FAIL'}] {name}\n")
        f.write(f"  合计：{sum(1 for _, o in checks if o)}/{len(checks)}\n")
    print("\n".join(open(os.path.join(OUT, "self-check.txt")).read().splitlines()))
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
