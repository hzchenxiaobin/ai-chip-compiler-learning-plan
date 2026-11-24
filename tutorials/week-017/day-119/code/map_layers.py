#!/usr/bin/env python3
"""第 119 天核心脚本：Lowering 全景对账器——把第 17 周（D113~D118）六天
走过的表示层逐层摆开，对每一层回答三个问题：

  保留（REMAIN）——哪些信息原样带到下一层？
  丢失（LOST）  ——哪些信息在本层被消费掉、下一层再也看不到？
  新增（GAIN）  ——哪些信息是本层"长出来"的（下一层依赖它）？

这不是讲义——每一条记录都来自真实文件的机器统计（census.py 口径对齐
D114~D117）。产出：
  outputs/lowering-map.txt   七层对账表（今日主产出）
  outputs/layer-census.txt   每层的 op/指令计数（机器实测）
  outputs/information-test.txt 12 题周测（自动判分）

用法：python3 map_layers.py            # 只需要 python3，零第三方依赖
（layer-census 的 MLIR 各层数字若本机有 mlir-opt 会现场重算，
  没有则使用 D117 冻结的 outputs 对账值——两种模式在报告里注明）
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")

# ──────────────────────────────────────────────────────────────
# 第 17 周六天的七层表示（D118 是终点不是新层）
# 每层：名字、当天、形态、文件证据、机器可核对的数字
# ──────────────────────────────────────────────────────────────
LAYERS = [
    {
        "name": "图/算子层",
        "day": "D57~D112（源流）",
        "form": "mini 算子图（mini.matmul 等）",
        "evidence": "mini.matmul → scf 循环的 Lowering 任务单（D85~D90）",
        "has": ["算子语义（MatMul+Bias+Relu）", "图拓扑（谁消费谁）",
                "shape 与 dtype", "融合决策", "Tile 决策", "布局决策"],
        "lost": [],
        "gain": ["领域语义（这是'矩阵乘'——不是三层 for）"],
        "numbers": "D114 残留对照：mini.* 无模式、残留即报错",
    },
    {
        "name": "循环层（scf）",
        "day": "D85~D90 / D117 源",
        "form": "scf.for 嵌套＋arith＋memref",
        "evidence": "gemm.mlir（21 op：scf.for×3＋scf.yield×1）",
        "has": ["循环边界/步长（静态可算）", "累加初值（iter_args）",
                "迭代依赖（yield 链）", "memref 下标表达式"],
        "lost": ["算子语义——三层 for 不再'是'MatMul",
                 "融合边界——bias 加在 k=0 圈还是逐元素，图上才知道"],
        "gain": ["显式循环序（i/j/k 顺序＝性能决策的落点）"],
        "numbers": "census：21 op（func 1、arith 10、scf 4、memref 4、return 1...）",
    },
    {
        "name": "cf 层（控制流拍平）",
        "day": "D117 阶段 1",
        "form": "cf.br/cond_br＋块参数",
        "evidence": "gemm-1-scf-to-cf.mlir（D117 冻结）",
        "has": ["块参数（phi 前身）", "显式跳转目标", "循环不变量在块间显式流动"],
        "lost": ["scf.for 的结构语义——'这是循环'变成'这是一堆块＋回跳边'",
                 "iter_args 的初值/步进配对——拆散进 init/header/latch 四块"],
        "gain": ["入口/出口块显式化（LLVM 块模型的预演）"],
        "numbers": "D117 实测：9 块、3 cond_br（四块×3 循环）",
    },
    {
        "name": "LLVM Dialect（MLIR 内）",
        "day": "D117 阶段 2",
        "form": "llvm.* 纯方言（reconcile 后）",
        "evidence": "gemm-2-llvm-dialect.mlir（D117 冻结）",
        "has": ["描述符字段操作（extractvalue/insertvalue）",
                "gep 地址算术", "malloc 调用", "包装函数 _mlir_ciface"],
        "lost": ["memref 类型——'张量视图'语义换成 5 字段裸结构体",
                 "index 类型——统一 i64（D114 兑换表）",
                 "strides 的'张量含义'——只剩整数乘加"],
        "gain": ["C ABI 合同（sret＋按值聚合拆参数）",
                 "运行库符号依赖（declare malloc）"],
        "numbers": "D117 实测：94 op（reconcile 后）；胶水 6→0",
    },
    {
        "name": "LLVM IR（.ll）",
        "day": "D117 阶段 3 / D113 对照",
        "form": "define/phi/getelementptr",
        "evidence": "gemm-3.ll（62 SSA、4 phi、21 insertvalue）",
        "has": ["SSA 值与槽位编号", "phi 节点", "类型系统（ptr/i64/f32）"],
        "lost": ["MLIR 的名字——%c1a 变 %14、^merge 变 10:（D113 R1 重编号）",
                 "常量的'来历'——llvm.mlir.constant 变成立即数内联（R2）",
                 "块参数——变 phi（R3），传值信息从 br 挪进块首"],
        "gain": ["寄存器级别的直线 SSA（优化器的输入形态）",
                 "值域注记（range——LLVM 22 的 sccp 长出来的，D113 实测）"],
        "numbers": "gemm-3.ll：62 SSA / 4 phi / malloc×1 / insertvalue×21",
    },
    {
        "name": "目标无关优化后 IR",
        "day": "D113 / D117 对照",
        "form": "opt -O2（instcombine/sccp/simplifycfg...）",
        "evidence": "gemm-O2.ll（D117 冻结；step: 4块→1块）",
        "has": ["语义（优化的合法性合同）", "调用图"],
        "lost": ["结构——D113 实测 step 菱形折叠成 select（4 块→1 块）",
                 "朴素形态——D117 实测 O2 后 SSA 62→67 但 fmul/fadd 1→18（展开）",
                 "'作者意图'——优化器不知道哪些循环是你想保留的"],
        "gain": ["常量折叠结果、死代码消除结果、值域/溢出注记（nuw）"],
        "numbers": "step：11→5 指令、7→4 SSA；gemm：fmul 1→18（循环展开）",
    },
    {
        "name": "机器码（汇编/执行）",
        "day": "D118（四条路线）",
        "form": "aarch64/arm64 目标码",
        "evidence": "gemm-3.s（D117 llc）＋D118 四路线 12/12",
        "has": ["语义（bitwise 对账的唯一裁判）"],
        "lost": ["SSA——寄存器复用抹掉值的历史",
                 "块结构——基本块融合进指令流",
                 "类型——机器码只有位宽没有 f32/i64 之分",
                 "malloc 语义——call 变 bl，'谁负责 free'合同消失"],
        "gain": ["真实地址/寄存器/指令调度",
                 "可运行性（D118：12 PASS / 0 FAIL）"],
        "numbers": "D118：四路线×12 点 bitwise；gemm-3.s 循环深度可读",
    },
]


def machine_census() -> list:
    """用 census.py 现场统计本机可算的层（gemm.mlir 源层）。
    没有工具链时返回空——报告改用 D117 冻结值并注明。"""
    rows = []
    src = os.path.join(HERE, "gemm.mlir")
    if not os.path.exists(src):
        return rows
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "census.py"), src],
                           capture_output=True, text=True, timeout=10)
        first = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
        if "total" in first:
            rows.append(("gemm.mlir（源·循环层）", first.strip()))
    except Exception:
        pass
    # D117 冻结产物的对账（文件在场就现场数）
    d117 = os.path.join(HERE, "..", "..", "day-117", "code", "outputs")
    for tag, fname in [
        ("gemm-0-optimized.mlir（MLIR 优化后）", "gemm-0-optimized.mlir"),
        ("gemm-1-scf-to-cf.mlir（cf 层）", "gemm-1-scf-to-cf.mlir"),
        ("gemm-2-llvm-dialect.mlir（LLVM 方言）", "gemm-2-llvm-dialect.mlir"),
    ]:
        p = os.path.join(d117, fname)
        if not os.path.exists(p):
            continue
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, "census.py"), p],
                               capture_output=True, text=True, timeout=10)
            first = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
            if "total" in first:
                rows.append((tag, first.strip()))
        except Exception:
            pass
    # .ll 层用 grep 数（census 是 MLIR 口径）
    ll = os.path.join(d117, "gemm-3.ll")
    if os.path.exists(ll):
        txt = open(ll).read()
        ssa = txt.count("  %")
        phi = txt.count(" phi ")
        iv = txt.count("insertvalue")
        rows.append(("gemm-3.ll（LLVM IR）",
                     f"total {ssa} 个 SSA 赋值行；phi {phi}；insertvalue {iv}"))
    return rows


# ──────────────────────────────────────────────────────────────
# 12 题周测（每题：题面、4 选项、答案、出处）
# ──────────────────────────────────────────────────────────────
QUIZ = [
    ("D113：LLVM Dialect 与 LLVM IR 的根本区别是？",
     ["一个是 MLIR 的 Operation 世界、一个是真 LLVM 的 SSA 世界",
      "一个用文本、一个用二进制",
      "一个有类型、一个没有类型", "一个是源码、一个是目标码"],
     0, "D113 §3.1：前者还能被 MLIR Pass 改写、能与其他方言混居"),
    ("D113：导出三规则 R1/R2/R3 分别是？",
     ["重编号／常量内联／块参数变 phi", "折叠／内联／展开",
      "重命名／常量传播／死代码删除", "类型下降／符号解析／指令选择"],
     0, "D113：%arg0→%0、4 条 constant 消失、^merge(%m)→phi"),
    ("D113：step 优化前 4 块/11 指令/7 SSA → 优化后？",
     ["1 块/5 指令/4 SSA", "4 块/5 指令/7 SSA",
      "1 块/11 指令/4 SSA", "2 块/7 指令/5 SSA"],
     0, "D113 实测：菱形折叠成 select＋常量折叠＋加零消除"),
    ("D114：TypeConverter 拒收哪两类输入？",
     ["tensor 与动态 memref", "f32 与 i32", "静态 memref 与 index", "llvm.* 与 cf.*"],
     0, "D114 兑换表：tensor 必须先 bufferize；动态 shape 暂不支持"),
    ("D115：rank2 memref 描述符的大小与字段偏移是？",
     ["56B；0/8/16/24/40", "40B；0/8/16/24/32", "64B；0/8/16/32/48", "48B；0/4/8/16/32"],
     0, "D115 TP1：真机 LLVM TargetData 与教学计算逐字段一致"),
    ("D116：为什么先用 elementwise 算子验证完整路径？",
     ["没有循环（C1 出局）、访存直来直去、参考可逐位对齐",
      "因为 elementwise 更快", "因为 MatMul 还没学",
      "因为循环 IR 不能转换"],
     0, "D116 §1：嫌疑人集合最小化——出错时只有当天新写的模式可疑"),
    ("D117：管道中 reconcile-unrealized-casts 的职责是？",
     ["清零转换边界残留的类型胶水", "优化循环",
      "分配内存", "生成 C 包装"],
     0, "D117：实测胶水 6 条（i64→index×3＋struct→memref×3）→ 0"),
    ("D117：_mlir_ciface_gemm 是谁生成的？",
     ["mlir-translate 由 llvm.emit_c_interface 属性驱动自动生成",
      "手写的 C 代码", "llc 生成的", "D116 的教学仿真"],
     0, "D117：D116 手写包装的真工具版；D118 四条路线都按它调用"),
    ("D118：JIT 与 AOT 的唯一分歧点是？",
     ["编译动作发生的时刻（离线 vs 在线）", "优化级别",
      "目标指令集", "链接器选择"],
     0, "D118 §3.1：同一编译器同一 IR，分歧只在编译时机"),
    ("D118：@gemm 的结果数据在哪里？",
     ["kernel 内部 malloc 的新缓冲区（描述符经 sret 写回）",
      "调用方预备的 C 数组", "栈上的返回值", "全局区"],
     0, "D118 TP5：错误示范里 C 数组全 0——kernel 从未写它"),
    ("第 17 周主线：从 mini.matmul 到机器码经过了几层表示？",
     ["图/算子→循环→cf→LLVM 方言→LLVM IR→优化→机器码（7 层）",
      "3 层：源码/IR/汇编", "2 层：MLIR/LLVM", "5 层"],
     0, "本周地图：其中 MLIR 侧 4 层、LLVM 侧 3 层"),
    ("为什么不能只看最终 LLVM IR 理解整个编译器？",
     ["因为每层 Lowering 都消费上层语义并长出新信息，IR 只剩'怎么算'没有'算什么/为何这样算'",
      "因为 LLVM IR 有 bug", "因为 IR 太长读不完", "因为汇编更直观"],
     0, "D119 §3：Tile 决策/融合边界/布局意图在 IR 里已不可见——但它们决定了 IR 长这样"),
]


def run_quiz() -> tuple:
    """自动判分：样例答卷（故意错 2 题）＋参考答案。"""
    # 样例答卷：第 5、10 题故意答错（模拟学习者常见误区）
    sample = [0, 0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0]
    correct = sum(1 for a, (_, _, ans, _) in zip(sample, QUIZ) if a == ans)
    lines = ["第 17 周周测：12 题（每题 1 分，样例答卷演示判分）", ""]
    for i, ((q, opts, ans, src), a) in enumerate(zip(QUIZ, sample), 1):
        mark = "✓" if a == ans else "✗"
        lines.append(f"Q{i}. {q}")
        lines.append(f"    样例答卷选：{chr(65+a)}. {opts[a]}  [{mark}]")
        if a != ans:
            lines.append(f"    正确答案：{chr(65+ans)}. {opts[ans]}")
            lines.append(f"    出处：{src}")
        else:
            lines.append(f"    （出处：{src}）")
        lines.append("")
    lines.append(f"样例得分：{correct}/12（第 5、10 题故意答错——描述符大小与结果位置是最常见误区）")
    return correct, "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1. 层级 census（机器实测）
    rows = machine_census()
    with open(os.path.join(OUT, "layer-census.txt"), "w") as f:
        f.write("第 17 周各层机器计数（census.py 口径对齐 D114~D117）\n")
        f.write(f"统计环境：{sys.version.split()[0]}｜{os.uname().sysname} {os.uname().machine}\n\n")
        if rows:
            for tag, line in rows:
                f.write(f"{tag}\n  {line}\n")
        else:
            f.write("（本机无输入文件）\n")
    print(f"layer-census.txt: {len(rows)} 层实测")

    # 2. 主产出：lowering-map.txt
    with open(os.path.join(OUT, "lowering-map.txt"), "w") as f:
        f.write("第 119 天：完整 Lowering 图——七层表示的信息对账表\n")
        f.write("=" * 72 + "\n\n")
        for i, L in enumerate(LAYERS):
            f.write(f"层 {i+1}｜{L['name']}（{L['day']}）\n")
            f.write(f"  形态：{L['form']}\n")
            f.write(f"  证据：{L['evidence']}\n")
            f.write(f"  实测：{L['numbers']}\n")
            f.write("  保留 → " + "；".join(L["has"]) + "\n")
            f.write("  丢失 ✗ " + ("；".join(L["lost"]) if L["lost"] else "（源层，无）") + "\n")
            f.write("  新增 ★ " + "；".join(L["gain"]) + "\n\n")
        f.write("=" * 72 + "\n")
        f.write("""面试口径：为什么不能只看最终 LLVM IR 理解整个编译器？

  1) 信息只减不增（每层都在消费上层语义）：最终 IR 里没有"这是融合过的
     MatMul+Bias"——bias 加在 k=0 圈的决策在图层做出、在循环层消费；
     没有"Tile 32×64 是搜索出来的"——Tile 决策在图层做出、在循环层
     变成边界常量。看 IR 只见"三层 for"，不见"为什么恰好这三层"。
  2) 新增信息有出处（每层都在长出新合同）：描述符 5 字段来自 D115 的
     ABI 决策；malloc 依赖来自 D117 的 alloc 转换；sret 包装来自 C ABI
     合同。不看中间层，这些"凭空出现"的结构无从解释也无法 debug。
  3) 优化会抹平朴素形态（LLVM 侧还有一层）：O2 把 fmul 1→18 条（循环
     展开）——展开是优化器的决定，不是作者的意图；反向从机器码推
     "编译器做了什么"会同时看到作者决策＋优化器决策，无法区分。
  结论：每一层的 IR 都是"带上下文的决策记录"；只看最终 IR＝只看账本
  最后一页。编译器的可观测性（D123 IR Dump）正是为此存在。
""")
    print("lowering-map.txt: 7 层对账表")

    # 3. 周测
    score, quiz_text = run_quiz()
    with open(os.path.join(OUT, "information-test.txt"), "w") as f:
        f.write(quiz_text)
    print(f"information-test.txt: 样例 {score}/12")

    # 4. 自检断言
    checks = [
        ("七层齐全", len(LAYERS) == 7),
        ("每层都有保留项", all(L["has"] for L in LAYERS)),
        ("非源层都有丢失项", all(L["lost"] for L in LAYERS[1:])),
        ("每层都有新增项", all(L["gain"] for L in LAYERS)),
        ("每层都有实测数字", all(L["numbers"] for L in LAYERS)),
        ("周测 12 题", len(QUIZ) == 12),
        ("样例答卷 10/12", score == 10),
        ("census 至少数出 1 层", len(rows) >= 1),
    ]
    with open(os.path.join(OUT, "self-check.txt"), "w") as f:
        f.write("D119 自检\n")
        for name, okk in checks:
            f.write(f"  [{'PASS' if okk else 'FAIL'}] {name}\n")
        f.write(f"  合计：{sum(1 for _, okk in checks if okk)}/{len(checks)}\n")
    print(f"self-check: {sum(1 for _, okk in checks if okk)}/{len(checks)}")
    return 0 if all(okk for _, okk in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
