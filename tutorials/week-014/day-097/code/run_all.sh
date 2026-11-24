#!/usr/bin/env bash
# run_all.sh —— 第 97 天一键复现：正确性套件 → 性能表(512) → 冷启动对照 → 第二次运行(漂移)
#              → 尾部 shape(516) → 向量指令计数 → 环境记录
# 全部真实输出落在 outputs/，耗时约 40 秒。
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

BUILD='g++ -std=c++17 -O3 -ffp-contract=off'

echo "== [1/8] 编译 =="
g++ -std=c++17 -O3 -ffp-contract=off -DBUILD_FLAGS="\"$BUILD\"" -o config_bench config_bench.cpp
echo "编译完成: $BUILD"

echo "== [2/8] 实验环境记录 -> outputs/env.txt =="
{
  date
  uname -a
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread\(s\) per core|Core\(s\) per socket|Socket\(s\)|L1d cache|L1i cache|L2 cache|L3 cache|CPU max MHz|CPU min MHz)'
  echo "g++: $(g++ --version | head -1)"
  echo "build: $BUILD"
  ./config_bench env
  echo "测量协议: warmup=3(丢弃) + repeats=21(计时取中位数), 未绑核"
} > outputs/env.txt
cat outputs/env.txt

echo "== [3/8] 正确性套件(5 shape x 6 配置) -> outputs/correctness.txt =="
./config_bench suite | tee outputs/correctness.txt

echo "== [4/8] 性能实验 shape=512 -> outputs/perf-512.txt + samples-512.csv =="
./config_bench bench 512 512 512 3 21 | tee outputs/perf-512.txt | grep '^CSV,' > outputs/samples-512.csv
wc -l outputs/samples-512.csv

echo "== [5/8] 冷启动对照(每个配置一个新进程跑 1 次) -> outputs/cold.txt =="
: > outputs/cold.txt
for i in 0 1 2 3 4 5; do
  ./config_bench cold "$i" 512 512 512 >> outputs/cold.txt
done
cat outputs/cold.txt

echo "== [6/8] 同一实验再跑一遍(看 run-to-run 漂移) -> outputs/perf-512-run2.txt =="
./config_bench bench 512 512 512 3 21 | tee outputs/perf-512-run2.txt | grep '^CSV,' > outputs/samples-512-run2.csv
{
  echo "同一实验两次独立运行的中位数对照（GFLOPS）："
  paste -d' ' <(grep '^MED' outputs/perf-512.txt) <(grep '^MED' outputs/perf-512-run2.txt) |
  awk -F'[, ]+' '{d=($3-$6)/$3*100; printf "%-9s run1=%.3f  run2=%.3f  drift=%+.2f%%\n", $2, $3, $6, d}'
} > outputs/repeatability.txt
cat outputs/repeatability.txt

echo "== [7/8] 尾部 shape=516(D98 预告) -> outputs/perf-516.txt =="
./config_bench bench 516 516 516 3 21 | tee outputs/perf-516.txt | grep '^CSV,' > outputs/samples-516.csv

echo "== [8/8] 机器码向量指令计数 -> outputs/vec-instr.txt =="
objdump -dC config_bench | awk '
  /^[0-9a-f]+ <.*>:/ { sym = $0; sub(/^[0-9a-f]+ /, "", sym); sub(/:$/, "", sym) }
  sym ~ /tiled_matmul|naive_ref/ && ($0 ~ /v[0-9]+\.4s/ || $0 ~ /(ldr|str)[ \t]+q[0-9]+/) { cnt[sym]++ }
  END {
    for (s in cnt) printf "%5d 条 128-bit 向量指令(.4s 算术 + ldr/str q)  %s\n", cnt[s], s
    print "    （未列出的 tiled_matmul<0>/naive_ref 含 0 条向量指令——纯标量）"
  }
' | sort > outputs/vec-instr.txt
cat outputs/vec-instr.txt

echo "== 全部完成：outputs/ 下共 $(ls outputs | wc -l) 份记录 =="
