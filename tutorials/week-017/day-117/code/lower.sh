#!/usr/bin/env bash
# 第 117 天核心脚本：完整 Lowering 管道（优化 + 转换 + 导出 + 验证），
# 分阶段保存中间文件。用法：
#     ./lower.sh <输入.mlir> <输出前缀>
# 产物写进 outputs/<前缀>-*.mlir / .ll / .s：
#   <前缀>-0-optimized.mlir        阶段 0：MLIR 级优化（canonicalize + CSE）
#   <前缀>-1-scf-to-cf.mlir        阶段 1：C1 落地（scf.for 拆四块）
#   <前缀>-2-llvm-dialect-noreconcile.mlir  阶段 2：五 pass 转完（胶水未清）
#   <前缀>-2-llvm-dialect.mlir     阶段 2b：reconcile 清胶水 -> 纯 LLVM 方言
#   <前缀>-3.ll                    阶段 3：mlir-translate 导出的 LLVM IR
#   <前缀>-3.s                     阶段 4：llc 编译到汇编（证明可编译，不执行）
#
# "必要 Pass"清单（每条 pass 负责一层，右侧是对 D114 模式编号的接管关系）：
#   --canonicalize --cse           MLIR 级优化（折叠朴素冗余）
#   --convert-scf-to-cf            C1：scf.for 拆四块（init/header/body/latch）
#   --finalize-memref-to-llvm      M1/M2/M3：读写/分配 -> 描述符字段操作
#   --convert-func-to-llvm         F1：签名 -> llvm.func（memref 按 7 字段展开）
#   --convert-cf-to-llvm           cf.br/cond_br -> llvm.br/cond_br
#   --convert-arith-to-llvm        A2/A3：arith 整数/浮点 -> llvm 指令
#   --convert-index-to-llvm        index -> i64（清 i64<->index 胶水的前半）
#   --reconcile-unrealized-casts  胶水清零（管道中间态实测 6 条）
set -euo pipefail

BIN=/usr/lib/llvm-18/bin
IN="${1:?用法: ./lower.sh 输入.mlir 输出前缀}"
TAG="${2:?用法: ./lower.sh 输入.mlir 输出前缀}"
OUT="$(dirname "$0")/outputs"
mkdir -p "$OUT"

# 阶段 0：MLIR 级优化——先优化再降级（真实编译器的纪律）
"$BIN"/mlir-opt "$IN" --canonicalize --cse -o "$OUT/$TAG-0-optimized.mlir"

# 阶段 1：C1 落地——单独保存，观察"拆四块 + 块参数（phi 的前身）"
"$BIN"/mlir-opt "$OUT/$TAG-0-optimized.mlir" --convert-scf-to-cf \
  -o "$OUT/$TAG-1-scf-to-cf.mlir"

# 阶段 2：五个转换 pass（顺序有讲究：scf->cf 在最前、memref 在 func 前、
#         reconcile 收尾——顺序错的报错见 run_all.sh 的 TP10）
"$BIN"/mlir-opt "$OUT/$TAG-0-optimized.mlir" \
  --convert-scf-to-cf \
  --finalize-memref-to-llvm \
  --convert-func-to-llvm \
  --convert-cf-to-llvm \
  --convert-arith-to-llvm \
  --convert-index-to-llvm \
  -o "$OUT/$TAG-2-llvm-dialect-noreconcile.mlir"

# 阶段 2b：胶水清零 -> 纯 LLVM 方言（可导出形态）
"$BIN"/mlir-opt "$OUT/$TAG-2-llvm-dialect-noreconcile.mlir" \
  --reconcile-unrealized-casts -o "$OUT/$TAG-2-llvm-dialect.mlir"

# 阶段 3：mlir-translate 导出 LLVM IR（.ll）
"$BIN"/mlir-translate --mlir-to-llvmir "$OUT/$TAG-2-llvm-dialect.mlir" \
  -o "$OUT/$TAG-3.ll"

# 阶段 4：真 LLVM 验证（parse + verify + 编译到汇编；执行留给 D118）
"$BIN"/llvm-as "$OUT/$TAG-3.ll" -o /dev/null
"$BIN"/opt -passes=verify -disable-output "$OUT/$TAG-3.ll"
"$BIN"/llc "$OUT/$TAG-3.ll" -o "$OUT/$TAG-3.s"
echo "lower.sh: $IN -> outputs/$TAG-{0-optimized,1-scf-to-cf,2-llvm-dialect,3.ll,3.s}"
