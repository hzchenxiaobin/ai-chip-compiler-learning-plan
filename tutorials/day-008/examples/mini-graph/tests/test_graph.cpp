// 第 8 天的验收测试：结构、依赖、拓扑序、所有权语义。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "Graph.h"
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

struct Example {
    // y = relu(a + b)
    Graph graph{"add-relu"};
    Value* a = nullptr;
    Value* b = nullptr;
    Node* add = nullptr;
    Node* relu = nullptr;

    Example() {
        a = graph.add_input("a");
        b = graph.add_input("b");
        add = graph.add_node("add", {a, b}, "t");
        relu = graph.add_node("relu", {add->result()}, "y");
        graph.mark_output(relu->result());
    }
};

}  // namespace

int main() {
    // ---- 1. 基本结构 ----
    Example e;
    CHECK(e.graph.num_values() == 4);          // a, b, t, y
    CHECK(e.graph.num_nodes() == 2);
    CHECK(e.graph.inputs().size() == 2);
    CHECK(e.graph.outputs().size() == 1);
    CHECK(e.graph.outputs()[0] == e.relu->result());

    // ---- 2. 图输入：没有生产者 ----
    CHECK(e.a->producer() == nullptr);
    CHECK(e.b->producer() == nullptr);
    CHECK(e.a->id() != e.b->id());

    // ---- 3. 节点：kind、输入借用、结果借用 ----
    CHECK(e.add->kind() == "add");
    CHECK(e.relu->kind() == "relu");
    CHECK(e.add->num_inputs() == 2);
    CHECK(e.add->input(0) == e.a);
    CHECK(e.add->input(1) == e.b);
    CHECK(e.relu->num_inputs() == 1);
    CHECK(e.relu->input(0) == e.add->result());

    // ---- 4. 值回指生产者：数据依赖双向可查 ----
    CHECK(e.add->result()->producer() == e.add);
    CHECK(e.relu->result()->producer() == e.relu);

    // ---- 5. 拓扑序：依赖排在自己前面 ----
    std::vector<const Node*> order = e.graph.topological_order();
    CHECK(order.size() == 2);
    CHECK(order[0] == e.add);
    CHECK(order[1] == e.relu);
    // 创建顺序本身就是拓扑序：这个 API 只能引用已存在的值。
    for (std::size_t i = 0; i < order.size(); ++i) {
        CHECK(order[i]->id() == static_cast<std::int64_t>(i));
    }

    // ---- 6. 菱形结构：一个值分给两个消费者，再汇合 ----
    {
        Graph d("diamond");
        Value* x = d.add_input("x");
        Node* left = d.add_node("neg", {x}, "l");
        Node* right = d.add_node("exp", {x}, "r");
        Node* join = d.add_node("add", {left->result(), right->result()}, "z");
        d.mark_output(join->result());
        CHECK(d.num_nodes() == 3);
        // 同一个 %x 被两个节点当输入：边可以分叉。
        CHECK(left->input(0) == x && right->input(0) == x);

        std::vector<const Node*> top = d.topological_order();
        CHECK(top.size() == 3);
        CHECK(top[0]->id() == 0);                      // neg / exp 在 add 之前
        CHECK(top[2]->id() == join->id());
        // 每个节点的依赖都排在它前面（拓扑序的定义）。
        for (const Node* n : top) {
            for (const Value* in : n->inputs()) {
                const Node* p = in->producer();
                if (p == nullptr) {
                    continue;
                }
                std::size_t p_pos = top.size(), n_pos = top.size();
                for (std::size_t i = 0; i < top.size(); ++i) {
                    if (top[i] == p) p_pos = i;
                    if (top[i] == n) n_pos = i;
                }
                CHECK(p_pos < n_pos);
            }
        }
    }

    // ---- 7. 空图 ----
    {
        Graph empty("empty");
        CHECK(empty.num_nodes() == 0);
        CHECK(empty.topological_order().empty());
        CHECK(empty.to_string() == "graph \"empty\" (0 inputs, 0 outputs) {\n}");
    }

    // ---- 8. 文本 IR ----
    {
        const std::string text = e.graph.to_string();
        CHECK(text.find("%a = input") != std::string::npos);
        CHECK(text.find("add(%a, %b) -> %t") != std::string::npos);
        CHECK(text.find("relu(%t) -> %y") != std::string::npos);
        CHECK(text.find("output %y") != std::string::npos);
    }

    // ---- 9. 空指针被拒绝（今天唯一的合法性检查） ----
    {
        Example f;
        bool threw = false;
        try {
            f.graph.add_node("add", {f.a, nullptr}, "bad");
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        CHECK(threw);
        // 抛异常之后图还是完整的。
        CHECK(f.graph.num_nodes() == 2);
    }

    // ---- 10. 拷贝被删除：所有权是类型系统的事实 ----
    static_assert(!std::is_copy_constructible<Node>::value, "Node 不可拷贝");
    static_assert(!std::is_copy_constructible<Value>::value, "Value 不可拷贝");
    static_assert(!std::is_copy_constructible<Graph>::value, "Graph 不可拷贝");
    CHECK(true);

    // ---- 11. 移动图：节点和值的地址一个都不变 ----
    {
        Example f;
        const Node* add_before = f.add;
        const Value* t_before = f.add->result();
        Graph moved = std::move(f.graph);  // 搬家的是 unique_ptr，不是节点本体
        CHECK(moved.num_nodes() == 2);
        CHECK(moved.num_values() == 4);
        CHECK(add_before->kind() == "add");       // 旧指针仍然有效
        CHECK(t_before->producer() == add_before);
        CHECK(moved.to_string().find("relu(%t) -> %y") != std::string::npos);
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
