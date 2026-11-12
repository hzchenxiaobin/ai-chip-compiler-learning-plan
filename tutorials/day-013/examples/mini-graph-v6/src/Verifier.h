#pragma once

#include <string>
#include <vector>

class Graph;

// VerifyReport：验证报告。Verifier 不抛异常、不改图——
// 把一张图上的所有问题一次列全，交给调用方决定怎么办
//（打印、拒绝执行、打日志……）。一次列全而不是抛第一个，
// 是为了让「修一轮」能修完所有问题，而不是修一个跑一次。
struct VerifyReport {
    bool ok = true;
    std::vector<std::string> errors;

    void fail(const std::string& msg) {
        ok = false;
        errors.push_back(msg);
    }

    // 条件成立才记一笔，让检查代码读起来像一句话。
    void fail_if(bool cond, const std::string& msg) {
        if (cond) {
            fail(msg);
        }
    }
};

// 图级验证入口（第 12 天）：
//   1) 图级检查：输出表非空、无重复、值都属于本图；
//   2) 结构检查（逐节点）：kind 合法、输入非空、结果回指、值归属；
//   3) 语义检查（逐算子）：输入数量、Shape 兼容性、dtype 一致性、
//      结果类型——经 NodeVisitor 分发（第 11 天框架的第一个正式客户）；
//   4) 账本核对：use-def 双向一致性，双向各数一遍。
// 边界：环检测留给第 16 天的拓扑排序，今天不查。
// 对应 MLIR 的 Operation::verify() / verify()——解析之后、
// 每个 Pass 之后各跑一次。
VerifyReport verify_graph(const Graph& g);
