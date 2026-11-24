//===- MiniDialect.td - mini dialect ------------------------*- tablegen -*-===//
//
// 第 36 天创建的方言骨架：只登记"户口本"（名字 mini、C++ 命名空间 ::mini），
// 还没有任何算子——第 37 天在 MiniOps.td 里给它添第一个算子 mini.matmul。
//
// 第 49 天（第 7 周复盘）修复：补上 hasConstantMaterializer = 1。
// 复盘时把本周代码放到真实的 MLIR 18 环境下编译，MiniDialect.cpp 里
// 第 47 天写的 materializeConstant 定义立刻报错：
//   error: no declaration matches 'mlir::Operation*
//          mini::MiniDialect::materializeConstant(...)'
// 原因：materializeConstant 是基类 Dialect 的虚函数，C++ 规定
// "类外定义"必须对应"本类里声明的"成员——MiniDialect 只继承了它，
// 没有声明它，类外定义就无处安放。声明不能手写（类由 .inc 生成），
// 唯一入口就是 TableGen：Dialect 基类提供 hasConstantMaterializer
// 开关，置 1 后 mlir-tblgen 会在生成的 MiniDialect 类里声明
//   Operation *materializeConstant(OpBuilder&, Attribute, Type,
//                                  Location) override;
// MiniDialect.cpp 的类外定义从此有了对应的声明。
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

    // 第 49 天：声明"本方言提供常量物化钩子"。tblgen 由此在
    // MiniDialect 类里生成 materializeConstant 的声明（见文件头注释）。
    let hasConstantMaterializer = 1;
}

//===----------------------------------------------------------------------===//
// mini 算子的公共基类：姓 mini 的算子都从这里派生。
// Mnemonic 是不带姓的"名"（如 matmul），全名 = mini.matmul。
//===----------------------------------------------------------------------===//

class Mini_Op<string mnemonic, list<Trait> traits = []> :
        Op<Mini_Dialect, mnemonic, traits>;

#endif // MINI_DIALECT
