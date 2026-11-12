#include "Verifier.h"

#include <cstdint>
#include <unordered_set>

#include "Graph.h"
#include "Node.h"
#include "NodeVisitor.h"
#include "OpKind.h"
#include "Value.h"

namespace {

// 错误消息里的「位置」：算子名 + 节点 id，如 "[matmul%n3]"。
// 枚举外的野 kind 会打印成 "[?%n4]"——与第 11 天 use 表里的
// "?%n0" 同款面目，一眼认出就是昨天那个漏网之鱼。
std::string where(const Node& n) {
    return "[" + op_name(n.kind()) + "%n" + std::to_string(n.id()) + "]";
}

// ---- 语义层：每种算子各自的约定（第 11 天框架的第一个正式客户）----
//
// 结构检查（kind 合法、指针非空）由 verify_graph 在分发之前做完；
// 走到这里面的节点，输入指针一定可安全解引用。
// 这里查的就是工厂函数查过的那些约定（raw 入口没查过），
// 外加一条工厂永远给对、只有 raw 才可能错的：结果类型。
class NodeVerifier : public NodeVisitor {
public:
    explicit NodeVerifier(VerifyReport& rep) : rep_(rep) {}

    void visit_constant(const Node& n) override {
        expect_inputs(n, 0);
        const TensorType& t = n.result()->type();
        rep_.fail_if(static_cast<std::int64_t>(n.attrs().data.size()) != t.num_elements(),
                     where(n) + ": 常量数据 " + std::to_string(n.attrs().data.size()) +
                         " 个，与结果 " + t.to_string() + " 的元素数 " +
                         std::to_string(t.num_elements()) + " 不符");
    }

    void visit_matmul(const Node& n) override {
        if (!expect_inputs(n, 2)) {
            return;  // 数量不对就不碰 input(1)：越界解引用比错误报告更糟
        }
        const TensorType& ta = n.input(0)->type();
        const TensorType& tb = n.input(1)->type();
        const TensorType& tr = n.result()->type();

        rep_.fail_if(ta.rank() != 2 || tb.rank() != 2,
                     where(n) + ": 输入 %" + n.input(0)->name() + " 或 %" +
                         n.input(1)->name() + " 不是二维（" + ta.to_string() + " × " +
                         tb.to_string() + "）");
        rep_.fail_if(ta.dtype != tb.dtype,
                     where(n) + ": 两个输入 dtype 不一致：" + dtype_name(ta.dtype) + " vs " +
                         dtype_name(tb.dtype));
        if (ta.rank() == 2 && tb.rank() == 2 && ta.dtype == tb.dtype) {
            const bool ta_t = n.attrs().transpose_a;
            const bool tb_t = n.attrs().transpose_b;
            const std::int64_t m = ta_t ? ta.shape[1] : ta.shape[0];
            const std::int64_t k = ta_t ? ta.shape[0] : ta.shape[1];
            const std::int64_t k2 = tb_t ? tb.shape[1] : tb.shape[0];
            const std::int64_t n_dim = tb_t ? tb.shape[0] : tb.shape[1];
            rep_.fail_if(k != k2,
                         where(n) + ": 内维不匹配：%" + n.input(0)->name() + " 是 " +
                             std::to_string(k) + "，%" + n.input(1)->name() + " 是 " +
                             std::to_string(k2));
            rep_.fail_if(tr.dtype != ta.dtype || tr.rank() != 2 || tr.shape[0] != m ||
                             tr.shape[1] != n_dim,
                         where(n) + ": 结果类型应为 " + dtype_name(ta.dtype) + "<" +
                             std::to_string(m) + "x" + std::to_string(n_dim) + ">，实际是 " +
                             tr.to_string());
        }
    }

    void visit_add(const Node& n) override { expect_elementwise(n); }

    void visit_relu(const Node& n) override {
        if (!expect_inputs(n, 1)) {
            return;  // 同上：数量不对就不碰 input(0)
        }
        const TensorType& tx = n.input(0)->type();
        const TensorType& tr = n.result()->type();
        rep_.fail_if(!(tx == tr),
                      where(n) + ": 结果类型应与输入一致（" + tx.to_string() + "），实际是 " +
                          tr.to_string());
    }

    void visit_mul(const Node& n) override { expect_elementwise(n); }

private:
    // 逐元素二元算子（add / mul）共用一套语义检查：两个输入类型完全
    // 一致，结果类型与输入一致。第一个逐元素算子（add，第 12 天）把
    // 检查写在 visit_add 里；第二个（mul，今天）到来时把它抽成公共
    // 函数——新增同类算子的边际成本从「抄十行」降到「写一行」。
    void expect_elementwise(const Node& n) {
        if (!expect_inputs(n, 2)) {
            return;  // 数量不对就不碰 input(1)：越界解引用比错误报告更糟
        }
        const TensorType& tx = n.input(0)->type();
        const TensorType& ty = n.input(1)->type();
        const TensorType& tr = n.result()->type();
        rep_.fail_if(tx.dtype != ty.dtype || !tx.same_shape(ty),
                     where(n) + ": 两个输入类型不一致：" + tx.to_string() + " vs " +
                         ty.to_string());
        rep_.fail_if(!(tx == tr),
                     where(n) + ": 结果类型应与输入一致（" + tx.to_string() + "），实际是 " +
                         tr.to_string());
    }

    // 返回 false 表示数量不符（已记一笔），调用方应跳过后续语义检查：
    // 后面的检查要按下标解引用输入，数量不对时越界解引用比报告更糟。
    bool expect_inputs(const Node& n, std::size_t expected) {
        if (n.num_inputs() != expected) {
            rep_.fail(where(n) + ": 需要 " + std::to_string(expected) + " 个输入，实际有 " +
                      std::to_string(n.num_inputs()) + " 个");
            return false;
        }
        return true;
    }

    VerifyReport& rep_;
};

}  // namespace

VerifyReport verify_graph(const Graph& g) {
    VerifyReport rep;

    // ---- 图级检查 ----
    if (g.outputs().empty()) {
        rep.fail("图没有输出：所有计算结果都无人消费");
    }
    std::unordered_set<const Value*> value_set;
    for (const std::unique_ptr<Value>& v : g.values()) {
        value_set.insert(v.get());
    }
    for (std::size_t i = 0; i < g.outputs().size(); ++i) {
        const Value* out = g.outputs()[i];
        if (value_set.find(out) == value_set.end()) {
            rep.fail("输出表第 " + std::to_string(i) + " 项 %" + out->name() +
                     " 不属于本图（跨图指针？）");
        }
        for (std::size_t j = 0; j < i; ++j) {
            if (g.outputs()[j] == out) {
                rep.fail("输出表第 " + std::to_string(j) + " 项与第 " + std::to_string(i) +
                         " 项重复（%" + out->name() + "）");
            }
        }
    }

    // ---- 结构检查（逐节点）＋ 语义检查（经 Visitor 分发）----
    std::unordered_set<const Node*> node_set;
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        node_set.insert(n.get());
    }

    NodeVerifier semantics(rep);
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        // 顺序有讲究：kind 合法性必须最先查——apply_visitor 的 switch
        // 对野 kind 会静默跳过（第 11 天 bugs/err_silent_fake_kind.cpp
        // 演示的正是这个洞），不能把检查交给分发本身。
        if (!is_valid_kind(n->kind())) {
            rep.fail(where(*n) + ": 未知的算子类型 " +
                     std::to_string(static_cast<int>(
                         static_cast<std::uint8_t>(n->kind()))) +
                     "（合法值：constant / matmul / add / relu / mul）");
        }

        // 空指针与结果回指：语义检查要解引用这些指针，必须先过这关。
        bool structure_ok = is_valid_kind(n->kind());
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (n->input(i) == nullptr) {
                rep.fail(where(*n) + ": 第 " + std::to_string(i) + " 个输入是空指针");
                structure_ok = false;
            }
        }
        if (n->result() == nullptr) {
            rep.fail(where(*n) + ": 结果值是空指针");
            structure_ok = false;
        } else if (n->result()->producer() != n.get()) {
            rep.fail(where(*n) + ": 结果值的 def 回指错误（%" +
                     n->result()->name() + " 的 producer 不是本节点）");
        }

        // 值归属：输入必须来自本图。工厂查不了这条——它只看得见
        // 手里的指针，看不见「这个值住在哪张图里」。
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            if (n->input(i) != nullptr && value_set.find(n->input(i)) == value_set.end()) {
                rep.fail(where(*n) + ": 第 " + std::to_string(i) + " 个输入 %" +
                         n->input(i)->name() + " 不属于本图（跨图指针？）");
            }
        }

        // 语义检查：结构完整才分发（visit_xxx 要解引用输入）。
        if (structure_ok) {
            apply_visitor(semantics, *n);
        }
    }

    // ---- 账本核对：use-def 双向一致性 ----
    // 正向：每个输入槽 (n, i) 指向 v，则 v 的账本里恰有一条 (n, i)。
    for (const std::unique_ptr<Node>& n : g.nodes()) {
        for (std::size_t i = 0; i < n->num_inputs(); ++i) {
            const Value* v = n->input(i);
            if (v == nullptr) {
                continue;  // 空指针已在上面点名
            }
            std::size_t cnt = 0;
            for (const Use& u : v->users()) {
                if (u.user == n.get() && u.operand == i) {
                    ++cnt;
                }
            }
            if (cnt != 1) {
                rep.fail(where(*n) + ": 第 " + std::to_string(i) + " 个输入槽指向 %" +
                         v->name() + "，但 %" + v->name() + " 的账本里有 " +
                         std::to_string(cnt) + " 条这条使用记录（应为 1）");
            }
        }
    }
    // 反向：账本里的每条 (n, i)，n 属于本图、槽位不越界、槽确实指回 v。
    for (const std::unique_ptr<Value>& v : g.values()) {
        for (const Use& u : v->users()) {
            if (node_set.find(u.user) == node_set.end()) {
                rep.fail("%" + v->name() + " 的账本里有使用者 " + op_name(u.user->kind()) +
                         "%n" + std::to_string(u.user->id()) + "，但这个节点不属于本图");
            } else if (u.operand >= u.user->num_inputs()) {
                rep.fail("%" + v->name() + " 的账本记录（" + op_name(u.user->kind()) + "%n" +
                         std::to_string(u.user->id()) + "，第 " + std::to_string(u.operand) +
                          " 槽）越界：该节点只有 " + std::to_string(u.user->num_inputs()) +
                          " 个输入槽");
            } else if (u.user->input(u.operand) != v.get()) {
                const Value* actual = u.user->input(u.operand);
                rep.fail("%" + v->name() + " 的账本说第 " + std::to_string(u.operand) +
                         " 槽被 " + op_name(u.user->kind()) + "%n" +
                         std::to_string(u.user->id()) + " 使用，但该槽实际指向 " +
                         (actual ? "%" + actual->name() : "空指针"));
            }
        }
    }

    return rep;
}
