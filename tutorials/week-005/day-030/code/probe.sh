#!/usr/bin/env bash
# probe.sh —— 第 30 天：Operation 与 Value 概念探针
# 重放教程全部实验：round-trip 换名、generic form、多结果、JIT、类型巡游、
# 命名作用域，以及 4 个故意触发的错误探针（SSA 三铁律 + 签名一致性）。
# 用法：bash probe.sh（可在任意目录执行，自动定位同目录下的 .mlir 文件）

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

line() { echo; echo "──────── $1 ────────"; }

echo "==== 第 30 天概念探针 ===="
echo "日期     : $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "mlir-opt : $(mlir-opt-18 --version | head -1)"

line "实验① round-trip：名字全丢（不加任何 Pass）"
mlir-opt-18 "$HERE/bias_relu.mlir"

line "实验② 换名对照：结构相同、名字不同 → 打印输出完全相同"
if diff <(mlir-opt-18 "$HERE/bias_relu.mlir") \
         <(mlir-opt-18 "$HERE/bias_relu_renamed.mlir") >/dev/null; then
  echo "diff 为空：两份文件解析后打印完全相同（名字是糖，结构才是身份）"
else
  echo "diff 非空：请检查两份文件结构是否真的相同"
  exit 1
fi

line "实验③ generic form：剥掉全部语法糖"
mlir-opt-18 "$HERE/bias_relu.mlir" --mlir-print-op-generic

line "实验④ 多结果：一条 func.call 定义两个值"
mlir-opt-18 "$HERE/divmod.mlir"

line "实验⑤ JIT：divmod 的 q + r（17 = 5×3 + 2 → 打印 5）"
mlir-opt-18 "$HERE/divmod.mlir" \
  --convert-func-to-llvm --convert-arith-to-llvm -o "$TMP/divmod.llvm.mlir" &&
mlir-cpu-runner-18 "$TMP/divmod.llvm.mlir" --entry-point-result=i32

line "5.4 对照实验：只用第一个结果（qonly 版，预测打印 3）"
mlir-opt-18 "$HERE/divmod_qonly.mlir"
mlir-opt-18 "$HERE/divmod_qonly.mlir" \
  --convert-func-to-llvm --convert-arith-to-llvm -o "$TMP/qonly.llvm.mlir" &&
mlir-cpu-runner-18 "$TMP/qonly.llvm.mlir" --entry-point-result=i32

line "实验⑥ 类型巡游：每个值恰好一个类型（i32 / f32 / index / tensor / memref）"
cat > "$TMP/type_tour.mlir" <<'EOF'
func.func @type_tour(%scalar_i: i32, %scalar_f: f32, %idx: index,
                     %t: tensor<2x3xf32>, %m: memref<2x3xf32, strided<[3, 1], offset: 0>>) {
  return
}
EOF
mlir-opt-18 "$TMP/type_tour.mlir"

line "命名作用域：不同函数里同名值互不冲突"
cat > "$TMP/name_scope.mlir" <<'EOF'
func.func @g(%x: i32) -> i32 {
  %a = arith.constant 1 : i32
  return %a : i32
}
func.func @h(%x: i32) -> i32 {
  %a = arith.constant 2 : i32
  return %a : i32
}
EOF
mlir-opt-18 "$TMP/name_scope.mlir" && echo "OK：同名值在不同函数里相安无事"

line "错误探针 1：SSA 重定义（违反单赋值铁律）"
cat > "$TMP/err_redef.mlir" <<'EOF'
func.func @f(%x: i32) -> i32 {
  %a = arith.constant 1 : i32
  %a = arith.constant 2 : i32
  return %a : i32
}
EOF
mlir-opt-18 "$TMP/err_redef.mlir" 2>&1; echo "exit=$?"

line "错误探针 2：使用未定义的值（违反先定义后使用）"
cat > "$TMP/err_undef.mlir" <<'EOF'
func.func @f(%x: i32) -> i32 {
  %r = arith.addi %x, %ghost : i32
  return %r : i32
}
EOF
mlir-opt-18 "$TMP/err_undef.mlir" 2>&1; echo "exit=$?"

line "错误探针 3：一个值当两个类型用（违反一值一类型）"
cat > "$TMP/err_type.mlir" <<'EOF'
func.func @f(%x: i32, %y: f32) -> i32 {
  %r = arith.addi %x, %y : i32
  return %r : i32
}
EOF
mlir-opt-18 "$TMP/err_type.mlir" 2>&1; echo "exit=$?"

line "错误探针 4：return 个数与函数签名不符（违反结果数一致性）"
cat > "$TMP/err_retcount.mlir" <<'EOF'
func.func @f(%x: i32) -> i32 {
  %y = arith.constant 2 : i32
  return %x, %y : i32, i32
}
EOF
mlir-opt-18 "$TMP/err_retcount.mlir" 2>&1; echo "exit=$?"

line "结论"
echo "四条铁律均由工具当场拦截：单赋值、先定义后使用、一值一类型、结果数与签名一致。"
echo "第 30 天探针全部完成。"
