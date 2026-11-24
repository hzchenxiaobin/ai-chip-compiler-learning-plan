// 第 16 天的主程序：拓扑排序与依赖检查。
// 第一幕：双通道 DAG——拓扑序、执行波次表、端到端执行；
// 第二幕：环从哪里来——replace / rewire 两条真实事故路径，
//         账本自洽、验证通过，拓扑排序当场拒绝。

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "OpKind.h"
#include "TopoSort.h"
#include "Value.h"
#include "Verifier.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9～14 天）。
void print_matrix(const char* name, const TensorType& type, const std::vector<double>& data) {
    std::printf("  %%%s (%s) =\n", name, type.to_string().c_str());
    for (std::int64_t i = 0; i < type.shape[0]; ++i) {
        std::printf("   ");
        for (std::int64_t j = 0; j < type.shape[1]; ++j) {
            std::printf(" %g", data[static_cast<std::size_t>(i * type.shape[1] + j)]);
        }
        std::printf("\n");
    }
}

// 打印一份验证报告（同第 12～14 天）。
void print_report(const Graph& g, const VerifyReport& rep) {
    if (rep.ok) {
        std::printf("verify: PASS（%lld 个节点、%lld 个值、%lld 个输出，全部检查通过）\n",
                    static_cast<long long>(g.num_nodes()),
                    static_cast<long long>(g.num_values()),
                    static_cast<long long>(g.outputs().size()));
    } else {
        std::printf("verify: FAIL，共 %zu 个问题：\n", rep.errors.size());
        for (const std::string& e : rep.errors) {
            std::printf("  error: %s\n", e.c_str());
        }
    }
}

std::string node_tag(const Node* n) {
    return op_name(n->kind()) + "%n" + std::to_string(n->id());
}

// 波次表：TopoSort 的第一份输出——同波可并行，波数 = 关键路径深度。
void print_topo_success(const TopoSortResult& r) {
    std::printf("  ok = 1，%zu 波 · %lld 个节点（波数 = 关键路径深度）\n", r.waves.size(),
                static_cast<long long>(r.order.size()));
    for (std::size_t w = 0; w < r.waves.size(); ++w) {
        std::printf("  wave %zu（%zu 个%s）:", w + 1, r.waves[w].size(),
                    r.waves[w].size() > 1 ? "，可并行" : "");
        for (const Node* n : r.waves[w]) {
            std::printf(" %s", node_tag(n).c_str());
        }
        std::printf("\n");
    }

    std::printf("\n== 执行时间表（波次拼接成线性序） ==\n");
    for (std::size_t step = 0; step < r.order.size(); ++step) {
        const Node* n = r.order[step];
        std::printf("  step %zu: %s reads [", step + 1, node_tag(n).c_str());
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (i != 0) {
                std::printf(", ");
            }
            std::printf("%%%s", n->input(i)->name().c_str());
        }
        std::printf("] writes %%%s\n", n->result()->name().c_str());
    }
}

// 拒绝时的完整诊断：环路径、已剥前缀、卡住计数。
void print_topo_failure(const Graph& g, const TopoSortResult& r) {
    std::printf("  topo_sort: 拒绝（ok = 0）\n");
    if (!r.cycle.empty()) {
        std::printf("  环路径: %s（环上 %zu 个节点）\n", cycle_to_string(r.cycle).c_str(),
                    r.cycle.size() - 1);
    }
    std::printf("  已剥 %lld 个（前缀：", static_cast<long long>(r.peeled));
    for (const Node* n : r.order) {
        std::printf(" %s", node_tag(n).c_str());
    }
    std::printf("）、卡住 %lld 个\n", static_cast<long long>(r.stuck));
    std::printf("  诊断: %s\n", topo_error_message(g, r).c_str());
}

// 第一幕的主角：双通道图。Y = relu((A×B + bias) + (A×B + bias))。
// 两路 matmul 吃同样的输入——互不依赖，是「同一波」的天然居民；
// 4 波 = 关键路径深度（const/mm → add → add → relu）。
Graph build_dual_channel() {
    Graph g("dual-channel");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm1 = g.add_matmul(a, b, "C1");
    Node* mm2 = g.add_matmul(a, b, "C2");  // 与 mm1 输入相同：CSE 的原料（第 26 天）
    Node* d = g.add_elementwise(OpKind::Add, mm1->result(), bias->result(), "D");
    Node* e = g.add_elementwise(OpKind::Add, mm2->result(), bias->result(), "E");
    Node* s = g.add_elementwise(OpKind::Add, d->result(), e->result(), "S");
    Node* r = g.add_relu(s->result(), "R");
    g.mark_output(r->result());
    return g;
}

// 第二幕的主角：经典链 bias + A×B + add + relu（同第 9 天起的样子）。
Graph build_chain(const char* name) {
    Graph g(name);
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* r = g.add_relu(add->result(), "R");
    g.mark_output(r->result());
    return g;
}

void bind_ab(Interpreter& interp, const Graph& g) {
    interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
    interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
}

}  // namespace

int main() {
    // ================= 第一幕：一张能并行的 DAG =================
    std::printf("== 第一幕：双通道图——拓扑排序给出执行时间表与波次表 ==\n\n");

    Graph g = build_dual_channel();
    std::printf("%s\n", g.to_string().c_str());

    print_report(g, verify_graph(g));

    std::printf("\n== 拓扑排序（TopoSort：逐波剥离） ==\n");
    const TopoSortResult r1 = topo_sort(g);
    print_topo_success(r1);

    bool same = r1.order.size() == static_cast<std::size_t>(g.num_nodes());
    for (std::size_t i = 0; same && i < r1.order.size(); ++i) {
        same = r1.order[i] == g.nodes()[i].get();
    }
    std::printf("  （波次拼接后与创建序%s——工厂只许引用已存在的值；\n"
                "   第二幕立刻会看到：一旦改图，这个定理就失效）\n",
                same ? "一致" : "不一致");

    std::printf("\n== 端到端执行（解释器按拓扑序求值） ==\n");
    std::printf("  手算：C1=C2=[58 64/139 154] → D=E=[58 -36/-11 104] →\n"
                "        S=[116 -72/-22 208] → relu → R=[116 0/0 208]\n");
    Interpreter interp;
    bind_ab(interp, g);
    interp.run(g);
    print_matrix("R", g.outputs()[0]->type(), interp.of(g.outputs()[0]));

    // ================= 第二幕：环从哪里来 =================
    std::printf("\n== 第二幕：环从哪里来——两个真实事故现场 ==\n");

    // ---- 现场一：replace_all_uses_of 制造自环 ----
    // 事故剧本：一个「想复用中间结果」的 Pass 把 %C 的使用者都改指 %D。
    // 可 %D 的生产者 n2 恰好是 %C 的使用者——它从此吃起了自己的结果。
    std::printf("\n现场一：Pass 想复用结果，replace_all_uses_of(%%C, %%D)——自环诞生\n");
    {
        Graph gl = build_chain("self-loop");
        // 节点创建序：bias(n0) → mm(n1) → add(n2) → relu(n3)。
        Node* mm = gl.nodes()[1].get();
        Node* add = gl.nodes()[2].get();
        const Value* c = mm->result();
        const Value* d = add->result();
        gl.replace_all_uses_of(c, d);

        std::printf("  改完后 n2 的第 0 槽从 %%C 换成 %%D，而 %%D 正是 n2 自己的结果：\n");
        std::printf("%s\n", gl.to_string().c_str());
        print_report(gl, verify_graph(gl));
        std::printf("  （环不归 Verifier 管——账本一致、类型正确，它如实放行）\n\n");

        std::printf("  use 账本（仍然自洽——一致性不变量没有破）：\n%s\n",
                    gl.uses_to_string().c_str());

        std::printf("  拓扑排序：\n");
        const TopoSortResult r = topo_sort(gl);
        print_topo_failure(gl, r);

        std::printf("  解释器想按拓扑序执行——入口处就被拦下：\n");
        try {
            Interpreter it;
            bind_ab(it, gl);
            it.run(gl);
            std::printf("  竟然跑完了？不该走到这里\n");
        } catch (const std::invalid_argument& e) {
            std::printf("  what(): %s\n", e.what());
        }
    }

    // ---- 现场二：rewire_input 手滑一格，两个节点抱成环 ----
    // 事故剧本：手滑的 Pass 想把 n2 的 bias 槽改成别的常量，
    // 结果接到了 %R——relu 的输出又反过来依赖 n2，环长变成 2。
    std::printf("\n现场二：rewire_input 手滑——n2 的 bias 槽改接 %%R，环长 2\n");
    {
        Graph gl = build_chain("two-node-cycle");
        Node* add = gl.nodes()[2].get();  // 创建序：bias(n0) → mm(n1) → add(n2) → relu(n3)
        Node* relu = gl.nodes()[3].get();
        gl.rewire_input(add, 1, relu->result());

        std::printf("  改完后：n2 = add(%%C, %%R)，n3 = relu(%%D)——n2 等 n3，n3 等 n2：\n");
        std::printf("%s\n", gl.to_string().c_str());
        print_report(gl, verify_graph(gl));
        std::printf("  （类型全对：%%C 和 %%R 都是 f32<2x2>，逐元素检查照样通过）\n\n");

        std::printf("  拓扑排序：\n");
        const TopoSortResult r = topo_sort(gl);
        print_topo_failure(gl, r);

        std::printf("  解释器：\n");
        try {
            Interpreter it;
            bind_ab(it, gl);
            it.run(gl);
            std::printf("  竟然跑完了？不该走到这里\n");
        } catch (const std::invalid_argument& e) {
            std::printf("  what(): %s\n", e.what());
        }
    }

    return 0;
}
