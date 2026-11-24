//===- MiniOps.td - mini dialect ops ------------------------*- tablegen -*-===//
//
// 第 37 天的主角：用 ODS（Operation Definition Specification）定义
// mini.matmul —— 两个输入、一个结果、Tensor 类型。
//
// 这个 .td 文件交给 mlir-tblgen 后，会自动生成 C++ 类 MatmulOp、
// 解析器、打印器和约束检查代码，不需要手写。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_OPS
#define MINI_OPS

include "mini/MiniDialect.td"
include "mlir/IR/CommonTypeConstraints.td"
include "mlir/Interfaces/SideEffectInterfaces.td"

//===----------------------------------------------------------------------===//
// 自制类型约束：元素为 f32、秩 >= 2 的 RankedTensor。
//
// RankedTensorOf<[F32], [HasRankGreaterOrEqualPred<2>]> 展开后等价于三条
// 逻辑判断的 AND（摘自 mlir/IR/CommonTypeConstraints.td）：
//   1. ::llvm::isa<::mlir::RankedTensorType>($_self)   —— 是有秩张量
//   2. 元素类型是 f32                                  —— 由 [F32] 展开
//   3. ::llvm::cast<::mlir::ShapedType>($_self).getRank() >= 2
// 违反任何一条，Verifier 都会拒绝这个 op（错误信息用下面的 summary 文本）。
//===----------------------------------------------------------------------===//

def Mini_F32Tensor2DPlus
  : RankedTensorOf<[F32], [HasRankGreaterOrEqualPred<2>],
      "ranked f32 tensor with rank >= 2">;

//===----------------------------------------------------------------------===//
// mini.matmul
//===----------------------------------------------------------------------===//

def Mini_MatmulOp : Mini_Op<"matmul", [Pure]> {
    let summary = "matrix multiplication";

    let description = [{
        The `mini.matmul` operation computes the matrix product of two
        tensors of rank >= 2. Operand shapes are expected to be
        batch-compatible, e.g. for rank 2: `lhs` is M x K, `rhs` is K x N
        and the result is M x N. Full shape checking lives in the C++
        Verifier (Day 39).

        Example:

        ```mlir
        %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
        ```
    }];

    // 两个输入：lhs（A，M x K）与 rhs（B，K x N）
    let arguments = (ins
      Mini_F32Tensor2DPlus:$lhs,
      Mini_F32Tensor2DPlus:$rhs
    );

    // 一个结果：res（C，M x N）
    let results = (outs
      Mini_F32Tensor2DPlus:$res
    );

    // 声明式语法格式：同时生成解析器和打印器
    let assemblyFormat = [{
      $lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)
    }];
}

#endif // MINI_OPS
