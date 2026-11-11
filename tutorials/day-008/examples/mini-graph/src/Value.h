#pragma once

#include <cstdint>
#include <string>

class Node;

// Value：一次计算产出的「值」，也是图上的一条数据边。
// 今天的最小能力：编号、名字、生产者（回指，借用）。
// 使用者列表（use-def）第 10 天才引入。
class Value {
public:
    Value(const Value&) = delete;
    Value& operator=(const Value&) = delete;

    std::int64_t id() const noexcept { return id_; }
    const std::string& name() const noexcept { return name_; }

    // 生产者：nullptr 表示图输入（不来自任何节点）。
    // 借用指针：Value 不拥有 Node，析构时什么都不用做。
    Node* producer() const noexcept { return producer_; }

private:
    friend class Graph;
    Value(std::int64_t id, std::string name) noexcept
        : id_(id), name_(std::move(name)) {}

    std::int64_t id_;
    std::string name_;
    Node* producer_ = nullptr;  // 由 Graph 在创建节点时挂上
};
