#!/usr/bin/env bash
# 第 31 天实验一键重放：bash tutorials/day-031/code/probe.sh
# 环境：Ubuntu 20.04 (aarch64)、LLVM 18.1.8（mlir-opt-18 / mlir-cpu-runner-18）
# 用法：在 tutorials/day-031/ 目录下执行 bash code/probe.sh
set -u
cd "$(dirname "$0")"

run() { echo "\$ $*"; "$@"; echo; }

echo "======== 实验① branch_relu round-trip：块标签与前驱注释 ========"
run mlir-opt-18 branch_relu.mlir

echo "======== 实验② branch_relu generic form：Region/Block 层级裸奔 ========"
run mlir-opt-18 branch_relu.mlir --mlir-print-op-generic

echo "======== 实验③ if_relu generic form：一条 op 持有两个 Region ========"
run mlir-opt-18 if_relu.mlir --mlir-print-op-generic

echo "======== 实验④ loop_sum round-trip：scf.for 与块参数 ========"
run mlir-opt-18 loop_sum.mlir

echo "======== 实验⑤ 结构化控制流降级为 CFG（--convert-scf-to-cf） ========"
run mlir-opt-18 if_relu.mlir --convert-scf-to-cf
run mlir-opt-18 loop_sum.mlir --convert-scf-to-cf

echo "======== 实验⑥ JIT 执行：上界开区间 vs 闭区间 ========"
run mlir-opt-18 loop_sum.mlir --convert-scf-to-cf --convert-cf-to-llvm \
    --convert-func-to-llvm --convert-arith-to-llvm -o /tmp/day031_open.llvm.mlir
run mlir-cpu-runner-18 /tmp/day031_open.llvm.mlir --entry-point-result=i32
run mlir-opt-18 loop_sum_closed.mlir --convert-scf-to-cf --convert-cf-to-llvm \
    --convert-func-to-llvm --convert-arith-to-llvm -o /tmp/day031_closed.llvm.mlir
run mlir-cpu-runner-18 /tmp/day031_closed.llvm.mlir --entry-point-result=i32

echo "======== 错误探针（5 个，全部真实报错，exit 码均为 1） ========"
probe_dir=$(mktemp -d)
cat > "$probe_dir/err_no_term.mlir" <<'EOF'
func.func @no_term(%x: i32) -> i32 {
  %c0 = arith.constant 0 : i32
}
EOF
cat > "$probe_dir/err_argc.mlir" <<'EOF'
func.func @wrong_argc(%x: i32) -> i32 {
  %c0 = arith.constant 0 : i32
  %neg = arith.cmpi slt, %x, %c0 : i32
  cf.cond_br %neg, ^a, ^merge
^a:
  cf.br ^merge(%c0 : i32)
^merge(%val: i32):
  return %val : i32
}
EOF
cat > "$probe_dir/err_type.mlir" <<'EOF'
func.func @wrong_type(%x: i32) -> i32 {
  %c0 = arith.constant 0 : i32
  cf.br ^merge(%c0 : i32)
^merge(%val: f32):
  return %x : i32
}
EOF
cat > "$probe_dir/err_dom.mlir" <<'EOF'
func.func @dominance(%flag: i1) -> i32 {
  cf.cond_br %flag, ^a, ^b
^a:
  %va = arith.constant 1 : i32
  cf.br ^merge
^b:
  cf.br ^merge
^merge:
  return %va : i32
}
EOF
cat > "$probe_dir/err_yield.mlir" <<'EOF'
func.func @missing_yield(%x: i32) -> i32 {
  %c0 = arith.constant 0 : i32
  %pos = arith.cmpi sgt, %x, %c0 : i32
  %r = scf.if %pos -> (i32) {
  } else {
    scf.yield %c0 : i32
  }
  return %r : i32
}
EOF
for name in err_no_term err_argc err_type err_dom err_yield; do
  echo "---- 探针 $name ----"
  mlir-opt-18 "$probe_dir/$name.mlir" 2>&1
  echo "(exit: $?)"
  echo
done
rm -rf "$probe_dir"
