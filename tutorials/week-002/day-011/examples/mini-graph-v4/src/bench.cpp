#include "bench.h"

#include <memory>

#include "Graph.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpKind.h"
#include "Value.h"

// 对照组：switch 直接分发。每种 kind 加不同的权（防编译器把四个
// case 合并成一个），返回加权总数——同时兼作正确性检查。
std::int64_t bench_switch(const Graph& g, int reps) {
    std::int64_t total = 0;
    for (int r = 0; r < reps; ++r) {
        for (const std::unique_ptr<Node>& np : g.nodes()) {
            const Node* n = np.get();
            switch (n->kind()) {
                case OpKind::Constant: total += 1; break;
                case OpKind::MatMul:   total += 2; break;
                case OpKind::Add:      total += 3; break;
                case OpKind::Relu:     total += 4; break;
            }
        }
    }
    return total;
}

// 实验组：apply_visitor → 虚函数动态分发。
// 这里只能看到 NodeVisitor&，动态类型不可知 → 无法去虚化。
void bench_visitor(const Graph& g, NodeVisitor& v, int reps) {
    for (int r = 0; r < reps; ++r) {
        for (const std::unique_ptr<Node>& np : g.nodes()) {
            apply_visitor(v, *np);
        }
    }
}
