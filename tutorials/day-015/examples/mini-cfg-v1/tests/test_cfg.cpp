// 第 15 天的验收测试：从 DAG 到 CFG。
// 五组问题：
//   1) 结构——块、指令、终结符、入口都长在正确的位置上；
//   2) 控制流邻接——后继从终结符读出，前驱反向收集，菱形与循环各验一遍；
//   3) 数据流——变量在哪些块定义、哪些块使用；多重定义（u）与
//      零定义（入参 a/n）都如实记录；
//   4) 执行——路径、结果、同块多跑（循环）、燃料上限（死循环刹车）、
//      路径条件化的未初始化变量；
//   5) 纪律——验证失败的诊断、建造守卫（空目标/重名/双终结符/外来块）、
//      unreachable 标注、move-only 所有权。
// 全部通过时打印一行 "all N assertions passed"。

#include <cstdio>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "Cfg.h"
#include "Interpreter.h"

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

bool contains(const std::string& hay, const char* needle) {
    return hay.find(needle) != std::string::npos;
}

std::vector<std::string> names(const std::vector<const BasicBlock*>& blocks) {
    std::vector<std::string> out;
    for (const auto* b : blocks) {
        out.push_back(b->name());
    }
    return out;
}

template <typename Fn>
std::string throws_with(Fn&& fn) {
    try {
        fn();
    } catch (const std::invalid_argument& e) {
        return e.what();
    }
    return "";
}

Cfg build_diamond() {
    Cfg cfg("leaky-scale");
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
    b3->term_return(Operand::var_of("z"));
    cfg.set_entry(b0);
    return cfg;
}

Cfg build_loop() {
    Cfg cfg("sum-1-to-n");
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
    b2->term_jump(b1);
    b3->term_return(Operand::var_of("sum"));
    cfg.set_entry(b0);
    return cfg;
}

}  // namespace

int main() {
    // ===================== 1. 结构 =====================
    {
        Cfg cfg = build_diamond();
        CHECK(cfg.name() == "leaky-scale");
        CHECK(cfg.num_blocks() == 4);
        CHECK(cfg.blocks().size() == 4);
        CHECK(cfg.num_instrs() == 5);
        CHECK(cfg.num_edges() == 4);
        CHECK(cfg.entry() != nullptr);
        CHECK(cfg.entry()->name() == "b0");
        CHECK(cfg.blocks()[0]->instrs().size() == 2);
        CHECK(cfg.blocks()[0]->term().kind == TermKind::CondBranch);
        CHECK(cfg.blocks()[1]->instrs().size() == 1);
        CHECK(cfg.blocks()[1]->term().kind == TermKind::Jump);
        CHECK(cfg.blocks()[2]->instrs().size() == 1);
        CHECK(cfg.blocks()[2]->term().kind == TermKind::Jump);
        CHECK(cfg.blocks()[3]->instrs().size() == 1);
        CHECK(cfg.blocks()[3]->term().kind == TermKind::Return);

        const Instr& first = cfg.blocks()[0]->instrs()[0];
        CHECK(first.op == Op::Mul);
        CHECK(first.dst == "s");
        CHECK(!first.lhs.is_imm && first.lhs.var == "a");
        CHECK(!first.rhs.is_imm && first.rhs.var == "a");

        const Instr& cond = cfg.blocks()[0]->instrs()[1];
        CHECK(cond.op == Op::Gt);
        CHECK(cond.rhs.is_imm && cond.rhs.imm == 4);

        CHECK(op_name(Op::Le) == std::string("le"));
        CHECK(Operand::of(-7).to_string() == "-7");
        CHECK(Operand::var_of("u").to_string() == "u");

        std::string why;
        CHECK(cfg.verify(&why));
        CHECK(why.empty());
    }
    {
        Cfg cfg = build_loop();
        CHECK(cfg.num_blocks() == 4);
        CHECK(cfg.num_instrs() == 5);
        CHECK(cfg.num_edges() == 4);
        CHECK(cfg.blocks()[0]->instrs()[0].op == Op::Const);
        CHECK(cfg.blocks()[0]->instrs()[0].dst == "i");
        CHECK(cfg.blocks()[0]->instrs()[0].rhs.imm == 1);
        CHECK(cfg.verify());
    }

    // ===================== 2. 控制流邻接 =====================
    {
        Cfg cfg = build_diamond();
        const BasicBlock* b0 = cfg.blocks()[0].get();
        const BasicBlock* b1 = cfg.blocks()[1].get();
        const BasicBlock* b2 = cfg.blocks()[2].get();
        const BasicBlock* b3 = cfg.blocks()[3].get();

        CHECK(names(cfg.successors(b0)) == std::vector<std::string>({"b1", "b2"}));
        CHECK(names(cfg.successors(b1)) == std::vector<std::string>({"b3"}));
        CHECK(names(cfg.successors(b2)) == std::vector<std::string>({"b3"}));
        CHECK(cfg.successors(b3).empty());
        CHECK(names(cfg.predecessors(b0)).empty());
        CHECK(names(cfg.predecessors(b1)) == std::vector<std::string>({"b0"}));
        CHECK(names(cfg.predecessors(b2)) == std::vector<std::string>({"b0"}));
        CHECK(names(cfg.predecessors(b3)) == std::vector<std::string>({"b1", "b2"}));

        // then/else 指向同一个块：合法（退化分支），后继去重后只有一条边。
        Cfg same("same-target");
        BasicBlock* x = same.new_block("x");
        BasicBlock* y = same.new_block("y");
        x->emit_const("c", 0);
        x->term_cond_branch(Operand::var_of("c"), y, y);
        y->term_return(Operand::var_of("c"));
        same.set_entry(x);
        CHECK(same.num_edges() == 1);
        CHECK(names(same.successors(x)) == std::vector<std::string>({"y"}));
        CHECK(same.verify());
    }
    {
        Cfg cfg = build_loop();
        const BasicBlock* b0 = cfg.blocks()[0].get();
        const BasicBlock* b1 = cfg.blocks()[1].get();
        const BasicBlock* b2 = cfg.blocks()[2].get();
        const BasicBlock* b3 = cfg.blocks()[3].get();

        CHECK(names(cfg.successors(b0)) == std::vector<std::string>({"b1"}));
        CHECK(names(cfg.successors(b1)) == std::vector<std::string>({"b2", "b3"}));
        CHECK(names(cfg.successors(b2)) == std::vector<std::string>({"b1"}));  // 回边
        CHECK(cfg.successors(b3).empty());
        CHECK(names(cfg.predecessors(b0)).empty());
        // 循环头 b1 的前驱有两个：入口 b0（进圈）和循环体 b2（回到边）。
        CHECK(names(cfg.predecessors(b1)) == std::vector<std::string>({"b0", "b2"}));
        CHECK(names(cfg.predecessors(b2)) == std::vector<std::string>({"b1"}));
        CHECK(names(cfg.predecessors(b3)) == std::vector<std::string>({"b1"}));
    }

    // ===================== 3. 数据流 =====================
    {
        Cfg cfg = build_diamond();
        const auto flow = cfg.dataflow();
        CHECK(flow.size() == 5);  // a c s u z
        CHECK(flow.at("a").def_blocks.empty());
        CHECK(flow.at("a").use_blocks == std::vector<std::string>({"b0"}));
        CHECK(flow.at("s").def_blocks == std::vector<std::string>({"b0"}));
        CHECK(flow.at("s").use_blocks == std::vector<std::string>({"b0", "b1", "b2"}));
        // u：两个定义块——第 17 天 SSA/PHI 的原料，今天先如实记录。
        CHECK(flow.at("u").def_blocks == std::vector<std::string>({"b1", "b2"}));
        CHECK(flow.at("u").use_blocks == std::vector<std::string>({"b3"}));
        CHECK(flow.at("z").def_blocks == std::vector<std::string>({"b3"}));
        // return 也算一次使用。
        CHECK(flow.at("z").use_blocks == std::vector<std::string>({"b3"}));
        // c 的使用发生在终结符里。
        CHECK(flow.at("c").def_blocks == std::vector<std::string>({"b0"}));
        CHECK(flow.at("c").use_blocks == std::vector<std::string>({"b0"}));

        const std::string text = cfg.dataflow_to_string();
        CHECK(contains(text, "多重定义"));
        CHECK(contains(text, "运行期入参"));
    }
    {
        Cfg cfg = build_loop();
        const auto flow = cfg.dataflow();
        // sum 在 b0 初始化、在 b2 里被反复重写——多重定义在循环里是常态。
        CHECK(flow.at("sum").def_blocks == std::vector<std::string>({"b0", "b2"}));
        CHECK(flow.at("sum").use_blocks == std::vector<std::string>({"b2", "b3"}));
        CHECK(flow.at("i").def_blocks == std::vector<std::string>({"b0", "b2"}));
        CHECK(flow.at("i").use_blocks == std::vector<std::string>({"b1", "b2"}));
        CHECK(flow.at("n").def_blocks.empty());
    }

    // ===================== 4. 执行 =====================
    {
        Cfg cfg = build_diamond();
        const RunResult r1 = run_cfg(cfg, "a", 1);
        CHECK(r1.ok);
        CHECK(r1.value == 3);
        CHECK(r1.path == std::vector<std::string>({"b0", "b2", "b3"}));

        const RunResult r2 = run_cfg(cfg, "a", 2);
        CHECK(r2.ok);
        CHECK(r2.value == 6);  // s=4, 4>4 不成立 → else
        CHECK(r2.path == std::vector<std::string>({"b0", "b2", "b3"}));

        const RunResult r3 = run_cfg(cfg, "a", 3);
        CHECK(r3.ok);
        CHECK(r3.value == 19);
        CHECK(r3.path == std::vector<std::string>({"b0", "b1", "b3"}));

        const RunResult rn = run_cfg(cfg, "a", -3);
        CHECK(rn.ok);
        CHECK(rn.value == 19);  // s=9 → then，和 a=3 同路
        CHECK(rn.path == std::vector<std::string>({"b0", "b1", "b3"}));
    }
    {
        Cfg cfg = build_loop();
        const RunResult r5 = run_cfg(cfg, "n", 5);
        CHECK(r5.ok);
        CHECK(r5.value == 15);
        CHECK(r5.path.front() == "b0");
        CHECK(r5.path.back() == "b3");
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
        CHECK(b1_count == 6);  // 5 次进圈 + 1 次判出
        CHECK(b2_count == 5);
        CHECK(r5.path.size() == 13);  // 1 + 6 + 5 + 1

        const RunResult r0 = run_cfg(cfg, "n", 0);
        CHECK(r0.ok);
        CHECK(r0.value == 0);
        CHECK(r0.path == std::vector<std::string>({"b0", "b1", "b3"}));  // 一次都不进圈

        const RunResult r1 = run_cfg(cfg, "n", 1);
        CHECK(r1.ok);
        CHECK(r1.value == 1);
        CHECK(r1.path == std::vector<std::string>({"b0", "b1", "b2", "b1", "b3"}));
    }
    {
        // 死循环：b1 -> b2 -> b1 -> ...（跳转目标合法、验证通过，但语义写错了）。
        // DAG 解释器不存在这个问题（拓扑序必然终止）；CFG 解释器必须带刹车。
        Cfg cfg("infinite");
        BasicBlock* b0 = cfg.new_block("b0");
        BasicBlock* b1 = cfg.new_block("b1");
        BasicBlock* b2 = cfg.new_block("b2");
        b0->term_jump(b1);
        b1->term_cond_branch(Operand::of(1), b2, b2);
        b2->term_jump(b1);
        cfg.set_entry(b0);
        CHECK(cfg.verify());  // 结构完全合法——死循环不是构造错误
        const RunResult r = run_cfg(cfg, "", 0, 200);
        CHECK(!r.ok);
        CHECK(contains(r.error, "步数上限"));
        CHECK(contains(r.error, "b1 -> b2 -> b1"));
    }
    {
        // 路径条件化的未初始化：w 只在 then 里定义，实际走了 else。
        // 「定义了吗」在 CFG 里不是一个静态问题——是「在这条路径上定义了吗」。
        Cfg cfg("uninit");
        BasicBlock* b0 = cfg.new_block("b0");
        BasicBlock* b1 = cfg.new_block("b1");
        BasicBlock* b2 = cfg.new_block("b2");
        BasicBlock* b3 = cfg.new_block("b3");
        b0->emit_const("c", 0);
        b0->term_cond_branch(Operand::var_of("c"), b1, b2);
        b1->emit_const("w", 1);
        b1->term_jump(b3);
        b2->term_jump(b3);
        b3->emit_bin(Op::Add, "z", Operand::var_of("w"), Operand::of(1));
        b3->term_return(Operand::var_of("z"));
        cfg.set_entry(b0);
        CHECK(cfg.verify());
        const RunResult r = run_cfg(cfg, "", 0);
        CHECK(!r.ok);
        CHECK(r.path == std::vector<std::string>({"b0", "b2", "b3"}));
        CHECK(contains(r.error, "w"));
        CHECK(contains(r.error, "没有被定义过"));
    }

    // ===================== 5. 纪律 =====================
    {
        // 没有终结符：验证点名（建造可以完成，检查拦下）。
        Cfg cfg("no-term");
        BasicBlock* b0 = cfg.new_block("b0");
        b0->emit_const("x", 1);
        cfg.set_entry(b0);
        std::string why = "未初始化";
        CHECK(!cfg.verify(&why));
        CHECK(contains(why, "b0"));
        CHECK(contains(why, "没有终结符"));
        // 不验证直接跑：解释器在块底掉出去，同样报错。
        const RunResult r = run_cfg(cfg, "", 0);
        CHECK(!r.ok);
        CHECK(contains(r.error, "掉出了块底"));
    }
    {
        // 没设入口。
        Cfg cfg("no-entry");
        BasicBlock* b0 = cfg.new_block("b0");
        b0->term_return(Operand::of(0));
        CHECK(!cfg.verify());
        const RunResult r = run_cfg(cfg, "", 0);
        CHECK(!r.ok);
        CHECK(contains(r.error, "入口"));
    }
    {
        // 跳到别的 CFG 的块：借用指针跨了图，验证拦下。
        Cfg cfgA("A");
        Cfg cfgB("B");
        BasicBlock* a0 = cfgA.new_block("a0");
        BasicBlock* b0 = cfgB.new_block("b0");
        b0->term_return(Operand::of(0));
        a0->term_jump(b0);  // a0 的出口指向 B 的块
        cfgA.set_entry(a0);
        std::string why;
        CHECK(!cfgA.verify(&why));
        CHECK(contains(why, "不属于这张 CFG"));
    }
    {
        // 建造守卫：空目标、重名块、双终结符、emit_bin 装常量。
        Cfg cfg("guards");
        BasicBlock* b0 = cfg.new_block("b0");
        CHECK(contains(throws_with([&] { cfg.new_block("b0"); }), "已存在"));
        CHECK(contains(throws_with([&] { b0->term_jump(nullptr); }), "空指针"));
        CHECK(contains(throws_with([&] { b0->term_cond_branch(Operand::of(1), nullptr, nullptr); }),
                       "空指针"));
        b0->term_return(Operand::of(0));
        CHECK(contains(throws_with([&] { b0->term_jump(b0); }), "只能有一个出口"));
        CHECK(contains(throws_with([&] { b0->emit_bin(Op::Const, "x", Operand::of(1), Operand::of(1)); }),
                       "emit_const"));
    }
    {
        // unreachable：没有前驱也不是入口——不是错误，是死代码（第 25 天的原料）。
        Cfg cfg = build_diamond();
        BasicBlock* dead = cfg.new_block("b_dead");
        dead->emit_const("never", 42);
        dead->term_return(Operand::var_of("never"));
        CHECK(cfg.verify());  // 合法
        CHECK(cfg.predecessors(dead).empty());
        const std::string table = cfg.preds_succs_to_string();
        CHECK(contains(table, "unreachable"));
        const RunResult r = run_cfg(cfg, "a", 3);
        CHECK(r.ok);
        bool saw_dead = false;
        for (const auto& name : r.path) {
            if (name == "b_dead") {
                saw_dead = true;
            }
        }
        CHECK(!saw_dead);  // 没有入边的块永远不会执行
        CHECK(cfg.num_blocks() == 5);  // 但它诚实地待在 IR 里，等 DCE 来删
    }
    {
        // 打印格式的抽查：文本 CFG 的关键行。
        Cfg cfg = build_diamond();
        const std::string text = cfg.to_string();
        CHECK(contains(text, "cfg \"leaky-scale\" (4 blocks, entry b0)"));
        CHECK(contains(text, "s = mul a, a"));
        CHECK(contains(text, "cond_branch c -> b1, b2"));
        CHECK(contains(text, "jump b3"));
        CHECK(contains(text, "return z"));
        CHECK(contains(text, "# preds: b1 b2"));
        const std::string edges = cfg.edges_to_string();
        CHECK(contains(edges, "b0 -> b1   (then)"));
        CHECK(contains(edges, "b0 -> b2   (else)"));
        CHECK(contains(edges, "b2 -> b3   (jump)"));
    }
    {
        // 所有权：move-only；搬家不换房本，借用指针搬家后照旧有效。
        static_assert(!std::is_copy_constructible<Cfg>::value, "Cfg 必须不可拷贝");
        static_assert(std::is_move_constructible<Cfg>::value, "Cfg 必须可移动");
        Cfg cfg = build_diamond();
        const BasicBlock* b3_before = cfg.blocks()[3].get();
        const BasicBlock* entry_before = cfg.entry();
        Cfg moved = std::move(cfg);
        CHECK(moved.num_blocks() == 4);
        CHECK(moved.entry() == entry_before);
        CHECK(moved.blocks()[3].get() == b3_before);
        CHECK(moved.verify());
        const RunResult r = run_cfg(moved, "a", 3);
        CHECK(r.ok);
        CHECK(r.value == 19);
        // 原 Cfg 对象已被搬空——按约定不再使用（同第 8/13 天的纪律）。
    }

    std::printf("all %d assertions passed\n", g_checks);
    return 0;
}
