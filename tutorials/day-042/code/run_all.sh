#!/usr/bin/env bash
# 第 42 天（第 6 周复盘）一键重放：
#   1. 构建新增 mini.mul 后的 mini-opt（verifier 版）
#   2. 正例 4 个 -> 负例 5 个 -> 回归 -> Pass 集成（CSE / count-ops）
#   3. 对照实验：现场生成"trait 版 mini.mul"（SameOperandsAndResultType、
#      无手写 Verifier），用同一批评例看两版的诊断差异
# 环境：Ubuntu 20.04、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29/37/38/39/40/41 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录 /tmp/day042/build、/tmp/day042-trait/
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day042/build
MINI_SRC="$HERE/mini"
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

run_probe() {  # run_probe <mini-opt> <file>：跑一个探针，打印首条 error（若有）和真实 rc
  local opt=$1 f=$2 out rc
  out=$("$opt" "$f" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then
    echo "rc=0 (通过)"
  else
    echo "$out" | grep -m1 "error:"
    echo "rc=$rc"
  fi
}

banner "0/7 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1

banner "1/7 构建：新增 mini.mul（verifier 版）的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/7 正例：2x2*2x2 / 秩0 / ?x3*2x3->2x3 / 目标图（各应 rc=0）"
for f in mul_ok.mlir mul_scalar_ok.mlir mul_dynamic_refine.mlir target_graph_mul.mlir; do
  echo "--- $f ---"
  run_probe "$MINI_OPT" "$HERE/$f"
done

banner "3/7 负例：mismatch / 广播x2 / 动态mismatch / 结果侧（各应 rc=1）"
for f in mul_mismatch.mlir mul_broadcast_scale.mlir mul_rank_broadcast.mlir mul_dynamic_bad.mlir mul_bad_result.mlir; do
  echo "--- $f ---"
  run_probe "$MINI_OPT" "$HERE/$f"
done

banner "4/7 回归：Day 41 目标图 MatMul->Add->Relu 必须原样通过（应 rc=0）"
echo "--- pipeline_regression.mlir ---"
run_probe "$MINI_OPT" "$HERE/pipeline_regression.mlir"

banner "5/7 Pass 集成：-cse 合并重复的 mini.mul；-mini-count-ops 数出新算子"
echo "--- cse_dup_mul.mlir 原样（mini.mul 出现 2 行）---"
"$MINI_OPT" "$HERE/cse_dup_mul.mlir" | grep -c "mini.mul"
echo "--- cse_dup_mul.mlir -cse（%p2 被合并，只剩 1 行）---"
"$MINI_OPT" -cse "$HERE/cse_dup_mul.mlir" | grep -c "mini.mul"
echo "--- target_graph_mul.mlir -mini-count-ops（remark 应含 mini.mul=1）---"
"$MINI_OPT" -mini-count-ops "$HERE/target_graph_mul.mlir" 2>&1 | grep "ops in @"
echo "--- cse_dup_mul.mlir -cse -mini-count-ops（CSE 后再数：mini.mul=1）---"
"$MINI_OPT" -cse -mini-count-ops "$HERE/cse_dup_mul.mlir" 2>&1 | grep "ops in @"

banner "6/7 对照实验（上）：现场生成 trait 版 mini.mul"
TRAIT_SRC=/tmp/day042-trait-src
TRAIT_BUILD=/tmp/day042-trait/build
rm -rf "$TRAIT_SRC" && mkdir -p "$TRAIT_SRC"
cp -r "$MINI_SRC" "$TRAIT_SRC/mini"
python3 - "$TRAIT_SRC/mini" <<'PY'
import re, sys, pathlib
root = pathlib.Path(sys.argv[1])

# 1) MiniOps.td：mul 挂 SameOperandsAndResultType、关掉 hasVerifier、
#    补回该 trait 需要的 include（Day 38 踩过、Day 40 摘掉的）。
td = root / "include/mini/MiniOps.td"
text = td.read_text()
text = text.replace(
    'include "mlir/Interfaces/SideEffectInterfaces.td"',
    'include "mlir/Interfaces/SideEffectInterfaces.td"\n'
    'include "mlir/Interfaces/InferTypeOpInterface.td"')
m = re.search(r'def Mini_MulOp.*?\n\}\n', text, re.S)
block = m.group(0)
block = block.replace('Mini_Op<"mul", [Pure]>',
                       'Mini_Op<"mul", [Pure, SameOperandsAndResultType]>')
block = block.replace('    let hasVerifier = 1;\n\n', '')
td.write_text(text[:m.start()] + block + text[m.end():])

# 2) Ops.h：生成代码会引用 InferTypeOpInterface（Day 38 的坑）。
ops_h = root / "include/mini/Ops.h"
h = ops_h.read_text()
h = h.replace('#include "mlir/IR/Builders.h"',
              '#include "mlir/IR/Builders.h"\n'
              '#include "mlir/Interfaces/InferTypeOpInterface.h"')
ops_h.write_text(h)

# 3) trait 版没有 verify() 声明，MulVerifier.cpp 不能再编译（否则
#    "定义了未声明的成员函数"，编译直接报错）。
cm = root / "lib/CMakeLists.txt"
c = cm.read_text().replace("  MulVerifier.cpp\n", "")
cm.write_text(c)
(root / "lib/MulVerifier.cpp").unlink()
print("trait 版源码就绪：mul 带 SameOperandsAndResultType，无手写 Verifier")
PY
cmake -G Ninja -B "$TRAIT_BUILD" -S "$TRAIT_SRC/mini" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir >/dev/null
cmake --build "$TRAIT_BUILD" >/dev/null
TRAIT_OPT="$TRAIT_BUILD/bin/mini-opt"

banner "7/7 对照实验（下）：同一批探针，trait 版 vs verifier 版"
for f in mul_dynamic_refine.mlir mul_broadcast_scale.mlir mul_ok.mlir; do
  echo "=== $f ==="
  echo "--- trait 版（SameOperandsAndResultType）---"
  run_probe "$TRAIT_OPT" "$HERE/$f"
  echo "--- verifier 版（手写 verify()）---"
  run_probe "$MINI_OPT" "$HERE/$f"
done
