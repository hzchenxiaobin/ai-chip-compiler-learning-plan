// 反面教材（第 16 天错误二）：一个「合法」的 replace，静默造出自环。
// 现场模拟：某天要写一个「复用中间结果」的小 Pass——
//   把 %C 的使用者统统改指 %D（add 的结果），省一次重复计算。
// 问题是：%D 的生产者 add 恰好是 %C 的使用者——它从此吃起了自己的结果。
// 三个观察点：
//   1) 三道防线的前两道都放行：账本自洽（不变量没破）、verify PASS
//      （环不是结构/类型/账本问题，Verifier 的职责清单里没有它）；
//   2) 第三道防线拦下：TopoSort 拒绝，环路径 add%n2 -> add%n2；
//   3) 若回到没有第三道防线的 v7：按 v7 工程实测（本仓库
//      tutorials/day-014/examples/mini-graph-v7 原样构建运行）：
//        v7 旧算法给出的序： constant%n0 matmul%n1 add%n2 relu%n3
//        v7 解释器报错: 解释器: %D 没有数据（输入未绑定？）
//      ——病因是图有环，症状像「忘了绑输入」，误导排查方向。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp \
//     ../src/Frontend.cpp ../src/TopoSort.cpp err_replace_self_loop.cpp \
//     -o err_replace_self_loop && ./err_replace_self_loop; echo "exit code: $?"
#include <cstdio>
#include <stdexcept>
#include <string>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "OpKind.h"
#include "TopoSort.h"
#include "Value.h"
#include "Verifier.h"

int main() {
    Graph g("self-loop");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "R");
    g.mark_output(relu->result());

    std::printf("「Pass」动手：replace_all_uses_of(%%C, %%D)\n");
    g.replace_all_uses_of(mm->result(), add->result());
    std::printf("%s\n", g.to_string().c_str());

    // 前两道防线：账本、Verifier——都放行。
    const VerifyReport rep = verify_graph(g);
    std::printf("verify: %s\n", rep.ok ? "PASS（账本、结构、类型全对——环不归它管）"
                                       : "FAIL");
    std::printf("账本: %%D 的使用者有 %zu 个（relu 和 add 自己）, %%C 的使用者有 %zu 个\n",
                add->result()->num_uses(), mm->result()->num_uses());

    // 第三道防线：拓扑排序——拒绝。
    const TopoSortResult r = topo_sort(g);
    std::printf("topo_sort: ok = %d\n", r.ok ? 1 : 0);
    std::printf("  %s\n", topo_error_message(g, r).c_str());

    // 解释器入口同样被拦（它调 topological_order）。
    Interpreter it;
    it.bind(a, {1, 2, 3, 4, 5, 6});
    it.bind(b, {7, 8, 9, 10, 11, 12});
    try {
        it.run(g);
        std::printf("竟然跑完了？不该走到这里\n");
    } catch (const std::invalid_argument& e) {
        std::printf("解释器被拦: what(): %s\n", e.what());
    }
    return 0;
}
