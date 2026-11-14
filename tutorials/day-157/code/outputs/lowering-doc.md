# Lowering 文档：一个 MatMul 的六阶段旅程

主线：抽象逐级消失、语义全程保持。
示例：main.graph（11 节点）→ 执行（12/12 bitwise）

## 阶段 1：图 IR（抽象最高）
  `%10 = relu(%9 = add(%7 = matmul(%6, %4), %8))`
  · 算子语义在场：「这是融合过的 MatMul+Bias+Relu」
  · 关键转换（→阶段 2）：S1 融合——三个节点变一个 fused_matmul_bias_relu

## 阶段 2：循环 IR（scf.for＋memref）
  `scf.for %k ... iter_args(%acc = %bj)` + `memref.load/store`
  · bias 融在 k=0 圈（iter_args 初值）；k 序乘加链；cmpf+select（relu）
  · 关键转换（→阶段 3）：convert-scf-to-cf——结构化的 for 拆成
    init/header/body/latch 四块（块参数出现——phi 的前身）

## 阶段 3：cf 层（块＋跳转）
  `cf.br ^bb(%c0, %cst)` / `cf.cond_br %cond, ^hi, ^lo`
  · 「这是循环」的结构语义消失——只剩块与跳转边
  · 关键转换（→阶段 4）：五个 convert——memref→描述符、func→llvm.func、
    cf→llvm.br、arith→llvm 指令、index→i64

## 阶段 4：LLVM Dialect（纯 llvm.*）
  `llvm.extractvalue`×N＋`llvm.getelementptr`＋`llvm.load/fmul/fadd`
  · memref 类型消失——5 字段描述符（56B）；胶水由 reconcile 清零
  · 关键转换（→阶段 5）：mlir-translate——R1 重编号/R2 常量内联/R3 块参数→phi

## 阶段 5：LLVM IR（.ll）
  `%45 = icmp slt i64 %44, %29` + `%53 = load float, ptr %52`
  · MLIR 的名字消失（%c1a→%14）；常量内联进指令；块参数变 phi
  · `_mlir_ciface_main_kernel(ptr, ptr, ptr, ptr)`——C 合同在此定形
  · 关键转换（→阶段 6）：llc/clang 指令选择＋寄存器分配

## 阶段 6：机器码（.s→.so）
  `ldr s0, [x1, x8, lsl #2]` / `fmul s1, s0, s2`（arm64 汇编）
  · SSA 消失（寄存器复用）；类型消失（只有位宽）；malloc→bl 调用
  · 执行：ctypes 按 C 合同调用——12/12 bitwise ✓

## 信息守恒（D119 的结论在新证据下的复述）
  每层「保留什么」与「丢失什么」：
  · 算子语义：阶段 2 消失（三层 for 不再「是」MatMul）
  · shape 决策：阶段 5 内联成常量（icmp slt ..., 4 的 4=M）
  · 描述符合同：阶段 4 新增（D115 的 56B 契约）
  · 正确性裁判：阶段 6 的执行＋golden——每层的语义保持由它总验
