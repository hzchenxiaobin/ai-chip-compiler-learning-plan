//===- MiniDialect.td - mini dialect ------------------------*- tablegen -*-===//
//
// mini 方言的"户口本"：只登记最基础的信息——
//   name         ：IR 文本里的前缀（mini.xxx 的 mini）
//   cppNamespace ：生成的 C++ 类放在哪个命名空间（::mini）
//   summary/description：给人看的说明
// 还没有任何算子；第一个算子 mini.matmul 在 Day 37 的 MiniOps.td 里定义。
//
//===----------------------------------------------------------------------===//

#ifndef MINI_DIALECT
#define MINI_DIALECT

include "mlir/IR/OpBase.td"

//===----------------------------------------------------------------------===//
// mini dialect 定义。
//===----------------------------------------------------------------------===//

def Mini_Dialect : Dialect {
    let name = "mini";
    let summary = "mini 编译器的张量算子方言";
    let description = [{
        mini 是本学习计划自定义的 MLIR 方言：先承载 MatMul、Add、Relu 等
        张量算子，再逐步长出 Shape 推导、融合与 Lowering 所需的能力。
    }];
    let cppNamespace = "::mini";
}

//===----------------------------------------------------------------------===//
// mini 算子的公共基类：姓 mini 的算子都从这里派生。
// Mnemonic 是不带姓的"名"（如 matmul），全名 = mini.matmul。
// 今天还没有算子用到它——Day 37 的 Mini_MatmulOp 是第一个。
//===----------------------------------------------------------------------===//

class Mini_Op<string mnemonic, list<Trait> traits = []> :
        Op<Mini_Dialect, mnemonic, traits>;

#endif // MINI_DIALECT
