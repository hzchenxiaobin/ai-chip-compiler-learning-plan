#include "Graph.h"

#include <functional>
#include <stdexcept>
#include <utility>

#include "Node.h"
#include "Value.h"

Value* Graph::add_input(std::string name) {
    // make_unique 无法调用 private 构造（friend 不会传递给它），
    // 所以由唯一所有人 Graph 亲自 new——友元关系恰好覆盖这一行。
    std::unique_ptr<Value> value(new Value(next_value_id_++, std::move(name)));
    Value* raw = value.get();
    values_.push_back(std::move(value));
    inputs_.push_back(raw);
    return raw;
}

Node* Graph::add_node(std::string kind, std::vector<const Value*> inputs,
                      std::string result_name) {
    // 今天的廉价检查：只拒绝空指针。值是否真的属于本图，第 12 天 Verifier 再管。
    for (std::size_t i = 0; i < inputs.size(); ++i) {
        if (inputs[i] == nullptr) {
            throw std::invalid_argument("add_node: 第 " + std::to_string(i) +
                                        " 个输入是空指针");
        }
    }

    // 1) 先造结果值，再造节点——两样都归图所有，地址从此稳定；
    // 2) 节点借用结果、结果回指生产者（双向借用，不构成所有权环）。
    std::unique_ptr<Value> result(new Value(next_value_id_++, std::move(result_name)));
    std::unique_ptr<Node> node(new Node(next_node_id_++, std::move(kind),
                                        std::move(inputs)));
    node->result_ = result.get();
    result->producer_ = node.get();

    Node* raw = node.get();
    values_.push_back(std::move(result));
    nodes_.push_back(std::move(node));
    return raw;
}

void Graph::mark_output(const Value* v) {
    if (v == nullptr) {
        throw std::invalid_argument("mark_output: 输出是空指针");
    }
    outputs_.push_back(v);
}

std::vector<const Node*> Graph::topological_order() const {
    std::vector<const Node*> order;
    std::vector<char> visited(static_cast<std::size_t>(num_nodes()), 0);

    // DFS 后序：先把输入的依赖走完，再记录自己 → 依赖一定排在前面。
    std::function<void(const Node*)> visit = [&](const Node* n) {
        if (visited[static_cast<std::size_t>(n->id())]) {
            return;
        }
        visited[static_cast<std::size_t>(n->id())] = 1;
        for (const Value* in : n->inputs()) {
            if (const Node* producer = in->producer()) {
                visit(producer);
            }
        }
        order.push_back(n);
    };
    for (const std::unique_ptr<Node>& n : nodes_) {
        visit(n.get());
    }
    return order;
}

std::string Graph::to_string() const {
    std::string text = "graph \"" + name_ + "\" (" + std::to_string(inputs_.size()) +
                       " inputs, " + std::to_string(outputs_.size()) + " outputs) {\n";
    for (const Value* v : inputs_) {
        text += "  %" + v->name() + " = input\n";
    }
    for (const std::unique_ptr<Node>& n : nodes_) {
        text += "  %n" + std::to_string(n->id()) + " = " + n->kind() + "(";
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (i != 0) {
                text += ", ";
            }
            text += "%" + n->input(i)->name();
        }
        text += ") -> %" + n->result()->name() + "\n";
    }
    for (const Value* v : outputs_) {
        text += "  output %" + v->name() + "\n";
    }
    text += "}";
    return text;
}
