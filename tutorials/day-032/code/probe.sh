#!/usr/bin/env bash
# 第 32 天实验一键重放：bash tutorials/day-032/code/probe.sh
# 环境：Ubuntu 20.04 (aarch64)、LLVM 18.1.8（mlir-opt-18 / mlir-cpu-runner-18）
# 用法：在 tutorials/day-032/ 目录下执行 bash code/probe.sh
set -u
cd "$(dirname "$0")"

run() { echo "\$ $*"; "$@"; echo; }

echo "======== 实验① bias_scale round-trip：建议名与科学计数法 ========"
run mlir-opt-18 bias_scale.mlir

echo "======== 实验② bias_scale generic form：属性字典全裸奔 ========"
run mlir-opt-18 bias_scale.mlir --mlir-print-op-generic

echo "======== 实验③ 类型画廊 round-trip：10 个合法类型 ========"
run mlir-opt-18 type_gallery.mlir

echo "======== 实验④ 动态维：tensor.dim 与 mixed 维度 ========"
run mlir-opt-18 dyn_dims.mlir
run mlir-opt-18 dyn_dims.mlir --mlir-print-op-generic

echo "======== 实验⑤ --canonicalize：9 条折成 1 条（常量住在属性里的收益） ========"
run mlir-opt-18 fold_demo.mlir --canonicalize

echo "======== 实验⑥ JIT：亲手展开成标量循环，打印 13 ========"
run mlir-opt-18 bias_scale_run.mlir --one-shot-bufferize -o /tmp/day032_buf.mlir
run mlir-opt-18 bias_scale_run.mlir --one-shot-bufferize --convert-scf-to-cf \
    --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm \
    --convert-index-to-llvm --finalize-memref-to-llvm --canonicalize \
    -o /tmp/day032_run.llvm.mlir
run mlir-cpu-runner-18 /tmp/day032_run.llvm.mlir --entry-point-result=i32

echo "======== 5.4 对照 (a)：改属性里的一个数（6.0 → 7.0），打印 15 ========"
run mlir-opt-18 bias_scale_run7.mlir --one-shot-bufferize --convert-scf-to-cf \
    --convert-cf-to-llvm --convert-func-to-llvm --convert-arith-to-llvm \
    --convert-index-to-llvm --finalize-memref-to-llvm --canonicalize \
    -o /tmp/day032_run7.llvm.mlir
run mlir-cpu-runner-18 /tmp/day032_run7.llvm.mlir --entry-point-result=i32

echo "======== 错误探针（8 个，全部真实报错，exit 码均为 1） ========"
probe_dir=$(mktemp -d)
cat > "$probe_dir/err_dense_shape.mlir" <<'EOF'
func.func @bad(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
  %cst = arith.constant dense<[1.0, 2.0]> : tensor<2x3xf32>
  %r = arith.addf %x, %cst : tensor<2x3xf32>
  return %r : tensor<2x3xf32>
}
EOF
cat > "$probe_dir/err_scalar_for_tensor.mlir" <<'EOF'
func.func @bad(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
  %cst = arith.constant 1.0 : tensor<2x3xf32>
  %r = arith.addf %x, %cst : tensor<2x3xf32>
  return %r : tensor<2x3xf32>
}
EOF
cat > "$probe_dir/err_attr_type.mlir" <<'EOF'
func.func @bad() -> i32 {
  %c0 = "arith.constant"() <{value = 0 : i64}> : () -> i32
  return %c0 : i32
}
EOF
cat > "$probe_dir/err_mixed_operand.mlir" <<'EOF'
func.func @bad(%x: i32, %y: f32) -> i32 {
  %r = arith.addf %x, %y : i32
  return %r : i32
}
EOF
cat > "$probe_dir/err_shape_mismatch.mlir" <<'EOF'
func.func @bad(%x: tensor<2x3xf32>, %y: tensor<3x2xf32>) -> tensor<2x3xf32> {
  %r = arith.addf %x, %y : tensor<2x3xf32>
  return %r : tensor<2x3xf32>
}
EOF
cat > "$probe_dir/err_dyn_dense.mlir" <<'EOF'
func.func @bad(%x: tensor<?x?xf32>) -> tensor<?x?xf32> {
  %cst = arith.constant dense<1.0> : tensor<?x?xf32>
  %r = arith.addf %x, %cst : tensor<?x?xf32>
  return %r : tensor<?x?xf32>
}
EOF
cat > "$probe_dir/err_unknown_type.mlir" <<'EOF'
func.func @bad(%x: !foo.bar) {
  return
}
EOF
cat > "$probe_dir/err_extract_rank.mlir" <<'EOF'
func.func @bad(%x: tensor<2x3xf32>) -> f32 {
  %i = arith.constant 1 : index
  %e = tensor.extract %x[%i] : tensor<2x3xf32>
  return %e : f32
}
EOF
for name in err_dense_shape err_scalar_for_tensor err_attr_type err_mixed_operand \
            err_shape_mismatch err_dyn_dense err_unknown_type err_extract_rank; do
  echo "---- 探针 $name ----"
  mlir-opt-18 "$probe_dir/$name.mlir" 2>&1
  echo "(exit: $?)"
  echo
done
rm -rf "$probe_dir"
