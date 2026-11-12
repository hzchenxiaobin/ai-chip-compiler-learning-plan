// 第 15 天的对照实验：只改一个常量——条件阈值从 4 改成 9。
// 同一个程序、同样的三个输入 a = 1/2/3：
//   变体 A（阈值 4）：a=1 走 else、a=2 走 else（4>4 不成立）、a=3 走 then
//   变体 B（阈值 9）：a=3 时 s=9，9>9 不成立 → 也走 else！
// 同一个输入 a=3，两条变体走不同的边、得到不同的结果——
// CFG 记录的是「可能怎么走」（所有边），真正走哪条边由运行期的数据决定。
// 这正是「计算图 DAG 的执行顺序是编译期确定的拓扑序」与
// 「CFG 的执行顺序是运行期选出来的路径」的根本差别。
// 编译运行（在 experiments/ 目录下）：
//   g++ -std=c++17 -Wall -Wextra -I ../src ../src/Cfg.cpp ../src/Interpreter.cpp
//     threshold_ab.cpp -o threshold_ab && ./threshold_ab
#include <cstdio>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

Cfg build_leaky(std::int64_t threshold) {
    Cfg cfg(threshold == 4 ? "leaky-th4" : "leaky-th9");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");
    BasicBlock* b2 = cfg.new_block("b2");
    BasicBlock* b3 = cfg.new_block("b3");
    b0->emit_bin(Op::Mul, "s", Operand::var_of("a"), Operand::var_of("a"));
    b0->emit_bin(Op::Gt, "c", Operand::var_of("s"), Operand::of(threshold));  // ← 唯一变量
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_bin(Op::Mul, "u", Operand::var_of("s"), Operand::of(2));
    b1->term_jump(b3);
    b2->emit_bin(Op::Add, "u", Operand::var_of("s"), Operand::of(1));
    b2->term_jump(b3);
    b3->emit_bin(Op::Add, "z", Operand::var_of("u"), Operand::of(1));
    b3->term_return(Operand::var_of("z"));
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    Cfg a4 = build_leaky(4);
    Cfg a9 = build_leaky(9);

    std::printf("变体 A：if (s > 4)  变体 B：if (s > 9)   （程序其余部分一字不动）\n\n");
    std::printf("  a      s=a*a    A: 走的边 / z        B: 走的边 / z\n");
    for (const std::int64_t a : {1, 2, 3}) {
        const RunResult ra = run_cfg(a4, "a", a);
        const RunResult rb = run_cfg(a9, "a", a);
        const auto edge = [&ra](const char* then_name, const char* else_name) -> const char* {
            for (const auto& name : ra.path) {
                if (name == then_name) {
                    return "then";
                }
                if (name == else_name) {
                    return "else";
                }
            }
            return "?";
        };
        const auto edge_b = [&rb](const char* then_name, const char* else_name) -> const char* {
            for (const auto& name : rb.path) {
                if (name == then_name) {
                    return "then";
                }
                if (name == else_name) {
                    return "else";
                }
            }
            return "?";
        };
        std::printf("  %lld      %lld        %-6s / %lld          %-6s / %lld\n",
                    static_cast<long long>(a), static_cast<long long>(a * a),
                    edge("b1", "b2"), static_cast<long long>(ra.value),
                    edge_b("b1", "b2"), static_cast<long long>(rb.value));
    }

    std::printf("\n两份 CFG 的结构完全相同（4 块 4 边的菱形），diff 只有一行：\n");
    std::printf("  <   c = gt s, 4\n");
    std::printf("  >   c = gt s, 9\n");
    std::printf("但 a=3 的执行路径从 b0->b1->b3 变成了 b0->b2->b3，结果从 19 变成 11。\n");
    std::printf("边的「形状」是编译期的事，走哪条边是运行期的事——这就是控制流。\n");
    return 0;
}
