#!/usr/bin/env bash
# env_check.sh —— 第 29 天：MLIR 环境记录
# 逐项确认工具存在并打印版本；末尾做一次冒烟测试（解析 + 验证一个最小 IR）。
# 用法：bash env_check.sh

set -u

echo "==== 系统信息 ===="
echo "日期       : $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "内核/架构  : $(uname -srm)"
. /etc/os-release 2>/dev/null && echo "发行版     : $NAME $VERSION_ID" || true

echo
echo "==== MLIR 工具链 ===="
# 本教程基于 Ubuntu 的 LLVM 18 包（后缀 -18）；其他来源的 mlir-opt 请改这里的名字。
TOOLS="mlir-opt-18 mlir-cpu-runner-18 FileCheck-18 mlir-lsp-server-18 mlir-tblgen-18 mlir-cat-18"
FAIL=0
for t in $TOOLS; do
  if command -v "$t" >/dev/null 2>&1; then
    v=$("$t" --version 2>/dev/null | grep -m1 -E "version" || echo "(无 --version 输出)")
    printf "  [PASS] %-20s %s\n" "$t" "$v"
  else
    printf "  [MISS] %-20s 未安装或不在 PATH\n" "$t"
    FAIL=1
  fi
done

echo
echo "==== 冒烟测试：解析 + 验证一个最小 IR ===="
cat > /tmp/mlir_day029_smoke.mlir <<'EOF'
module {
  func.func @smoke(%x: i32) -> i32 {
    %c0 = arith.constant 0 : i32
    %r = arith.addi %x, %c0 : i32
    return %r : i32
  }
}
EOF
if mlir-opt-18 /tmp/mlir_day029_smoke.mlir -o /dev/null 2>/tmp/mlir_day029_smoke.err; then
  echo "  [PASS] mlir-opt-18 成功解析并验证最小 IR"
else
  echo "  [FAIL] 冒烟测试失败："; cat /tmp/mlir_day029_smoke.err
  FAIL=1
fi
rm -f /tmp/mlir_day029_smoke.mlir /tmp/mlir_day029_smoke.err

echo
if [ "$FAIL" -eq 0 ]; then
  echo "结论：MLIR 环境就绪，可以开始第 30 天。"
  exit 0
else
  echo "结论：有缺失项，请按教程第 5.1 节安装后再试。"
  exit 1
fi
