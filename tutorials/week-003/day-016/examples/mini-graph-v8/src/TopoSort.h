#pragma once

#include <cstdint>
#include <string>
#include <vector>

class Graph;
class Node;

// TopoSort（第 16 天的主角）：拓扑排序 ＋ 环检测 ＋ 执行波次。
//
// 输入：一张计算图（第 8～14 天的 Graph）。
// 输出：TopoSortResult——成功时给出拓扑序与波次；失败时给出环路径。
//
// 它是「分析」而不是「变换」：只读图、不改图（第 20 天会把分析
// 与变换 Pass 正式分开，今天先按这个纪律写）。解释器、拓扑打印、
// 第 99～100 天的内存规划都吃它的输出。
//
// 三个前置假设（Verifier 第 12 天查过的，这里不越权代查）：
//   1) 每个输入值要么是图输入，要么生产者属于本图（值归属）；
//   2) 输入槽非空指针（空槽是非法图）；
//   3) use 账本与输入槽一致（账本核对）。
// 对不满足 1 的图，本算法宁可拒绝（报「无法调度」），绝不悄悄
// 给出一个错误的顺序——诊断见 topo_error_message 的第二种分支。
struct TopoSortResult {
    bool ok = true;

    // ok = true：完整拓扑序（波次顺序拼接，波内按创建序）；
    // ok = false：已经剥下的「部分序」——排在前面的前缀仍可用作诊断。
    std::vector<const Node*> order;

    // 执行波次：第 k 波里的节点只依赖前 k-1 波，彼此互不依赖——
    // 同一波可以并行执行。波数 = 图的关键路径深度（最长依赖链长度）。
    // ok = false 时 waves 只含剥下的前缀，最后一波之后就是卡住的地方。
    std::vector<std::vector<const Node*>> waves;

    // ok = false 时：若找到环，存环路径（首尾是同一个节点，如
    // [n2, n3, n2]）；若因依赖了不属于本图的节点而卡住，则为空。
    std::vector<const Node*> cycle;

    std::int64_t peeled = 0;  // 成功剥下（进入 order）的节点数
    std::int64_t stuck = 0;   // 剥不动（依赖成环或缺失）的节点数
};

// 拓扑排序主入口（Kahn 算法的波次变体，见 TopoSort.cpp）。
TopoSortResult topo_sort(const Graph& g);

// 环路径打印成 "add%n2 -> relu%n3 -> add%n2"（首尾同节点）。
std::string cycle_to_string(const std::vector<const Node*>& cycle);

// 把失败结果翻译成一句人话诊断：
//   含环：给出环路径、环长、已剥/卡住计数；
//   依赖缺失（Verifier 应已拦下）：只给计数，不冒充环检测。
std::string topo_error_message(const Graph& g, const TopoSortResult& r);
