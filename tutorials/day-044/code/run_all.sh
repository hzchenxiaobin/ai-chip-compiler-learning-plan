#!/usr/bin/env bash
# Day 44 一键重放：构建带 -mini-infer-shape 的 mini-opt，跑 8 个探针。
# 构建目录可用环境变量 BUILD_DIR 覆盖（默认 /tmp/day044/build），
# 例如：BUILD_DIR=/tmp/opencode/day044/build ./run_all.sh
set -u
cd "$(dirname "$0")"

BUILD_DIR=${BUILD_DIR:-/tmp/day044/build}
OPT=$BUILD_DIR/bin/mini-opt
mkdir -p "$BUILD_DIR"

echo "== [1/2] 构建 mini-opt（Day 44 源码 ./mini，日志在 $BUILD_DIR/）=="
if [ ! -x "$OPT" ]; then
  cmake -G Ninja -B "$BUILD_DIR" -S mini -DCMAKE_BUILD_TYPE=Release \
        -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > "$BUILD_DIR/configure.log" 2>&1 \
    || { tail -20 "$BUILD_DIR/configure.log"; exit 1; }
  cmake --build "$BUILD_DIR" > "$BUILD_DIR/build.log" 2>&1 \
    || { tail -20 "$BUILD_DIR/build.log"; exit 1; }
fi
echo "mini-opt 就绪: $OPT"

echo
echo "== [2/2] 探针：-mini-infer-shape 到底改了什么 =="

echo "-- 成功组（rc=0）：? 被细化成数字，静态维原样保留 --"
for f in probe_static probe_refine_k probe_batch probe_chain probe_res_spellings; do
  echo "--- $f.mlir"
  if "$OPT" "$f.mlir" -mini-infer-shape > "$BUILD_DIR/out.txt" 2> "$BUILD_DIR/err.txt"; then
    grep mini.matmul "$BUILD_DIR/out.txt" | sed 's/^ *//'
    echo "rc=0"
  else
    cat "$BUILD_DIR/err.txt"
    echo "rc=1  （不该发生！）"
  fi
done

echo
echo "-- 失败组（预期 rc=1）--"
echo "--- probe_conflict.mlir  （推导 R1 与静态承诺冲突，Pass 报错）"
if "$OPT" probe_conflict.mlir -mini-infer-shape > "$BUILD_DIR/out.txt" 2> "$BUILD_DIR/err.txt"; then
  echo "rc=0  （不该发生！）"
else
  grep "error:" "$BUILD_DIR/err.txt"
  echo "rc=1"
fi

echo "--- probe_return_mismatch.mlir  （细化后 func.return 与函数签名不一致）"
if "$OPT" probe_return_mismatch.mlir -mini-infer-shape > "$BUILD_DIR/out.txt" 2> "$BUILD_DIR/err.txt"; then
  echo "rc=0  （不该发生！）"
else
  grep "error:" "$BUILD_DIR/err.txt"
  echo "rc=1"
fi

echo "--- probe_verifier_first.mlir  （静态冲突，Verifier 在解析期就拦下）"
if "$OPT" probe_verifier_first.mlir -mini-infer-shape > "$BUILD_DIR/out.txt" 2> "$BUILD_DIR/err.txt"; then
  echo "rc=0  （不该发生！）"
else
  grep "error:" "$BUILD_DIR/err.txt"
  echo "rc=1"
fi

echo "--- probe_verifier_first.mlir  （对照：不加 Pass，同样的错 —— 与推导无关）"
if "$OPT" probe_verifier_first.mlir > "$BUILD_DIR/out.txt" 2> "$BUILD_DIR/err.txt"; then
  echo "rc=0  （不该发生！）"
else
  grep "error:" "$BUILD_DIR/err.txt"
  echo "rc=1"
fi
