#pragma once

#include <cstdint>
#include <string>

#include "TensorType.h"

class Node;

// Value：一次计算产出的「值」，也是图上的一条数据边。
// 相比第 8 天，多了 type_（dtype + shape）：值不仅有名字，还有类型。
// 类型记在 Value 上而不是 Node 上——它是「值」的性质；
// 一个节点将来有多个输出时，每个输出各带各的类型。
// 使用者列表（use-def）第 10 天才引入。
class Value {
public:
    Value(const Value&) = delete;
    Value& operator=(const Value&) = delete;

    std::int64_t id() const noexcept { return id_; }
    const std::string& name() const noexcept { return name_; }
    const TensorType& type() const noexcept { return type_; }

    // 生产者：nullptr 表示图输入（不来自任何节点）。
    // 借用指针：Value 不拥有 Node，析构时什么都不用做。
    Node* producer() const noexcept { return producer_; }

private:
    friend class Graph;
    Value(std::int64_t id, std::string name, TensorType type) noexcept
        : id_(id), name_(std::move(name)), type_(std::move(type)) {}

    std::int64_t id_;
    std::string name_;
    TensorType type_;
    Node* producer_ = nullptr;  // 由 Graph 在创建节点时挂上
};
