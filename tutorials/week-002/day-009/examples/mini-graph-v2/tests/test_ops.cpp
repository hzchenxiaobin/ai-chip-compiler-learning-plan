// 第 9 天的验收测试：四种算子的类型与属性记录、廉价检查、小解释器。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <type_traits>
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

struct Example {
    // Y = relu(A x B + bias)
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

// 反复构造同一个图太啰嗦：错误用例在独立的小图上触发。
Graph one_matmul_graph() {
    Graph g("t");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {2, 3}});  // 存成转置
    g.add_matmul(a, b, "C", false, true);
    return g;
}

}  // namespace

int main() {
    // ---- 1. 基本结构：2 输入 + 4 节点 = 6 个值 ----
    Example e;
    CHECK(e.graph.num_values() == 6);   // A, B, bias, C, D, Y
    CHECK(e.graph.num_nodes() == 4);
    CHECK(e.graph.inputs().size() == 2);
    CHECK(e.graph.outputs().size() == 1);
    CHECK(e.graph.outputs()[0] == e.relu->result());

    // ---- 2. 类型记录在值上 ----
    CHECK(e.a->type() == (TensorType{Dtype::F32, {2, 3}}));
    CHECK(e.a->type().to_string() == "f32<2x3>");
    CHECK(e.a->type().num_elements() == 6);
    CHECK(e.a->type().bytes() == 24);
    CHECK(e.b->type().to_string() == "f32<3x2>");
    CHECK(e.mm->result()->type() == (TensorType{Dtype::F32, {2, 2}}));  // 由工厂算出
    CHECK(e.add->result()->type() == e.mm->result()->type());
    CHECK(e.relu->result()->type() == e.add->result()->type());
    CHECK(e.bias->result()->type() == (TensorType{Dtype::F32, {2, 2}}));

    // ---- 3. constant：没有输入，数据在属性里 ----
    CHECK(e.bias->kind() == OpKind::Constant);
    CHECK(e.bias->num_inputs() == 0);
    CHECK(e.bias->attrs().data == (std::vector<double>{0.0, -100.0, -150.0, -50.0}));
    CHECK(e.bias->result()->producer() == e.bias);
    CHECK(e.bias->result()->type().dtype == Dtype::F32);

    // ---- 4. matmul：输入、默认属性、生产者 ----
    CHECK(e.mm->kind() == OpKind::MatMul);
    CHECK(e.mm->num_inputs() == 2);
    CHECK(e.mm->input(0) == e.a);
    CHECK(e.mm->input(1) == e.b);
    CHECK(e.mm->attrs().transpose_a == false);
    CHECK(e.mm->attrs().transpose_b == false);
    CHECK(e.mm->result()->producer() == e.mm);

    // ---- 5. add / relu：一元二元的类型传播 ----
    CHECK(e.add->kind() == OpKind::Add);
    CHECK(e.add->num_inputs() == 2);
    CHECK(e.add->input(0) == e.mm->result());
    CHECK(e.add->input(1) == e.bias->result());
    CHECK(e.relu->kind() == OpKind::Relu);
    CHECK(e.relu->num_inputs() == 1);
    CHECK(e.relu->input(0) == e.add->result());

    // ---- 6. dtype 传播：f16 进 f16 出 ----
    {
        Graph g("f16");
        Value* x = g.add_input("x", {Dtype::F16, {4, 8}});
        Value* y = g.add_input("y", {Dtype::F16, {8, 2}});
        Node* mm = g.add_matmul(x, y, "z");
        CHECK(mm->result()->type().dtype == Dtype::F16);
        CHECK(mm->result()->type().to_string() == "f16<4x2>");
        CHECK(x->type().bytes() == 64);  // 4x8x2 字节
    }

    // ---- 7. transpose 属性：同一个小差异，不派生子类 ----
    {
        Graph g = one_matmul_graph();
        const Node* mm = g.nodes().back().get();
        CHECK(mm->attrs().transpose_b == true);
        CHECK(mm->attrs().transpose_a == false);
        CHECK(mm->result()->type() == (TensorType{Dtype::F32, {2, 2}}));
        CHECK(g.to_string().find("transpose_b") != std::string::npos);
    }

    // ---- 8. 文本 IR：类型与属性都打印出来 ----
    {
        const std::string text = e.graph.to_string();
        CHECK(text.find("%A = input : f32<2x3>") != std::string::npos);
        CHECK(text.find("%B = input : f32<3x2>") != std::string::npos);
        CHECK(text.find("constant() {data = [0, -100, -150, -50]}") != std::string::npos);
        CHECK(text.find("matmul(%A, %B) -> %C : f32<2x2>") != std::string::npos);
        CHECK(text.find("add(%C, %bias) -> %D : f32<2x2>") != std::string::npos);
        CHECK(text.find("relu(%D) -> %Y : f32<2x2>") != std::string::npos);
        CHECK(text.find("output %Y") != std::string::npos);
    }

    // ---- 9. 廉价检查：错误消息指名道姓 ----
    CHECK(throws_with("内维不匹配 3 vs 2", [] {
              Graph g("t");
              Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
              Value* b = g.add_input("B", {Dtype::F32, {2, 3}});
              g.add_matmul(a, b, "C");  // 不带 transpose_b：3 vs 2
          }));
    CHECK(throws_with("dtype 不一致 f32 vs f16", [] {
              Graph g("t");
              Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
              Value* b = g.add_input("B", {Dtype::F16, {3, 2}});
              g.add_matmul(a, b, "C");
          }));
    CHECK(throws_with("类型必须完全一致", [] {
              Graph g("t");
              Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
              Value* y = g.add_input("y", {Dtype::F32, {2, 3}});
              g.add_elementwise(OpKind::Add, x, y, "z");
          }));
    CHECK(throws_with("数据个数 3 与元素数 4 不符", [] {
              Graph g("t");
              g.add_constant("c", {Dtype::F32, {2, 2}}, {1.0, 2.0, 3.0});
          }));
    CHECK(throws_with("只支持二维", [] {
              Graph g("t");
              Value* x = g.add_input("x", {Dtype::F32, {3}});
              Value* y = g.add_input("y", {Dtype::F32, {3}});
              g.add_matmul(x, y, "z");
          }));

    // ---- 10. 小解释器：记录的类型/属性足够还原语义 ----
    {
        Interpreter interp;
        interp.bind(e.a, {1, 2, 3, 4, 5, 6});
        interp.bind(e.b, {7, 8, 9, 10, 11, 12});
        interp.run(e.graph);
        const std::vector<double>& c = interp.of(e.mm->result());
        CHECK(c == (std::vector<double>{58, 64, 139, 154}));       // A x B
        const std::vector<double>& d = interp.of(e.add->result());
        CHECK(d == (std::vector<double>{58, -36, -11, 104}));      // + bias
        const std::vector<double>& y = interp.of(e.relu->result());
        CHECK(y == (std::vector<double>{58, 0, 0, 104}));          // relu 截断负数
    }

    // ---- 11. 解释器对照：transpose_b 版本算出同样的数 ----
    {
        Graph g = one_matmul_graph();
        Interpreter interp;
        interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
        interp.bind(g.inputs()[1], {7, 9, 11, 8, 10, 12});  // B^T 按行存
        interp.run(g);
        CHECK(interp.of(g.nodes().back()->result()) ==
              (std::vector<double>{58, 64, 139, 154}));
    }

    // ---- 12. 拷贝仍被删除、移动仍可用（第 8 天的所有权语义没变） ----
    static_assert(!std::is_copy_constructible<Graph>::value, "Graph 不可拷贝");
    static_assert(!std::is_copy_assignable<Graph>::value, "Graph 不可拷贝赋值");
    static_assert(std::is_nothrow_move_constructible<Graph>::value, "Graph 可移动");
    {
        Example e2;
        const Value* c_before = e2.mm->result();
        Graph moved = std::move(e2.graph);
        CHECK(c_before->producer() == moved.nodes()[1].get());  // 借用指针依然有效
        CHECK(moved.num_values() == 6);
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
