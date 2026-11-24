#!/usr/bin/env bash
# 第 35 天一键重放：闭卷标注 → generic form 判卷 → 降级阶梯 → JIT → 报错探针
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29 记录一致
# 用法：bash run_all.sh        # 在本目录执行，中间产物写到 /tmp/day035/
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
OUT=/tmp/day035
mkdir -p "$OUT"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/8 环境检查"
mlir-opt-18 --version | head -1

banner "1/8 闭卷考卷：pretty form round-trip（解析→验证→打印）"
mlir-opt-18 "$HERE/week5_exam.mlir"

banner "2/8 判卷钥匙：generic form（Region/Block/属性全部现形）"
mlir-opt-18 "$HERE/week5_exam.mlir" --mlir-print-op-generic

banner "3/8 机器数数：--print-op-stats（13 个 op、5 个方言）"
mlir-opt-18 "$HERE/week5_exam.mlir" --print-op-stats 2>&1 | grep -E "^\s+\S+\s+,"

banner "4/8 phi 重逢：--convert-scf-to-cf（循环头块参数带 2 个前驱）"
mlir-opt-18 "$HERE/week5_exam.mlir" --convert-scf-to-cf

banner "5/8 降级阶梯：tensor → memref → cf → LLVM，每级方言进出"
mlir-opt-18 "$HERE/week5_run.mlir" --one-shot-bufferize="bufferize-function-boundaries" -o "$OUT/s1.mlir"
mlir-opt-18 "$OUT/s1.mlir" --convert-scf-to-cf -o "$OUT/s2.mlir"
mlir-opt-18 "$OUT/s2.mlir" --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm \
    --convert-index-to-llvm --finalize-memref-to-llvm --canonicalize -o "$OUT/s3.mlir"
for f in "$HERE/week5_run.mlir" "$OUT/s1.mlir" "$OUT/s2.mlir" "$OUT/s3.mlir"; do
  ds=$(mlir-opt-18 "$f" --print-op-stats 2>&1 | grep -E "^\s+\S+\s+," \
       | awk -F',' '{gsub(/ /,"",$1); split($1,a,"."); print a[1]}' | sort -u | tr '\n' ' ')
  n=$(mlir-opt-18 "$f" --print-op-stats 2>&1 | grep -E "^\s+\S+\s+," | awk -F',' '{s+=$2} END {print s}')
  echo "$f : ${n} ops, dialects: $ds"
done

banner "6/8 JIT 真跑：clamped_dot([1,-2,3,-4], 0.5) → 5"
mlir-cpu-runner-18 "$OUT/s3.mlir" --entry-point-result=i32

banner "7/8 换参数再跑：bias 0.5 → 2.0（先预测：[3,0,5,0] 求和 = 8）"
sed 's/arith.constant 0.5 : f32/arith.constant 2.0 : f32/' "$HERE/week5_run.mlir" > "$OUT/run_bias2.mlir"
mlir-opt-18 "$OUT/run_bias2.mlir" --one-shot-bufferize="bufferize-function-boundaries" --convert-scf-to-cf \
    --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm \
    --finalize-memref-to-llvm --canonicalize -o "$OUT/bias2.llvm.mlir"
mlir-cpu-runner-18 "$OUT/bias2.llvm.mlir" --entry-point-result=i32

banner "8/8 三支报错探针（现象 → 原因归属）"
echo "── 探针① iter_args 初值类型不匹配（解析器第①站拦截）"
mlir-opt-18 "$HERE/week5_exam_broken_type.mlir" 2>&1 | grep -m2 -E "error:|note:"
echo "── 探针② 漏 --finalize-memref-to-llvm（JIT 门口报方言没户口）"
mlir-opt-18 "$HERE/week5_run.mlir" --one-shot-bufferize="bufferize-function-boundaries" --convert-scf-to-cf \
    --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm \
    --canonicalize -o "$OUT/no_memref.llvm.mlir"
mlir-cpu-runner-18 "$OUT/no_memref.llvm.mlir" --entry-point-result=i32 2>&1 | grep -m1 "error:"
echo "── 探针③ 漏 --convert-scf-to-cf（scf.for 留在产物里）"
mlir-opt-18 "$HERE/week5_run.mlir" --one-shot-bufferize="bufferize-function-boundaries" \
    --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm \
    --finalize-memref-to-llvm --canonicalize -o "$OUT/no_scf.llvm.mlir"
mlir-cpu-runner-18 "$OUT/no_scf.llvm.mlir" --entry-point-result=i32 2>&1 | grep -m1 "error:"

banner "彩蛋：文本只是视图之一——bytecode 序列化"
mlir-opt-18 "$HERE/week5_exam.mlir" --emit-bytecode -o "$OUT/exam.mlirbc"
if diff <(mlir-opt-18 "$HERE/week5_exam.mlir") <(mlir-opt-18 "$OUT/exam.mlirbc") >/dev/null; then
  echo "文本 $(wc -c < "$HERE/week5_exam.mlir") 字节 vs bytecode $(wc -c < "$OUT/exam.mlirbc") 字节；两种序列化读回后打印完全一致"
else
  echo "（意外）两种序列化读回后打印不一致，请检查环境"
fi
