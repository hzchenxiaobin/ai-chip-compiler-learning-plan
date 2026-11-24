#include <cstdio>
#include <string>

#include "Graph.h"
#include "Node.h"
#include "Value.h"

int main() {
    Graph g("add-relu");

    // 贯穿全文的例子：y = relu(a + b)
    Value* a = g.add_input("a");
    Value* b = g.add_input("b");
    Node* add = g.add_node("add", {a, b}, "t");
    Node* relu = g.add_node("relu", {add->result()}, "y");
    g.mark_output(relu->result());

    std::printf("== 一张 a,b -> add -> relu 的小图 ==\n%s\n\n", g.to_string().c_str());

    // 拓扑序：依赖一定排在自己前面。
    std::printf("== 拓扑序（DFS 后序） ==\n  ");
    for (const Node* n : g.topological_order()) {
        std::printf("n%lld(%s) ", static_cast<long long>(n->id()), n->kind().c_str());
    }
    std::printf("\n\n");

    // 结构观察：数据依赖双向可查（节点 -> 输入值 / 值 -> 生产者）。
    std::printf("== 数据依赖的三个事实 ==\n");
    std::printf("  add 的输入：%s, %s\n",
                add->input(0)->name().c_str(), add->input(1)->name().c_str());
    std::printf("  %%t 的生产者：n%lld(%s)\n",
                static_cast<long long>(add->result()->producer()->id()),
                add->result()->producer()->kind().c_str());
    std::printf("  relu 的输入 %%t：来自节点 n%lld，不是 relu 自己\n",
                static_cast<long long>(relu->input(0)->producer()->id()));
    std::printf("\n== 所有权盘点（判据：看谁负责析构） ==\n");
    std::printf("  Graph 拥有 %lld 个 Value、%lld 个 Node（unique_ptr，各一份）\n",
                static_cast<long long>(g.num_values()),
                static_cast<long long>(g.num_nodes()));
    std::printf("  Node、Value 的拷贝被删除：所有依赖指针都只是借用\n");
    return 0;
}
