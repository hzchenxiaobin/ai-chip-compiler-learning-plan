#!/usr/bin/env bash
# D108 一键复现（约 2~3 分钟）：
#   ① 自检（33 项断言，含微型端到端调优）
#   ② 断点续跑演示 part1：--limit 28（正好 S1 一个 shape 的 24 筛选 + 4 决赛）
#      预算到站收工；切断点选在 shape 边界——D107 实测跨进程漂移 ~8.6%，
#      同一张排名表不许混两个进程的读数
#   ③ 断点续跑演示 part2：同一目录同一命令，跳过已完成 28 条继续到终点
#   ④ 结果表（每 shape 排名 + 被拒台账）⑤ 搜索成本账 ⑥ 稳定性重算 ⑦ 环境记录
# 注意：②③ 共同构成完整的一轮搜索（part2 不重测 part1 测过的候选）。
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

python3 tune.py --exp self-test       | tee outputs/self-test.txt

echo "== 断点续跑演示 part1：--limit 28（预算到站收工） =="
python3 tune.py --exp tune --limit 28 | tee outputs/resume-part1.txt

echo "== 断点续跑演示 part2：同一命令继续（跳过已完成） =="
python3 tune.py --exp tune            | tee outputs/tune-run.txt

python3 tune.py --exp table           | tee outputs/tune-table.txt
python3 tune.py --exp cost            | tee outputs/search-cost.txt
python3 tune.py --exp stability       | tee outputs/stability.txt
python3 tune.py --exp env             | tee outputs/env.txt

echo "== 好奇心实验：绕过门直接给投毒内核计时（不进任何排名表） =="
python3 - <<'EOF' | tee outputs/poison-timing.txt
from statistics import median
from kernel_gen import KernelConfig, make_kernel, make_inputs, alloc_c
import time

M, N, K = 90, 96, 64
print("对照对象：S3 = 90×96×64，jki 顺序（内层 i，M=90 不被 4 整除 → 尾部 2 圈）")
for desc, cfg in (("单 tile 90×96×64 jki U=4", KernelConfig(90, 96, 64, "jki", 4)),
                 ("32³ tile    jki U=4", KernelConfig(32, 32, 32, "jki", 4))):
    good = make_kernel(cfg)
    bad = make_kernel(cfg, drop_tail=True)
    A, B, bias = make_inputs(M, N, K, 42)
    C0 = alloc_c(bias, M, N)
    print(f"\n {desc}")
    for name, fn in (("  正确版（有尾部循环）", good), ("  no-tail（尾部循环不生成）", bad)):
        for _ in range(3):
            C = [r[:] for r in C0]; fn(A, B, C, M, N, K)
        xs = []
        for _ in range(21):
            C = [r[:] for r in C0]
            t0 = time.perf_counter(); fn(A, B, C, M, N, K)
            xs.append((time.perf_counter() - t0) * 1000)
        print(f" {name}: 21 样本中位数 {median(xs):7.2f} ms")
EOF

echo "完成：outputs/ 下 10 份真实运行记录"
