; ──────────────────────────────────────────────────────
; 第 113 天产出 1：带注释的 LLVM IR（自动生成）
; 输入：step.mlir（LLVM Dialect）→ mini_translate.py 导出 → outputs/step.ll
; 注释由 annotate.py 遍历 llvmlite 解析出的真实 LLVM 结构生成
; ──────────────────────────────────────────────────────
; ▼ 函数 @step：参数 1 个、基本块 4 个、返回类型 i32
;   参数对照：%0 ← MLIR %arg0
;   返回点：1 处
define i32 @step(i32 %0) {
; ── 基本块 1/4：entry（MLIR 隐式入口块）
;    前驱 0 个（入口块）
;    后继 2 个：%6、%8
  %2 = add i32 2, 3
  %3 = mul i32 %2, 4
  %4 = add i32 %0, 0
  %5 = icmp sgt i32 %4, %3
  br i1 %5, label %6, label %8   ; ← 条件跳转（llvm.cond_br）：真/假各走一个后继
; ── 基本块 2/4：6（MLIR ^hi）
;    前驱 1 个：entry
;    后继 1 个：%10
6:
  %7 = add i32 %4, %3
  br label %10   ; ← 无条件跳转（llvm.br）
; ── 基本块 3/4：8（MLIR ^lo）
;    前驱 1 个：entry
;    后继 1 个：%10
8:
  %9 = sub i32 %4, %3
  br label %10   ; ← 无条件跳转（llvm.br）
; ── 基本块 4/4：10（MLIR ^merge）
;    前驱 2 个：6、8
;    后继 0 个（出口块，含 ret）
10:
  %11 = phi i32 [ %7, %6 ], [ %9, %8 ]   ; ← phi：本块的块参数（MLIR ^merge 的 %m）；前驱各送一个值：%7 来自 %6；%9 来自 %8
  ret i32 %11   ; ← 返回值：%11
}
