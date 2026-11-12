#ifndef MINI_OPS
#define MINI_OPS

// MiniOps.td —— 第 56 天（第 8 周复盘）版本。
//
// 在第 55 天验收壳（matmul / add / relu / fused_add_relu /
// fused_matmul_bias / fused_matmul_bias_relu）的基础上，把第 47 天的
// mini.constant 带回来：今天的复盘主线是「一条 IR 的四站旅程」——
// 验证 → Shape 推导 → 折叠 → 融合，折叠站需要有常量可折。
//
// 相对第 55 天壳的三处结构改动（复盘 = 把各天的能力接进同一条管道）：
//   1. 新增 mini.constant（value 属性 + Pure + ConstantLike + hasFolder），
//      口径与第 47/49 天的 mini 工程一致；
//   2. Dialect 打开 hasConstantMaterializer = 1——fold 只返回属性，
//      把属性物化回 mini.constant 节点靠这个钩子（第 49 天踩过的坑：
//      手抄类外定义编译不过，唯一正确入口是 TableGen 开关）；
//   3. Verifier 口径（MiniRules.h）：matmul 的「结果维」允许写 ?
//      （待推导，第 39/44 天的保守放行），操作数仍要求静态——
//      这样一张带着 ?x2 的图能通过验证站，等推导站细化。

include "mlir/IR/OpBase.td"
include "mlir/IR/CommonTypeConstraints.td"
include "mlir/IR/CommonAttrConstraints.td"
include "mlir/Interfaces/InferTypeOpInterface.td"
include "mlir/Interfaces/SideEffectInterfaces.td"   // Pure / NoMemoryEffect

def Mini_Dialect : Dialect {
  let name = "mini";
  let cppNamespace = "::mini";
  let summary = "学习计划第 8 周使用的 mini Dialect（四站复盘壳）";
  let description = [{
    第 56 天版本：constant / matmul / add / relu / fused_add_relu /
    fused_matmul_bias / fused_matmul_bias_relu。本壳限定 rank-2 f32 张量；
    matmul 结果维允许 ?（待 Shape 推导细化），操作数必须静态。
  }];
  // fold 折出的属性要物化回 mini.constant，靠这个钩子（第 49 天结论）
  let hasConstantMaterializer = 1;
}

class MiniOp<string mnemonic, list<Trait> traits = []> :
    Op<Mini_Dialect, mnemonic, traits>;

// dense f32 元素属性（第 38 天起沿用）：TypedAttr，自带类型，
// 配合 AllTypesMatch 让解析器从属性推断出结果类型。
def Mini_F32ElementsAttr : FloatElementsAttr<32>;

// ---------- mini.constant：第 47 天的常量算子，今天回归 ----------
// data 不走操作数，挂在 op 自己身上（value 属性）。
// fold = 递纸条：驱动来要常量值时把 value 原样奉还。
def Mini_ConstantOp : MiniOp<"constant",
    [Pure, ConstantLike, AllTypesMatch<["value", "res"]>]> {
  let summary = "constant tensor";
  let description = [{
    把一个字面量变成 SSA 值。数据不通过操作数传入，而是作为 op 自身的
    `value` 属性（dense f32 elements）。结果必须是 ranked f32 张量，
    且类型与属性一致（手写 Verifier 校验，第 39/47 天口径）。

    ```mlir
    %c0 = mini.constant dense<0.5> : tensor<2x2xf32>
    ```

    fold 直接把 value 属性原样奉还——不是化简，是给驱动递纸条：
    当 mini.add 折叠时，驱动向操作数定义者「要常量值」，
    mini.constant 就是通过 fold 通道把 dense 属性交出去的。
  }];
  let hasFolder = 1;
  let hasVerifier = 1;
  let arguments = (ins Mini_F32ElementsAttr:$value);
  let results = (outs AnyType:$res);
  let assemblyFormat = "$value attr-dict";
}

// ---------- mini.matmul：MxK · KxN -> MxN ----------
def Mini_MatmulOp : MiniOp<"matmul"> {
  let summary = "matrix multiplication";
  let description = [{
    两个 rank-2 f32 张量相乘：lhs 是 MxK，rhs 是 KxN，结果是 MxN。
    内维匹配与结果形状检查在手写 Verifier 里（MiniRules.h）。
    第 56 天口径：操作数必须静态；结果维允许写 ?（待推导），
    是数字就必须等于期望的 [M,N]。

    ```mlir
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)";
}

// ---------- mini.add：bias 三分类在手写 Verifier（? 维保守放行） ----------
def Mini_AddOp : MiniOp<"add"> {
  let summary = "addition (bias shapes classified by hand)";
  let description = [{
    加法。右侧操作数相对左侧做形状三分类（第 40 天口径）：
    Same（同形，放行）/ BroadcastOnly（[N] 对 [M,N]，报「需要广播，
    第 60 天放行」）/ Mismatch（连广播都对不上）。结果类型必须等于 lhs。
    第 56 天口径：分类时把 ? 维视为「可能匹配」（第 39 天保守放行的
    延续）——真假留给 Shape 推导之后裁决。

    ```mlir
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let hasFolder = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)";
}

// ---------- mini.relu：形状保持，trait 留着 ----------
def Mini_ReluOp : MiniOp<"relu", [SameOperandsAndResultType]> {
  let summary = "elementwise relu";
  let arguments = (ins AnyType:$x);
  let results = (outs AnyType:$result);
  let assemblyFormat = "$x attr-dict `:` type($x)";
}

// ---------- mini.fused_add_relu：第 51 天的小融合目标 ----------
def Mini_FusedAddReluOp : MiniOp<"fused_add_relu"> {
  let summary = "fused add + relu";
  let description = [{
    res[m,n] = relu(lhs[m,n] + rhs[m,n])

    第 51 天定义。Pattern 管道里是「让位版」P51g 的目标：锚在 relu
    上，但 add 的操作数里有 matmul 乘积就收手。Verifier 规则与
    mini.add 相同（操作数 Same 分类放行，结果类型等于 lhs）。

    ```mlir
    %y = mini.fused_add_relu %x, %w : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)";
}

// ---------- mini.fused_matmul_bias：两算子大融合目标 ----------
def Mini_FusedMatmulBiasOp : MiniOp<"fused_matmul_bias"> {
  let summary = "fused matmul + bias add";
  let description = [{
    res[m,n] = sum_k lhs[m,k] * rhs[k,n] + bias[m,n]

    第 53 天定义。两阶段路线第一步的产物，也是半融合不动点
    （shared_result 负例最终停在这里 + 一个 relu）。
    语义 = 成员规则求并集（第 50 天的方法）。

    ```mlir
    %y = mini.fused_matmul_bias %a, %b, %bias :
         tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs, AnyType:$bias);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs `,` $bias attr-dict `:` type($lhs) `,` type($rhs) `,` type($bias) `->` type($res)";
}

// ---------- mini.fused_matmul_bias_relu：第 50 天定义的三算子目标 ----------
def Mini_FusedMatmulBiasReluOp : MiniOp<"fused_matmul_bias_relu"> {
  let summary = "fused matmul + bias add + relu";
  let description = [{
    res[m,n] = relu( sum_k lhs[m,k] * rhs[k,n] + bias[m,n] )

    第 50 天定义。两阶段路线第二步（P2 吸收 Relu）与直接三算子路线
    （P3 一步到位）的共同目标。Verifier 规则与 fused_matmul_bias
    完全一致（relu 是形状保持的，不贡献新规则）。

    ```mlir
    %y = mini.fused_matmul_bias_relu %a, %b, %bias :
         tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs, AnyType:$bias);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs `,` $bias attr-dict `:` type($lhs) `,` type($rhs) `,` type($bias) `->` type($res)";
}

#endif // MINI_OPS
