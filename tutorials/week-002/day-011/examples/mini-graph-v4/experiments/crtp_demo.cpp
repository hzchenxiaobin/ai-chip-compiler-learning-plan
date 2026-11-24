// crtp_demo.cpp —— CRTP（Curiously Recurring Template Pattern，奇异递归模板）：
// 把「派生类自己」作为模板参数传回基类，编译期就能拿到真正的类型。
// 用途：零虚表开销的「按类型分派」；代价：类型必须编译期已知。
// 真实世界的参照：MLIR 里每一种算子类都是这个形状——
//   struct TransposeOp : public Op<TransposeOp, ...> { ... };
// 模板基类 Op<> 把派生类自己传回去，静态分发、无虚表。
// 编译运行（在 experiments/ 目录下）：
//   g++ -std=c++17 -Wall -Wextra -O2 crtp_demo.cpp -o crtp_demo && ./crtp_demo
#include <cstdio>
#include <memory>
#include <vector>

// ---------- 同一件事（报出算子名和输入数），两种写法 ----------

// 写法一：虚函数——运行期分发，今天主线用的方案。
class VirtualOp {
public:
    virtual ~VirtualOp() = default;
    virtual const char* name() const = 0;
    virtual int num_inputs() const = 0;
};

class VMatMul : public VirtualOp {
public:
    const char* name() const override { return "matmul"; }
    int num_inputs() const override { return 2; }
};

class VRelu : public VirtualOp {
public:
    const char* name() const override { return "relu"; }
    int num_inputs() const override { return 1; }
};

// 写法二：CRTP——基类把 Derived 静态转型回来，没有 virtual、没有虚表，
// name()/num_inputs() 在编译期就绑定到具体实现，调用点可以直接内联。
template <class Derived>
class CrtpOp {
public:
    const char* name() const { return self().name_impl(); }
    int num_inputs() const { return self().num_inputs_impl(); }

private:
    const Derived& self() const { return static_cast<const Derived&>(*this); }
};

class CMatMul : public CrtpOp<CMatMul> {
public:
    const char* name_impl() const { return "matmul"; }
    int num_inputs_impl() const { return 2; }
};

class CRelu : public CrtpOp<CRelu> {
public:
    const char* name_impl() const { return "relu"; }
    int num_inputs_impl() const { return 1; }
};

// 编译期绑定：OpT 是具体类型，describe<CMatMul> 和 describe<VRelu>
// 是两份独立生成的代码。
template <class OpT>
void describe(const OpT& op) {
    std::printf("  %s：%d 个输入\n", op.name(), op.num_inputs());
}

int main() {
    std::printf("== 虚函数：类型可以等到运行期才知道 ==\n");
    std::vector<std::unique_ptr<VirtualOp>> bag;  // 异构容器装得下不同算子
    bag.push_back(std::make_unique<VMatMul>());
    bag.push_back(std::make_unique<VRelu>());
    for (const auto& op : bag) {
        describe(*op);  // 这里才决定调谁的 name()
    }

    std::printf("\n== CRTP：类型必须在编译期已知 ==\n");
    CMatMul mm;
    CRelu relu;
    describe(mm);    // describe<CMatMul>，静态绑定
    describe(relu);  // describe<CRelu>，静态绑定

    std::printf("\n== CRTP 的代价（为什么今天不用它）==\n");
    std::printf("  1) CrtpOp 是模板不是类，没有公共基类——\n");
    std::printf("     std::vector<CrtpOp*> 装不下 CMatMul 和 CRelu（根本无法编译），\n");
    std::printf("     异构对象只能各存各的容器；\n");
    std::printf("  2) 每种组合实例化一份代码：算子越多，编译越慢、体积越大；\n");
    std::printf("  3) 「运行期拿到 kind 再选动作」（apply_visitor 干的事）帮不上忙。\n");
    std::printf("  结论：CRTP 适合「编译期已知类型 + 追求零开销 + 需要共享大量\n");
    std::printf("  模板基类设施」的场合——MLIR 的 Op 类层次正是为此用它；\n");
    std::printf("  我们的节点是「一个类 + kind 枚举」，用不上 CRTP。\n");
    return 0;
}
