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

// Graph：整张计算图的唯一所有人，也是 use-def 账本的唯一登记员。
// 第 9 天的四个工厂函数原样保留；今天在「改图」这一侧开三个新入口：
//   replace_all_uses_of(from, to)：改写 from 的全部使用者（第 26 天 CSE、
//                                  第 45 天 RewritePattern 的底层原语）
//   erase_node(n)：删除节点及其结果值（第 25 天 DCE 的底层原语）
//   uses_to_string()：打印 use 表（今天的教学/调试工具）
// 一致性不变量（erase/replace 都必须保住它）：
//   节点 n 的第 i 个输入槽指向值 v  ⟺  v 的 uses_ 里恰有一条 (n, i)。
class Graph {
public:
    explicit Graph(std::string name) : name_(std::move(name)) {}

    Graph(const Graph&) = delete;
    Graph& operator=(const Graph&) = delete;
    Graph(Graph&&) noexcept = default;
    Graph& operator=(Graph&&) noexcept = default;

    // ---- 造（第 9 天原样）----

    Value* add_input(std::string name, TensorType type);

    Node* add_constant(std::string result_name, TensorType type, std::vector<double> data);

    Node* add_matmul(const Value* a, const Value* b, std::string result_name,
                     bool transpose_a = false, bool transpose_b = false);

    Node* add_elementwise(OpKind kind, const Value* x, const Value* y,
                          std::string result_name);

    Node* add_relu(const Value* x, std::string result_name);

    void mark_output(const Value* v);

    // ---- 改（今天的新入口）----

    // 把 from 的所有使用者改写成 to（类型必须完全一致）。
    // 只搬账本、改输入槽，不删除任何节点——删节点是 erase_node 的职责，
    // 两步分开正是第 45 天 Rewriter「先 replaceUses 再 eraseOp」的雏形。
    void replace_all_uses_of(const Value* from, const Value* to);

    // 删除节点 n，连同它的结果值一起归还。
    // 前提：结果已无任何使用者，且不是图输出；否则抛异常点名剩余使用者。
    // 删除后，指向该节点及其结果值的指针全部失效（同 MLIR eraseOp）。
    void erase_node(Node* n);

    // ---- 查 ----

    const std::string& name() const noexcept { return name_; }
    std::int64_t num_values() const noexcept { return static_cast<std::int64_t>(values_.size()); }
    std::int64_t num_nodes() const noexcept { return static_cast<std::int64_t>(nodes_.size()); }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }
    const std::vector<const Value*>& outputs() const noexcept { return outputs_; }
    const std::vector<std::unique_ptr<Node>>& nodes() const noexcept { return nodes_; }
    const std::vector<std::unique_ptr<Value>>& values() const noexcept { return values_; }

    std::vector<const Node*> topological_order() const;

    // 文本形式 IR：类型和属性都打印出来（第 9 天原样）。
    std::string to_string() const;

    // use 表：每个值的 def（生产者）与全部 use（使用者＋槽位）。教学/调试用。
    std::string uses_to_string() const;

private:
    Node* make_node(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                    TensorType result_type, std::string result_name);

    // 注销一条 use 记录：n 的第 operand 个槽不再使用 v。
    static void remove_use(Value* v, const Node* n, std::size_t operand);

    std::string name_;
    std::vector<std::unique_ptr<Value>> values_;  // 所有权：值
    std::vector<std::unique_ptr<Node>> nodes_;    // 所有权：节点
    std::vector<const Value*> inputs_;            // 借用：图输入表
    std::vector<const Value*> outputs_;           // 借用：图输出表
    std::int64_t next_value_id_ = 0;
    std::int64_t next_node_id_ = 0;
};
