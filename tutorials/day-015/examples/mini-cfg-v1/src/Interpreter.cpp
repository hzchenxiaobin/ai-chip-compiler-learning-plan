#include "Interpreter.h"

#include <map>
#include <sstream>

namespace {

int64_t eval_operand(const Operand& op, const std::map<std::string, std::int64_t>& env,
                     const std::string& block, RunResult* out) {
    if (op.is_imm) {
        return op.imm;
    }
    const auto it = env.find(op.var);
    if (it == env.end()) {
        std::ostringstream what;
        what << "run: 变量 \"" << op.var << "\" 在块 " << block
             << " 执行到时还没有值——在这条实际执行的路径上，它没有被定义过";
        out->error = what.str();
        out->ok = false;
        return 0;
    }
    return it->second;
}

int64_t eval_bin(Op op, std::int64_t lhs, std::int64_t rhs) {
    switch (op) {
        case Op::Add: return lhs + rhs;
        case Op::Sub: return lhs - rhs;
        case Op::Mul: return lhs * rhs;
        case Op::Gt: return lhs > rhs ? 1 : 0;
        case Op::Le: return lhs <= rhs ? 1 : 0;
        case Op::Const: break;
    }
    return 0;
}

}  // namespace

RunResult run_cfg(const Cfg& cfg, const std::string& arg_name, std::int64_t arg_value,
                  std::int64_t max_steps) {
    RunResult out;
    if (cfg.entry() == nullptr) {
        out.error = "run: 没有入口块";
        return out;
    }

    std::map<std::string, std::int64_t> env;
    if (!arg_name.empty()) {
        env[arg_name] = arg_value;
    }

    const BasicBlock* cur = cfg.entry();
    std::int64_t steps = 0;

    while (true) {
        // 燃料按「进入一个块」计数：没有指令的空块同样消耗燃料——
        // 只数指令的话，b1->b2->b1->b2 这样没有指令的圈会永远转下去。
        if (++steps > max_steps) {
            std::ostringstream what;
            what << "run: 超过步数上限 " << max_steps
                 << "——CFG 允许成环，执行没有自然结束（死循环？跳转目标写错？）"
                    "最后的路径片段：";
            const std::size_t n = out.path.size();
            const std::size_t from = n > 12 ? n - 12 : 0;
            for (std::size_t i = from; i < n; ++i) {
                what << (i == from ? "" : " -> ") << out.path[i];
            }
            out.error = what.str();
            return out;
        }
        out.path.push_back(cur->name());

        for (const auto& instr : cur->instrs()) {
            const std::int64_t lhs = eval_operand(instr.lhs, env, cur->name(), &out);
            if (!out.error.empty()) {
                return out;
            }
            const std::int64_t rhs = eval_operand(instr.rhs, env, cur->name(), &out);
            if (!out.error.empty()) {
                return out;
            }
            if (instr.op == Op::Const) {
                env[instr.dst] = instr.rhs.imm;
            } else {
                env[instr.dst] = eval_bin(instr.op, lhs, rhs);
            }
        }

        switch (cur->term().kind) {
            case TermKind::Return: {
                const std::int64_t value = eval_operand(cur->term().ret, env, cur->name(), &out);
                if (!out.error.empty()) {
                    return out;
                }
                out.value = value;
                out.ok = true;
                return out;
            }
            case TermKind::Jump:
                cur = cur->term().target;
                break;
            case TermKind::CondBranch: {
                const std::int64_t cond = eval_operand(cur->term().cond, env, cur->name(), &out);
                if (!out.error.empty()) {
                    return out;
                }
                cur = cond != 0 ? cur->term().tthen : cur->term().telse;
                break;
            }
            case TermKind::None:
                out.error = "run: 块 " + cur->name() +
                            " 走到末尾没有终结符——直线执行掉出了块底";
                return out;
        }
    }
}
