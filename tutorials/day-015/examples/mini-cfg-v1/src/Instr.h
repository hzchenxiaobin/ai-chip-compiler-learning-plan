#pragma once

#include <cstdint>
#include <string>

// 值指令的算子。Gt/Le 产出 0/1（假/真），供条件跳转使用。
enum class Op { Const, Add, Sub, Mul, Gt, Le };

inline const char* op_name(Op op) {
    switch (op) {
        case Op::Const: return "const";
        case Op::Add: return "add";
        case Op::Sub: return "sub";
        case Op::Mul: return "mul";
        case Op::Gt: return "gt";
        case Op::Le: return "le";
    }
    return "?";
}

// 操作数：要么是变量名，要么是整型立即数。
// 显式区分（is_imm），不靠「字符串像不像数字」去猜——猜是第 13 天
// 之前的老问题，今天的新世界（可变变量）更要一开始就说清楚。
struct Operand {
    bool is_imm = false;
    std::string var;       // is_imm == false 时有效
    std::int64_t imm = 0;  // is_imm == true 时有效

    static Operand var_of(std::string name) { return {false, std::move(name), 0}; }
    static Operand of(std::int64_t v) { return {true, "", v}; }

    std::string to_string() const {
        return is_imm ? std::to_string(imm) : var;
    }
};

// 一条指令：dst <- op(lhs, rhs)。Const 只用 imm 字段。
// 注意：dst 是「变量名」，同一名字可以被写多次（今天的 RAM 机器）——
// 这正是第 17 天 SSA 要治的病，今天先诚实保留。
struct Instr {
    Op op = Op::Const;
    std::string dst;
    Operand lhs;
    Operand rhs;
};
