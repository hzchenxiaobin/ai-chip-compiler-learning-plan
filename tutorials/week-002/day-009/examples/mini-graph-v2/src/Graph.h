#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "Attrs.h"
#include "OpKind.h"
#include "TensorType.h"

class Node;
class Value;

// Graph：整张计算图的唯一所有人（所有权结构同第 8 天，原样保留）。
// 今天的变化在「造节点」这一侧：
//   add_node(kind 字符串, ...)  →  四个带类型检查的工厂函数
//     add_constant / add_matmul / add_elementwise / add_relu
// 每个工厂算好结果的 TensorType 再调用私有的 make_node——
// 「算子特有逻辑」住在工厂里，而不是子类的虚函数里。
class Graph {
public:
    explicit Graph(std::string name) : name_(std::move(name)) {}

    Graph(const Graph&) = delete;
    Graph& operator=(const Graph&) = delete;
    Graph(Graph&&) noexcept = default;
    Graph& operator=(Graph&&) noexcept = default;

    // 图输入：没有生产者的值，类型由调用者声明。
    Value* add_input(std::string name, TensorType type);

    // constant：没有输入，常量值放在属性里。
    Node* add_constant(std::string result_name, TensorType type, std::vector<double> data);

    // matmul：[M,K] x [K,N] -> [M,N]，transpose 标志记录在属性里。
    Node* add_matmul(const Value* a, const Value* b, std::string result_name,
                     bool transpose_a = false, bool transpose_b = false);

    // 逐元素二元算子（今天是 Add；第 14 天的 Mul 可复用）。
    Node* add_elementwise(OpKind kind, const Value* x, const Value* y,
                          std::string result_name);

    // relu：一元逐元素。
    Node* add_relu(const Value* x, std::string result_name);

    void mark_output(const Value* v);

    const std::string& name() const noexcept { return name_; }
    std::int64_t num_values() const noexcept { return static_cast<std::int64_t>(values_.size()); }
    std::int64_t num_nodes() const noexcept { return static_cast<std::int64_t>(nodes_.size()); }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }
    const std::vector<const Value*>& outputs() const noexcept { return outputs_; }
    const std::vector<std::unique_ptr<Node>>& nodes() const noexcept { return nodes_; }

    std::vector<const Node*> topological_order() const;

    // 文本形式 IR：类型和属性都打印出来。
    std::string to_string() const;

private:
    // 通用构造路径：工厂们算好 result_type 后都走这里。
    Node* make_node(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                    TensorType result_type, std::string result_name);

    std::string name_;
    std::vector<std::unique_ptr<Value>> values_;  // 所有权：值
    std::vector<std::unique_ptr<Node>> nodes_;    // 所有权：节点
    std::vector<const Value*> inputs_;            // 借用：图输入表
    std::vector<const Value*> outputs_;           // 借用：图输出表
    std::int64_t next_value_id_ = 0;
    std::int64_t next_node_id_ = 0;
};
