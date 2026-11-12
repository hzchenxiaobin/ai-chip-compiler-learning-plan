// 第 15 天的主程序：两幕。
// 第一幕：菱形 CFG——条件缩放（leaky 风格），三分支输入各走一条路；
// 第二幕：带回边的 CFG——循环求和，同一块被执行多次。
// 每一幕都打印：文本 CFG、边表、前驱/后继表、数据流表、验证、执行路径。

#include <iostream>
#include <string>

#include "Cfg.h"
#include "Interpreter.h"

namespace {

using OperandVar = Operand;

// ---------------------------------------------------------------
// 第一幕的程序：
//   s = a * a
//   if (s > 4)  u = s * 2     // then
//   else        u = s + 1     // else
//   z = u + 1
//   return z
// 手算：a=1 → s=1 → else → u=2  → z=3
//       a=2 → s=4 → else → u=5  → z=6   （4 > 4 不成立）
//       a=3 → s=9 → then → u=18 → z=19
// ---------------------------------------------------------------
Cfg build_diamond() {
    Cfg cfg("leaky-scale");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");  // then
    BasicBlock* b2 = cfg.new_block("b2");  // else
    BasicBlock* b3 = cfg.new_block("b3");  // join（汇合）

    b0->emit_bin(Op::Mul, "s", OperandVar::var_of("a"), OperandVar::var_of("a"));
    b0->emit_bin(Op::Gt, "c", OperandVar::var_of("s"), OperandVar::of(4));
    b0->term_cond_branch(OperandVar::var_of("c"), b1, b2);

    b1->emit_bin(Op::Mul, "u", OperandVar::var_of("s"), OperandVar::of(2));
    b1->term_jump(b3);

    b2->emit_bin(Op::Add, "u", OperandVar::var_of("s"), OperandVar::of(1));
    b2->term_jump(b3);

    b3->emit_bin(Op::Add, "z", OperandVar::var_of("u"), OperandVar::of(1));
    b3->term_return(OperandVar::var_of("z"));

    cfg.set_entry(b0);
    return cfg;
}

// ---------------------------------------------------------------
// 第二幕的程序（循环求和 1+2+...+n）：
//   i = 1; sum = 0
// loop: if (i <= n) goto body else goto exit
// body: sum = sum + i; i = i + 1; goto loop
// exit: return sum
// b2 -> b1 是回边（back edge）：CFG 有环，DAG 没有的东西。
// 手算：n=5 → 15；b1 执行 6 次、b2 执行 5 次。
// ---------------------------------------------------------------
Cfg build_loop() {
    Cfg cfg("sum-1-to-n");
    BasicBlock* b0 = cfg.new_block("b0");
    BasicBlock* b1 = cfg.new_block("b1");  // loop head（循环头）
    BasicBlock* b2 = cfg.new_block("b2");  // body（循环体）
    BasicBlock* b3 = cfg.new_block("b3");  // exit

    b0->emit_const("i", 1);
    b0->emit_const("sum", 0);
    b0->term_jump(b1);

    b1->emit_bin(Op::Le, "c", OperandVar::var_of("i"), OperandVar::var_of("n"));
    b1->term_cond_branch(OperandVar::var_of("c"), b2, b3);

    b2->emit_bin(Op::Add, "sum", OperandVar::var_of("sum"), OperandVar::var_of("i"));
    b2->emit_bin(Op::Add, "i", OperandVar::var_of("i"), OperandVar::of(1));
    b2->term_jump(b1);  // ← 回边：目标 b1 的前驱里出现 b2 自己这一圈

    b3->term_return(OperandVar::var_of("sum"));

    cfg.set_entry(b0);
    return cfg;
}

void show_run(const Cfg& cfg, const std::string& arg_name, std::int64_t arg_value) {
    const RunResult r = run_cfg(cfg, arg_name, arg_value);
    std::cout << "  " << arg_name << " = " << arg_value << " :";
    if (!r.ok) {
        std::cout << "  失败——" << r.error << "\n";
        return;
    }
    std::cout << "  路径 ";
    for (std::size_t i = 0; i < r.path.size(); ++i) {
        std::cout << (i == 0 ? "" : " -> ") << r.path[i];
    }
    std::cout << "  =>  结果 = " << r.value << "\n";
}

void print_all(const Cfg& cfg) {
    std::cout << cfg.to_string() << "\n";
    std::cout << cfg.edges_to_string() << "\n";
    std::cout << cfg.preds_succs_to_string() << "\n";
    std::cout << cfg.dataflow_to_string() << "\n";
    std::string why;
    if (cfg.verify(&why)) {
        std::cout << "verify: PASS（" << cfg.num_blocks() << " 块、" << cfg.num_instrs()
                  << " 条指令、" << cfg.num_edges() << " 条边，全部检查通过）\n\n";
    } else {
        std::cout << why << "\n\n";
    }
}

}  // namespace

int main() {
    std::cout << "== 第一幕：菱形 CFG——条件缩放（leaky 风格） ==\n";
    std::cout << "程序：s = a*a;  if (s > 4) { u = s*2 } else { u = s+1 };  z = u+1;  return z\n\n";
    Cfg diamond = build_diamond();
    print_all(diamond);
    for (const std::int64_t a : {1, 2, 3}) {
        show_run(diamond, "a", a);
    }
    std::cout << "\n";

    std::cout << "== 第二幕：带回边的 CFG——循环求和 1+2+...+n ==\n";
    std::cout << "程序：i=1; sum=0; while (i <= n) { sum += i; i += 1 }; return sum\n\n";
    Cfg loop = build_loop();
    print_all(loop);
    show_run(loop, "n", 5);
    std::cout << "\n";

    std::cout << "== 对照：DAG 节点恰执行一次，CFG 的块按路径执行 ==\n";
    const RunResult r5 = run_cfg(loop, "n", 5);
    std::size_t b1_count = 0;
    std::size_t b2_count = 0;
    for (const auto& name : r5.path) {
        if (name == "b1") {
            ++b1_count;
        }
        if (name == "b2") {
            ++b2_count;
        }
    }
    std::cout << "  n=5 时：b1（循环头）执行 " << b1_count << " 次，b2（循环体）执行 " << b2_count
              << " 次，b0/b3 各 1 次——\n";
    std::cout << "  第 9 天的解释器按拓扑序把每个节点恰好算一遍；今天的解释器沿控制流走，\n";
    std::cout << "  同一块可以一次不执行（菱形里每次只走 then/else 之一）、也可以执行多次。\n";
    return 0;
}
