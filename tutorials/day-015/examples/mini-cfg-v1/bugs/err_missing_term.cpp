// 反面教材（第 15 天错误一）：块尾忘了写终结符——「单一出口」被破坏。
// 现场模拟：菱形程序写完后，最后一个块 b3 写完指令就去睡觉了，
// 忘了 term_return。三种人依次撞上它：
//   1) verify_cfg：当场点名「没有终结符」——这是检查器该拦的；
//   2) 不检查直接跑（跳过 verify 是错误示范）：解释器执行完 b3 的指令，
//      眼看要往下走——块底没有了，报告「掉出块底」；
//   3) 现象背后的原理：基本块的定义要求「只能在最后一条指令离开」，
//      没有终结符的块在 IR 里就是一个缺口：前驱边指向它，它的出口
//      却是「未定义行为」。LLVM 里 builder 会自动放终结符占位，
//      我们的迷你 CFG 选择把它留给 Verifier 点名。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Cfg.cpp ../src/Interpreter.cpp err_missing_term.cpp \
//     -o err_missing_term && ./err_missing_term; echo "exit code: $?"
#include <cstdio>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

Cfg build_diamond_missing_return() {
    Cfg cfg("leaky-scale-no-return");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");
    BasicBlock* b2 = cfg.new_block("b2");
    BasicBlock* b3 = cfg.new_block("b3");
    b0->emit_bin(Op::Mul, "s", Operand::var_of("a"), Operand::var_of("a"));
    b0->emit_bin(Op::Gt, "c", Operand::var_of("s"), Operand::of(4));
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_bin(Op::Mul, "u", Operand::var_of("s"), Operand::of(2));
    b1->term_jump(b3);
    b2->emit_bin(Op::Add, "u", Operand::var_of("s"), Operand::of(1));
    b2->term_jump(b3);
    b3->emit_bin(Op::Add, "z", Operand::var_of("u"), Operand::of(1));
    // ← 这里漏了 b3->term_return(...)！
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    Cfg cfg = build_diamond_missing_return();

    std::printf("== 第 1 位：Verifier（先验后跑的纪律） ==\n");
    std::string why;
    if (!cfg.verify(&why)) {
        std::printf("%s\n", why.c_str());
    }

    std::printf("\n== 第 2 位：不检查直接跑（错误示范） ==\n");
    const RunResult r = run_cfg(cfg, "a", 3);
    std::printf("  ok = %d\n", r.ok ? 1 : 0);
    std::printf("  路径：");
    for (const auto& name : r.path) {
        std::printf(" %s", name.c_str());
    }
    std::printf("\n  失败原因：%s\n", r.error.c_str());

    std::printf("\n== 对照：补上终结符之后 ==\n");
    // 修复方式：在建造处补 b3->term_return(Operand::var_of("z"))。
    // 这里用同一份代码重建一个正确的菱形，验证结果。
    Cfg fixed("leaky-scale-fixed");
    BasicBlock* b0 = fixed.new_block("b0");
    BasicBlock* b1 = fixed.new_block("b1");
    BasicBlock* b2 = fixed.new_block("b2");
    BasicBlock* b3 = fixed.new_block("b3");
    b0->emit_bin(Op::Mul, "s", Operand::var_of("a"), Operand::var_of("a"));
    b0->emit_bin(Op::Gt, "c", Operand::var_of("s"), Operand::of(4));
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_bin(Op::Mul, "u", Operand::var_of("s"), Operand::of(2));
    b1->term_jump(b3);
    b2->emit_bin(Op::Add, "u", Operand::var_of("s"), Operand::of(1));
    b2->term_jump(b3);
    b3->emit_bin(Op::Add, "z", Operand::var_of("u"), Operand::of(1));
    b3->term_return(Operand::var_of("z"));  // ← 修复就这一行
    fixed.set_entry(b0);
    std::string why2;
    std::printf("  verify: %s\n", fixed.verify(&why2) ? "PASS" : why2.c_str());
    const RunResult ok = run_cfg(fixed, "a", 3);
    std::printf("  a=3 => 结果 = %lld\n", static_cast<long long>(ok.value));
    return 0;
}
