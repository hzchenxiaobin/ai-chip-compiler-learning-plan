#include "Cfg.h"

#include <algorithm>
#include <set>
#include <sstream>
#include <utility>

BasicBlock* Cfg::new_block(std::string name) {
    if (name.empty()) {
        throw std::invalid_argument("new_block: 块名不能为空");
    }
    if (by_name_.count(name) != 0) {
        throw std::invalid_argument("new_block: 块名 \"" + name + "\" 已存在——一个 CFG 里名字唯一");
    }
    const auto id = static_cast<std::int64_t>(blocks_.size());
    // make_unique 在标准库上下文里构造，够不到 private 构造函数——
    // 这里在 Cfg（BasicBlock 的 friend）里手写 new，纪律不变：
    // 外界仍然只能通过 new_block 造块。
    // 注意：名字先拷给块（构造函数按值收），登记表再 move——
    // 顺序反过来登记表里就只剩空串。
    blocks_.push_back(std::unique_ptr<BasicBlock>(new BasicBlock(name, id)));
    BasicBlock* b = blocks_.back().get();
    by_name_.emplace(std::move(name), b);
    return b;
}

void Cfg::set_entry(BasicBlock* b) {
    if (!owns(b)) {
        throw std::invalid_argument("set_entry: 入口块不属于这张 CFG");
    }
    entry_ = b;
}

bool Cfg::owns(const BasicBlock* b) const {
    for (const auto& owned : blocks_) {
        if (owned.get() == b) {
            return true;
        }
    }
    return false;
}

std::vector<const BasicBlock*> Cfg::successors(const BasicBlock* b) const {
    std::vector<const BasicBlock*> out;
    const auto push = [&out](const BasicBlock* t) {
        bool seen = false;
        for (const auto* existing : out) {
            if (existing == t) {
                seen = true;
            }
        }
        if (!seen) {
            out.push_back(t);
        }
    };
    switch (b->term().kind) {
        case TermKind::CondBranch:
            push(b->term().tthen);
            push(b->term().telse);
            break;
        case TermKind::Jump:
            push(b->term().target);
            break;
        case TermKind::Return:
        case TermKind::None:
            break;
    }
    return out;
}

std::vector<const BasicBlock*> Cfg::predecessors(const BasicBlock* b) const {
    std::vector<const BasicBlock*> out;
    for (const auto& candidate : blocks_) {
        for (const auto* succ : successors(candidate.get())) {
            if (succ == b) {
                bool seen = false;
                for (const auto* existing : out) {
                    if (existing == candidate.get()) {
                        seen = true;
                    }
                }
                if (!seen) {
                    out.push_back(candidate.get());
                }
            }
        }
    }
    return out;
}

std::int64_t Cfg::num_edges() const {
    std::int64_t n = 0;
    for (const auto& b : blocks_) {
        n += static_cast<std::int64_t>(successors(b.get()).size());
    }
    return n;
}

std::int64_t Cfg::num_instrs() const noexcept {
    std::int64_t n = 0;
    for (const auto& b : blocks_) {
        n += static_cast<std::int64_t>(b->instrs().size());
    }
    return n;
}

std::map<std::string, VarFlow> Cfg::dataflow() const {
    std::map<std::string, VarFlow> flow;
    const auto note_def = [&flow](const std::string& var, const std::string& block) {
        auto& list = flow[var].def_blocks;
        if (std::find(list.begin(), list.end(), block) == list.end()) {
            list.push_back(block);
        }
    };
    const auto note_use = [&flow](const std::string& var, const std::string& block) {
        auto& list = flow[var].use_blocks;
        if (std::find(list.begin(), list.end(), block) == list.end()) {
            list.push_back(block);
        }
    };
    const auto scan_operand = [&note_use](const Operand& op, const std::string& block) {
        // 空名是终结符里「用不到的字段」的默认值（如 Jump 的 ret），不算使用。
        if (!op.is_imm && !op.var.empty()) {
            note_use(op.var, block);
        }
    };
    for (const auto& b : blocks_) {
        for (const auto& instr : b->instrs()) {
            note_def(instr.dst, b->name());
            scan_operand(instr.lhs, b->name());
            scan_operand(instr.rhs, b->name());
        }
        scan_operand(b->term().ret, b->name());
        scan_operand(b->term().cond, b->name());
    }
    return flow;
}

bool Cfg::verify(std::string* why) const {
    const auto fail = [why](const std::string& msg) {
        if (why != nullptr) {
            *why = msg;
        }
        return false;
    };
    if (entry_ == nullptr) {
        return fail("verify: 没有入口块（set_entry 没调用？）");
    }
    for (const auto& b : blocks_) {
        if (b->term().kind == TermKind::None) {
            return fail("verify: 块 " + b->name() +
                        " 没有终结符——直线执行会掉出块底，基本块的单一出口被破坏");
        }
        const auto check_target = [&](const BasicBlock* t, const char* which) {
            if (t == nullptr) {
                fail("verify: 块 " + b->name() + " 的 " + which + " 目标是空指针");
                return false;
            }
            if (!owns(t)) {
                fail("verify: 块 " + b->name() + " 的 " + which + " 目标 \"" +
                     t->name() + "\" 不属于这张 CFG");
                return false;
            }
            return true;
        };
        if (b->term().kind == TermKind::Jump && !check_target(b->term().target, "jump")) {
            return false;
        }
        if (b->term().kind == TermKind::CondBranch) {
            if (!check_target(b->term().tthen, "then")) {
                return false;
            }
            if (!check_target(b->term().telse, "else")) {
                return false;
            }
        }
    }
    return true;
}

std::string Cfg::to_string() const {
    std::ostringstream out;
    out << "cfg \"" << name_ << "\" (" << num_blocks() << " blocks, entry "
        << (entry_ != nullptr ? entry_->name() : "<无>") << ") {\n";
    for (const auto& b : blocks_) {
        out << b->name() << ":";  // 前驱写在同行注释里——看结构不用来回翻
        if (b.get() == entry_) {
            out << "  # 入口";
        } else {
            const auto preds = predecessors(b.get());
            std::string list;
            for (const auto* p : preds) {
                if (!list.empty()) {
                    list += " ";
                }
                list += p->name();
            }
            out << "  # preds: " << (list.empty() ? "（无——unreachable）" : list);
        }
        out << "\n";
        for (const auto& instr : b->instrs()) {
            out << "  " << instr.dst << " = " << op_name(instr.op);
            if (instr.op == Op::Const) {
                out << " " << instr.rhs.imm;
            } else {
                out << " " << instr.lhs.to_string() << ", " << instr.rhs.to_string();
            }
            out << "\n";
        }
        switch (b->term().kind) {
            case TermKind::Return:
                out << "  return " << b->term().ret.to_string() << "\n";
                break;
            case TermKind::Jump:
                out << "  jump " << b->term().target->name() << "\n";
                break;
            case TermKind::CondBranch:
                out << "  cond_branch " << b->term().cond.to_string() << " -> "
                    << b->term().tthen->name() << ", " << b->term().telse->name() << "\n";
                break;
            case TermKind::None:
                out << "  <没有终结符！>\n";
                break;
        }
    }
    out << "}\n";
    return out.str();
}

std::string Cfg::edges_to_string() const {
    std::ostringstream out;
    out << "== 边表（控制流：一条 = 一次可能的跳转） ==\n";
    for (const auto& b : blocks_) {
        switch (b->term().kind) {
            case TermKind::Jump:
                out << "  " << b->name() << " -> " << b->term().target->name() << "   (jump)\n";
                break;
            case TermKind::CondBranch: {
                out << "  " << b->name() << " -> " << b->term().tthen->name() << "   (then)\n";
                if (b->term().telse != b->term().tthen) {
                    out << "  " << b->name() << " -> " << b->term().telse->name() << "   (else)\n";
                }
                break;
            }
            case TermKind::Return:
                break;
            case TermKind::None:
                out << "  " << b->name() << " -> ???   (没有终结符！)\n";
                break;
        }
    }
    return out.str();
}

std::string Cfg::preds_succs_to_string() const {
    std::ostringstream out;
    out << "== 前驱 / 后继（控制流的邻接表） ==\n";
    out << "  block  preds          succs\n";
    for (const auto& b : blocks_) {
        const auto join = [](const std::vector<const BasicBlock*>& list) {
            std::string s;
            for (const auto* p : list) {
                if (!s.empty()) {
                    s += " ";
                }
                s += p->name();
            }
            return s.empty() ? "-" : s;
        };
        const auto preds = predecessors(b.get());
        const auto is_entry = b.get() == entry_;
        std::string pred_col = is_entry ? "(entry)" : join(preds);
        if (!is_entry && preds.empty()) {
            pred_col += " unreachable";
        }
        out << "  " << b->name() << std::string(7 - std::min<std::size_t>(b->name().size(), 6), ' ')
            << pred_col;
        // 对齐列宽（名字最长不超过 5 个字符，这里给足余量）。
        const std::size_t pad = pred_col.size() < 14 ? 14 - pred_col.size() : 1;
        out << std::string(pad, ' ') << join(successors(b.get())) << "\n";
    }
    return out.str();
}

std::string Cfg::dataflow_to_string() const {
    std::ostringstream out;
    out << "== 变量的定义块 / 使用块（数据流，沿控制流跨块） ==\n";
    out << "  var   def            use\n";
    for (const auto& [var, flow] : dataflow()) {
        const auto join = [](const std::vector<std::string>& list) {
            std::string s;
            for (const auto& name : list) {
                if (!s.empty()) {
                    s += " ";
                }
                s += name;
            }
            return s.empty() ? "-" : s;
        };
        std::string def_col = join(flow.def_blocks);
        if (flow.def_blocks.empty()) {
            def_col += " (运行期入参)";
        }
        if (flow.def_blocks.size() > 1) {
            def_col += " (多重定义!)";
        }
        out << "  " << var << std::string(6 - std::min<std::size_t>(var.size(), 5), ' ')
            << def_col;
        const std::size_t pad = def_col.size() < 22 ? 22 - def_col.size() : 1;
        out << std::string(pad, ' ') << join(flow.use_blocks) << "\n";
    }
    return out.str();
}
