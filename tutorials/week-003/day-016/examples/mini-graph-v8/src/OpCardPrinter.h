#pragma once

#include <string>

#include "Node.h"
#include "NodeVisitor.h"
#include "OpKind.h"
#include "Value.h"

// OpCardPrinter：第 11 天的「图打印器」——一个全新的只读 Visitor。
// 它给每种算子打印一行人类可读的「名片」：做什么、吃几个输入、
// 产出什么。注意它是一个独立的新文件：Node、Graph、Interpreter
// 一行都没改——这就是「对扩展开放、对修改关闭」的直观体验。
// 用法：
//   std::string text;
//   OpCardPrinter printer(text);
//   for (const auto& n : graph.nodes()) apply_visitor(printer, *n);
// 遍历顺序由调用方决定（创建序 / 拓扑序都可以），visitor 只管节点。
class OpCardPrinter : public NodeVisitor {
public:
    explicit OpCardPrinter(std::string& out) : out_(out) {}

    void visit_constant(const Node& n) override {
        card(n, "常量", "0 个输入，值写在属性里", "data[" +
                                                     std::to_string(n.attrs().data.size()) +
                                                     " 个元素]");
    }

    void visit_matmul(const Node& n) override {
        std::string how = "2 个输入（%" + n.input(0)->name() + " × %" + n.input(1)->name() + "）";
        if (n.attrs().transpose_a || n.attrs().transpose_b) {
            how += n.attrs().transpose_a ? "，转置 A" : "";
            how += n.attrs().transpose_a && n.attrs().transpose_b ? "，" : "";
            how += n.attrs().transpose_b ? "转置 B" : "";
        }
        card(n, "矩阵乘", how, "");
    }

    void visit_add(const Node& n) override {
        card(n, "逐元素加",
             "2 个同形输入（%" + n.input(0)->name() + " + %" + n.input(1)->name() + "）", "");
    }

    void visit_relu(const Node& n) override {
        card(n, "取正", "1 个输入（%" + n.input(0)->name() + "），逐元素 max(0, x)", "");
    }

    void visit_mul(const Node& n) override {
        card(n, "逐元素乘",
             "2 个同形输入（%" + n.input(0)->name() + " × %" + n.input(1)->name() + "）", "");
    }

    // 每种算子一张名片，格式：
    //   [matmul%n1] 矩阵乘：2 个输入（%A × %B）→ 结果 %C : f32<2x2>
    //（extra 为空时省略末尾的「；……」段）
    void card(const Node& n, const char* title, const std::string& how,
              const std::string& extra) {
        out_ += "  [" + op_name(n.kind()) + "%n" + std::to_string(n.id()) + "] " + title +
                "：" + how;
        if (!extra.empty()) {
            out_ += "；" + extra;
        }
        out_ += " → 结果 %" + n.result()->name() + " : " + n.result()->type().to_string() + "\n";
    }

private:
    std::string& out_;
};
