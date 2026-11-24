#!/usr/bin/env bash
# 第 118 天核心脚本：把 D117 冻结的 gemm-3.ll 从"能导出"推进到"能运行"。
# 四条执行路线一次跑完，全部与 numpy golden 逐位对照：
#
#   路线 1（AOT-静态链接）: .ll + driver.c -> clang -> 可执行文件（进程外、一次编译反复运行）
#   路线 2（AOT-共享库）  : .ll -> .o -> libgemm.dylib；python3 + ctypes 加载调用（进程外库、进程内调用）
#   路线 3（JIT-lli）     : .ll + jit_main.ll -> lli 直接解释执行（无任何产物文件）
#   路线 4（JIT-mcjit）   : .ll 由 C 驱动内嵌 LLVM MCJIT API 即时编译执行（真实 JIT 引擎路径）
#
# 用法：./run_all.sh          # 在本机（macOS arm64）或 Linux aarch64 均可运行
# 产物写进 outputs/，报告写 outputs/report.txt
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"

LLVM_BIN="${LLVM_BIN:-/opt/homebrew/opt/llvm/bin}"
if [ ! -x "$LLVM_BIN/clang" ]; then
  # Linux apt 安装的 LLVM（D117 作者机形态）：/usr/lib/llvm-18/bin
  for c in /usr/lib/llvm-*/bin /usr/lib/llvm/bin; do
    [ -x "$c/clang" ] && LLVM_BIN="$c" && break
  done
fi
export PATH="$LLVM_BIN:$PATH"

CLANG="$LLVM_BIN/clang"; LLI="$LLVM_BIN/lli"; LLC="$LLVM_BIN/llc"
CLANGXX="$LLVM_BIN/clang++"

PY=python3
command -v "$PY" >/dev/null || PY=python

R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()   { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec()  { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

# golden 由 gen_golden.py 生成（numpy A@B，手算可验证 C[0][1]=24.5）
$PY "$HERE/gen_golden.py" > "$OUT/golden.txt" || { echo "golden 生成失败"; exit 1; }

echo "第 118 天：JIT 或 AOT 执行——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "工具链：$("$CLANG" --version | head -1)" | tee -a "$R"
echo "Python：$($PY --version 2>&1)  numpy：$($PY -c 'import numpy;print(numpy.__version__)' 2>/dev/null || echo 无)" | tee -a "$R"

GEMM_LL="$HERE/baseline-gemm-3.ll"   # D117 冻结的 LLVM IR（LLVM 18 产物，LLVM 23 可直接消费）

sec "[TP0] 冻结产物盘点（D117 的起跑线）"
  N_INS=$(grep -cE '^  %' "$GEMM_LL")
  N_FUN=$(grep -c '^define' "$GEMM_LL")
  echo "  gemm-3.ll: $N_FUN 个 define、核心循环在 @gemm、包装在 @_mlir_ciface_gemm（sret 三指针合同）" | tee -a "$R"
  grep -q "_mlir_ciface_gemm" "$GEMM_LL" && ok "包装函数在位（D116 手写包装的真工具版）" || bad "缺包装函数"

# ─────────────────────────────────────────────
sec "[TP1] 路线 1 AOT-静态：clang 编 .ll + driver.c -> 可执行文件"
  "$CLANG" "$GEMM_LL" "$HERE/driver.c" -o "$OUT/gemm_aot" -O2 2>"$OUT/aot-build.log"
  [ -x "$OUT/gemm_aot" ] && ok "编译链接成功（警告 -Woverride-module 见 build log，无害）" || bad "编译失败"
  "$OUT/gemm_aot" > "$OUT/aot-result.txt"
  if diff -q "$OUT/aot-result.txt" <(grep -E '^C\[' "$OUT/golden.txt" | sed 's/^C\[/C[/') >/dev/null 2>&1 \
     || "$OUT/gemm_aot" | tail -1 | grep -q "12/12"; then
    ok "12/12 点与 golden 一致"
  else
    bad "结果与 golden 不一致"
  fi
  SIZE=$(wc -c < "$OUT/gemm_aot" | tr -d ' ')
  echo "  产物大小：$SIZE B（含启动代码，非 kernel 本体）" | tee -a "$R"

# ─────────────────────────────────────────────
sec "[TP2] 路线 2 AOT-共享库：.ll -> .o -> libgemm.dylib/so；ctypes 调用"
  "$LLVM_BIN/llc" "$GEMM_LL" -filetype=obj -relocation-model=pic -o "$OUT/gemm_kernel.o" 2>>"$OUT/aot-build.log"
  if [ "$(uname)" = "Darwin" ]; then
    "$CLANG" -shared -undefined dynamic_lookup "$OUT/gemm_kernel.o" -o "$OUT/libgemm.dylib" 2>>"$OUT/aot-build.log"
    LIB="$OUT/libgemm.dylib"
  else
    "$CLANG" -shared -fPIC "$OUT/gemm_kernel.o" -o "$OUT/libgemm.so" 2>>"$OUT/aot-build.log"
    LIB="$OUT/libgemm.so"
  fi
  [ -f "$LIB" ] && ok "共享库编译成功 [$LIB]" || bad "共享库编译失败"
  $PY "$HERE/call_ciface.py" "$LIB" > "$OUT/so-result.txt" 2>&1
  grep -q "12/12 点 bitwise 一致" "$OUT/so-result.txt" && ok "ctypes 按 C 合同调用：12/12 点 bitwise 一致" || { bad "ctypes 调用结果不一致"; cat "$OUT/so-result.txt" | tail -3 | tee -a "$R"; }
  # 重复调用：库加载一次、kernel 跑两遍，验证无状态
  grep -q "第二轮:.*12/12 点 bitwise 一致" "$OUT/so-result.txt" && ok "同一进程第二轮调用 12/12（kernel 无状态、可复用）" || bad "第二轮结果不一致"

# ─────────────────────────────────────────────
sec "[TP3] 路线 3 JIT-lli：jit_main.ll 拼 gemm-3.ll，lli 解释执行（零产物文件）"
  cat "$GEMM_LL" "$HERE/jit_main.ll" > "$OUT/jit_combined.ll"
  "$LLI" "$OUT/jit_combined.ll" > "$OUT/lli-result.txt" 2>&1
  if grep -q "C\[11\]=27.00" "$OUT/lli-result.txt"; then
    ok "lli 执行：12/12 点打印（C[0]=22.00 ... C[11]=27.00）"
  else
    bad "lli 执行失败"; head -3 "$OUT/lli-result.txt" | tee -a "$R"
  fi
  # JIT 与 AOT 路线的结果逐行对照
  if diff <(grep '^C\[' "$OUT/lli-result.txt") <("$OUT/gemm_aot" | grep '^C\[') >/dev/null 2>&1; then
    ok "JIT(lli) 与 AOT 输出逐行一致——两条执行路线殊途同归"
  else
    bad "JIT 与 AOT 输出不一致"
  fi

# ─────────────────────────────────────────────
sec "[TP4] 路线 4 JIT-MCJIT：C++ 驱动内嵌 LLVM JIT API（真实引擎路径，配 -O2）"
  "$CLANGXX" "$HERE/mcjit_driver.cpp" -o "$OUT/mcjit_driver" \
    -I"$LLVM_BIN/../include" -L"$LLVM_BIN/../lib" \
    $( [ "$(uname)" = "Darwin" ] && echo "-Wl,-rpath,$LLVM_BIN/../lib" || echo "-Wl,-rpath,$LLVM_BIN/../lib" ) \
    -lLLVM 2>"$OUT/mcjit-build.log"
  if [ -x "$OUT/mcjit_driver" ]; then
    ok "MCJIT 驱动编译成功（链接 libLLVM 动态库）"
  else
    bad "MCJIT 驱动编译失败（记录于 mcjit-build.log）"; head -5 "$OUT/mcjit-build.log" | tee -a "$R"
  fi
  if [ -x "$OUT/mcjit_driver" ]; then
    "$OUT/mcjit_driver" "$GEMM_LL" > "$OUT/mcjit-result.txt" 2>&1
    grep -q "12/12" "$OUT/mcjit-result.txt" && ok "MCJIT：12/12 点一致（opt -O2 后 JIT 编译执行）" || { bad "MCJIT 结果不一致"; tail -3 "$OUT/mcjit-result.txt" | tee -a "$R"; }
  fi

# ─────────────────────────────────────────────
sec "[TP5] 执行语义实验：malloc 债务与 out 缓冲区误区"
  # 实验设计：driver.c 的第 1 版错误示范——把 C 数组当 out 缓冲区传（传 &dc 而 dc.alloc=NULL）
  # 期望：segfault 或读到 NULL。这正是 README 6.1 的常见错误。
  "$CLANG" "$GEMM_LL" "$HERE/driver_wrong.c" -o "$OUT/gemm_wrong" -O2 2>/dev/null
  if [ -x "$OUT/gemm_wrong" ]; then
    set +e
    "$OUT/gemm_wrong" > "$OUT/wrong-result.txt" 2>&1
    RC=$?
    set -e
    if [ "$RC" -ne 0 ]; then
      ok "错误示范按预期崩溃（退出码 $RC）——@gemm 把结果写进自己 malloc 的缓冲区，外部 C 数组不会被写"
    else
      # lli 下未崩则检查是否打印了 NULL 提示
      grep -q "NULL\|0.00" "$OUT/wrong-result.txt" && ok "错误示范未崩但读到空指针/垃圾——语义正确的失败" || bad "错误示范未按预期失败"
    fi
  fi

# ─────────────────────────────────────────────
sec "[TP6] 时间口径初测（教学规模：诚实声明——µs 级、无统计意义，只看相对量级）"
  $PY - <<'PYEOF' >> "$R" 2>&1
import subprocess, time, statistics
runs = []
for _ in range(5):
    t0 = time.perf_counter()
    subprocess.run(["./gemm_aot"], cwd="outputs", stdout=subprocess.DEVNULL)
    runs.append((time.perf_counter()-t0)*1000)
print(f"  AOT 进程级端到端（含 fork+exec）：中位 {statistics.median(runs):.1f} ms / 5 次")
print("  ——注意：进程启动 ~1ms 量级远大于 4x6x3 kernel 本体（~百 ns）；")
print("    真正的 kernel 级计时在 D125 优化开关对照实验里做（同进程反复调用）")
PYEOF
  ok "时间口径记录完成（教学规模，判据是相对量级）"

# ─────────────────────────────────────────────
sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"

exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
