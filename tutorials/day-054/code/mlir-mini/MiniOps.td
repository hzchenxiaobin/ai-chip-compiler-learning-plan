#ifndef MINI_OPS
#define MINI_OPS

// 第 54 天的 ODS 壳：在第 53 天的五个算子（matmul / add / relu /
// fused_matmul_bias / fused_matmul_bias_relu）基础上，把第 51 天的
// fused_add_relu 也接进来——今天要演示「第 51 天的 Pattern 和第 53 天的
// Pattern 放进同一个管道后，最终形态由谁决定」，所以两个家族的融合目标
// 必须同时在场。
//
//   两个家族的关系（抢跑事故的主角）：
//     小融合  mini.fused_add_relu         res = relu(lhs + rhs)
//     大融合  mini.fused_matmul_bias(_relu)  res = relu(lhs·rhs + bias)
//   对同一张 MatMul -> Add -> Relu 图，两者都能给出合法但不同的最终形态。

include "mlir/IR/OpBase.td"
include "mlir/Interfaces/InferTypeOpInterface.td"

def Mini_Dialect : Dialect {
  let name = "mini";
  let cppNamespace = "::mini";
  let summary = "学习计划第 8 周使用的 mini Dialect（融合实验最小子集）";
  let description = [{
    第 54 天版本：matmul / add / relu / fused_add_relu / fused_matmul_bias /
    fused_matmul_bias_relu。本壳限定 rank-2 静态 f32 张量。
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

// ---------- mini.fused_add_relu：第 51 天的小融合目标，今天回到场上 ----------
def Mini_FusedAddReluOp : MiniOp<"fused_add_relu"> {
  let summary = "fused add + relu";
  let description = [{
    res[m,n] = relu(lhs[m,n] + rhs[m,n])

    第 51 天定义（当天教程的主角），今天客串「抢跑者」：它锚在 relu 上，
    和锚在 add 上的大融合 Pattern 抢同一对 Add+Relu 邻居。Verifier 规则
    与 mini.add 相同（操作数 Same 分类放行，结果类型等于 lhs）。

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

// ---------- mini.fused_matmul_bias：两算子大融合目标（两阶段第一步的产物） ----------
def Mini_FusedMatmulBiasOp : MiniOp<"fused_matmul_bias"> {
  let summary = "fused matmul + bias add";
  let description = [{
    res[m,n] = sum_k lhs[m,k] * rhs[k,n] + bias[m,n]

    第 53 天定义。今天是「两阶段路线」第一步的产物：P1 把 MatMul+Add
    融到这里，第二步（P2）再把 Relu 吸收成 fused_matmul_bias_relu。
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

    第 50 天定义。今天是「两阶段路线」第二步的产物（P2 吸收 Relu），
    也是「直接三算子」路线（P3）一步到位的目标。Verifier 规则与
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
