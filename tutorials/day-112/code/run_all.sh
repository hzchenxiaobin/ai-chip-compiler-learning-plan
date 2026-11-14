#!/usr/bin/env bash
# D112 一键复现（约 2 分钟）——第 16 周复盘：性能反例四组实验。
#   ① 校准：窄 regime 16 根单价落盘 calibration.json（D110/D111 同款纪律：
#      后续全部实验共享同一份缓存，同进程口径一致）
#   ② a-narrow   反例一：S1 64³ 的 24 候选同进程全测 vs 模型 → K=1 实测代价
#   ③ b-resolution 分辨率：模型近对差 vs 5 轮交错 A/B vs 相邻进程掷硬币
#   ④ c-regime   第二套单价：宽 regime 校准（行宽 512）→ 表漂移 + 出域重排
#   ⑤ d-wide     出域对照：W1 64×512×64 全测 36 候选，窄/宽两表对账 + 出域闸门
#   ⑥ env        环境记录
# 产出：outputs/ 下 15 个文件（6 份报告 + 2 份校准缓存 + 2 份 JSONL 测量
#       记录 + 4 份机器可读 JSON 摘要 + 环境记录）；想留总日志可
#       `./run_all.sh 2>&1 | tee outputs/run-all-log.txt`。
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

python3 counterexample.py --exp calibrate      | tee outputs/calibration.txt
python3 counterexample.py --exp a-narrow       | tee outputs/a-narrow.txt
python3 counterexample.py --exp b-resolution   | tee outputs/b-resolution.txt
python3 counterexample.py --exp c-regime       | tee outputs/c-regime.txt
python3 counterexample.py --exp d-wide         | tee outputs/d-wide.txt
python3 counterexample.py --exp env            | tee outputs/env.txt

echo "完成：outputs/ 下 $(ls outputs | wc -l) 个条目"
