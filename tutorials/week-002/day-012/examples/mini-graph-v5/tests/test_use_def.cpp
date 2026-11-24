// 第 10 天的验收测试：use-def 账本的登记、查询、替换与删除。
// 核心是 use_def_consistent()：双向一致性不变量的机器检查，
// 在每次变形（构造、替换、删除、移动）之后都重跑一遍。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "Value.h"

namespace {

int g_checks = 0;

#define CHECK(cond)                                                      \
    do {                                                                 \
        if (!(cond)) {                                                   \
            std::fprintf(stderr, "CHECK 失败：%s（第 %d 行）\n", #cond,   \
                         __LINE__);                                      \
            return 1;                                                    \
        }                                                                \
        ++g_checks;                                                      \
    } while (0)

// 抛出 std::invalid_argument 且消息包含 substr 才算通过。
bool throws_with(const char* substr, void (*fn)()) {
    try {
        fn();
    } catch (const std::invalid_argument& e) {
        return std::string(e.what()).find(substr) != std::string::npos;
    }
    return false;
}

// 经典图：Y = relu(A x B + bias)（第 9 天同款）。
struct Example {
    Graph graph{"matmul-bias-relu"};
    Value* a = nullptr;
    Value* b = nullptr;
    Node* bias = nullptr;
    Node* mm = nullptr;
    Node* add = nullptr;
    Node* relu = nullptr;

    Example() {
        a = graph.add_input("A", {Dtype::F32, {2, 3}});
        b = graph.add_input("B", {Dtype::F32, {3, 2}});
        bias = graph.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
        mm = graph.add_matmul(a, b, "C");
        add = graph.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
        relu = graph.add_relu(add->result(), "Y");
        graph.mark_output(relu->result());
    }
};

// 迷你 CSE 场景：两个输入与属性完全相同的 matmul。
struct Duplicate {
    Graph graph{"duplicate-matmul"};
    Value* a = nullptr;
    Value* b = nullptr;
    Node* mm1 = nullptr;
    Node* mm2 = nullptr;
    Node* add = nullptr;
    Node* relu = nullptr;

    Duplicate() {
        a = graph.add_input("A", {Dtype::F32, {2, 3}});
        b = graph.add_input("B", {Dtype::F32, {3, 2}});
        mm1 = graph.add_matmul(a, b, "C1");
        mm2 = graph.add_matmul(a, b, "C2");
        add = graph.add_elementwise(OpKind::Add, mm1->result(), mm2->result(), "D");
        relu = graph.add_relu(add->result(), "Y");
        graph.mark_output(relu->result());
    }
};

// 不变量：每个输入槽 (节点 n, 槽 i) 指向值 v，当且仅当 v 的
// 账本里恰有一条 (n, i)。正向数一遍，反向对一遍，合成双射。
bool use_def_consistent(const Graph& g) {
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            std::size_t cnt = 0;
            for (const Use& u : n->input(i)->users()) {
                if (u.user == n.get() && u.operand == i) {
                    ++cnt;
                }
            }
            if (cnt != 1) {
                return false;
            }
        }
    }
    for (const std::unique_ptr<Value>& v : g.values()) {
        for (const Use& u : v->users()) {
            if (u.user->input(u.operand) != v.get()) {
                return false;
            }
        }
    }
    return true;
}

std::vector<double> run_and_get(const Graph& g, const Value* a, const Value* b,
                                const Value* want) {
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.run(g);
    return interp.of(want);
}

}  // namespace

int main() {
    // ---- 1. 初始账本：经典图的每条 use 都登记在册 ----
    Example e;
    CHECK(e.graph.num_values() == 6);
    CHECK(e.graph.num_nodes() == 4);
    CHECK(e.a->num_uses() == 1);
    CHECK(e.a->users()[0].user == e.mm);
    CHECK(e.a->users()[0].operand == 0);
    CHECK(e.b->num_uses() == 1);
    CHECK(e.b->users()[0].user == e.mm);
    CHECK(e.b->users()[0].operand == 1);
    CHECK(e.bias->result()->num_uses() == 1);
    CHECK(e.bias->result()->users()[0].user == e.add);
    CHECK(e.bias->result()->users()[0].operand == 1);
    CHECK(e.mm->result()->num_uses() == 1);
    CHECK(e.mm->result()->users()[0].user == e.add);
    CHECK(e.mm->result()->users()[0].operand == 0);
    CHECK(e.add->result()->num_uses() == 1);
    CHECK(e.add->result()->users()[0].user == e.relu);
    CHECK(e.relu->result()->num_uses() == 0);
    CHECK(!e.relu->result()->has_uses());
    CHECK(e.a->has_uses());
    CHECK(use_def_consistent(e.graph));

    // ---- 2. def 侧不受影响：producer 回指照旧 ----
    CHECK(e.mm->result()->producer() == e.mm);
    CHECK(e.bias->result()->producer() == e.bias);
    CHECK(e.a->producer() == nullptr);

    // ---- 3. 同一节点重复使用同一个值：add(%C, %C) 是两条记录 ----
    {
        Graph g("self-use");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");
        Node* add = g.add_elementwise(OpKind::Add, mm->result(), mm->result(), "D");
        g.mark_output(add->result());
        CHECK(mm->result()->num_uses() == 2);
        CHECK(mm->result()->users()[0].user == add);
        CHECK(mm->result()->users()[1].user == add);
        const bool slots_are_0_and_1 =
            (mm->result()->users()[0].operand == 0 && mm->result()->users()[1].operand == 1) ||
            (mm->result()->users()[0].operand == 1 && mm->result()->users()[1].operand == 0);
        CHECK(slots_are_0_and_1);
        CHECK(use_def_consistent(g));
    }

    // ---- 4. 多个不同节点使用同一个值 ----
    {
        Graph g("two-users");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");
        Node* add = g.add_elementwise(OpKind::Add, mm->result(), mm->result(), "D");
        Node* relu = g.add_relu(mm->result(), "E");
        g.mark_output(add->result());
        g.mark_output(relu->result());
        CHECK(mm->result()->num_uses() == 3);  // add 的两个槽 + relu 的一个槽
        CHECK(use_def_consistent(g));
    }

    // ---- 5. replace_all_uses_of：账本搬家，槽位改写 ----
    Duplicate d;
    CHECK(d.a->num_uses() == 2);  // 两个 matmul 都在用 %A
    CHECK(d.b->num_uses() == 2);
    CHECK(d.mm1->result()->num_uses() == 1);
    CHECK(d.mm2->result()->num_uses() == 1);
    d.graph.replace_all_uses_of(d.mm2->result(), d.mm1->result());
    CHECK(d.mm2->result()->num_uses() == 0);
    CHECK(!d.mm2->result()->has_uses());
    CHECK(d.mm1->result()->num_uses() == 2);
    CHECK(d.add->input(0) == d.mm1->result());
    CHECK(d.add->input(1) == d.mm1->result());
    CHECK(d.a->num_uses() == 2);  // mm2 还活着（僵尸节点），仍在用 %A——删除是第二步
    CHECK(d.b->num_uses() == 2);
    CHECK(use_def_consistent(d.graph));
    CHECK(d.graph.to_string().find("add(%C1, %C1)") != std::string::npos);

    // ---- 6. 替换后语义不变：解释器数字与手算 2 x C 一字不差 ----
    const std::vector<double> d_after = run_and_get(d.graph, d.a, d.b, d.add->result());
    CHECK(d_after == (std::vector<double>{116.0, 128.0, 278.0, 308.0}));
    const std::vector<double> y_after = run_and_get(d.graph, d.a, d.b, d.relu->result());
    CHECK(y_after == (std::vector<double>{116.0, 128.0, 278.0, 308.0}));

    // ---- 7. erase 拒绝仍有使用者的节点（失败的原操作不留下半套修改）----
    CHECK(throws_with("仍有", [] {
        Duplicate d;
        d.graph.erase_node(d.mm1);  // %C1 正被 add 使用
    }));
    CHECK(throws_with("%C1", [] {
        Duplicate d;
        d.graph.erase_node(d.mm1);
    }));
    CHECK(d.graph.num_nodes() == 4);  // 上面那次失败没有破坏 d 的账本
    CHECK(use_def_consistent(d.graph));

    // ---- 8. erase 拒绝图输出（输出也是一种「使用者」）----
    CHECK(throws_with("图输出", [] {
        Example e;
        e.graph.erase_node(e.relu);  // %Y 是图输出
    }));
    CHECK(throws_with("图输出", [] {
        Graph g("t");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_matmul(a, b, "C");
        g.mark_output(mm->result());
        g.erase_node(mm);
    }));

    // ---- 9. erase 成功路径：先替换后删除，数量对、不变量对、数字对 ----
    const std::int64_t nodes_before = d.graph.num_nodes();
    const std::int64_t values_before = d.graph.num_values();
    d.graph.erase_node(d.mm2);  // %C2 已无使用者
    CHECK(d.graph.num_nodes() == nodes_before - 1);
    CHECK(d.graph.num_values() == values_before - 1);
    CHECK(d.a->num_uses() == 1);  // 僵尸节点删掉后，%A 才真的只剩 mm1 在用
    CHECK(d.b->num_uses() == 1);
    CHECK(use_def_consistent(d.graph));
    CHECK(d.graph.to_string().find("%C2") == std::string::npos);
    const std::vector<double> d_erased = run_and_get(d.graph, d.a, d.b, d.add->result());
    CHECK(d_erased == (std::vector<double>{116.0, 128.0, 278.0, 308.0}));

    // ---- 10. replace 的三个廉价检查 ----
    CHECK(throws_with("类型不一致", [] {
        Example e;
        Value* other = e.graph.add_input("X", {Dtype::F32, {2, 3}});
        e.graph.replace_all_uses_of(e.mm->result(), other);  // 2x2 vs 2x3
    }));
    CHECK(throws_with("同一个值", [] {
        Example e;
        e.graph.replace_all_uses_of(e.mm->result(), e.mm->result());
    }));
    CHECK(throws_with("空指针", [] {
        Example e;
        e.graph.replace_all_uses_of(nullptr, e.mm->result());
    }));

    // ---- 11. 无使用者的值替换：合法的空操作 ----
    {
        Example e;
        Node* other = e.graph.add_constant("bias2", {Dtype::F32, {2, 2}}, {1.0, 2.0, 3.0, 4.0});
        e.graph.replace_all_uses_of(e.relu->result(), other->result());  // %Y 本来就无人用
        CHECK(e.relu->result()->num_uses() == 0);
        CHECK(other->result()->num_uses() == 0);
        CHECK(use_def_consistent(e.graph));
    }

    // ---- 12. erase 的守门检查：空指针与外图节点 ----
    CHECK(throws_with("空指针", [] {
        Example e;
        e.graph.erase_node(nullptr);
    }));
    CHECK(throws_with("不属于本图", [] {
        Graph g1("one");
        Graph g2("two");
        Value* a = g2.add_input("A", {Dtype::F32, {2, 3}});
        Node* n2 = g2.add_relu(a, "r");
        g1.erase_node(n2);  // n2 属于 g2，不属于 g1
    }));

    // ---- 13. 第 8/9 天遗风：移动整个 Graph，账本依然有效 ----
    {
        Duplicate d;
        d.graph.replace_all_uses_of(d.mm2->result(), d.mm1->result());
        Graph moved = std::move(d.graph);  // unique_ptr 集中所有权 → 地址不变
        CHECK(moved.num_nodes() == 4);
        CHECK(d.mm1->result()->num_uses() == 2);
        CHECK(d.mm2->result()->num_uses() == 0);
        CHECK(use_def_consistent(moved));
        const std::vector<double> d_moved = run_and_get(moved, d.a, d.b, d.add->result());
        CHECK(d_moved == (std::vector<double>{116.0, 128.0, 278.0, 308.0}));
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
