#!/usr/bin/env bash
# run_all.sh —— 第 69 天一键复跑：主实验 + 验收测试 + 4 个 MLIR 探针
# 在 code/ 目录下执行：bash run_all.sh
set -u
cd "$(dirname "$0")"
mkdir -p outputs

echo "== [1/3] 主实验 combo_lab.py =="
python3 combo_lab.py 2>&1 | tee outputs/combo_lab.txt
r1=${PIPESTATUS[0]}

echo ""
echo "== [2/3] 验收测试 test_combo_lab.py =="
python3 test_combo_lab.py 2>&1 | tee outputs/test_combo_lab.txt
r2=${PIPESTATUS[0]}

echo ""
echo "== [3/3] MLIR 探针（需要 mlir-opt）=="
MLIR="${MLIR_OPT:-$(command -v mlir-opt || echo /usr/lib/llvm-18/bin/mlir-opt)}"
r3=0
if [ -x "$MLIR" ]; then
  echo "-- 探针 1/2：幂等 --"
  "$MLIR" idem_canon.mlir --canonicalize > outputs/idem_canon.1.mlir
  "$MLIR" idem_canon.mlir --canonicalize --canonicalize > outputs/idem_canon.2.mlir
  "$MLIR" idem_cse.mlir --cse > outputs/idem_cse.1.mlir
  "$MLIR" idem_cse.mlir --cse --cse > outputs/idem_cse.2.mlir
  diff -q outputs/idem_canon.1.mlir outputs/idem_canon.2.mlir >/dev/null \
    && echo "canonicalize x2 == x1" || { echo "canonicalize 不幂等"; r3=1; }
  diff -q outputs/idem_cse.1.mlir outputs/idem_cse.2.mlir >/dev/null \
    && echo "cse x2 == x1" || { echo "cse 不幂等"; r3=1; }

  echo "-- 探针 3：顺序敏感（arith）--"
  "$MLIR" order_arith.mlir --canonicalize --cse > outputs/order_arith.A.mlir
  "$MLIR" order_arith.mlir --cse --canonicalize > outputs/order_arith.B.mlir
  "$MLIR" order_arith.mlir --cse --canonicalize --cse > outputs/order_arith.C.mlir
  echo "canon->cse        addf = $(grep -c 'arith.addf' outputs/order_arith.A.mlir)"
  echo "cse->canon        addf = $(grep -c 'arith.addf' outputs/order_arith.B.mlir)"
  echo "cse->canon->cse   addf = $(grep -c 'arith.addf' outputs/order_arith.C.mlir)"

  echo "-- 探针 4：Cast 消除解锁 CSE --"
  "$MLIR" order_cast.mlir --canonicalize > outputs/order_cast.canon.mlir
  "$MLIR" order_cast.mlir --canonicalize --cse > outputs/order_cast.A.mlir
  "$MLIR" order_cast.mlir --cse --canonicalize > outputs/order_cast.B.mlir
  echo "canonicalize 单独：tensor.cast 剩 $(grep -c 'tensor.cast' outputs/order_cast.canon.mlir)"
  echo "canon->cse        generic = $(grep -c 'linalg.generic' outputs/order_cast.A.mlir)"
  echo "cse->canon        generic = $(grep -c 'linalg.generic' outputs/order_cast.B.mlir)"
else
  echo "mlir-opt 不可用，跳过探针"
fi

echo ""
echo "汇总：combo_lab=$r1 test_combo_lab=$r2 mlir=$r3"
[ "$r1" = "0" ] && [ "$r2" = "0" ] && [ "$r3" = "0" ] && echo "ALL PASS" || echo "存在失败"
exit $(( r1 + r2 + r3 > 0 ? 1 : 0 ))
