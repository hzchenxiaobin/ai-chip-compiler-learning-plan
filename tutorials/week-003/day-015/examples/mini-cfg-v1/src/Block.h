#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include "Instr.h"

class BasicBlock;

// 终结符（terminator）：块末的控制转移指令。一个块最多一个，
// 且只能出现在最后——这是「基本块」定义的另一半：单一出口。
enum class TermKind { None, Return, Jump, CondBranch };

struct Terminator {
    TermKind kind = TermKind::None;
    Operand ret;                   // Return：返回什么
    BasicBlock* target = nullptr;  // Jump：目标
    Operand cond;                  // CondBranch：条件变量
    BasicBlock* tthen = nullptr;   // CondBranch：真目标
    BasicBlock* telse = nullptr;   // CondBranch：假目标
};

// 基本块：一段直线代码——从第一条指令进入，中间不进不出，
// 走到最后一条指令（终结符）离开。执行时要么整块跑完，要么整块不跑。
class BasicBlock {
public:
    const std::string& name() const noexcept { return name_; }
    std::int64_t id() const noexcept { return id_; }
    const std::vector<Instr>& instrs() const noexcept { return instrs_; }
    const Terminator& term() const noexcept { return term_; }

    // ---- 造：追加指令（只能加在块尾，顺序就是执行顺序） ----

    void emit_const(std::string dst, std::int64_t imm) {
        instrs_.push_back({Op::Const, std::move(dst), Operand::of(imm), Operand::of(imm)});
    }

    void emit_bin(Op op, std::string dst, Operand lhs, Operand rhs) {
        if (op == Op::Const) {
            throw std::invalid_argument("emit_bin: const 走 emit_const（" + name_ + "）");
        }
        instrs_.push_back({op, std::move(dst), lhs, rhs});
    }

    // ---- 造：设置终结符（每块最多一次；第二次是建造错误） ----

    void term_return(Operand value) {
        ensure_free();
        term_ = Terminator{TermKind::Return, value, nullptr, {}, nullptr, nullptr};
    }

    void term_jump(BasicBlock* target) {
        ensure_free();
        if (target == nullptr) {
            throw std::invalid_argument("term_jump: 目标不能是空指针（块 " + name_ + "）");
        }
        term_ = Terminator{TermKind::Jump, {}, target, {}, nullptr, nullptr};
    }

    void term_cond_branch(Operand cond, BasicBlock* tthen, BasicBlock* telse) {
        ensure_free();
        if (tthen == nullptr || telse == nullptr) {
            throw std::invalid_argument(
                "term_cond_branch: then/else 目标不能是空指针（块 " + name_ + "）");
        }
        term_ = Terminator{TermKind::CondBranch, {}, nullptr, cond, tthen, telse};
    }

private:
    friend class Cfg;

    BasicBlock(std::string name, std::int64_t id) : name_(std::move(name)), id_(id) {}

    void ensure_free() const {
        if (term_.kind != TermKind::None) {
            throw std::invalid_argument("块 " + name_ + " 已有终结符——一个块只能有一个出口");
        }
    }

    std::string name_;
    std::int64_t id_;
    std::vector<Instr> instrs_;
    Terminator term_;
};
