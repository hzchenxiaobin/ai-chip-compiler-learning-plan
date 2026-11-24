#!/usr/bin/env bash
# 第 107 天一键复现：统一 Benchmark 工具的全套实验（约 40～60 秒）
set -e
cd "$(dirname "$0")"
mkdir -p outputs

echo "==> 1/6 主实验：7 个配置过统一入口（表 + JSONL + 样本 CSV）"
python3 bench.py --exp table --outdir outputs | tee outputs/bench-table.txt

echo ""
echo "==> 2/6 长跑 201 样本：离群值 / 均值 vs 中位数 / 重复次数扫描"
python3 bench.py --exp outliers --outdir outputs | tee outputs/outliers.txt

echo ""
echo "==> 3/6 口径对照：计时窗内 gc 关 vs 开"
python3 bench.py --exp gc --outdir outputs | tee outputs/gc.txt

echo ""
echo "==> 4/6 正确性门套件：54 项逐位检查 + no-tail 内核被拒"
python3 bench.py --exp gate --outdir outputs | tee outputs/correctness.txt

echo ""
echo "==> 5/6 配置 → 源码：统一入口测的不是黑盒"
python3 bench.py --exp show-src --outdir outputs | tee outputs/src-ikj-u4.txt

echo ""
echo "==> 6/6 断言自检"
python3 bench.py --exp self-test | tee outputs/test-all.txt

{
  python3 -c 'import bench; print(bench.env_block())'
} > outputs/env.txt

echo ""
echo "全部完成。记录见 outputs/：bench-table / outliers / gc / correctness /"
echo "src-ikj-u4 / test-all / env / results.jsonl / samples.csv / gate-records.jsonl"
