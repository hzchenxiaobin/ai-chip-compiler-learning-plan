#!/usr/bin/env bash
# Day 43 一键重放：规则表测试 + mini-opt 现状探针。
# mini-opt 用 Day 42 的源码构建（本教程不改 mini 工程，只做设计）。
set -u
cd "$(dirname "$0")"
mkdir -p /tmp/day043

MINI_SRC=../../day-042/code/mini
BUILD=/tmp/day043/build
OPT=$BUILD/bin/mini-opt

echo "== [1/3] 规则表测试（可执行版，15 行）=="
python3 test_matmul_infer.py
echo "rc=$?"

echo
echo "== [2/3] 构建 mini-opt（Day 42 源码，构建日志 /tmp/day043/build.log）=="
if [ ! -x "$OPT" ]; then
  cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
        -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > /tmp/day043/build.log 2>&1 \
    || { tail -20 /tmp/day043/build.log; exit 1; }
  cmake --build "$BUILD" >> /tmp/day043/build.log 2>&1 \
    || { tail -20 /tmp/day043/build.log; exit 1; }
fi
echo "mini-opt 就绪: $OPT"

echo
echo "== [3/3] 现状探针：今天的结果类型全靠人手写 =="
for f in probe_static_ok probe_dynamic_m probe_dynamic_refine \
         probe_result_all_dynamic probe_batch_ok probe_k_mismatch; do
  echo "--- $f.mlir"
  if "$OPT" "$f.mlir" > /tmp/day043/out.txt 2> /tmp/day043/err.txt; then
    grep mini.matmul /tmp/day043/out.txt | sed 's/^ *//'
    echo "rc=0"
  else
    cat /tmp/day043/err.txt
    echo "rc=1"
  fi
done
