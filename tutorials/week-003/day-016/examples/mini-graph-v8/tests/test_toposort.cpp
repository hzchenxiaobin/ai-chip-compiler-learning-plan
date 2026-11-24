// 第 16 天的验收测试：拓扑排序与依赖检查。
// 五组：
//   一、合法图的排序正确性（经典链、双通道、重复槽位、恒等图、死节点）；
//   二、波次性质（同波互不依赖、波数 = 关键路径深度、确定性）；
//   三、环检测（自环 / 2 环 / 3 环 / 环+下游 / 独立分支）；
//   四、改图路径（rewire 的账本搬家与守卫、replace 的自环与合法用法、
//       创建序在改图后失效、erase 后重排）；
//   五、防线联动（拓扑排序拒绝 ⇢ topological_order 抛异常 ⇢ 解释器拒绝）。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "OpKind.h"
#include "TopoSort.h"
#include "Value.h"
#include "Verifier.h"

namespace {

int g_checks = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (!(cond)) {                                                  \
            std::fprintf(stderr, "CHECK 失败：%s（第 %d 行）\n", #cond,    \
                         __LINE__);                                     \
            return 1;                                                   \
        }                                                               \
        ++g_checks;                                                     \
    } while (0)

bool has_sub(const std::string& s, const std::string& sub) {
    return s.find(sub) != std::string::npos;
}

// 通用的「这是个合法拓扑序吗」：每个节点恰好出现一次，
// 且每条数据边（生产者 → 使用者）都从左往右。
bool is_valid_topo_order(const Graph& g, const std::vector<const Node*>& order) {
    if (order.size() != static_cast<std::size_t>(g.num_nodes())) {
        return false;
    }
    std::unordered_map<const Node*, std::size_t> pos;
    for (std::size_t i = 0; i < order.size(); ++i) {
        if (!pos.emplace(order[i], i).second) {
            return false;  // 出现两次
        }
    }
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (const Value* in : n->inputs()) {
            if (in == nullptr || in->producer() == nullptr) {
                continue;
            }
            const auto it = pos.find(in->producer());
            if (it == pos.end() || it->second >= pos[n.get()]) {
                return false;  // 生产者必须排在使用者前面
            }
        }
    }
    return true;
}

// 前缀合法性（环图剥下的部分序）：出现的不重复；
// 两端都落在前缀里的边，仍要从左往右（指向环外的边不算数）。
bool is_valid_partial_order(const Graph& g, const std::vector<const Node*>& order) {
    std::unordered_map<const Node*, std::size_t> pos;
    for (std::size_t i = 0; i < order.size(); ++i) {
        if (!pos.emplace(order[i], i).second) {
            return false;
        }
    }
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        const auto pit = pos.find(n.get());
        if (pit == pos.end()) {
            continue;
        }
        for (const Value* in : n->inputs()) {
            if (in == nullptr || in->producer() == nullptr) {
                continue;
            }
            const auto qit = pos.find(in->producer());
            if (qit != pos.end() && qit->second >= pit->second) {
                return false;
            }
        }
    }
    return true;
}

// 节点在第几波（0 起）；不在任何波里返回 -1。
int wave_of(const TopoSortResult& r, const Node* n) {
    for (std::size_t w = 0; w < r.waves.size(); ++w) {
        for (const Node* x : r.waves[w]) {
            if (x == n) {
                return static_cast<int>(w);
            }
        }
    }
    return -1;
}

// 同一波里的节点两两互不依赖（谁都别是另一个的生产者下游）。
bool wave_is_parallel(const std::vector<const Node*>& wave) {
    for (const Node* a : wave) {
        for (const Node* b : wave) {
            if (a == b) {
                continue;
            }
            for (const Value* in : b->inputs()) {
                if (in != nullptr && in->producer() == a) {
                    return false;  // b 在等 a——不能同波
                }
            }
        }
    }
    return true;
}

// 经典链：bias + A×B + add + relu（第二幕事故前的好图）。
struct Chain {
    Graph graph{"chain"};
    Value* a = nullptr;
    Value* b = nullptr;
    Node* bias = nullptr;
    Node* mm = nullptr;
    Node* add = nullptr;
    Node* relu = nullptr;

    Chain() {
        a = graph.add_input("A", {Dtype::F32, {2, 3}});
        b = graph.add_input("B", {Dtype::F32, {3, 2}});
        bias = graph.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
        mm = graph.add_matmul(a, b, "C");
        add = graph.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
        relu = graph.add_relu(add->result(), "R");
        graph.mark_output(relu->result());
    }
};

}  // namespace

int main() {
    // ---------- 一、合法图的排序正确性 ----------

    // 1. 经典链：ok、恰好排下、每条边从左到右、创建序即拓扑序（工厂定理）。
    {
        Chain ex;
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(r.stuck == 0);
        CHECK(r.peeled == 4);
        CHECK(r.order.size() == 4);
        CHECK(is_valid_topo_order(ex.graph, r.order));
        CHECK(r.order[0] == ex.bias);
        CHECK(r.order[1] == ex.mm);
        CHECK(r.order[2] == ex.add);
        CHECK(r.order[3] == ex.relu);
        CHECK(r.waves.size() == 3);  // [bias, mm] → [add] → [relu]
        CHECK(r.waves[0].size() == 2);
        CHECK(r.waves[1].size() == 1);
        CHECK(r.waves[2].size() == 1);
    }

    // 2. 双通道图：波数 = 关键路径深度 4；同一波可并行。
    {
        Graph g("dual");
        Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
        Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
        Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0, -100, -150, -50});
        Node* mm1 = g.add_matmul(a, b, "C1");
        Node* mm2 = g.add_matmul(a, b, "C2");
        Node* d = g.add_elementwise(OpKind::Add, mm1->result(), bias->result(), "D");
        Node* e = g.add_elementwise(OpKind::Add, mm2->result(), bias->result(), "E");
        Node* s = g.add_elementwise(OpKind::Add, d->result(), e->result(), "S");
        Node* r0 = g.add_relu(s->result(), "R");
        g.mark_output(r0->result());

        const TopoSortResult r = topo_sort(g);
        CHECK(r.ok);
        CHECK(r.order.size() == 7);
        CHECK(is_valid_topo_order(g, r.order));
        CHECK(r.waves.size() == 4);  // const/mm/mm → add/add → add → relu
        CHECK(wave_is_parallel(r.waves[0]));
        CHECK(wave_is_parallel(r.waves[1]));
        CHECK(wave_is_parallel(r.waves[2]));
        CHECK(wave_is_parallel(r.waves[3]));
        CHECK(r.waves[0].size() == 3);
        CHECK(r.waves[1].size() == 2);
        CHECK(r.waves[2].size() == 1);
        CHECK(r.waves[3].size() == 1);

        // 汇合点 S 必须晚于它的两个生产者 D、E；D、E 同波。
        CHECK(wave_of(r, s) == 2);
        CHECK(wave_of(r, d) == 1);
        CHECK(wave_of(r, e) == 1);
        CHECK(wave_of(r, s) > wave_of(r, d));
        CHECK(wave_of(r, s) > wave_of(r, e));

        // 共享输入的账本：A 被 mm1、mm2 各用一次。
        CHECK(a->num_uses() == 2);
        CHECK(b->num_uses() == 2);
        CHECK(bias->result()->num_uses() == 2);

        // 拼接顺序与波次一致。
        std::size_t k = 0;
        for (const std::vector<const Node*>& w : r.waves) {
            for (const Node* n : w) {
                CHECK(r.order[k++] == n);
            }
        }
    }

    // 3. 重复槽位 add(%C, %C)：pending 按槽计数、账本按记录减，
    //    两笔账一一对消，照样剥得干净。
    {
        Chain ex;
        Node* dup =
            ex.graph.add_elementwise(OpKind::Add, ex.mm->result(), ex.mm->result(), "D2");
        ex.graph.mark_output(dup->result());
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(r.order.size() == 5);
        CHECK(is_valid_topo_order(ex.graph, r.order));
        CHECK(ex.mm->result()->num_uses() == 3);  // add、relu、dup
        // 解释器也要能按这份序算对。
        Interpreter it;
        it.bind(ex.a, {1, 2, 3, 4, 5, 6});
        it.bind(ex.b, {7, 8, 9, 10, 11, 12});
        it.run(ex.graph);  // 不抛即通过
        const std::vector<double>& out = it.of(dup->result());
        CHECK(out[0] == 116.0);  // 2×58
    }

    // 4. 恒等图（没有节点）：排序也该安静地成功。
    {
        Graph g("identity");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        g.mark_output(x);
        const TopoSortResult r = topo_sort(g);
        CHECK(r.ok);
        CHECK(r.order.empty());
        CHECK(r.waves.empty());
        CHECK(r.peeled == 0);
        CHECK(r.stuck == 0);
        CHECK(verify_graph(g).ok);
    }

    // 5. 只有常量：单节点单波。
    {
        Graph g("const-only");
        Node* k = g.add_constant("k", {Dtype::F32, {2, 2}}, {1, 2, 3, 4});
        g.mark_output(k->result());
        const TopoSortResult r = topo_sort(g);
        CHECK(r.ok);
        CHECK(r.order.size() == 1);
        CHECK(r.order[0] == k);
        CHECK(r.waves.size() == 1);
    }

    // 6. 死节点照排：没人用、不是输出，拓扑排序照样给它排座位
    //    （排不排是调度的事，删不删是第 25 天 DCE 的事）。
    //    它只依赖 mm（第 1 波），所以落在第 2 波——和 add 同波、在 relu 前。
    {
        Chain ex;
        Node* dead = ex.graph.add_relu(ex.mm->result(), "dead");
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(r.order.size() == 5);
        CHECK(is_valid_topo_order(ex.graph, r.order));
        CHECK(wave_of(r, dead) == 1);       // 与 add 同一波
        CHECK(wave_of(r, ex.relu) == 2);    // relu 依赖 add，再晚一波
        CHECK(r.order[3] == dead);          // 波次拼接后死节点排在 relu 前面
        CHECK(r.order[4] == ex.relu);
    }

    // 7. 确定性：同一张图排两遍，结果逐节点一致。
    {
        Chain ex;
        const TopoSortResult r1 = topo_sort(ex.graph);
        const TopoSortResult r2 = topo_sort(ex.graph);
        CHECK(r1.order == r2.order);
        CHECK(r1.waves.size() == r2.waves.size());
        for (std::size_t w = 0; w < r1.waves.size(); ++w) {
            CHECK(r1.waves[w] == r2.waves[w]);
        }
    }

    // ---------- 二、环检测与诊断 ----------

    // 8. 自环：replace_all_uses_of(%C, %D) 让 add 吃起自己的结果。
    {
        Chain ex;
        ex.graph.replace_all_uses_of(ex.mm->result(), ex.add->result());
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(!r.ok);
        CHECK(r.peeled == 2);  // bias、mm 剥下来了
        CHECK(r.stuck == 2);   // add、relu 卡住
        CHECK(r.cycle.size() == 2);
        CHECK(r.cycle[0] == ex.add);
        CHECK(r.cycle[1] == ex.add);  // 首尾同节点
        CHECK(cycle_to_string(r.cycle) == "add%n2 -> add%n2");
        CHECK(r.waves.size() == 1);  // 只剥出一波（前缀）
        CHECK(is_valid_partial_order(ex.graph, r.order));  // 前缀对前缀内部仍是合法序
        CHECK(r.order.size() == 2);
        CHECK(r.order[0] == ex.bias);  // 前缀恰好是环外的部分
        CHECK(r.order[1] == ex.mm);

        // 验证器照样 PASS：环不是结构/类型/账本问题。
        CHECK(verify_graph(ex.graph).ok);
        // 账本自洽（不变量保持）：%D 有两条记录——原住民 relu，
        // 新搬来的 add 自己（吃自己的结果）。
        CHECK(ex.add->result()->num_uses() == 2);
        CHECK(ex.mm->result()->num_uses() == 0);  // %C 替换后无人使用
    }

    // 9. 2 环：rewire 把 add 的 bias 槽改接 %R——add 等 relu，relu 等 add。
    {
        Chain ex;
        ex.graph.rewire_input(ex.add, 1, ex.relu->result());
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(!r.ok);
        CHECK(r.peeled == 2);
        CHECK(r.stuck == 2);
        CHECK(r.cycle.size() == 3);
        CHECK(r.cycle[0] == ex.add);
        CHECK(r.cycle[1] == ex.relu);
        CHECK(r.cycle[2] == ex.add);
        CHECK(cycle_to_string(r.cycle) == "add%n2 -> relu%n3 -> add%n2");
        CHECK(verify_graph(ex.graph).ok);  // 类型全对，Verifier 放行

        const std::string msg = topo_error_message(ex.graph, r);
        CHECK(has_sub(msg, "含环"));
        CHECK(has_sub(msg, "无拓扑序"));
        CHECK(has_sub(msg, "add%n2 -> relu%n3 -> add%n2"));
        CHECK(has_sub(msg, "已剥 2 个、卡住 2 个"));
        CHECK(has_sub(msg, "环上 2 个节点"));
    }

    // 10. 3 环：relu 链 x→v1→v2→v3，再把 v1 的生产者改吃 v3。
    //     依赖方向 v1←v3←v2←v1，环长 3，一个节点都剥不下来。
    {
        Graph g("three-cycle");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Node* r1 = g.add_relu(x, "v1");
        Node* r2 = g.add_relu(r1->result(), "v2");
        Node* r3 = g.add_relu(r2->result(), "v3");
        g.rewire_input(r1, 0, r3->result());  // n0 反过来吃 n2 的结果
        g.mark_output(r3->result());
        const TopoSortResult r = topo_sort(g);
        CHECK(!r.ok);
        CHECK(r.peeled == 0);
        CHECK(r.stuck == 3);
        CHECK(r.cycle.size() == 4);
        CHECK(cycle_to_string(r.cycle) == "relu%n0 -> relu%n2 -> relu%n1 -> relu%n0");
        CHECK(r.order.empty());
        CHECK(r.waves.empty());
    }

    // 11. 环 + 下游：环上的 3 个卡住，下游也卡——「卡住」≠「环上」；
    //     环外独立分支照常剥下。
    {
        Graph g("cycle-plus");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Node* r1 = g.add_relu(x, "v1");
        Node* r2 = g.add_relu(r1->result(), "v2");
        Node* r3 = g.add_relu(r2->result(), "v3");
        g.rewire_input(r1, 0, r3->result());
        Node* tail = g.add_relu(r3->result(), "v4");  // 下游：不在环上，但被环堵死
        Node* free_k = g.add_constant("k", {Dtype::F32, {2, 2}}, {1, 2, 3, 4});  // 独立分支
        g.mark_output(tail->result());
        g.mark_output(free_k->result());
        const TopoSortResult r = topo_sort(g);
        CHECK(!r.ok);
        CHECK(r.stuck == 4);  // 环 3 + 下游 1
        CHECK(r.peeled == 1);  // 常量节点不依赖任何人，照剥
        CHECK(r.cycle.size() == 4);  // 环路径只画环上的 3 个
        CHECK(r.order[0] == free_k);
    }

    // 12. 大环长一点（5 环）：路径首尾闭合、长度如实报告。
    {
        Graph g("five-cycle");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        std::vector<Node*> chain;
        for (int i = 0; i < 5; ++i) {
            if (i == 0) {
                chain.push_back(g.add_relu(x, "c0"));
            } else {
                chain.push_back(g.add_relu(chain.back()->result(), "c" + std::to_string(i)));
            }
        }
        g.rewire_input(chain[0], 0, chain[4]->result());  // c0 吃 c4：5 环
        g.mark_output(chain[4]->result());
        const TopoSortResult r = topo_sort(g);
        CHECK(!r.ok);
        CHECK(r.stuck == 5);
        CHECK(r.peeled == 0);
        CHECK(r.cycle.size() == 6);  // 5 个节点 + 首尾重复
        CHECK(r.cycle.front() == r.cycle.back());
        CHECK(has_sub(cycle_to_string(r.cycle), "relu%n0"));
        CHECK(has_sub(cycle_to_string(r.cycle), "relu%n4"));
    }

    // ---------- 三、改图路径与守卫 ----------

    // 13. 合法的 rewire：换一个同类型常量——账本搬家、无环、排序照常。
    {
        Chain ex;
        Node* bias2 = ex.graph.add_constant("bias2", {Dtype::F32, {2, 2}}, {1, 1, 1, 1});
        ex.graph.rewire_input(ex.add, 1, bias2->result());
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(r.order.size() == 5);
        CHECK(is_valid_topo_order(ex.graph, r.order));
        CHECK(ex.bias->result()->num_uses() == 0);  // 旧值：记录注销了
        CHECK(bias2->result()->num_uses() == 1);    // 新值：记录登记了
        CHECK(verify_graph(ex.graph).ok);
        CHECK(r.order[4] == ex.relu);
    }

    // 14. rewire 的三个守卫：空指针、越界、外来节点。
    {
        Chain ex;
        bool threw = false;
        try {
            ex.graph.rewire_input(ex.add, 0, nullptr);
        } catch (const std::invalid_argument& e) {
            threw = has_sub(e.what(), "空指针");
        }
        CHECK(threw);

        threw = false;
        try {
            ex.graph.rewire_input(ex.relu, 1, ex.a);  // relu 只有 1 个槽
        } catch (const std::invalid_argument& e) {
            threw = has_sub(e.what(), "越界");
        }
        CHECK(threw);

        Graph donor("donor");
        Value* dx = donor.add_input("D", {Dtype::F32, {2, 2}});
        Value* dy = donor.add_input("E", {Dtype::F32, {2, 2}});
        Node* fmm = donor.add_matmul(dx, dy, "FC");
        threw = false;
        try {
            ex.graph.rewire_input(fmm, 0, ex.a);  // 节点是外图的——不行
        } catch (const std::invalid_argument& e) {
            threw = has_sub(e.what(), "不属于本图");
        }
        CHECK(threw);
    }

    // 15. 改图之后「创建序 = 拓扑序」失效：n1 先造、后改吃 n2 的结果——
    //     无环，但创建序不再是合法拓扑序，Kahn 给出正确顺序。
    {
        Graph g("reordered");
        Value* x = g.add_input("x", {Dtype::F32, {2, 2}});
        Value* y = g.add_input("y", {Dtype::F32, {2, 2}});
        Node* n1 = g.add_relu(x, "v1");       // 创建序第 1
        Node* n2 = g.add_relu(y, "v2");       // 创建序第 2
        g.rewire_input(n1, 0, n2->result());  // 第 1 个改吃第 2 个
        g.mark_output(n1->result());
        const TopoSortResult r = topo_sort(g);
        CHECK(r.ok);
        CHECK(r.order.size() == 2);
        CHECK(r.order[0] == n2);  // 生产者必须在前
        CHECK(r.order[1] == n1);
        std::vector<const Node*> creation{g.nodes()[0].get(), g.nodes()[1].get()};
        CHECK(creation[0] == n1);
        CHECK(!is_valid_topo_order(g, creation));  // 创建序已经不合法了
        CHECK(verify_graph(g).ok);
    }

    // 16. replace 的合法用法（把 bias 换成 bias2）之后重排：一切照常。
    {
        Chain ex;
        Node* bias2 = ex.graph.add_constant("bias2", {Dtype::F32, {2, 2}}, {9, 9, 9, 9});
        ex.graph.replace_all_uses_of(ex.bias->result(), bias2->result());
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(is_valid_topo_order(ex.graph, r.order));
        CHECK(ex.bias->result()->num_uses() == 0);
        CHECK(bias2->result()->num_uses() == 1);
        CHECK(verify_graph(ex.graph).ok);
    }

    // 17. erase 之后重排：名单短了，序仍然合法。
    {
        Chain ex;
        Node* dead = ex.graph.add_relu(ex.mm->result(), "dead");
        ex.graph.erase_node(dead);
        const TopoSortResult r = topo_sort(ex.graph);
        CHECK(r.ok);
        CHECK(r.order.size() == 4);
        CHECK(is_valid_topo_order(ex.graph, r.order));
    }

    // 18. 跨图依赖（Verifier 该拦的病图）：拓扑排序不冒充环检测，
    //     但也绝不悄悄给错序——拒绝执行，诊断走另一条分支。
    {
        Graph donor("donor");
        Value* dx = donor.add_input("D", {Dtype::F32, {2, 2}});
        Node* dmm = donor.add_matmul(dx, dx, "DC");  // 2x2×2x2 合法
        Graph host("host");
        Node* r0 = host.add_raw_node(OpKind::Relu, {dmm->result()}, Attrs{},
                                      {Dtype::F32, {2, 2}}, "HR");
        host.mark_output(r0->result());
        const TopoSortResult r = topo_sort(host);
        CHECK(!r.ok);
        CHECK(r.cycle.empty());  // 不是环，别冒充
        CHECK(r.stuck == 1);
        CHECK(r.peeled == 0);
        const std::string msg = topo_error_message(host, r);
        CHECK(has_sub(msg, "无法调度"));
        CHECK(has_sub(msg, "先跑 Verifier"));
        CHECK(!verify_graph(host).ok);  // Verifier 才是第一道防线
    }

    // ---------- 四、防线联动 ----------

    // 19. topological_order()：好图给序，环图抛异常并带环路径。
    {
        Chain ex;
        const std::vector<const Node*> order = ex.graph.topological_order();
        CHECK(order.size() == 4);
        CHECK(is_valid_topo_order(ex.graph, order));

        ex.graph.rewire_input(ex.add, 1, ex.relu->result());
        bool threw = false;
        try {
            ex.graph.topological_order();
        } catch (const std::invalid_argument& e) {
            threw = has_sub(e.what(), "add%n2 -> relu%n3 -> add%n2");
            threw = threw && has_sub(e.what(), "含环，无拓扑序");
        }
        CHECK(threw);
    }

    // 20. 解释器按拓扑序执行：好图算得对；环图在入口处被拒。
    {
        Chain ex;
        Interpreter it;
        it.bind(ex.a, {1, 2, 3, 4, 5, 6});
        it.bind(ex.b, {7, 8, 9, 10, 11, 12});
        it.run(ex.graph);
        const std::vector<double>& out = it.of(ex.relu->result());
        CHECK(out[0] == 58.0);
        CHECK(out[1] == 0.0);   // 64 - 100 = -36 → relu → 0
        CHECK(out[2] == 0.0);   // 139 - 150 = -11 → relu → 0
        CHECK(out[3] == 104.0);

        ex.graph.rewire_input(ex.add, 1, ex.relu->result());
        Interpreter bad;
        bad.bind(ex.a, {1, 2, 3, 4, 5, 6});
        bad.bind(ex.b, {7, 8, 9, 10, 11, 12});
        bool threw = false;
        try {
            bad.run(ex.graph);
        } catch (const std::invalid_argument& e) {
            threw = has_sub(e.what(), "含环");
        }
        CHECK(threw);
    }

    // 21. 图名进入诊断：换张图，消息跟着换。
    {
        Chain ex;
        ex.graph.rewire_input(ex.add, 1, ex.relu->result());
        const TopoSortResult r = topo_sort(ex.graph);
        const std::string msg = topo_error_message(ex.graph, r);
        CHECK(has_sub(msg, "\"chain\""));  // Chain 的图名
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
