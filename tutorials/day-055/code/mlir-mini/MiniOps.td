#ifndef MINI_OPS
#define MINI_OPS

// 第 55 天复用第 54 天的 ODS 壳：六个算子原样保留（matmul / add / relu /
// fused_add_relu / fused_matmul_bias / fused_matmul_bias_relu）。
// 今天不造新算子——总验收的对象是「现有 Pattern 集在全部正负例上的
// 行为」，需要两个融合家族的成员同时在场：
//
//   小融合  mini.fused_add_relu         res = relu(lhs + rhs)
//   大融合  mini.fused_matmul_bias(_relu)  res = relu(lhs·rhs + bias)
//
// 验收语料里的负例会用到 f64 / 混合 dtype / 错形状——这些都过不了
// 下方 Verifier 或 Pattern 闸门，正是今天要观察的判决。

include "mlir/IR/OpBase.td"
include "mlir/Interfaces/InferTypeOpInterface.td"

def Mini_Dialect : Dialect {
  let name = "mini";
  let cppNamespace = "::mini";
  let summary = "学习计划第 8 周使用的 mini Dialect（融合实验最小子集）";
  let description = [{
    第 55 天版本（与第 54 天同壳）：matmul / add / relu / fused_add_relu /
    fused_matmul_bias / fused_matmul_bias_relu。本壳限定 rank-2 静态 f32 张量
    （f64 等类型由 Verifier / Pattern 闸门拦下，是今天的负例主角）。
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

// ---------- mini.add：不带 SameOperandsAndResultType（bias 三分类在手写 Verifier） ----------
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

// ---------- mini.fused_add_relu：第 51 天的小融合目标 ----------
def Mini_FusedAddReluOp : MiniOp<"fused_add_relu"> {
  let summary = "fused add + relu";
  let description = [{
    res[m,n] = relu(lhs[m,n] + rhs[m,n])

    第 51 天定义。今天的验收管道里它是「让位版」P51g 的目标：锚在 relu
    上，但 add 的操作数里有 matmul 乘积就收手。Verifier 规则与 mini.add
    相同（操作数 Same 分类放行，结果类型等于 lhs）。

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

    第 53 天定义。今天是「两阶段路线」第一步的产物，也是半融合不动点
    （shared_result 负例最终停在这里 + 一个 relu）。语义 = 成员规则求并集
    （第 50 天的方法）。

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
