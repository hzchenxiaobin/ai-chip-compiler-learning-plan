// 反面教材（第 15 天错误三）：变量只在「没走到的分支」里定义。
// 现场模拟：想在 z 的计算里用 w，w 在 then 分支里定义——
// 而这条输入实际走了 else。三个层次的读法：
//   1) verify: PASS——「变量有没有值」根本不是 CFG 验证器的检查项，
//      因为答案不是图的结构属性，是「路径 × 定义位置」的组合；
//   2) 数据流表已经把风险亮出来了：w 的 def 只有 b1（一条路径），
//      use 在 b3（汇合点）——「定义不覆盖所有到达路径」就是风险本身；
//   3) 真正的修复是：让定义覆盖每条可能的路径（在 b0 先给 w 一个值），
//      或者更进一步——这正是第 17 天 SSA 的 PHI 节点要解决的正规问题。
// 这个现场把「控制流」和「数据流」第一次拧在一起：条件决定路径，
// 路径决定哪个定义到达使用点——这就是教科书里 reaching definitions
// （到达定义）问题的雏形。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Cfg.cpp ../src/Interpreter.cpp err_uninit_on_path.cpp \
//     -o err_uninit_on_path && ./err_uninit_on_path; echo "exit code: $?"
#include <cstdio>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

Cfg build_w_only_in_then() {
    Cfg cfg("w-in-then-only");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");
    BasicBlock* b2 = cfg.new_block("b2");
    BasicBlock* b3 = cfg.new_block("b3");
    b0->emit_const("c", 0);  // 0 = 假 → 实际走 else（b2）
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_const("w", 1);  // w 只在这条（没走到的）路径上定义
    b1->term_jump(b3);
    b2->term_jump(b3);
    b3->emit_bin(Op::Add, "z", Operand::var_of("w"), Operand::of(1));  // 使用点在汇合
    b3->term_return(Operand::var_of("z"));
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    Cfg cfg = build_w_only_in_then();

    std::printf("== Verifier：结构检查（注意它管不管 w） ==\n");
    std::string why;
    std::printf("  verify: %s\n", cfg.verify(&why) ? "PASS（结构没有问题——w 不是结构属性）"
                                                   : why.c_str());

    std::printf("\n== 数据流表：风险其实早就写在纸上 ==\n");
    std::printf("%s", cfg.dataflow_to_string().c_str());

    std::printf("\n== 解释器：走到 b3 才发现 w 没有值 ==\n");
    const RunResult r = run_cfg(cfg, "", 0);
    std::printf("  ok = %d\n", r.ok ? 1 : 0);
    std::printf("  路径：");
    for (const auto& name : r.path) {
        std::printf(" %s", name.c_str());
    }
    std::printf("\n  失败原因：%s\n", r.error.c_str());

    std::printf("\n== 对照：定义覆盖所有路径（b0 先给 w 一个值） ==\n");
    Cfg fixed("w-initialized");
    BasicBlock* b0 = fixed.new_block("b0");
    BasicBlock* b1 = fixed.new_block("b1");
    BasicBlock* b2 = fixed.new_block("b2");
    BasicBlock* b3 = fixed.new_block("b3");
    b0->emit_const("w", 0);  // ← 修复：入圈前先定义，每条路径都有值
    b0->emit_const("c", 0);
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_const("w", 1);
    b1->term_jump(b3);
    b2->term_jump(b3);
    b3->emit_bin(Op::Add, "z", Operand::var_of("w"), Operand::of(1));
    b3->term_return(Operand::var_of("z"));
    fixed.set_entry(b0);
    const RunResult ok = run_cfg(fixed, "", 0);
    std::printf("  结果 = %lld（b0 的 w=0 生效：then 的 w=1 没走到）\n",
                static_cast<long long>(ok.value));
    return 0;
}
