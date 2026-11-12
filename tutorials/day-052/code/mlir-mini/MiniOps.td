#ifndef MINI_OPS
#define MINI_OPS

include "mlir/IR/OpBase.td"
include "mlir/Interfaces/InferTypeOpInterface.td"

def Mini_Dialect : Dialect {
  let name = "mini";
  let cppNamespace = "::mini";
  let summary = "学习计划第 8 周使用的 mini Dialect（融合实验最小子集）";
  let description = [{
    只包含本教程需要的三个算子：add、relu、fused_add_relu。
  }];
}

class MiniOp<string mnemonic, list<Trait> traits = []> :
    Op<Mini_Dialect, mnemonic, traits>;

def Mini_AddOp : MiniOp<"add", [SameOperandsAndResultType]> {
  let summary = "elementwise add";
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$result);
  let assemblyFormat = "$lhs `,` $rhs attr-dict `:` type($lhs)";
}

def Mini_ReluOp : MiniOp<"relu", [SameOperandsAndResultType]> {
  let summary = "elementwise relu";
  let arguments = (ins AnyType:$x);
  let results = (outs AnyType:$result);
  let assemblyFormat = "$x attr-dict `:` type($x)";
}

def Mini_FusedAddReluOp : MiniOp<"fused_add_relu", [SameOperandsAndResultType]> {
  let summary = "fused elementwise add + relu";
  let arguments = (ins AnyType:$lhs, AnyType:$rhs);
  let results = (outs AnyType:$result);
  let assemblyFormat = "$lhs `,` $rhs attr-dict `:` type($lhs)";
}

#endif // MINI_OPS
