// 第 12 天的验收测试：图的合法性检查（Verifier）。
// 三层检查各有用例：图级（输出表）、结构级（kind/空指针/归属/账本）、
// 语义级（输入数量、Shape 兼容性、dtype、结果类型）。
// 非法用例按「怎么造出来的」分两组：raw 后门造的（解析器同款处境）
// 和工厂也能造出来的（跨图指针——工厂根本查不了）。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <string>
#include <vector>

#include "Graph.h"
#include "Node.h"
#include "Value.h"
#include "Verifier.h"

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

// 报告包含某段文字。
bool has_error(const VerifyReport& rep, const std::string& substr) {
    for (const std::string& e : rep.errors) {
        if (e.find(substr) != std::string::npos) {
            return true;
        }
    }
    return false;
}

// 经典图：Y = relu(A x B + bias)（第 9 天起一路沿用）。
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

}  // namespace

int main() {
    // ---------- 一、合法用例：好图必须安静地通过 ----------

    // 1. 经典图：0 错误。
    {
        Example ex;
        const VerifyReport rep = verify_graph(ex.graph);
        CHECK(rep.ok);
        CHECK(rep.errors.empty());
    }

    // 2. transpose 属性的 matmul：Bᵀ(2x3) × Aᵀ(3x2) 内维 3=3，必须通过。
    {
        Example ex;
        Node* mmt = ex.graph.add_matmul(ex.b, ex.a, "CT",
                                        /*transpose_a=*/true, /*transpose_b=*/true);
        ex.graph.mark_output(mmt->result());
        const VerifyReport rep = verify_graph(ex.graph);
        CHECK(rep.ok);
    }

    // 3. 同一个值用在两个槽（add(%C, %C)）：账本里是两条独立记录，合法。
    {
        Example ex;
        Node* dup = ex.graph.add_elementwise(OpKind::Add, ex.mm->result(), ex.mm->result(),
                                             "D2");
        ex.graph.mark_output(dup->result());
        const VerifyReport rep = verify_graph(ex.graph);
        CHECK(rep.ok);
        CHECK(ex.mm->result()->num_uses() == 3);  // n2、n3 之外多了 D2
    }

    // 4. 图输入直接当输出（恒等图）：合法。
    {
        Graph g("identity");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        g.mark_output(x);
        const VerifyReport rep = verify_graph(g);
        CHECK(rep.ok);
    }

    // 5. raw 入口造的「正确」matmul：raw 不等于非法，验证只看事实。
    {
        Graph g("raw-but-correct");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(rep.ok);
        CHECK(rep.errors.empty());
    }

    // 6. replace ＋ erase 之后账本仍然自洽（第 10 天入口的不变量）。
    {
        Example ex;
        Node* bias2 =
            ex.graph.add_constant("bias2", {Dtype::F32, {2, 2}}, {1.0, 1.0, 1.0, 1.0});
        ex.graph.replace_all_uses_of(ex.bias->result(), bias2->result());
        ex.graph.erase_node(ex.bias);
        const VerifyReport rep = verify_graph(ex.graph);
        CHECK(rep.ok);
        CHECK(ex.graph.num_nodes() == 4);
    }

    // 7. 验证是只读的：跑两遍结果一致，图的文本不变。
    {
        Example ex;
        const std::string before = ex.graph.to_string();
        const VerifyReport r1 = verify_graph(ex.graph);
        const VerifyReport r2 = verify_graph(ex.graph);
        CHECK(r1.ok && r2.ok);
        CHECK(ex.graph.to_string() == before);
    }

    // ---------- 二、语义层非法用例：raw 后门造出来的 ----------

    // 8. 枚举外的野 kind（第 11 天 bugs 的主角，今天正面封堵）。
    {
        Graph g("fake-kind");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        Node* ghost = g.add_raw_node(static_cast<OpKind>(99), {x, y}, Attrs{},
                                     {Dtype::F32, {2, 2}}, "G");
        g.mark_output(ghost->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "未知的算子类型 99"));
        CHECK(rep.errors.size() == 1);  // 野 kind 只报这一条，不猜语义
    }

    // 9. matmul 只给 1 个输入。
    {
        Graph g("mm-arity");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "需要 2 个输入，实际有 1 个"));
    }

    // 10. matmul 内维不匹配：2x3 × 2x2（第二幕命运二同款）。
    {
        Graph g("mm-inner");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {2, 2}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "内维不匹配"));
        CHECK(has_error(rep, "是 3"));
        CHECK(has_error(rep, "是 2"));
    }

    // 11. matmul 输入不是二维。
    {
        Graph g("mm-rank");
        Value* a = g.add_input("A", {Dtype::F32, {2, 2, 2}});
        Value* b = g.add_input("B", {Dtype::F32, {2, 2}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "不是二维"));
    }

    // 12. matmul 结果类型错：内维 3=3 匹配，但结果声明成 f32<2x3>。
    //     这条工厂永远给对（结果类型是它算出来的），只有 raw 能造错。
    {
        Graph g("mm-result-type");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 3}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "结果类型应为 f32<2x2>，实际是 f32<2x3>"));
    }

    // 13. matmul 两个输入 dtype 不一致。
    {
        Graph g("mm-dtype");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::I32, {3, 2}});
        Node* mm = g.add_raw_node(OpKind::MatMul, {a, b}, Attrs{}, {Dtype::F32, {2, 2}}, "C");
        g.mark_output(mm->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "dtype 不一致"));
    }

    // 14. add 两个输入 shape 不一致。
    {
        Graph g("add-shape");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 3}});
        Node* add = g.add_raw_node(OpKind::Add, {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "Z");
        g.mark_output(add->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "类型不一致"));
        CHECK(has_error(rep, "f32<2x2> vs f32<2x3>"));
    }

    // 15. add 结果 dtype 与输入不一致（f32 进、i32 出）。
    {
        Graph g("add-result");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        Node* add = g.add_raw_node(OpKind::Add, {x, y}, Attrs{}, {Dtype::I32, {2, 2}}, "Z");
        g.mark_output(add->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "结果类型应与输入一致（f32<2x2>），实际是 i32<2x2>"));
    }

    // 16. relu 塞了 2 个输入。
    {
        Graph g("relu-arity");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        Node* r = g.add_raw_node(OpKind::Relu, {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "R");
        g.mark_output(r->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "需要 1 个输入，实际有 2 个"));
    }

    // 17. relu 结果 shape 与输入不一致。
    {
        Graph g("relu-result");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Node* r = g.add_raw_node(OpKind::Relu, {x}, Attrs{}, {Dtype::F32, {2, 3}}, "R");
        g.mark_output(r->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "结果类型应与输入一致（f32<2x2>），实际是 f32<2x3>"));
    }

    // 18. constant 声明 f32<2x2> 却只给 3 个数。
    {
        Graph g("const-data");
        Attrs attrs;
        attrs.data = {1, 2, 3};
        Node* k = g.add_raw_node(OpKind::Constant, {}, attrs, {Dtype::F32, {2, 2}}, "k");
        g.mark_output(k->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "常量数据 3 个"));
        CHECK(has_error(rep, "元素数 4 不符"));
    }

    // 19. constant 却带 1 个输入。
    {
        Graph g("const-arity");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Attrs attrs;
        attrs.data = {1, 2, 3, 4};
        Node* k = g.add_raw_node(OpKind::Constant, {x}, attrs, {Dtype::F32, {2, 2}}, "k");
        g.mark_output(k->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "需要 0 个输入，实际有 1 个"));
    }

    // ---------- 三、结构层非法用例 ----------

    // 20. 空指针输入：raw 才能造出来（工厂当场抛）。
    {
        Graph g("null-input");
        Node* r = g.add_raw_node(OpKind::Relu, {nullptr}, Attrs{}, {Dtype::F32, {2, 2}}, "R");
        g.mark_output(r->result());
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "第 0 个输入是空指针"));
        CHECK(!has_error(rep, "结果类型"));  // 结构不完整，语义检查跳过
    }

    // 21. 图没有输出。
    {
        Graph g("no-output");
        g.add_input("x", {Dtype::F32, {2, 2}});  // 造了输入，不 mark_output
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "图没有输出"));
    }

    // 22. 输出表重复登记同一个值。
    {
        Example ex;
        ex.graph.mark_output(ex.relu->result());  // 第二次
        const VerifyReport rep = verify_graph(ex.graph);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "项重复"));
    }

    // 23. 跨图指针（输入侧）：g2 的值喂给 g1 的工厂——工厂查不了归属，
    //     两张图都病了：g1 报「输入不属于本图」，g2 报「账本里有外人」。
    {
        Graph g1("host");
        Graph g2("donor");
        Value* foreign = g2.add_input("F", {Dtype::F32, {2, 2}});
        Node* r = g1.add_relu(foreign, "R");  // 工厂只查了空指针和类型
        g1.mark_output(r->result());

        const VerifyReport rep1 = verify_graph(g1);
        CHECK(!rep1.ok);
        CHECK(has_error(rep1, "不属于本图"));

        const VerifyReport rep2 = verify_graph(g2);
        CHECK(!rep2.ok);
        CHECK(has_error(rep2, "账本里有使用者"));
        CHECK(has_error(rep2, "不属于本图"));
    }

    // 24. 跨图指针（输出侧）：mark_output 收下别图的值。
    {
        Graph g1("host-out");
        Graph g2("donor-out");
        Value* foreign = g2.add_input("F", {Dtype::F32, {2, 2}});
        g1.mark_output(foreign);
        const VerifyReport rep = verify_graph(g1);
        CHECK(!rep.ok);
        CHECK(has_error(rep, "输出表第 0 项"));
        CHECK(has_error(rep, "不属于本图"));
    }

    // 25. 多错误一次列全：假 kind ＋ relu 双输入 ＋ 常量缺数 ＋ 没有输出。
    {
        Graph g("four-errors");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        g.add_raw_node(static_cast<OpKind>(99), {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "G");
        g.add_raw_node(OpKind::Relu, {x, y}, Attrs{}, {Dtype::F32, {2, 2}}, "R");
        Attrs attrs;
        attrs.data = {1, 2, 3};
        g.add_raw_node(OpKind::Constant, {}, attrs, {Dtype::F32, {2, 2}}, "k");
        const VerifyReport rep = verify_graph(g);
        CHECK(!rep.ok);
        CHECK(rep.errors.size() == 4);  // 一张单子列全，顺序不限
        CHECK(has_error(rep, "未知的算子类型 99"));
        CHECK(has_error(rep, "需要 1 个输入，实际有 2 个"));
        CHECK(has_error(rep, "常量数据 3 个"));
        CHECK(has_error(rep, "图没有输出"));
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
