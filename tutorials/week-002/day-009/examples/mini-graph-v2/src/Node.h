#pragma once

#include <cstdint>
#include <vector>

#include "Attrs.h"
#include "OpKind.h"

class Value;

// Node：一次运算。相比第 8 天有两处升级：
//   kind_   从 string 换成 OpKind（拼错 → 编译失败）；
//   attrs_  新增属性：编译期已知的元数据（常量值、transpose 标志）。
// 仍然只有一个类：MatMul / Add / Relu / Constant 不派生子类，
// 「每种算子特有的逻辑」放在 Graph 的工厂函数里（见 Graph.cpp）。
// 输入和结果依旧是借用，不拥有任何东西。
class Node {
public:
    Node(const Node&) = delete;
    Node& operator=(const Node&) = delete;

    std::int64_t id() const noexcept { return id_; }
    OpKind kind() const noexcept { return kind_; }
    const Attrs& attrs() const noexcept { return attrs_; }

    std::size_t num_inputs() const noexcept { return inputs_.size(); }
    const Value* input(std::size_t i) const noexcept { return inputs_[i]; }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }

    // 本节点生产的值（借用指针，所有权在 Graph 手里）。
    const Value* result() const noexcept { return result_; }

private:
    friend class Graph;
    Node(std::int64_t id, OpKind kind, std::vector<const Value*> inputs, Attrs attrs)
        : id_(id), kind_(kind), inputs_(std::move(inputs)), attrs_(std::move(attrs)) {}

    std::int64_t id_;
    OpKind kind_;
    std::vector<const Value*> inputs_;  // 数据依赖：借用，不拥有
    Attrs attrs_;                       // 属性：编译期常量元数据
    const Value* result_ = nullptr;     // Graph 创建后挂上
};
