//===- MiniDialect.td - mini dialect ------------------------*- tablegen -*-===//
//
// 第 36 天创建的方言骨架：只登记"户口本"（名字 mini、C++ 命名空间 ::mini），
// 还没有任何算子——第 37 天在 MiniOps.td 里给它添第一个算子 mini.matmul。
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
//===----------------------------------------------------------------------===//

class Mini_Op<string mnemonic, list<Trait> traits = []> :
        Op<Mini_Dialect, mnemonic, traits>;

#endif // MINI_DIALECT
