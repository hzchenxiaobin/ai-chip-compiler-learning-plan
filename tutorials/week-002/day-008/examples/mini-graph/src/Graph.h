#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

class Node;
class Value;

// Graph：整张计算图的唯一所有人。
// - 拥有所有 Value 和所有 Node（unique_ptr，拷贝被删除）；
// - inputs_/outputs_ 里的指针只是借用。
// 数据依赖（节点 → 输入值）与所有权（Graph → 节点/值）是两种箭头。
class Graph {
public:
    explicit Graph(std::string name) : name_(std::move(name)) {}

    Graph(const Graph&) = delete;
    Graph& operator=(const Graph&) = delete;
    Graph(Graph&&) noexcept = default;
    Graph& operator=(Graph&&) noexcept = default;

    // 图输入：没有生产者的值。
    Value* add_input(std::string name);

    // 新建一个节点：inputs 是它借用的输入值，result_name 是它生产的新值。
    Node* add_node(std::string kind, std::vector<const Value*> inputs,
                   std::string result_name);

    // 把某个值标记为图输出。标记两次会重复出现——Verifier 第 12 天再管。
    void mark_output(const Value* v);

    const std::string& name() const noexcept { return name_; }
    std::int64_t num_values() const noexcept { return static_cast<std::int64_t>(values_.size()); }
    std::int64_t num_nodes() const noexcept { return static_cast<std::int64_t>(nodes_.size()); }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }
    const std::vector<const Value*>& outputs() const noexcept { return outputs_; }
    const std::vector<std::unique_ptr<Node>>& nodes() const noexcept { return nodes_; }

    // 拓扑序（DFS 后序）：依赖一定排在自己前面。
    // 今天不做环检测：这个 API 只能引用已存在的值，天生造不出环；
    // 第 16 天处理一般图的拓扑排序与报环。
    std::vector<const Node*> topological_order() const;

    // 文本形式 IR（第 13 天会把它做成正式输出）。
    std::string to_string() const;

private:
    std::string name_;
    std::vector<std::unique_ptr<Value>> values_;  // 所有权：值
    std::vector<std::unique_ptr<Node>> nodes_;     // 所有权：节点
    std::vector<const Value*> inputs_;             // 借用：图输入
    std::vector<const Value*> outputs_;            // 借用：图输出
    std::int64_t next_value_id_ = 0;
    std::int64_t next_node_id_ = 0;
};
