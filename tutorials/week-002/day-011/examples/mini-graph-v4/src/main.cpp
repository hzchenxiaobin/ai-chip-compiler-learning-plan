#include <chrono>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "Graph.h"
#include "Interpreter.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpCardPrinter.h"
#include "Value.h"
#include "bench.h"

namespace {

// 把一串 double 按二维 shape 打成矩阵的样子（同第 9/10 天）。
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

// 一个有状态的只读 Visitor：数每种算子各有多少个。
// 它写在 main.cpp 里——Node、Graph、Interpreter 一行没改。
// weighted() 给每种算子不同权重，和 bench_switch 的对照组可比。
class CounterVisitor : public NodeVisitor {
public:
    void visit_constant(const Node&) override { ++constant_; }
    void visit_matmul(const Node&) override { ++matmul_; }
    void visit_add(const Node&) override { ++add_; }
    void visit_relu(const Node&) override { ++relu_; }

    void reset() {
        constant_ = matmul_ = add_ = relu_ = 0;
    }

    std::int64_t count() const { return constant_ + matmul_ + add_ + relu_; }
    std::int64_t weighted() const { return constant_ + 2 * matmul_ + 3 * add_ + 4 * relu_; }

    std::int64_t constant_ = 0, matmul_ = 0, add_ = 0, relu_ = 0;
};

template <class Fn>
double time_ms(Fn&& fn) {
    const auto t0 = std::chrono::steady_clock::now();
    fn();
    const auto t1 = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(t1 - t0).count();
}

}  // namespace

int main() {
    // ================= 第一幕：visitor 版图打印器 =================
    // 经典图与第 10 天完全同款：Y = relu(A x B + bias)。
    Graph g("matmul-bias-relu");
    Value* a = g.add_input("A", {Dtype::F32, {2, 3}});
    Value* b = g.add_input("B", {Dtype::F32, {3, 2}});
    Node* bias = g.add_constant("bias", {Dtype::F32, {2, 2}}, {0.0, -100.0, -150.0, -50.0});
    Node* mm = g.add_matmul(a, b, "C");
    Node* add = g.add_elementwise(OpKind::Add, mm->result(), bias->result(), "D");
    Node* relu = g.add_relu(add->result(), "Y");
    g.mark_output(relu->result());

    std::printf("== 第一幕：to_string() 已改走 Visitor，输出与 v3 一字不差 ==\n%s\n\n",
                g.to_string().c_str());

    // 全新的打印行为：算子名片。OpCardPrinter 是一个新文件，
    // 库里一个字符都没改——「对扩展开放」的直接体验。
    std::string cards;
    OpCardPrinter card_printer(cards);
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(card_printer, *n);
    }
    std::printf("== 算子名片（OpCardPrinter，一个全新的只读 Visitor）==\n%s\n",
                cards.c_str());

    // 第三个访问者：计数器。同一个接口、三种用途，Graph 全程不知情。
    CounterVisitor counter;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        apply_visitor(counter, *n);
    }
    std::printf("计数器：constant=%ld matmul=%ld add=%ld relu=%ld（共 %ld 个节点）\n\n",
                static_cast<long>(counter.constant_), static_cast<long>(counter.matmul_),
                static_cast<long>(counter.add_), static_cast<long>(counter.relu_),
                static_cast<long>(counter.count()));

    // 只读性检查：访问者跑完之后，解释器算出的数字必须与第 10 天一致。
    Interpreter interp;
    interp.bind(a, {1, 2, 3, 4, 5, 6});
    interp.bind(b, {7, 8, 9, 10, 11, 12});
    interp.run(g);
    std::printf("== 访问者跑完，解释器再算（只读性：数字应仍是 58 0 / 0 104）==\n");
    print_matrix("Y", relu->result()->type(), interp.of(relu->result()));

    // ================= 第二幕：switch vs 虚函数的分发代价 =================
    // 混合大图：每轮 5 个节点（constant、matmul、constant、add、relu），
    // 20000 轮 = 100000 个节点、100001 个值。混合四种 kind，
    // 让分支预测和虚表都无法「一次猜中」。
    const int kIters = 20000;
    Graph big("mixed-chain");
    const Value* v = big.add_input("x", {Dtype::F32, {2, 2}});
    for (int i = 0; i < kIters; ++i) {
        const std::string tag = std::to_string(i);
        Node* w = big.add_constant("w" + tag, {Dtype::F32, {2, 2}}, {1, 0, 0, 1});
        Node* m = big.add_matmul(v, w->result(), "m" + tag);
        Node* bb = big.add_constant("b" + tag, {Dtype::F32, {2, 2}}, {1, 2, 3, 4});
        Node* aa = big.add_elementwise(OpKind::Add, m->result(), bb->result(), "a" + tag);
        Node* r = big.add_relu(aa->result(), "r" + tag);
        v = r->result();
    }
    big.mark_output(v);

    const std::int64_t n_nodes = big.num_nodes();
    const int kReps = 100;  // 每轮把 10 万个节点全部分发一遍
    const std::int64_t dispatches = n_nodes * kReps;

    // 正确性先于性能：两种分发必须数出同一个加权总数。
    // 每轮权重 1+2+1+3+4 = 11，20000 轮 × 100 遍。
    counter.reset();
    bench_visitor(big, counter, kReps);
    const std::int64_t visitor_total = counter.weighted();
    const std::int64_t switch_total = bench_switch(big, kReps);
    std::printf("\n== 第二幕：分发代价（%lld 个节点 × %d 遍 = %lld 次分发/方案）==\n",
                static_cast<long long>(n_nodes), kReps, static_cast<long long>(dispatches));
    std::printf("正确性：switch 加权总数 = %lld，visitor 加权总数 = %lld，%s\n\n",
                static_cast<long long>(switch_total), static_cast<long long>(visitor_total),
                switch_total == visitor_total && switch_total == 11 * kIters * kReps
                    ? "一致（= 每轮权重 11 × 20000 轮 × 100 遍）"
                    : "不一致！");

    // 每种方案跑 3 轮取最小值（这台机器上的单次测量也有毫秒级抖动）。
    double best_switch = 1e30, best_visitor = 1e30;
    for (int round = 1; round <= 3; ++round) {
        const std::int64_t sw = bench_switch(big, kReps);
        const double t_switch = time_ms([&] { bench_switch(big, kReps); });
        counter.reset();
        const double t_visitor = time_ms([&] { bench_visitor(big, counter, kReps); });
        if (sw < 0 || counter.count() != n_nodes * kReps) {
            std::printf("第 %d 轮计数异常\n", round);
            return 1;
        }
        best_switch = t_switch < best_switch ? t_switch : best_switch;
        best_visitor = t_visitor < best_visitor ? t_visitor : best_visitor;
        std::printf("第 %d 轮：switch %7.2f ms   visitor %7.2f ms\n", round, t_switch,
                    t_visitor);
    }
    std::printf("\n最好成绩：switch %7.2f ms（%.2f ns/次）   visitor %7.2f ms（%.2f ns/次）\n",
                best_switch, best_switch * 1e6 / static_cast<double>(dispatches), best_visitor,
                best_visitor * 1e6 / static_cast<double>(dispatches));
    std::printf("比值：visitor / switch ≈ %.2f 倍\n",
                best_visitor / best_switch);
    std::printf("（注意：这是 %s 构建。优化级别会显著改变这个比值，见正文 5.4 节）\n",
#ifdef __OPTIMIZE__
                "优化（-O2）"
#else
                "未优化（Debug）"
#endif
    );
    return 0;
}
