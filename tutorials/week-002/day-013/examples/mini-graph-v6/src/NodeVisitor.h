#pragma once

#include "Node.h"

// NodeVisitor：只读访问者的接口（第 11 天）。
// 想对图上每种算子做一件新事情（打印、统计、检查……），就从它派生
// 一个类、实现四个 visit——不碰 Node、不碰 Graph、不碰解释器。
// 接口只给 const Node&：访问者天然只读，想改图请走 Graph 的改图入口。
class NodeVisitor {
public:
    virtual ~NodeVisitor() = default;

    virtual void visit_constant(const Node& n) = 0;
    virtual void visit_matmul(const Node& n) = 0;
    virtual void visit_add(const Node& n) = 0;
    virtual void visit_relu(const Node& n) = 0;
};

// 唯一的 kind → visit 分发入口。整个工程只有这一个 switch 负责
// 「按算子类型选动作」的分发（op_name 的 switch 只是把枚举变字符串）。
// 故意不写 default：
//   1) -Wswitch 会在新增算子、忘记加 case 时报警；
//   2) 一旦给 NodeVisitor 补上新的纯虚 visit_xxx，所有漏实现的
//      访问者立刻变成抽象类，编译器逐个点名——这就是我们用
//      「编译错误」换「运行期静默漏改」的地方。
inline void apply_visitor(NodeVisitor& v, const Node& n) {
    switch (n.kind()) {
        case OpKind::Constant: v.visit_constant(n); break;
        case OpKind::MatMul:   v.visit_matmul(n);   break;
        case OpKind::Add:      v.visit_add(n);      break;
        case OpKind::Relu:     v.visit_relu(n);     break;
    }
}
