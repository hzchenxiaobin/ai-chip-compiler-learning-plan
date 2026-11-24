#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "Cfg.h"

// 一次 CFG 执行的完整记录：不只是「结果是多少」，
// 还包括「实际走了哪些块」——路径本身就是今天最重要的观察对象。
struct RunResult {
    bool ok = false;
    std::int64_t value = 0;
    std::vector<std::string> path;  // 依次执行过的块名（可重复——循环）
    std::string error;              // 失败原因（unreachable 块不会出现在路径里）
};

// 沿控制流执行：从入口出发，块内指令顺序求值，终结符决定下一块。
// arg_name/arg_value 是运行期绑定（入参）——数据流表里 def 为空的名字，
// 值就是从这里来的。
//
// max_steps 是「燃料上限」：DAG 解释器走一遍拓扑序必然停（第 9 天），
// CFG 解释器没有这个保证——CFG 允许成环，写错跳转目标就是死循环，
// 编译器必须自己带刹车（真实 JIT 里同样要有 step/time limit 保护）。
RunResult run_cfg(const Cfg& cfg, const std::string& arg_name, std::int64_t arg_value,
                  std::int64_t max_steps = 10000);
