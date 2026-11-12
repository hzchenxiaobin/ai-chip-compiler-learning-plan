#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "TensorType.h"

class Node;

// 一条 Use 记录：哪个节点在使用、用在第几个输入槽。
// 只存 Node* 不够，有两个原因：
//   1) 替换时要知道该改写哪个槽位；
//   2) 同一个节点可以重复使用同一个值（如 add(%C, %C)），
//      那是两条独立的记录，不是一条。
struct Use {
    Node* user;           // 借用：使用者节点（所有权在 Graph）
    std::size_t operand;  // user 的第几个输入槽
};

// Value：一次计算产出的「值」，也是图上的一条数据边。
// 第 8 天：骨架；第 9 天：type_（dtype + shape）。
// 今天新增 uses_：使用者账本——use-def 关系的反向链。
//   def -> use 的正向链一直存在：Node::inputs_（节点消费了谁）；
//   use -> def 的反向链也一直存在：producer_（谁生产了我）；
//   今天补上的是 def -> use 的反向查询：谁在用我、用在哪个槽。
// uses_ 由 Graph 独占维护（造节点登记、删节点注销、替换搬家），
// 其余代码只能读——保证双向关系永远同步。
class Value {
public:
    Value(const Value&) = delete;
    Value& operator=(const Value&) = delete;

    std::int64_t id() const noexcept { return id_; }
    const std::string& name() const noexcept { return name_; }
    const TensorType& type() const noexcept { return type_; }

    // 生产者（def）：nullptr 表示图输入（不来自任何节点）。
    // 借用指针：Value 不拥有 Node，析构时什么都不用做。
    Node* producer() const noexcept { return producer_; }

    // 使用者（use）：只读视图。记录是借用，不含所有权。
    std::size_t num_uses() const noexcept { return uses_.size(); }
    bool has_uses() const noexcept { return !uses_.empty(); }
    const std::vector<Use>& users() const noexcept { return uses_; }

private:
    friend class Graph;
    Value(std::int64_t id, std::string name, TensorType type) noexcept
        : id_(id), name_(std::move(name)), type_(std::move(type)) {}

    std::int64_t id_;
    std::string name_;
    TensorType type_;
    Node* producer_ = nullptr;  // def：由 Graph 在创建节点时挂上
    std::vector<Use> uses_;     // use：今天新增，由 Graph 独占维护
};
