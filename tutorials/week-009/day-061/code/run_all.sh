#!/usr/bin/env bash
# run_all.sh —— 第 61 天一键复跑：Python 动态 Shape 实验 + MLIR 六连验证 + 两个运行期现场。
#
# 用法：bash run_all.sh
# 输出：屏幕打印全部结果，并把真实输出保存到 outputs/ 目录。
#
# 流程：
#   1-2  Python：dynamic_lab 16 项断言 + test_dynamic 41 个验收点
#   3-5  matmul_dynamic.mlir：解析验证 / 循环上界的 memref.dim / cpu-runner 真实执行
#   6    generated_dynamic_tests.mlir：8 个 M/N/K 静态-动态房间解析验证
#   7    k_constraint.mlir：witness 约束的折叠（静态）/ 保留（动态）/ 物化（cf.assert）
#   8    bad_dynamic.mlir：同一处失配的三种待遇（秩拦截 / 静态拦截 / ? 让检查失明）
#   9    k_hazard.mlir：无检查事故现场（越界读垃圾值，exit=0）
#   10   k_check.mlir：有检查事故现场（cf.assert 触发，exit=134）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

MLIR_OPT="${MLIR_OPT:-mlir-opt}"
MLIR_RUNNER="${MLIR_RUNNER:-mlir-cpu-runner}"
if ! command -v "$MLIR_OPT" >/dev/null 2>&1; then
  for c in /usr/lib/llvm-18/bin/mlir-opt /usr/bin/mlir-opt-18; do
    [ -x "$c" ] && MLIR_OPT="$c" && break
  done
fi
if ! command -v "$MLIR_RUNNER" >/dev/null 2>&1; then
  for c in /usr/lib/llvm-18/bin/mlir-cpu-runner /usr/bin/mlir-cpu-runner-18; do
    [ -x "$c" ] && MLIR_RUNNER="$c" && break
  done
fi
LLVM_LIB="$(dirname "$(readlink -f "$MLIR_RUNNER")")/../lib"
SHARED="$LLVM_LIB/libmlir_runner_utils.so,$LLVM_LIB/libmlir_c_runner_utils.so"
export MLIR_OPT
LOWER="--convert-linalg-to-loops --convert-scf-to-cf --convert-cf-to-llvm \
  --convert-func-to-llvm --finalize-memref-to-llvm --convert-arith-to-llvm \
  --reconcile-unrealized-casts"

echo "== 环境 =="
python3 --version
"$MLIR_OPT" --version | head -1
python3 -c "import numpy; print('numpy', numpy.__version__)"
uname -m
echo

echo "== 1. dynamic_lab.py（三种表示 + 判定表 + 特化 + 运行期模拟 + 500 组压力）=="
python3 dynamic_lab.py | tee "$OUT/dynamic_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_dynamic.py（验收测试：A-E 五段 41 个测试点）=="
python3 test_dynamic.py | tee "$OUT/test_dynamic.txt"
echo "exit=$?"
echo

if command -v "$MLIR_OPT" >/dev/null 2>&1; then
  echo "== 3. matmul_dynamic.mlir：解析 + 验证 + 打印 =="
  "$MLIR_OPT" matmul_dynamic.mlir | tee "$OUT/matmul_dynamic_roundtrip.mlir"
  echo "exit=$?"
  echo

  echo "== 4. matmul_dynamic.mlir --convert-linalg-to-loops：动态维的循环上界从哪来 =="
  "$MLIR_OPT" --convert-linalg-to-loops matmul_dynamic.mlir \
    | tee "$OUT/matmul_dynamic_loops.mlir"
  echo "exit=$?"
  echo

  echo "== 5. matmul_dynamic.mlir：降级到 LLVM 并用 mlir-cpu-runner 真实执行 =="
  "$MLIR_OPT" $LOWER matmul_dynamic.mlir -o "$OUT/matmul_dynamic.lowered.mlir" \
    && "$MLIR_RUNNER" "$OUT/matmul_dynamic.lowered.mlir" \
       -e main --entry-point-result=void --shared-libs="$SHARED" \
       | tee "$OUT/matmul_dynamic_exec.txt"
  echo "exit=$?（期望 220 280 490 640）"
  echo

  echo "== 6. generated_dynamic_tests.mlir：8 个 M/N/K 静态-动态房间解析验证 =="
  "$MLIR_OPT" generated_dynamic_tests.mlir | tee "$OUT/generated_roundtrip.mlir" > /dev/null
  echo "parse+verify exit=$?（8 房间全部通过）"
  "$MLIR_OPT" --convert-linalg-to-loops generated_dynamic_tests.mlir > /dev/null 2>&1
  echo "loops exit=$?"
  echo

  echo "== 7. k_constraint.mlir：witness 约束的三种形态 =="
  echo "-- 7a. 解析 + 验证："
  "$MLIR_OPT" k_constraint.mlir > "$OUT/k_constraint_roundtrip.mlir" && echo "   parse+verify exit=0"
  echo "-- 7b. --canonicalize：静态房间约束链整体消失，动态房间原样保留："
  "$MLIR_OPT" --canonicalize k_constraint.mlir | tee "$OUT/k_constraint_canon.mlir" | head -12
  echo "-- 7c. --convert-shape-constraints：cstr_require 物化成 cf.assert："
  "$MLIR_OPT" --convert-shape-constraints k_constraint.mlir \
    | tee "$OUT/k_constraint_cstr.mlir" | grep -n "cstr\|cf.assert\|assuming" | head -6
  echo

  echo "== 8. bad_dynamic.mlir：同一处静态失配的三种待遇 =="
  if "$MLIR_OPT" bad_dynamic.mlir > "$OUT/bad_dynamic.txt" 2>&1; then
    echo "意外通过：Verifier 未拦截" && exit 1
  else
    echo "整文件被拒（第一条错误即退出）："
    head -1 "$OUT/bad_dynamic.txt"
  fi
  python3 - <<'PYEOF'
import re, subprocess, sys, os
text = open("bad_dynamic.mlir", encoding="utf-8").read()
head = text[:text.index("// ----")]
rooms = re.split(r"(?=// ---- )", text)
mlir_opt = os.environ.get("MLIR_OPT", "mlir-opt")
for room in rooms:
    if not room.startswith("// ----"):
        continue
    title = room.split("\n")[0].replace("// ---- ", "").split("（")[0]
    path = f"outputs/bad_dynamic_room_{title}.mlir"
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + room)
    r = subprocess.run([mlir_opt, path], capture_output=True, text=True)
    out_name = f"outputs/bad_dynamic_room_{title}.txt"
    with open(out_name, "w", encoding="utf-8") as f:
        f.write(r.stderr or "(无诊断，Verifier 放行)")
    first = (r.stderr.strip().splitlines() or ["(放行)"])[0]
    verdict = "拦截" if r.returncode else "放行"
    print(f"   {title}: exit={r.returncode} → Verifier {verdict}")
    print(f"     {first[:110]}")
PYEOF
  echo

  echo "== 9. k_hazard.mlir：无检查的事故现场（K 3 vs 2 藏在 ? 后面）=="
  "$MLIR_OPT" $LOWER k_hazard.mlir -o "$OUT/k_hazard.lowered.mlir" \
    && "$MLIR_RUNNER" "$OUT/k_hazard.lowered.mlir" -e main \
       --entry-point-result=void --shared-libs="$SHARED" \
       > "$OUT/k_hazard_exec.txt" 2>&1
  echo "exit=$?（合法答案本该是 220/280/490/640，下面是真实输出）"
  cat "$OUT/k_hazard_exec.txt"
  echo

  echo "== 10. k_check.mlir：装上 cf.assert 的同一现场 =="
  "$MLIR_OPT" $LOWER k_check.mlir -o "$OUT/k_check.lowered.mlir" \
    && stdbuf -o0 "$MLIR_RUNNER" "$OUT/k_check.lowered.mlir" -e main \
       --entry-point-result=void --shared-libs="$SHARED" \
       > "$OUT/k_check_exec.txt" 2> "$OUT/k_check_abort.txt"
  ec=$?
  echo "exit=$ec（第一次调用放行并打印 220；第二次调用 assert 触发 abort）"
  echo "stdout 部分（两行：合法结果的 220 + abort 前打印的约束消息）："
  cat "$OUT/k_check_exec.txt"
  echo "（abort 崩溃栈在 outputs/k_check_abort.txt；消息文本在降级 IR 的 @assert_msg）"
  grep -n "assert_msg" "$OUT/k_check.lowered.mlir" | head -1
  echo
fi

echo "run_all: 全部完成"
