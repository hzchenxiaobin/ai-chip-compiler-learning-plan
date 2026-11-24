//===- MiniOps.td - mini dialect ops ------------------------*- tablegen -*-===//
//
// 第 38 天的主角：在 mini.matmul 之外补齐 mini.add、mini.relu 和
// mini.constant，凑齐目标图 MatMul -> Add -> Relu 所需的全部算子。
//
// 第 40 天：mini.add / mini.relu 摘掉 SameOperandsAndResultType trait，
// 改为手写 Verifier（lib/AddVerifier.cpp / lib/ReluVerifier.cpp）——
// 为了报错能区分"shape 永久不匹配"和"只差 broadcast（Day 60 再支持）"，
// 也为了给动态维 ? 留出保守放行的余地（trait 只认字面类型相等）。
//
// mini.constant 是第一个"数据不带在操作数上、而是带在属性里"的算子；
// mini.add / mini.relu 则示范逐元素算子的标准约束 SameOperandsAndResultType
// 与无副作用 trait Pure。
//
// 第 42 天（第 6 周复盘）：新增第五个算子 mini.mul（逐元素乘法）。
// 它是 mini.add 的"同族兄弟"——shape 规则完全一致，所以照抄 add 的处方：
//   ODS 侧  Mini_F32Tensor（任意秩 ranked f32）+ Pure + assemblyFormat；
//   C++ 侧  hasVerifier = 1，lib/MulVerifier.cpp 复用 ShapeRelation.h
//           的三分类裁判（Same / BroadcastOnly / Mismatch）。
// 复盘看点：新增算子只动 3 个文件（本文件 + 新建 MulVerifier.cpp +
// lib/CMakeLists.txt 登记），MiniOpt.cpp / MiniDialect.cpp / Ops.h /
// Passes.h 一行不动——注册表架构让"算子是数据，不是工具里的代码分支"。
//
// 第 46 天：mini.add / mini.mul 打开 hasCanonicalizer，各自的
// getCanonicalizationPatterns 本体在 lib/AlgebraicSimplification.cpp：
// Add(x, -0.0) → x 与 Mul(x, 1.0) → x 两条代数化简（为什么是 -0.0
// 不是 +0.0，见同文件注释与当日教程）。
//
// 第 47 天：mini.add 再打开 hasFolder——tblgen 生成的类里多出一条
//   ::mlir::OpFoldResult fold(FoldAdaptor adaptor);
// 本体在 lib/AddFold.cpp：两个操作数都是常量时，把和直接算成一个
// dense 属性返回（Add(1.0, 2.0) → mini.constant 3.0）。与 Canonicalizer
// 的分工：Pattern 拿 Rewriter 改图，fold 只做纯计算、不碰 IR；
// 返回的属性由驱动经 MiniDialect::materializeConstant 物化回
// mini.constant（MiniDialect.cpp 今天同步新增）。
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
// 第 38 天曾为 SameOperandsAndResultType include 过
// mlir/Interfaces/InferTypeOpInterface.td；第 40 天摘掉该 trait 后，
// 这个 include 没有别的用户，一并移除（留着也能编过，只是骗人）。

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
        Verifier (see lib/MatmulVerifier.cpp, Day 39).

        Example:

        ```mlir
        %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
        ```
    }];

    // 第 39 天：打开手写 Verifier 开关。tblgen 会在生成的类里声明
    //   ::mlir::LogicalResult verify();
    // 并让 verifyInvariants 在跑完 ODS 约束之后调用它；
    // 函数本体由我们在 lib/MatmulVerifier.cpp 里手写。
    let hasVerifier = 1;

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

def Mini_AddOp : Mini_Op<"add", [Pure]> {
    let summary = "elementwise addition";

    let description = [{
        The `mini.add` operation performs element-wise addition between
        two ranked f32 tensors. Both operands and the result must have
        exactly the same shape. Broadcasting is deliberately NOT
        supported yet: a bias of shape 1x2 is rejected against an
        M x 2 tensor with an explicit "would broadcast, not supported
        yet" diagnostic (see lib/AddVerifier.cpp, Day 40; broadcast
        rules arrive on Day 60).

        Example:

        ```mlir
        %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
        ```
    }];

    // 第 40 天：摘掉 SameOperandsAndResultType、打开手写 Verifier 开关。
    // trait 的检查在 verifyInvariantsImpl 里先于 verify() 执行——只要 trait
    // 还在，我们自己的 shape 报错就永远轮不到出场（见教程错误 1）。
    let hasVerifier = 1;

    // 第 46 天：打开 Canonicalizer 开关（与 mini.relu 的 Day 45 同款机制）。
    // tblgen 生成 static getCanonicalizationPatterns 声明，本体在
    // lib/AlgebraicSimplification.cpp——SimplifyAddNegZero 把
    // Add(x, 全体元素 = -0.0 的常量) 塌缩成 x。注意是 -0.0 不是 +0.0：
    // IEEE 754 里 (-0.0) + (+0.0) = +0.0，+0.0 版本会改写 x = -0.0 时的
    // 结果（详见第 46 天教程 3.3 节的 IEEE 对照表）。
    let hasCanonicalizer = 1;

    // 第 47 天：打开 Folder 开关。与 hasCanonicalizer 生成的静态钩子不同，
    // fold 是实例方法：驱动把"操作数若是常量则携带的 dense 属性"打包成
    // FoldAdaptor 送进来，我们算出一个 Attribute 送回去——整个过程不许
    // 修改 IR（没有 Rewriter 可用），这是 fold 和 Pattern 的本质分工。
    // mini.add 的 fold 本体在 lib/AddFold.cpp，带两道护栏：
    //   类型护栏：结果类型与操作数类型完全一致才动手（与 Day 46 同款）；
    //   尺寸护栏：元素个数超过 kMaxFoldElements 就拒绝编译期展开。
    let hasFolder = 1;

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
// mini.mul —— 逐元素乘法（第 42 天：第 6 周复盘的主角）
//===----------------------------------------------------------------------===//

def Mini_MulOp : Mini_Op<"mul", [Pure]> {
    let summary = "elementwise multiplication";

    let description = [{
        The `mini.mul` operation performs element-wise multiplication
        (the Hadamard product) between two ranked f32 tensors. Shape
        rules are identical to `mini.add`: operands and result must
        have exactly the same shape (see lib/MulVerifier.cpp, Day 42).
        Broadcasting is deliberately NOT supported yet -- same policy,
        same diagnostics, same Day-60 upgrade path as mini.add.

        Example:

        ```mlir
        %p = mini.mul %m, %scale : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
        ```
    }];

    // 与 mini.add 同款开关：ODS 约束（Mini_F32Tensor）跑完之后，
    // verifyInvariants 继续调用 lib/MulVerifier.cpp 里手写的 verify()。
    let hasVerifier = 1;

    // 第 46 天：同款 Canonicalizer 开关。本体在
    // lib/AlgebraicSimplification.cpp——SimplifyMulOne 把
    // Mul(x, 全体元素 = 1.0 的常量) 塌缩成 x。1.0 乘任何值（含
    // NaN、±Inf、-0.0）数值都不变，是 f32 上严格安全的恒等式；
    // 对照 Mul(x, 0.0) → 0 不安全（NaN/±Inf 乘 0 得 NaN），不实现。
    let hasCanonicalizer = 1;

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

def Mini_ReluOp : Mini_Op<"relu", [Pure]> {
    let summary = "elementwise ReLU activation";

    let description = [{
        The `mini.relu` operation applies max(x, 0) element-wise to a
        ranked f32 tensor. The result must have the same shape as the
        input (checked by lib/ReluVerifier.cpp, Day 40).

        Since the output of relu is already non-negative, a second relu
        applied on top never changes any value: relu(relu(x)) == relu(x).
        Day 45 turns this identity into the dialect's first
        RewritePattern (lib/ReluCanonicalization.cpp): with
        hasCanonicalizer enabled below, the driver of `-canonicalize`
        calls into ReluOp::getCanonicalizationPatterns to collect it.

        Example:

        ```mlir
        %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
        ```
    }];

    // 第 40 天：与 mini.add 同款迁移——trait 换手写 Verifier。
    let hasVerifier = 1;

    // 第 45 天：打开 Canonicalizer 开关。tblgen 会在生成的类里声明
    //   static void getCanonicalizationPatterns(RewritePatternSet &,
    //                                           MLIRContext *);
    // 函数本体由我们在 lib/ReluCanonicalization.cpp 里手写：往 results
    // 里塞一个 SimplifyDoubleRelu（Relu(Relu(x)) -> Relu(x)）。
    // -canonicalize 的驱动会对图中每个已注册算子调用这个钩子收集
    // Pattern，mini.relu 从此参与规范化——不用写 Pass，不用改 mini-opt。
    let hasCanonicalizer = 1;

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

    // 第 47 天：constant 自己也打开 hasFolder——fold 直接把 value 属性
    // 原样奉还（lib/AddFold.cpp 里的 ConstantOp::fold）。这不是化简，
    // 而是给驱动递纸条：当 mini.add 折叠时，驱动向操作数的定义者
    // "要常量值"，mini.constant 就是通过这条 fold 通道把 dense 属性
    // 交出去的。上游 arith.constant 的 fold 也是同一句话。
    let hasFolder = 1;

    let assemblyFormat = "$value attr-dict";
}

#endif // MINI_OPS
