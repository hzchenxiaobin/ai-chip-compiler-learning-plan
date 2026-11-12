// 第 13 天的验收测试：从模型算子到图 IR 的映射。
// 三组问题：
//   1) 映射的忠实性——目标模型的每个名字、每个节点、每条连接、
//      每个属性都落到了正确的 IR 对象上（名字 → 身份的翻译没走样）；
//   2) 映射的三条纪律——名字唯一、定义先于使用（拓扑序）、
//      属性要么完整搬运要么拒绝，违反者全部构造失败且消息带上下文；
//   3) 回归——第 10/11/12 天的断言在 v6 里原样重跑（另两个测试文件）。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "Frontend.h"
#include "Graph.h"
#include "Interpreter.h"
#include "Model.h"
#include "Node.h"
#include "OpKind.h"
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

Model target_model() {
    Model m;
    m.name = "matmul-bias-relu";
    m.inputs = {{"A", {Dtype::F32, {2, 3}}}, {"B", {Dtype::F32, {3, 2}}}};
    m.weights = {{"bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0}}};
    m.layers = {
        {"MatMul", {"A", "B"}, "C"},
        {"Add", {"C", "bias"}, "D"},
        {"Relu", {"D"}, "Y"},
    };
    m.outputs = {"Y"};
    return m;
}

// catch 一次必抛的 lower，把异常消息带回来。
std::string lower_fails(const Model& m) {
    try {
        Graph g = lower_model_to_graph(m);
        (void)g;
    } catch (const std::invalid_argument& e) {
        return e.what();
    }
    return "";  // 没抛才算到这里
}

bool contains(const std::string& hay, const char* needle) {
    return hay.find(needle) != std::string::npos;
}

}  // namespace

int main() {
    // ===================== 1. 映射的忠实性 =====================
    {
        Graph g = lower_model_to_graph(target_model());

        CHECK(g.name() == "matmul-bias-relu");
        CHECK(static_cast<int>(g.inputs().size()) == 2);
        CHECK(g.inputs()[0]->name() == "A");
        CHECK(g.inputs()[1]->name() == "B");
        CHECK(g.inputs()[0]->type().to_string() == "f32<2x3>");
        CHECK(g.inputs()[1]->type().to_string() == "f32<3x2>");

        CHECK(g.num_nodes() == 4);  // constant + matmul + add + relu
        CHECK(g.num_values() == 6);  // 2 图输入 + 4 结果
        CHECK(g.nodes()[0]->kind() == OpKind::Constant);
        CHECK(g.nodes()[1]->kind() == OpKind::MatMul);
        CHECK(g.nodes()[2]->kind() == OpKind::Add);
        CHECK(g.nodes()[3]->kind() == OpKind::Relu);

        // 名字 → 身份：层的输入名字翻译成了正确的值对象（指针级核对）。
        const Node* cst = g.nodes()[0].get();
        const Node* mm = g.nodes()[1].get();
        const Node* add = g.nodes()[2].get();
        const Node* relu = g.nodes()[3].get();
        CHECK(cst->result()->name() == "bias");
        CHECK(mm->result()->name() == "C");
        CHECK(add->result()->name() == "D");
        CHECK(relu->result()->name() == "Y");
        CHECK(mm->input(0) == g.inputs()[0]);   // 层里的 "A" → 图输入 %A
        CHECK(mm->input(1) == g.inputs()[1]);   // 层里的 "B" → 图输入 %B
        CHECK(add->input(0) == mm->result());   // 层里的 "C" → matmul 的结果
        CHECK(add->input(1) == cst->result()); // 层里的 "bias" → 常量的结果
        CHECK(relu->input(0) == add->result()); // 层里的 "D" → add 的结果
        CHECK(cst->num_inputs() == 0);

        // 类型与属性也翻译到位。
        CHECK(mm->result()->type().to_string() == "f32<2x2>");
        CHECK(add->result()->type().to_string() == "f32<2x2>");
        CHECK(relu->result()->type().to_string() == "f32<2x2>");
        CHECK((cst->attrs().data == std::vector<double>{0, -100, -150, -50}));
        CHECK(!mm->attrs().transpose_a && !mm->attrs().transpose_b);

        CHECK(static_cast<int>(g.outputs().size()) == 1);
        CHECK(g.outputs()[0] == relu->result());

        // 前端是带守卫的建造路径：它的产物必须天然通过 Verifier。
        CHECK(verify_graph(g).ok);

        // 定理钉住：创建顺序就是拓扑序（文本 IR 因此天然可执行）。
        const std::vector<const Node*> order = g.topological_order();
        CHECK(order.size() == g.nodes().size());
        bool same = true;
        for (std::size_t i = 0; i < order.size(); ++i) {
            same = same && (order[i] == g.nodes()[i].get());
        }
        CHECK(same);

        // use-def：每个名字译过去的值，使用者与槽位都应正确。
        CHECK(g.inputs()[0]->num_uses() == 1);   // A → matmul 第 0 槽
        CHECK(g.inputs()[0]->users()[0].user == mm);
        CHECK(g.inputs()[0]->users()[0].operand == 0);
        CHECK(cst->result()->num_uses() == 1);   // bias → add 第 1 槽
        CHECK(cst->result()->users()[0].user == add);
        CHECK(cst->result()->users()[0].operand == 1);
        CHECK(mm->result()->num_uses() == 1);    // C → add 第 0 槽
        CHECK(add->result()->num_uses() == 1);   // D → relu 第 0 槽
        CHECK(relu->result()->num_uses() == 0);  // Y：只有图输出在用
        CHECK(g.inputs()[0]->producer() == nullptr);        // 图输入无生产者
        CHECK(mm->result()->producer() == mm);              // 结果回指生产者
        CHECK(cst->result()->producer() == cst);

        // 端到端：A = 1..6，B = 7..12 → Y = relu(A×B + bias) = 58 0 / 0 104。
        Interpreter interp;
        interp.bind(g.inputs()[0], {1, 2, 3, 4, 5, 6});
        interp.bind(g.inputs()[1], {7, 8, 9, 10, 11, 12});
        interp.run(g);
        const std::vector<double>& y = interp.of(g.outputs()[0]);
        CHECK(y[0] == 58 && y[1] == 0 && y[2] == 0 && y[3] == 104);
    }

    // ===================== 2. 共享与多输出 =====================
    {
        // 菱形：X 喂给 relu 和 add 两个消费者。
        Model m;
        m.name = "diamond";
        m.inputs = {{"X", {Dtype::F32, {2, 2}}}};
        m.layers = {
            {"Relu", {"X"}, "R"},
            {"Add", {"X", "R"}, "S"},
        };
        m.outputs = {"S"};

        Graph g = lower_model_to_graph(m);
        CHECK(g.num_nodes() == 2);
        CHECK(verify_graph(g).ok);
        CHECK(g.inputs()[0]->num_uses() == 2);  // 名字表：同一个 "X" 译成同一个值
        CHECK(g.inputs()[0]->users()[0].user == g.nodes()[0].get());  // relu 槽 0
        CHECK(g.inputs()[0]->users()[1].user == g.nodes()[1].get());  // add 槽 0

        // 中间值也可以当图输出：输出表和「谁生产」是两个概念（第 8 天）。
        Model m2 = target_model();
        m2.outputs = {"Y", "D"};
        Graph g2 = lower_model_to_graph(m2);
        CHECK(static_cast<int>(g2.outputs().size()) == 2);
        CHECK(verify_graph(g2).ok);

        // 直通模型：没有层，输入直接当输出。
        Model m3;
        m3.name = "identity";
        m3.inputs = {{"X", {Dtype::F32, {2, 2}}}};
        m3.outputs = {"X"};
        Graph g3 = lower_model_to_graph(m3);
        CHECK(g3.num_nodes() == 0);
        CHECK(verify_graph(g3).ok);
    }

    // ===================== 3. 映射的纪律 =====================
    {
        // 名字唯一：图输入撞名。
        {
            Model m = target_model();
            m.inputs.push_back({"A", {Dtype::F32, {2, 3}}});
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "已存在"));
            CHECK(contains(msg, "\"A\""));
        }
        // 名字唯一：权重与图输入撞名。
        {
            Model m = target_model();
            m.weights.push_back({"A", {Dtype::F32, {2, 3}}, {1, 2, 3, 4, 5, 6}});
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "已存在"));
        }
        // 名字唯一：两个层写同一个输出名。
        {
            Model m = target_model();
            m.layers[2].output = "C";
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "已存在"));
            CHECK(contains(msg, "第 3 层"));
        }
        // 定义先于使用：层序不是拓扑序（前向引用）。
        {
            Model m = target_model();
            m.layers = {{"Relu", {"D"}, "Y"}, {"Add", {"C", "bias"}, "D"}, {"MatMul", {"A", "B"}, "C"}};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "拓扑序"));
            CHECK(contains(msg, "第 1 层 Relu"));  // 报错原样引用模型写下的算子名
            CHECK(contains(msg, "\"D\""));
        }
        // 名字世界的自环：层的输出遮蔽了图输入（换一种病：不是环，是重定义）。
        {
            Model m;
            m.name = "self-loop";
            m.inputs = {{"C", {Dtype::F32, {2, 2}}}};
            m.layers = {{"Relu", {"C"}, "C"}};  // 输入解析成功，输出名撞上图输入
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "已存在"));
        }
        // 名字世界的自环：R = relu(R)，R 别处没有定义——真正的环。
        {
            Model m;
            m.name = "true-self-loop";
            m.inputs = {{"A", {Dtype::F32, {2, 2}}}};
            m.layers = {{"Relu", {"R"}, "R"}, {"Add", {"A", "R"}, "S"}};
            m.outputs = {"S"};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "自己的输出"));
            CHECK(contains(msg, "名字成环"));
        }
        {
            Model m;
            m.name = "self-loop2";
            m.inputs = {{"A", {Dtype::F32, {2, 2}}}};
            m.layers = {{"Relu", {"C"}, "D"}, {"Add", {"D", "C"}, "E"}};
            m.outputs = {"E"};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "在整个模型里都不存在"));
            CHECK(contains(msg, "\"C\""));
        }
        // 拼错名字。
        {
            Model m = target_model();
            m.layers[1].inputs[1] = "biasx";
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "在整个模型里都不存在"));
            CHECK(contains(msg, "第 2 层 Add 的第 1 个输入"));
        }
        // 算子名拼错（大小写也是错）。
        {
            Model m = target_model();
            m.layers[0].op = "Matmul";
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "不认识"));
        }
        // 常量不作为层。
        {
            Model m = target_model();
            m.layers.push_back({"Constant", {}, "K"});
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "常量请放进 weights"));
        }
        // 权重数据个数不符——报错带上权重名字（前端认得名字，工厂不认得）。
        {
            Model m = target_model();
            m.weights[0].data = {1, 2, 3};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "权重 \"bias\""));
            CHECK(contains(msg, "3"));
        }
        // 属性放错层：Add 带着 transpose 属性会被拒（不静默丢弃）。
        {
            Model m = target_model();
            m.layers[1].transpose_a = true;
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "transpose"));
        }
        // 层的输入个数不对：前端先于工厂拦下。
        {
            Model m = target_model();
            m.layers[0].inputs = {"A"};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "需要 2 个输入"));
        }
        // 图输出拼错。
        {
            Model m = target_model();
            m.outputs = {"Yx"};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "在整个模型里都不存在"));
        }
        // 图输出写两次。
        {
            Model m = target_model();
            m.outputs = {"Y", "Y"};
            const std::string msg = lower_fails(m);
            CHECK(contains(msg, "写了两次"));
        }
    }

    // ===================== 4. 身份、所有权与移动 =====================
    {
        // 两次 lower 得到两张独立的图：映射是纯函数，身份各自全新。
        Graph ga = lower_model_to_graph(target_model());
        Graph gb = lower_model_to_graph(target_model());
        CHECK(ga.nodes()[1]->result()->name() == gb.nodes()[1]->result()->name());
        CHECK(ga.nodes()[1]->result() != gb.nodes()[1]->result());  // 名字同、对象不同

        // 拷贝被编译期拒绝（第 8 天起的老规矩，前端返回值不破例）。
        static_assert(!std::is_copy_constructible<Graph>::value, "Graph 不可拷贝");
        static_assert(std::is_move_constructible<Graph>::value, "Graph 可移动");

        // 按值返回 → 移动：搬走房产证，节点和值原地不动，旧指针继续有效。
        const Value* y_before = ga.outputs()[0];
        const Node* relu_before = ga.nodes()[3].get();
        Graph moved = std::move(ga);
        CHECK(moved.outputs()[0] == y_before);
        CHECK(relu_before->result()->name() == "Y");
        CHECK(y_before->name() == "Y");
        CHECK(verify_graph(moved).ok);
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
