#pragma once

#include <cstdint>
#include <string>
#include <vector>

class Value;

// Node：一次运算。它只「借用」输入值和结果值，不拥有任何东西。
// kind 今天只是字符串占位（"add"、"relu"…），第 9 天换成真正的算子类型和属性。
class Node {
public:
    Node(const Node&) = delete;
    Node& operator=(const Node&) = delete;

    std::int64_t id() const noexcept { return id_; }
    const std::string& kind() const noexcept { return kind_; }

    std::size_t num_inputs() const noexcept { return inputs_.size(); }
    const Value* input(std::size_t i) const noexcept { return inputs_[i]; }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }

    // 本节点生产的值（借用指针，所有权在 Graph 手里）。
    const Value* result() const noexcept { return result_; }

private:
    friend class Graph;
    Node(std::int64_t id, std::string kind, std::vector<const Value*> inputs)
        : id_(id), kind_(std::move(kind)), inputs_(std::move(inputs)) {}

    std::int64_t id_;
    std::string kind_;
    std::vector<const Value*> inputs_;  // 数据依赖：借用，不拥有
    const Value* result_ = nullptr;     // Graph 创建后挂上
};
