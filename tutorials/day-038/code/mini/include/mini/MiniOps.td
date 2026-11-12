//===- MiniOps.td - mini dialect ops ------------------------*- tablegen -*-===//
//
// 第 38 天的主角：在 mini.matmul 之外补齐 mini.add、mini.relu 和
// mini.constant，凑齐目标图 MatMul -> Add -> Relu 所需的全部算子。
//
// mini.constant 是第一个"数据不带在操作数上、而是带在属性里"的算子；
// mini.add / mini.relu 则示范逐元素算子的标准约束 SameOperandsAndResultType
// 与无副作用 trait Pure。
//
// 这个 .td 文件交给 mlir-tblgen 后，会自动生成 C++ 类 AddOp、ReluOp、
// ConstantOp 和它们的解析器、打印器、约束检查代码，不需要手写。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_OPS
#define MINI_OPS

include "mini/MiniDialect.td"
include "mlir/IR/CommonTypeConstraints.td"
include "mlir/IR/CommonAttrConstraints.td"
include "mlir/Interfaces/SideEffectInterfaces.td"
// SameOperandsAndResultType 定义在上游 mlir/Interfaces/InferTypeOpInterface.td
// 里（math 方言用的也是它），不 include 这行，tblgen 会报
// "SameOperandsAndResultType was not declared"。
include "mlir/Interfaces/InferTypeOpInterface.td"

//===----------------------------------------------------------------------===//
// 类型与属性约束（mini 自己的"词汇表"）
//===----------------------------------------------------------------------===//

// 第 37 天：元素为 f32、秩 >= 2 的 RankedTensor（matmul 专用）。
def Mini_F32Tensor2DPlus
  : RankedTensorOf<[F32], [HasRankGreaterOrEqualPred<2>],
      "ranked f32 tensor with rank >= 2">;

// 第 38 天新增：元素为 f32 的 RankedTensor，不限秩。
// 逐元素算子对秩没有偏好：标量 tensor<f32>（秩 0）、向量、矩阵都合法。
def Mini_F32Tensor
  : RankedTensorOf<[F32], [], "ranked f32 tensor">;

// 第 38 天新增：装 f32 常量数据的 ElementsAttr。
// 写法照抄上游 CommonAttrConstraints.td 里的
//   def F64ElementsAttr : FloatElementsAttr<64>;
// 只是换成 32 位浮点。
def Mini_F32ElementsAttr : FloatElementsAttr<32>;

//===----------------------------------------------------------------------===//
// mini.matmul（第 37 天完成，原样保留）
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

    let arguments = (ins
      Mini_F32Tensor2DPlus:$lhs,
      Mini_F32Tensor2DPlus:$rhs
    );

    let results = (outs
      Mini_F32Tensor2DPlus:$res
    );

    let assemblyFormat = [{
      $lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)
    }];
}

//===----------------------------------------------------------------------===//
// mini.add —— 逐元素加法
//===----------------------------------------------------------------------===//

def Mini_AddOp : Mini_Op<"add", [Pure, SameOperandsAndResultType]> {
    let summary = "elementwise addition";

    let description = [{
        The `mini.add` operation performs element-wise addition between
        two ranked f32 tensors. Both operands and the result must have
        exactly the same type (same shape, same dtype). Broadcasting is
        NOT supported yet -- a bias of shape 1x2 will be rejected against
        an M x 2 tensor (Broadcast rules arrive on Day 60).

        Example:

        ```mlir
        %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
        ```
    }];

    let arguments = (ins
      Mini_F32Tensor:$lhs,
      Mini_F32Tensor:$rhs
    );

    let results = (outs
      Mini_F32Tensor:$res
    );

    let assemblyFormat = [{
      $lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)
    }];
}

//===----------------------------------------------------------------------===//
// mini.relu —— 逐元素 ReLU 激活函数
//===----------------------------------------------------------------------===//

def Mini_ReluOp : Mini_Op<"relu", [Pure, SameOperandsAndResultType]> {
    let summary = "elementwise ReLU activation";

    let description = [{
        The `mini.relu` operation applies max(x, 0) element-wise to a
        ranked f32 tensor. The result has the same type as the input.

        Example:

        ```mlir
        %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
        ```
    }];

    let arguments = (ins
      Mini_F32Tensor:$input
    );

    let results = (outs
      Mini_F32Tensor:$res
    );

    let assemblyFormat = [{
      $input attr-dict `:` type($input) `->` type($res)
    }];
}

//===----------------------------------------------------------------------===//
// mini.constant —— 常量
//===----------------------------------------------------------------------===//

def Mini_ConstantOp : Mini_Op<"constant",
    [Pure, ConstantLike, AllTypesMatch<["value", "res"]>]> {
    let summary = "constant";

    let description = [{
        The `mini.constant` operation turns a literal into an SSA value.
        Unlike add/relu, the data is NOT passed in through operands: it is
        attached to the operation itself as the `value` attribute
        (a dense f32 ElementsAttr). The result is a ranked f32 tensor
        whose type must agree with the attribute.

        Example:

        ```mlir
        %c0 = mini.constant dense<[[1.0, 2.0]]> : tensor<1x2xf32>
        ```

        The assembly format prints only the attribute: thanks to
        AllTypesMatch<["value", "res"]>, the parser infers the result
        type from the attribute's own tensor type -- the same trick that
        `arith.constant` uses. ODS constraints cannot express "attribute
        shape must equal result shape" beyond this type tie; a
        hand-written Verifier refines the diagnostics (Day 39).
    }];

    let arguments = (ins
      Mini_F32ElementsAttr:$value
    );

    let results = (outs
      Mini_F32Tensor:$res
    );

    let assemblyFormat = "$value attr-dict";
}

#endif // MINI_OPS
