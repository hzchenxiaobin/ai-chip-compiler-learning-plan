#!/usr/bin/env bash
# D109 一键复现（约 10 秒）：
#   ① 自检（公式/口径/血统/屋顶合理性/判定余量，探针现场实测）
#   ② 探针落盘 outputs/probes.json（屋顶读数只测一次，三个报告共享——
#     同一次复现内口径一致，避免 D107 实测过的跨进程漂移混进对账）
#   ③ 性能分析表（主交付物①：有效 GFLOPS / AI / 距屋顶倍数，per-shape）
#   ④ Roofline 报告（主交付物②：机器模型 / 屋脊点 / 内核点定位 / 解释税）
#   ⑤ 对照 A：mean vs median 换口径重算 GFLOPS（零重跑，读 D108 记录）
#   ⑥ 环境与口径记录
# 输入：inputs/results-d108.jsonl（D108 outputs/results.jsonl 的逐字节副本，
#       sha256=e8c8da…037f 在 analyze.py 里钉死，血统不对就拒绝分析）
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

python3 analyze.py --exp self-test       | tee outputs/self-test.txt
python3 analyze.py --exp probes          | tee outputs/probes.txt
python3 analyze.py --exp table           | tee outputs/perf-table.txt
python3 analyze.py --exp roofline        | tee outputs/roofline.txt
python3 analyze.py --exp mean-vs-median  | tee outputs/mean-vs-median.txt
python3 analyze.py --exp env             | tee outputs/env.txt

echo "完成：outputs/ 下 7 份文件（5 份运行记录 + self-test + probes.json 屋顶缓存）"
