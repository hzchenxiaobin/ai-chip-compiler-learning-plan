// 反面教材（第 16 天错误一）：没有刹车的拓扑排序——旧实现在环图上静默返回假序。
// 现场模拟：用 rewire 手滑造出一个 2 环，然后跑「第 9 天写下的旧算法」
//（从 mini-graph-v7 的 Graph::topological_order 原样拷贝，逻辑一行未改，
//  只是从成员函数改成了自由函数——Graph 的公开接口足够它工作）。
// 三个观察点：
//   1) 旧算法不报错：它「排」出 relu 在 add 前面的顺序——relu 的输入 %D
//      是 add 的产物，生产者排到了使用者后面，这是一份假拓扑序；
//   2) 同一张图，v8 的 TopoSort 当场拒绝，并画出环路径
//      add%n2 -> relu%n3 -> add%n2；
//   3) 假序的下游后果（在本仓库第 14 天的 v7 工程上实测，
//      见正文第 6 节）：解释器按假序执行，读到没算好的值时只会报
//      「%D 没有数据（输入未绑定？）」——把「图有环」伪装成「忘绑输入」。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp \
//     ../src/Frontend.cpp ../src/TopoSort.cpp err_silent_bogus_order.cpp \
//     -o err_silent_bogus_order && ./err_silent_bogus_order; echo "exit code: $?"
#include <cstdio>
#include <functional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "Graph.h"
#include "Node.h"
#include "OpKind.h"
#include "TopoSort.h"
#include "Value.h"

namespace {

// ===== 原样拷贝自 mini-graph-v7 的 Graph::topological_order =====
// 第 9 天的实现：记忆化的 DFS，访问过的直接返回——没有「在途」状态，
// 所以绕回自己的边（环）被当成「已经访问过」，一声不吭。
std::vector<const Node*> legacy_topological_order(const Graph& g) {
    std::vector<const Node*> order;
    std::unordered_set<const Node*> visited;

    std::function<void(const Node*)> visit = [&](const Node* n) {
        if (!visited.insert(n).second) {
            return;
        }
        for (const Value* in : n->inputs()) {
            if (const Node* producer = in->producer()) {
                visit(producer);
            }
        }
        order.push_back(n);
    };
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        visit(n.get());
    }
    return order;
}

// 检查一份序是否真是拓扑序：每条「生产者 → 使用者」边都得从左往右。
// 返回违例条数并逐条打印。
int audit_order(const Graph& g, const std::vector<const Node*>& order) {
    std::unordered_map<const Node*, std::size_t> pos;
    for (std::size_t i = 0; i < order.size(); ++i) {
        pos.emplace(order[i], i);
    }
    int bad = 0;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (const Value* in : n->inputs()) {
            if (in == nullptr || in->producer() == nullptr) {
                continue;
            }
            if (pos[in->producer()] >= pos[n.get()]) {
                std::printf("    违例: %s%%n%lld 的输入 %%%s 由 %s%%n%lld 生产，"
                            "但它排在前面\n",
                            op_name(n->kind()).c_str(), static_cast<long long>(n->id()),
                            in->name().c_str(), op_name(in->producer()->kind()).c_str(),
                            static_cast<long long>(in->producer()->id()));
                ++bad;
            }
        }
    }
    return bad;
}

}  // namespace

int main() {
    // 经典链 + 一次手滑：add 的 bias 槽改接 %R——2 环。
    Graph g("two-node-cycle");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "R");
    g.mark_output(relu->result());
    g.rewire_input(add, 1, relu->result());

    std::printf("旧算法（v7 原样拷贝）在这个 2 环图上：\n");
    const std::vector<const Node*> legacy = legacy_topological_order(g);
    std::printf("  给出的序:");
    for (const Node* n : legacy) {
        std::printf(" %s%%n%lld", op_name(n->kind()).c_str(), static_cast<long long>(n->id()));
    }
    std::printf("\n  审计这份序：\n");
    const int bad = audit_order(g, legacy);
    std::printf("  违例 %d 条——这不是拓扑序，但旧算法一声不吭\n", bad);

    std::printf("\n新算法（v8 TopoSort）在同一张图上：\n");
    const TopoSortResult r = topo_sort(g);
    std::printf("  ok = 0\n");
    std::printf("  诊断: %s\n", topo_error_message(g, r).c_str());
    return 0;
}
