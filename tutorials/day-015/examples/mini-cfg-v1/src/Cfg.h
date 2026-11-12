#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "Block.h"

// 变量的数据流画像：在哪些块被定义、在哪些块被使用。
// def_blocks 出现两次的名字（如菱形汇合前的 u）就是第 17 天
// SSA 要拆开的多重定义；def_blocks 为空的名字（如 a、n）是
// 运行期才绑定的入参——两种形态今天都先「如实记录」。
struct VarFlow {
    std::vector<std::string> def_blocks;
    std::vector<std::string> use_blocks;
};

// Cfg：一张控制流图——第 15 天版本的「函数」。
// 所有权纪律与第 8 天的 Graph 完全一致：块的所有权集中在 Cfg
// （unique_ptr 名单），块与块之间的跳转边全部是借用指针；
// 拷贝删除、移动保留——搬家不换房本，借用指针搬家后照旧有效。
class Cfg {
public:
    explicit Cfg(std::string name) : name_(std::move(name)) {}

    Cfg(const Cfg&) = delete;
    Cfg& operator=(const Cfg&) = delete;
    Cfg(Cfg&&) noexcept = default;
    Cfg& operator=(Cfg&&) noexcept = default;

    // ---- 造 ----

    // 新建一个块并取得它的借用指针。名字必须唯一且非空——
    // 打印、路径日志、将来的诊断全靠名字认块。
    BasicBlock* new_block(std::string name);

    void set_entry(BasicBlock* b);

    // ---- 查：控制流邻接（前驱 / 后继） ----

    // 后继：从终结符直接读出——边的来源就是跳转目标。
    // 按出现顺序返回，去重（then/else 同目标只算一条边）。
    std::vector<const BasicBlock*> successors(const BasicBlock* b) const;

    // 前驱：没有哪个字段直接存它——把所有块的后继扫一遍，
    // 谁的后继里有我，谁就是我的前驱（反向收集）。
    std::vector<const BasicBlock*> predecessors(const BasicBlock* b) const;

    // 边总数（去重后的后继条数之和）。
    std::int64_t num_edges() const;

    // ---- 查：数据流（变量的定义块 / 使用块，跨块） ----

    std::map<std::string, VarFlow> dataflow() const;

    // ---- 查：合法性 ----

    // 返回 true 表示通过；why 非空时写入第一条失败原因。
    // 检查项：入口已设置且属于本图；每块都有终结符；
    // Jump/CondBranch 的目标非空且属于本图。
    // 注意它「不」查的事：不查变量有没有定义（那是运行期路径决定的，
    // 第 6 节错误四专门讲这个坑）；不查可达性（没有前驱的块是死代码，
    // 打印时标注，删除是第 25 天 DCE 的事）。
    bool verify(std::string* why = nullptr) const;

    // ---- 打印 ----

    // 文本形式 CFG：每块一行头（名字＋前驱注释）＋指令＋终结符。
    std::string to_string() const;

    // 边表：b0 -> b1 (then) 这样一行一条控制边。
    std::string edges_to_string() const;

    // 前驱/后继总表：一行一个块，左右各是 preds、succs。
    // 没有前驱又不是入口的块标注 unreachable。
    std::string preds_succs_to_string() const;

    // 数据流总表：一行一个变量，定义块与使用块各一列。
    std::string dataflow_to_string() const;

    // ---- 基础信息 ----

    const std::string& name() const noexcept { return name_; }
    const std::vector<std::unique_ptr<BasicBlock>>& blocks() const noexcept { return blocks_; }
    const BasicBlock* entry() const noexcept { return entry_; }
    std::int64_t num_blocks() const noexcept { return static_cast<std::int64_t>(blocks_.size()); }
    std::int64_t num_instrs() const noexcept;
    bool owns(const BasicBlock* b) const;

private:
    // 块名 → 块的登记表（名字唯一合同，同第 13 天前端）。
    std::map<std::string, BasicBlock*> by_name_;

    std::string name_;
    std::vector<std::unique_ptr<BasicBlock>> blocks_;  // 所有权：块
    BasicBlock* entry_ = nullptr;                      // 借用：入口
};
