#!/usr/bin/env bash
# run_all.sh —— 第 96 天：一键复现全部实验（真实输出全部落进 outputs/）
#
# 用法：  cd tutorials/day-096/code && bash run_all.sh
# 依赖：  g++（本文环境 GCC 9.4.0, aarch64 Linux）、python3、
#         上游 mlir-opt（默认 /usr/lib/llvm-18/bin/mlir-opt，可用 MLIR_OPT 覆盖）
#
# 产物（outputs/）：
#   build-time.txt        两种优化级别的真实编译耗时（代码膨胀的编译期代价）
#   main-table.txt        主例 5x7x3 tile 2x4x2 U=2 的四内核对照（插桩计数）
#   shape-suite.txt       10 个 shape × unroll-k/unroll-j 正确性（U=4 和 U=5 两轮）
#   err-no-tail.txt       错误复现 1：展开后丢了尾部循环
#   err-overlap.txt       错误复现 2：主循环条件写成 k < khi
#   bench-scalar.txt      标量版（-O2 -fno-tree-vectorize）性能表
#   bench-vector.txt      自动向量化版（-O3）性能表
#   vec-report.txt        GCC -fopt-info-vec 的关键诊断（谁被/没被向量化、为什么）
#   vec-instr-count.txt   objdump 实测：每个内核的机器码指令数与向量指令数
#   ir-check.txt          unrollgen.py 三份 IR 的 mlir-opt 解析验证与大小统计
#   upstream-unroll.txt   上游 affine-loop-unroll 展开前后对照（18x18x18, U=4）

set -euo pipefail
cd "$(dirname "$0")"

MLIR_OPT="${MLIR_OPT:-/usr/lib/llvm-18/bin/mlir-opt}"
OUT=outputs
mkdir -p "$OUT" ir

banner() { printf '\n===== %s =====\n' "$1"; }

# ---------- 0. 编译：同一份源码，两种优化级别 ----------
banner "build"
{
  echo "g++: $(g++ --version | head -1)"
  echo "host: $(uname -m) $(uname -s), nproc=$(nproc)"
  echo
  t0=$(date +%s.%N)
  g++ -O2 -std=c++17 -Wall -Wextra -fno-tree-vectorize -ffp-contract=off \
      -o unroll_matmul unroll_matmul.cpp
  t1=$(date +%s.%N)
  echo "scalar : g++ -O2 -std=c++17 -fno-tree-vectorize -ffp-contract=off"
  echo "  wall=$(echo "$t1 $t0" | awk '{printf "%.2fs", $1-$2}')"
  t0=$(date +%s.%N)
  g++ -O3 -std=c++17 -Wall -Wextra -ffp-contract=off -o unroll_matmul_vec \
      unroll_matmul.cpp
  t1=$(date +%s.%N)
  echo "vector : g++ -O3 -std=c++17 -ffp-contract=off"
  echo "  wall=$(echo "$t1 $t0" | awk '{printf "%.2fs", $1-$2}')"
} | tee "$OUT/build-time.txt"

# ---------- 1. 主例对照表（插桩计数） ----------
banner "main table: 5x7x3 tile 2x4x2 U=2"
./unroll_matmul 5 7 3 2 4 2 2 --all | tee "$OUT/main-table.txt"

# ---------- 2. 非整除/边界 shape 正确性套件（U=4 与 U=5 两轮） ----------
banner "shape suite"
./unroll_matmul --suite 4 | tee "$OUT/shape-suite.txt"

# ---------- 3. 错误复现 ----------
banner "error 1: no-tail"
./unroll_matmul 5 7 3 2 4 2 2 --mode no-tail | tee "$OUT/err-no-tail.txt"
banner "error 2: overlap"
./unroll_matmul 5 7 3 2 4 2 2 --mode overlap | tee "$OUT/err-overlap.txt"

# ---------- 4. 性能：标量版与向量化版（384^3, tile 64, 中位数） ----------
banner "bench scalar (-O2 -fno-tree-vectorize)"
./unroll_matmul --bench 384 64 2 | tee "$OUT/bench-scalar.txt"
banner "bench vector (-O3 auto-vectorize)"
./unroll_matmul_vec --bench 384 64 2 | tee "$OUT/bench-vector.txt"

# ---------- 5. GCC 向量化诊断：谁被/没被向量化，为什么 ----------
banner "vectorization report"
g++ -O3 -std=c++17 -ffp-contract=off -fopt-info-vec-optimized \
    -fopt-info-vec-missed -o /dev/null -c unroll_matmul.cpp 2> "$OUT/vec-report-full.txt"
{
  echo "完整报告在 vec-report-full.txt，下面是关键行（sort -u）："
  grep "unroll_matmul.cpp" "$OUT/vec-report-full.txt" |
      grep -E "strided load|vectorized using|loop nest containing|control flow" |
      sort -u
} | tee "$OUT/vec-report.txt"

# ---------- 6. objdump：每个内核的指令数与向量指令数 ----------
banner "vector instruction count (objdump -O3 build)"
objdump -d unroll_matmul_vec > "$OUT/unroll_matmul_vec.asm"
{
  echo "统计每个 p_* 内核：机器码总指令数 vs 带 NEON 向量寄存器(vN.4s 等)的指令数"
  echo
  python3 - <<'PYEOF'
import re
text = open("outputs/unroll_matmul_vec.asm").read()
blocks = re.split(r"\n(?=[0-9a-f]+ <)", text)
vecpat = re.compile(r"\bv\d+\.\d+[bhsd]\b")
def mnemonic(l):
    parts = [p for p in l.split("\t") if p.strip()]
    if len(parts) >= 3:
        return parts[2].strip()
    return None
for b in blocks:
    nm = re.match(r"[0-9a-f]+ <(.+)>:", b)
    if not nm:
        continue
    name = nm.group(1)
    if not any(k in name for k in ("p_baseline", "p_reorder", "p_unroll")):
        continue
    lines = [l for l in b.splitlines()[1:] if re.match(r"\s+[0-9a-f]+:", l)]
    vec = [l for l in lines if vecpat.search(l)]
    from collections import Counter
    mn = Counter(m for m in map(mnemonic, vec) if m)
    print(f"{name}")
    print(f"  total instructions : {len(lines)}")
    print(f"  vector instructions: {len(vec)}  {dict(mn)}")
PYEOF
} | tee "$OUT/vec-instr-count.txt"
rm -f "$OUT/unroll_matmul_vec.asm"

# ---------- 7. IR：展开前后的 scf 方言 IR（mlir-opt 解析验证 + 大小统计） ----------
banner "IR: unrollgen.py + mlir-opt parse check"
python3 unrollgen.py 5 7 3 2 | tee "$OUT/ir-stats.txt"
{
  echo
  for f in ir/matmul_before.mlir ir/matmul_unroll_k2.mlir \
           ir/matmul_unroll_k4_divisible.mlir; do
    if "$MLIR_OPT" "$f" -o /dev/null 2>/dev/null; then
      echo "PARSE OK  $f  ($(wc -c < "$f") bytes)"
    else
      echo "PARSE FAIL  $f"
      exit 1
    fi
  done
} | tee -a "$OUT/ir-check.txt"

# ---------- 8. 上游对照：affine-loop-unroll 展开前后 ----------
banner "upstream: mlir-opt --affine-loop-unroll unroll-factor=4"
"$MLIR_OPT" --affine-loop-unroll="unroll-factor=4" \
    affine_unroll_check.mlir -o "$OUT/affine_after.mlir"
{
  before=affine_unroll_check.mlir
  after="$OUT/affine_after.mlir"
  echo "shape 18x18x18, unroll-factor=4 (18 % 4 = 2，有尾部)"
  echo "before: $(wc -c < "$before") bytes, arith.mulf x$(grep -c 'arith.mulf' "$before")"
  echo "after : $(wc -c < "$after") bytes, arith.mulf x$(grep -c 'arith.mulf' "$after")"
  echo "展开后 k 循环被拆成（节选）："
  grep -E "affine.for %arg[0-9]+ = (0|16) to (16|18)" "$after" |
      sed 's/^ *//' | head -4
} | tee "$OUT/upstream-unroll.txt"

# ---------- 9. 汇总 ----------
banner "summary"
{
  echo "main table  : 见 main-table.txt"
  echo "suite       : $(grep -o '[0-9]*/[0-9]* 通过' "$OUT/shape-suite.txt" | tail -1)（U=4+U=5 两轮）"
  echo "bench       : bench-scalar.txt / bench-vector.txt（中位数，预热 5 次）"
  echo "IR parse    : 3/3 OK（matmul_before / unroll_k2 / unroll_k4_divisible）"
  echo "upstream    : affine-loop-unroll 1121B/1mulf -> 2283B/5mulf"
} | tee "$OUT/summary.txt"

echo
echo "全部完成：outputs/ 下 $(ls "$OUT" | wc -l) 份文件。"
