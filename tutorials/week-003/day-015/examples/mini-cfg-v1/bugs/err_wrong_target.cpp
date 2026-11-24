// 反面教材（第 15 天错误二）：跳转目标写错一格——结构合法的死循环。
// 现场模拟：写循环求和时，循环体的回边手滑写成了「跳回自己」：
//   正确：b2->term_jump(b1)   // 回到循环头，下一轮先判条件
//   手滑：b2->term_jump(b2)   // 跳回自己——条件永远不再被检查
// 三个观察点：
//   1) verify: PASS——每块都有终结符、每个目标都存在且属于本图，
//      CFG 层面这是一张完全合法的图。第 14 天的教训换了个马甲：
//      「结构合法 ≠ 语义正确」，CFG 的 Verifier 只管结构；
//   2) 解释器没有像 DAG 解释器那样自然终止——CFG 允许成环，
//      「执行到头」不再由图结构保证，只能由燃料上限兜底；
//   3) 失败消息里带最后 12 个块的路径片段：b2 -> b2 -> b2 ...
//      路径日志本身就是定位工具——一眼看出卡在哪个圈里。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Cfg.cpp ../src/Interpreter.cpp err_wrong_target.cpp \
//     -o err_wrong_target && ./err_wrong_target; echo "exit code: $?"
#include <cstdio>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

Cfg build_sum_loop_wrong_target() {
    Cfg cfg("sum-1-to-n-oops");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");
    BasicBlock* b2 = cfg.new_block("b2");
    BasicBlock* b3 = cfg.new_block("b3");
    b0->emit_const("i", 1);
    b0->emit_const("sum", 0);
    b0->term_jump(b1);
    b1->emit_bin(Op::Le, "c", Operand::var_of("i"), Operand::var_of("n"));
    b1->term_cond_branch(Operand::var_of("c"), b2, b3);
    b2->emit_bin(Op::Add, "sum", Operand::var_of("sum"), Operand::var_of("i"));
    b2->emit_bin(Op::Add, "i", Operand::var_of("i"), Operand::of(1));
    b2->term_jump(b2);  // ← 手滑：本该是 b1（循环头）
    b3->term_return(Operand::var_of("sum"));
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    Cfg cfg = build_sum_loop_wrong_target();

    std::printf("== Verifier：这张图合法吗？ ==\n");
    std::string why;
    std::printf("  verify: %s\n", cfg.verify(&why) ? "PASS（结构没有问题）" : why.c_str());

    std::printf("\n== 解释器：用较小的燃料上限跑一次 ==\n");
    const RunResult r = run_cfg(cfg, "n", 5, 300);
    std::printf("  ok = %d\n", r.ok ? 1 : 0);
    std::printf("  路径前 8 步：");
    for (std::size_t i = 0; i < r.path.size() && i < 8; ++i) {
        std::printf(" %s", r.path[i].c_str());
    }
    std::printf(" ...\n  失败原因：%s\n", r.error.c_str());

    std::printf("\n== 对照：回边改回 b1 之后（修复就一个字） ==\n");
    Cfg fixed("sum-1-to-n-fixed");
    BasicBlock* b0 = fixed.new_block("b0");
    BasicBlock* b1 = fixed.new_block("b1");
    BasicBlock* b2 = fixed.new_block("b2");
    BasicBlock* b3 = fixed.new_block("b3");
    b0->emit_const("i", 1);
    b0->emit_const("sum", 0);
    b0->term_jump(b1);
    b1->emit_bin(Op::Le, "c", Operand::var_of("i"), Operand::var_of("n"));
    b1->term_cond_branch(Operand::var_of("c"), b2, b3);
    b2->emit_bin(Op::Add, "sum", Operand::var_of("sum"), Operand::var_of("i"));
    b2->emit_bin(Op::Add, "i", Operand::var_of("i"), Operand::of(1));
    b2->term_jump(b1);  // ← 修复：回到循环头，条件每轮都会被检查
    b3->term_return(Operand::var_of("sum"));
    fixed.set_entry(b0);
    const RunResult ok = run_cfg(fixed, "n", 5, 300);
    std::printf("  n=5 => 结果 = %lld\n", static_cast<long long>(ok.value));
    return 0;
}
