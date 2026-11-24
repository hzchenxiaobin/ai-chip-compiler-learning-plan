// 反面教材（第 16 天错误三）：拓扑序是「派生视图」——缓存它跨过一次改图。
// 现场模拟：调度器先排好时间表（缓存 order），随后某个 Pass 删掉一个
// 死节点；调度器继续用旧时间表执行——旧序里还躺着被删节点的指针。
// 三个观察点：
//   1) ASan 抓得干净利落：heap-use-after-free，读的正是被 erase 的节点
//      ——erase 之后，指向它的指针全部失效（第 10 天就写在合同里）；
//   2) 不开 ASan 时可能悄悄跑过（内存还没被复用）——这正是它阴险的地方：
//      错误的引用不立刻爆，改天换张图、换个分配顺序才爆；
//   3) 修复：拓扑序是「图在当前状态下的推导结果」，改图（replace /
//      rewire / erase）之后必须重排——第 20 天「分析结果失效」的
//      第一课，第 15 天「前驱表是派生视图」同一个道理。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp \
//     ../src/Frontend.cpp ../src/TopoSort.cpp err_stale_topo_cache.cpp \
//     -o err_stale_topo_cache && ./err_stale_topo_cache; echo "exit code: $?"
#include <cstdio>
#include <vector>

#include "Graph.h"
#include "Node.h"
#include "OpKind.h"
#include "Value.h"

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);  // 崩溃前的叙述不被缓冲吞掉

    Graph g("stale-cache");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "R");
    g.mark_output(relu->result());
    Node* dead = g.add_relu(mm->result(), "dead");  // 死节点：没人用、不是输出

    // 调度器排好时间表……
    std::vector<const Node*> schedule = g.topological_order();
    std::printf("排好的时间表（%zu 个节点）:", schedule.size());
    for (const Node* n : schedule) {
        std::printf(" %s%%n%lld", op_name(n->kind()).c_str(), static_cast<long long>(n->id()));
    }
    std::printf("\n");

    // ……随后一个 Pass 删掉了死节点（合法操作：结果无使用者）。
    const long long dead_id = dead->id();  // erase 之后不许再碰 dead——先记下编号
    g.erase_node(dead);
    std::printf("Pass 删除死节点 dead%%n%lld 后，图里剩 %lld 个节点——但缓存的时间表没重排\n",
                dead_id, static_cast<long long>(g.num_nodes()));

    // 调度器继续用旧时间表——第 5 项指向已经归还的节点。
    std::printf("调度器按旧时间表执行:\n");
    for (std::size_t i = 0; i < schedule.size(); ++i) {
        const Node* n = schedule[i];  // ← i == 4 时是悬垂指针
        std::printf("  step %zu: %s%%n%lld writes %%%s\n", i + 1,
                    op_name(n->kind()).c_str(), static_cast<long long>(n->id()),
                    n->result()->name().c_str());  // ASan 在这里开火
    }
    std::printf("竟然安全走完了？——没开 ASan 或者内存没被复用时的假象\n");
    return 0;
}
