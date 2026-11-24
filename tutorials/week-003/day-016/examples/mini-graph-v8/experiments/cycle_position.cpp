// 第 16 天对照实验：环长固定为 3，把环放在链上的不同位置。
//
// 图：一条 5 节点的 relu 链 c0 → c1 → c2 → c3 → c4（吃图输入 %x）。
// 「参数」只有一个：改谁的输入。把 c_i 的输入改接 %v_{i+2}——
//   c_i 等 c_{i+2}，c_{i+2} 等 c_{i+1}，c_{i+1} 等 c_i——环长恒为 3，
//   只有环的「位置」在动。
// 预测（动手前先写在纸上）：
//   环在位置 2（c2→c4→c3→c2）：下游没有节点，剥下 2 个、卡住 3 个；
//   环在位置 1（c1→c3→c2→c1）：下游是 c4，剥下 1 个、卡住 4 个；
//   环在位置 0（c0→c2→c1→c0）：下游是 c3、c4，剥下 0 个、卡住 5 个。
// 结论要盯住一句话：卡住的节点 = 环上 3 个 ＋ 被环堵死的下游，
// 「卡住数」不是「环长」；已剥的前缀恰好是环上游能安全执行的部分。

#include <cstdio>
#include <string>
#include <vector>

#include "Graph.h"
#include "Node.h"
#include "OpKind.h"
#include "TopoSort.h"
#include "Value.h"

namespace {

// 5 节点 relu 链；anchor = -1 表示不改（无环基线），
// anchor = 0/1/2 表示把 c_anchor 的输入改接 %v_{anchor+2}。
Graph build_chain(int anchor) {
    Graph g("cycle-position");
    Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
    std::vector<Node*> c;
    for (int i = 0; i < 5; ++i) {
        if (i == 0) {
            c.push_back(g.add_relu(x, "v0"));
        } else {
            c.push_back(g.add_relu(c.back()->result(), "v" + std::to_string(i)));
        }
    }
    if (anchor >= 0) {
        g.rewire_input(c[static_cast<std::size_t>(anchor)], 0,
                       c[static_cast<std::size_t>(anchor + 2)]->result());
    }
    g.mark_output(c[4]->result());
    return g;
}

}  // namespace

int main() {
    std::printf("环长固定 3，位置后移一格——已剥的前缀变短、卡住的名单变长\n\n");
    std::printf("  环位置   环路径                                          已剥  卡住  波数\n");

    const int anchors[] = {-1, 2, 1, 0};
    for (const int anchor : anchors) {
        Graph g = build_chain(anchor);
        const TopoSortResult r = topo_sort(g);

        std::string path;
        if (anchor == -1) {
            path = "（无环基线）";
        } else {
            path = cycle_to_string(r.cycle);
        }
        std::printf("  %-8s %-46s %lld    %lld    %zu\n",
                    anchor == -1 ? "基线" : ("c" + std::to_string(anchor) + " 起").c_str(),
                    path.c_str(), static_cast<long long>(r.peeled),
                    static_cast<long long>(r.stuck), r.waves.size());
    }

    std::printf("\n观察：\n");
    std::printf("  1) 环长都是 3（看环路径的首尾，首尾同节点），但卡住数是 3/4/5——\n");
    std::printf("     卡住 = 环上 ＋ 被环堵死的下游，诊断里的「环上 N 个」才是环长；\n");
    std::printf("  2) 已剥的 2/1/0 个恰好是环上游的安全前缀——它们不依赖环，\n");
    std::printf("     部分序本身就是有用的诊断信息（「剥到第几步开始转圈」）；\n");
    std::printf("  3) 无环基线：5 个节点、5 波、一个不卡——链上每个节点自成一波，\n");
    std::printf("     关键路径深度 5。\n");
    return 0;
}
