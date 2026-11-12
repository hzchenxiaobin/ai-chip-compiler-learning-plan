#!/usr/bin/env bash
# 第 33 天实验一键重放：bash tutorials/day-033/code/probe.sh
# 环境：Ubuntu 20.04 (aarch64)、LLVM 18.1.8（mlir-opt-18 / mlir-cpu-runner-18）
# 用法：在 tutorials/day-033/ 目录下执行 bash code/probe.sh
set -u
cd "$(dirname "$0")"

OUT=/tmp/day033
mkdir -p "$OUT"

run() { echo "\$ $*"; "$@"; echo; }

# 五级台阶的每级 Pass（正文 5.3 实验②③）
PIPE1="--one-shot-bufferize"
PIPE2="--convert-linalg-to-loops"
PIPE3="--convert-scf-to-cf"
PIPE4="--convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm --finalize-memref-to-llvm --canonicalize"

echo "======== 实验① 混合 IR：一个模块 5 个方言共住 ========"
run mlir-opt-18 matmul_run.mlir
echo "—— 方言计数（generic form 的 \"dialect.op\" 名字去重）："
mlir-opt-18 matmul_run.mlir --mlir-print-op-generic | grep -o '"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*"' | sed 's/"//g;s/\..*//' | sort | uniq -c
echo

echo "======== 实验② 五级台阶：逐级 dump（正文表 1 与图 3 的数据来源） ========"
run mlir-opt-18 matmul_run.mlir -o $OUT/s0.mlir
run mlir-opt-18 matmul_run.mlir $PIPE1 -o $OUT/s1.mlir
run mlir-opt-18 $OUT/s1.mlir $PIPE2 -o $OUT/s2.mlir
run mlir-opt-18 $OUT/s2.mlir $PIPE3 -o $OUT/s3.mlir
run mlir-opt-18 $OUT/s3.mlir $PIPE4 -o $OUT/s4.mlir
echo "—— 每级行数 / op 数 / 方言清单："
for f in s0 s1 s2 s3 s4; do
  lines=$(wc -l < $OUT/$f.mlir)
  ops=$(mlir-opt-18 $OUT/$f.mlir --mlir-print-op-generic | grep -o '"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*"' | wc -l)
  dialects=$(mlir-opt-18 $OUT/$f.mlir --mlir-print-op-generic | grep -o '"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*"' | sed 's/"//g;s/\..*//' | sort -u | tr '\n' ' ')
  echo "$f.mlir: lines=$lines ops=$ops dialects=[$dialects]"
done
echo "—— 循环层（s2）长什么样（fill 两层 + matmul 三层）："
sed -n '/scf.for %arg0/,/^    }/p' $OUT/s2.mlir | head -20
echo

echo "======== 实验③ JIT：走完五级台阶，打印 139 ========"
run mlir-cpu-runner-18 $OUT/s4.mlir --entry-point-result=i32

echo "======== 5.4 对照：改 K=3→4，JIT 打印 270，k 循环上界自动 3→4 ========"
run mlir-opt-18 matmul_run_k4.mlir --one-shot-bufferize --convert-linalg-to-loops -o $OUT/k4s2.mlir
echo "—— K=4 版循环上界（对比 K=3 版的 to %c3）："
grep -E "to %c[0-9]+" $OUT/k4s2.mlir | sort -u
grep -E "%c4 = arith.constant 4" $OUT/k4s2.mlir
run mlir-opt-18 matmul_run_k4.mlir $PIPE1 $PIPE2 $PIPE3 $PIPE4 -o $OUT/k4.llvm.mlir
run mlir-cpu-runner-18 $OUT/k4.llvm.mlir --entry-point-result=i32

echo "======== 探针① op 没户口（未注册方言 foo） ========"
cat > $OUT/p1.mlir <<'EOF'
func.func @p(%a: i32, %b: i32) -> i32 {
  %0 = "foo.add"(%a, %b) : (i32, i32) -> i32
  return %0 : i32
}
EOF
run mlir-opt-18 $OUT/p1.mlir
echo "—— 同一文件加 -allow-unregistered-dialect：裸奔通过（调试后门）——"
run mlir-opt-18 $OUT/p1.mlir -allow-unregistered-dialect

echo "======== 探针② 顺序错了：linalg→loops 直接吃 tensor 版 → 静默无效 ========"
run mlir-opt-18 matmul_run.mlir --convert-linalg-to-loops

echo "======== 探针③ 欠条没还：漏 --convert-index-to-llvm ========"
run mlir-opt-18 matmul_run.mlir $PIPE1 $PIPE2 $PIPE3 --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --finalize-memref-to-llvm -o $OUT/p3.mlir
echo "—— 残留的欠条（builtin.unrealized_conversion_cast）："
grep "unrealized_conversion_cast" $OUT/p3.mlir | head -3
run mlir-cpu-runner-18 $OUT/p3.mlir --entry-point-result=i32

echo "======== 探针④ 漏 --finalize-memref-to-llvm → JIT 拒收 memref ========"
run mlir-opt-18 matmul_run.mlir $PIPE1 $PIPE2 $PIPE3 --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm -o $OUT/p4.mlir
run mlir-cpu-runner-18 $OUT/p4.mlir --entry-point-result=i32

echo "======== 探针⑤ 漏 --convert-func-to-llvm → JIT 拒收 func ========"
run mlir-opt-18 matmul_run.mlir $PIPE1 $PIPE2 $PIPE3 --convert-cf-to-llvm --convert-arith-to-llvm --convert-index-to-llvm --finalize-memref-to-llvm -o $OUT/p5.mlir
run mlir-cpu-runner-18 $OUT/p5.mlir --entry-point-result=i32

echo "======== 探针⑥ 漏 --convert-scf-to-cf → scf.for 留在产物里 ========"
run mlir-opt-18 matmul_run.mlir $PIPE1 $PIPE2 --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm --convert-index-to-llvm --finalize-memref-to-llvm -o $OUT/p6.mlir
run mlir-cpu-runner-18 $OUT/p6.mlir --entry-point-result=i32

echo "======== 探针⑦ 翻车现场：tensor.empty 没清零直接 outs（输出不确定） ========"
run mlir-opt-18 matmul_nofill.mlir $PIPE1 $PIPE2 $PIPE3 $PIPE4 -o $OUT/nofill.llvm.mlir
for i in 1 2 3; do
  echo "\$ mlir-cpu-runner-18 $OUT/nofill.llvm.mlir --entry-point-result=i32   # 第 $i 次运行"
  mlir-cpu-runner-18 $OUT/nofill.llvm.mlir --entry-point-result=i32
done

echo "======== 选做练习 (a) 预告：M=3 版的 i 循环上界也应自动 2→3 ========"
