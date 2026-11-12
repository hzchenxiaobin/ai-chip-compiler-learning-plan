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
struct TopoSortResult;

// Graph：整张计算图的唯一所有人，也是 use-def 账本的唯一登记员。
// 第 9 天的四个工厂函数、第 10 天的改图入口（replace / erase）、
// 第 11 天的 Visitor 分发、第 12 天的 raw 后门原样保留；
// 第 16 天只加一个改图入口：
//   rewire_input —— 换掉节点的一个输入槽（账本同步搬家）。
// 一致性不变量（erase/replace/rewire 都必须保住它）：
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

    // ---- 造（第 12 天新增：不设防后门）----

    // 不做任何检查地造一个节点：不查 kind、不查空指针、不查输入数量、
    // 不查 Shape/dtype——连「输入必须非空」都放过（空槽跳过 use 登记，
    // 让节点能造出来，等 Verifier 点名）。
    // 为什么要有这样的入口：真实编译器的 IR 不只来自你自己的工厂——
    // 解析器读文本、Pass 改图、别的工具组装，都绕过你的检查（MLIR 的
    // OpBuilder::create 同样不跑 Verifier）。工厂是「带守卫的建造路径」，
    // 这里是「不设防的建造路径」；两条路汇合到同一个 Verifier。
    Node* add_raw_node(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                       TensorType result_type, std::string result_name);

    void mark_output(const Value* v);

    // ---- 改（第 10 天的入口）----

    // 把 from 的所有使用者改写成 to（类型必须完全一致）。
    // 只搬账本、改输入槽，不删除任何节点——删节点是 erase_node 的职责，
    // 两步分开正是第 45 天 Rewriter「先 replaceUses 再 eraseOp」的雏形。
    void replace_all_uses_of(const Value* from, const Value* to);

    // 删除节点 n，连同它的结果值一起归还。
    // 前提：结果已无任何使用者，且不是图输出；否则抛异常点名剩余使用者。
    // 删除后，指向该节点及其结果值的指针全部失效（同 MLIR eraseOp）。
    void erase_node(Node* n);

    // ---- 改（第 16 天新增：给未来的 Pass 用的手术刀）----

    // 把节点 n 的第 slot 个输入槽改指向 v，账本同步搬家
    //（旧值的记录注销、新值的记录登记——不变量保持）。
    // 刻意不做类型检查、不做环检查：这是「不设防的变换路径」，
    // 与 add_raw_node 同一份合同——Pass 负责 legality，Verifier
    // 兜结构类型，拓扑排序兜环（正是今天的主角）。它也让测试
    // 能亲手造出带环的图——工厂造不出环（只能引用已存在的值），
    // 环只会从「改图」里长出来。
    void rewire_input(Node* n, std::size_t slot, const Value* v);

    // ---- 查 ----

    const std::string& name() const noexcept { return name_; }
    std::int64_t num_values() const noexcept { return static_cast<std::int64_t>(values_.size()); }
    std::int64_t num_nodes() const noexcept { return static_cast<std::int64_t>(nodes_.size()); }
    const std::vector<const Value*>& inputs() const noexcept { return inputs_; }
    const std::vector<const Value*>& outputs() const noexcept { return outputs_; }
    const std::vector<std::unique_ptr<Node>>& nodes() const noexcept { return nodes_; }
    const std::vector<std::unique_ptr<Value>>& values() const noexcept { return values_; }

    // 拓扑排序（执行时间表）。第 16 天起改由 TopoSort 提供，
    // 本函数只是「要序号、不要诊断」的便捷外壳：
    // 图里有环时抛 std::invalid_argument，消息带完整环路径
    //（第 9 天的旧实现没有刹车——环图上会静默返回一个假序，
    // 那个洞正是今天要补的，见 bugs/err_silent_bogus_order.cpp）。
    std::vector<const Node*> topological_order() const;

    // 文本形式 IR：类型和属性都打印出来（第 9 天原样）。
    std::string to_string() const;

    // use 表：每个值的 def（生产者）与全部 use（使用者＋槽位）。教学/调试用。
    std::string uses_to_string() const;

private:
    // check_nulls = true：工厂路径，空指针当场抛（廉价检查）；
    // check_nulls = false：raw 路径，空槽照收，只是跳过 use 登记，
    // 让非法图能造出来，交给 Verifier 兜底。
    Node* make_node_impl(OpKind kind, std::vector<const Value*> inputs, Attrs attrs,
                         TensorType result_type, std::string result_name, bool check_nulls);

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
