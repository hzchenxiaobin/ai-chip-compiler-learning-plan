// 反面教材（第 15 天错误四）：改程序留下的孤块——unreachable 但不可见地错。
// 现场模拟：菱形程序上一版有两个出口（b3、b4 各返回一个值），
// 这一版删掉了分支上指向 b4 的边（b2 改跳 b3），但忘了删 b4 本身。
// 更糟的是：b4 里引用了一个从来没定义过的变量 q。
// 四个观察点：
//   1) verify: PASS——unreachable 不是错误！没有任何规则要求
//      「每个块都必须被跳到」。它是死代码，删不删是第 25 天
//      DCE Pass 的决定，验证器只负责如实报告；
//   2) 打印器在 preds 表里标注 unreachable，文本 CFG 的注释里
//      也写「（无——unreachable）」——IR 诚实，但你不看就不知道；
//   3) 解释器跑完没报错——b4 根本没执行，q 没值这件事无人发现：
//      死代码可以藏住任何错误（包括引用未定义变量），
//      这就是「先跑通再删」和「删完再跑」都必须做的原因；
//   4) 对照：把 b2 的跳转改回 b4，q 立刻爆出来——同一段代码，
//      活过来错误就显形。
// 编译运行（在 bugs/ 目录下）：
//   g++ -std=c++17 -g -fsanitize=address -static-libasan -I ../src \
//     ../src/Cfg.cpp ../src/Interpreter.cpp err_unreachable.cpp \
//     -o err_unreachable && ./err_unreachable; echo "exit code: $?"
#include <cstdio>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

// dead_exit = true：b4 留在图里但没有入边（这一版的现状）；
// dead_exit = false：b2 跳到 b4——b4 活过来，q 的错误立刻显形。
Cfg build(bool dead_exit) {
    Cfg cfg(dead_exit ? "diamond-with-dead-exit" : "diamond-b4-alive");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");
    BasicBlock* b2 = cfg.new_block("b2");
    BasicBlock* b3 = cfg.new_block("b3");
    BasicBlock* b4 = cfg.new_block("b4");  // 上一版的第二个出口
    b0->emit_bin(Op::Mul, "s", Operand::var_of("a"), Operand::var_of("a"));
    b0->emit_bin(Op::Gt, "c", Operand::var_of("s"), Operand::of(4));
    b0->term_cond_branch(Operand::var_of("c"), b1, b2);
    b1->emit_bin(Op::Mul, "u", Operand::var_of("s"), Operand::of(2));
    b1->term_jump(b3);
    b2->emit_bin(Op::Add, "u", Operand::var_of("s"), Operand::of(1));
    b2->term_jump(dead_exit ? b3 : b4);  // ← 这一版把出口改到了 b3
    b3->emit_bin(Op::Add, "z", Operand::var_of("u"), Operand::of(1));
    b3->term_return(Operand::var_of("z"));
    b4->emit_bin(Op::Add, "bad", Operand::var_of("q"), Operand::of(1));  // q 从未定义！
    b4->term_return(Operand::var_of("bad"));
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    Cfg cfg = build(true);

    std::printf("== Verifier：孤块算错误吗？ ==\n");
    std::string why;
    std::printf("  verify: %s\n", cfg.verify(&why) ? "PASS（unreachable 不是结构错误）"
                                                   : why.c_str());
    std::printf("  块数 = %lld\n", static_cast<long long>(cfg.num_blocks()));

    std::printf("\n== preds 表：打印器诚实地标注了它 ==\n");
    std::printf("%s", cfg.preds_succs_to_string().c_str());

    std::printf("\n== 解释器：a=3 跑一遍 ==\n");
    const RunResult r = run_cfg(cfg, "a", 3);
    std::printf("  ok = %d，结果 = %lld\n", r.ok ? 1 : 0,
                static_cast<long long>(r.value));
    std::printf("  路径：");
    for (const auto& name : r.path) {
        std::printf(" %s", name.c_str());
    }
    std::printf("\n  b4 没执行——它引用的未定义变量 q 无人发现（死代码藏错误）\n");

    std::printf("\n== 对照：让 b4 活过来（b2 跳到 b4） ==\n");
    Cfg alive = build(false);
    const RunResult r2 = run_cfg(alive, "a", 1);  // a=1 → 走 else 即 b2
    std::printf("  ok = %d\n", r2.ok ? 1 : 0);
    std::printf("  失败原因：%s\n", r2.error.c_str());
    return 0;
}
