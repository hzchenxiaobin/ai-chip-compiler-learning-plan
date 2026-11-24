#!/usr/bin/env bash
# run_all.sh —— 第 70 天一键复跑：主实验 + 验收测试 + MLIR 探针 + 本周全部测试
# 在 code/ 目录下执行：bash run_all.sh
set -u
cd "$(dirname "$0")"
mkdir -p outputs

echo "== [1/4] 主实验 counterexample_lab.py =="
python3 counterexample_lab.py 2>&1 | tee outputs/counterexample_lab.txt
r1=${PIPESTATUS[0]}

echo ""
echo "== [2/4] 验收测试 test_counterexamples.py =="
python3 test_counterexamples.py 2>&1 | tee outputs/test_counterexamples.txt
r2=${PIPESTATUS[0]}

echo ""
echo "== [3/4] MLIR 探针（需要 mlir-opt）=="
MLIR="${MLIR_OPT:-$(command -v mlir-opt || echo /usr/lib/llvm-18/bin/mlir-opt)}"
r3=0
if [ -x "$MLIR" ]; then
  echo "-- 探针 1：Cast 往返（精度语义）--"
  "$MLIR" probe_cast_roundtrip.mlir --canonicalize > outputs/probe_cast.canon.mlir
  echo "truncf+extf 剩 $(( $(grep -c 'arith.truncf' outputs/probe_cast.canon.mlir) + $(grep -c 'arith.extf' outputs/probe_cast.canon.mlir) )) 个（不被折叠）"

  echo "-- 探针 2：Reshape 链（形状语义）--"
  "$MLIR" probe_reshape_chain.mlir --canonicalize > outputs/probe_reshape.canon.mlir
  echo "tensor.reshape 剩 $(grep -c 'tensor.reshape' outputs/probe_reshape.canon.mlir) 个（stock 不合并）"

  echo "-- 探针 3：memref.copy（别名语义）--"
  "$MLIR" probe_copy_identity.mlir --canonicalize > outputs/probe_copy.canon.mlir
  "$MLIR" probe_copy_identity.mlir --cse > outputs/probe_copy.cse.mlir
  echo "copy 剩 $(grep -c 'memref.copy' outputs/probe_copy.canon.mlir) / $(grep -c 'memref.copy' outputs/probe_copy.cse.mlir) 个（都不删）"

  echo "-- 探针 4：副作用 vs 死代码 --"
  "$MLIR" probe_side_effect.mlir --cse > outputs/probe_side.cse.mlir
  "$MLIR" probe_side_effect.mlir --canonicalize > outputs/probe_side.canon.mlir
  echo "store 剩 $(grep -c 'memref.store' outputs/probe_side.cse.mlir) / $(grep -c 'memref.store' outputs/probe_side.canon.mlir)，死 addf 剩 $(grep -c 'arith.addf' outputs/probe_side.cse.mlir) / $(grep -c 'arith.addf' outputs/probe_side.canon.mlir)"

  echo "-- 探针 5：恒等排列物理转置（布局语义）--"
  "$MLIR" probe_identity_transpose.mlir --canonicalize > outputs/probe_idt.canon.mlir
  "$MLIR" probe_identity_transpose.mlir --cse > outputs/probe_idt.cse.mlir
  echo "linalg.transpose 剩 $(grep -c 'linalg.transpose' outputs/probe_idt.canon.mlir) / $(grep -c 'linalg.transpose' outputs/probe_idt.cse.mlir) 个（都不删）"
else
  echo "mlir-opt 不可用，跳过探针"
fi

echo ""
echo "== [4/4] 本周全部测试（Day 64–70 共 7 套）=="
bash run_week_tests.sh 2>&1 | tee outputs/week_tests_run.txt
r4=${PIPESTATUS[0]}

echo ""
echo "汇总：lab=$r1 test=$r2 mlir=$r3 week=$r4"
[ "$r1" = "0" ] && [ "$r2" = "0" ] && [ "$r3" = "0" ] && [ "$r4" = "0" ] \
  && echo "ALL PASS" || echo "存在失败"
exit $(( r1 + r2 + r3 + r4 > 0 ? 1 : 0 ))
