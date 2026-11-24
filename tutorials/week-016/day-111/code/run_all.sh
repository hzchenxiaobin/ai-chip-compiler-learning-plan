#!/usr/bin/env bash
# D111 一键复现（约 1.5~2 分钟）——第四阶段集成验收的『一条可重复运行的调优命令』：
#   ① 校准（16 根语句单价先落盘 calibration.json——后续全部实验共享同一份缓存，
#      跨文件口径一致；D109/D110 的同款纪律）
#   ② 集成调优 S1~S4（每份 mini.matmul 输入独立跑 S0~S5 六站：
#      前端解析 → Lowering 计划 → 候选空间 → 资源闸门 → 模型预筛 → 编译/验证/实测）
#   ③ 验收（同进程全测对照＋投毒内核＋D108 冠军一致性）
#   ④ 自检（31 项断言）⑤ 环境记录
# 产出：outputs/ 下 13 个文件（4 份调优报告 + acceptance + self-test + env +
#       calibration + tune-results.jsonl + tune-summary.json + 本日志）
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs
rm -f outputs/tune-results.jsonl outputs/tune-summary.json   # 每轮全量复现从头记账

python3 pipeline.py --exp calibrate | tee outputs/calibration.txt
for ir in inputs/matmul-bias-s1-64x64x64.mini \
          inputs/matmul-bias-s2-96x96x96.mini \
          inputs/matmul-bias-s3-90x96x64.mini \
          inputs/matmul-bias-s4-160x160x160.mini; do
    name=$(basename "$ir" .mini)
    python3 pipeline.py --exp tune --ir "$ir" | tee "outputs/${name}.txt"
done
python3 pipeline.py --exp accept    | tee outputs/acceptance.txt
python3 pipeline.py --exp self-test | tee outputs/self-test.txt
python3 pipeline.py --exp env       | tee outputs/env.txt

echo "完成：outputs/ 下 $(ls outputs | wc -l) 个条目（4 份调优报告 + 验收 + 自检 + 缓存与记录）"
