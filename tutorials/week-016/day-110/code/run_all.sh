#!/usr/bin/env bash
# D110 一键复现（约 1~2 分钟）：
#   ① 校准（16 根语句单价，先跑并落盘 calibration.json——本次复现内所有
#      报告读同一份缓存，跨文件口径一致；D109 probes.json 的同款纪律）
#   ② 自检（47 项断言，与后续报告共享同一份校准缓存）
#   ③ 真值校验（39 配置 × 17 项计数 vs settrace 逐行计数）
#   ④ 模型排序表（96 个候选的预测 vs D108 实测）
#   ⑤ 精度报告（ρ / recall@K / 误差分布 / 错误排序现场）
#   ⑥ 模型引导搜索（真跑：排序 → 只实测 top-5 → 决赛；落盘 guided-results.jsonl）
#   ⑦ TOP_K 敏感性（名额 1~5 扫描：K=1 完全相信模型的直接代价）
#   ⑧ 漂移 A/B（ikj vs kij 同进程交错复核：冠军分歧是误差还是环境）
#   ⑨ 外推账（D106 全空间 12,970 候选，明确标注估算）⑩ 环境记录
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

python3 cost_model.py --exp calibrate  | tee outputs/calibration.txt
python3 cost_model.py --exp self-test  | tee outputs/self-test.txt
python3 cost_model.py --exp verify     | tee outputs/verify.txt
python3 cost_model.py --exp rank       | tee outputs/model-table.txt
python3 cost_model.py --exp accuracy   | tee outputs/accuracy.txt
python3 tune_guided.py --exp guided    | tee outputs/guided-search.txt
python3 tune_guided.py --exp topk      | tee outputs/topk-sensitivity.txt
python3 tune_guided.py --exp drift     | tee outputs/drift-a-b.txt
python3 tune_guided.py --exp extrap    | tee outputs/extrapolation.txt
python3 cost_model.py --exp env        | tee outputs/env.txt

echo "完成：outputs/ 下 13 个文件（10 份实验记录 + calibration.json + guided-results.jsonl + 本日志）"
