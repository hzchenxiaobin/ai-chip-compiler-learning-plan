#ifndef MINI_OPS
#define MINI_OPS

// 第 53 天的 ODS 壳：在第 51/52 天的 add / relu / fused_add_relu 基础上，
// 为 MatMul + Bias 融合补齐五个算子。与第 51/52 天的两点不同：
//
//   1. mini.matmul 的操作数 (M,K)·(K,N) 和结果 (M,N) 形状不同，
//      汇编格式必须把三个类型都显式打印出来；
//   2. mini.add 摘掉了 SameOperandsAndResultType —— bias 的形状三分类
//      （Same / BroadcastOnly / Mismatch，第 40 天口径）必须在 Verifier 里
//      自己开口说话，trait 只会干巴巴地报「类型不相等」。
//      mini.relu 没有第二个操作数、形状保持不变，trait 留着正合适。

include "mlir/IR/OpBase.td"
include "mlir/Interfaces/InferTypeOpInterface.td"

def Mini_Dialect : Dialect {
  let name = "mini";
  let cppNamespace = "::mini";
  let summary = "学习计划第 8 周使用的 mini Dialect（融合实验最小子集）";
  let description = [{
    第 53 天版本：matmul / add / relu / fused_matmul_bias / fused_matmul_bias_relu。
    本壳限定 rank-2 静态 f32 张量（完整 matmul 规则见第 37/39 天的 mini 工程）。
  }];
}

class MiniOp<string mnemonic, list<Trait> traits = []> :
    Op<Mini_Dialect, mnemonic, traits>;

// ---------- mini.matmul：MxK · KxN -> MxN ----------
def Mini_MatmulOp : MiniOp<"matmul"> {
  let summary = "matrix multiplication";
  let description = [{
    两个 rank-2 静态 f32 张量相乘：lhs 是 MxK，rhs 是 KxN，结果是 MxN。
    内维匹配与结果形状检查在手写 Verifier 里（MiniRules.h）。

    ```mlir
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$res);
  let assemblyFormat =
    "$lhs `,` $rhs attr-dict `:` type($lhs) `,` type($rhs) `->` type($res)";
}

// ---------- mini.add：本日摘掉 SameOperandsAndResultType ----------
def Mini_AddOp : MiniOp<"add"> {
  let summary = "addition (bias shapes classified by hand)";
  let description = [{
    加法。右侧操作数相对左侧做形状三分类（第 40 天口径）：
    Same（同形，放行）/ BroadcastOnly（[N] 对 [M,N]，报「需要广播，
    第 60 天放行」）/ Mismatch（连广播都对不上）。结果类型必须等于 lhs。

    ```mlir
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    ```
  }];
  let hasVerifier = 1;
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

// ---------- mini.fused_matmul_bias：今天新定义的两算子融合目标 ----------
def Mini_FusedMatmulBiasOp : MiniOp<"fused_matmul_bias"> {
  let summary = "fused matmul + bias add";
  let description = [{
    res[m,n] = sum_k lhs[m,k] * rhs[k,n] + bias[m,n]

    第 53 天定义：MatMul + Add 的两算子融合目标。语义 = 成员规则求并集
    （第 50 天的方法）：matmul 的三条（内维匹配、结果 [M,N]、f32）加
    bias 一条（与结果同形；[N] 向量报「需要广播，第 60 天放行」）。

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

    第 50 天定义的老朋友，今天第一次被 Pattern 生成：加法结果的唯一
    使用者是 mini.relu 时，Relu 直接被吸收进来。Verifier 规则与
    fused_matmul_bias 完全一致（relu 是形状保持的，不贡献新规则）。

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
