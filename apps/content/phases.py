"""六阶段路线数据（与原静态站 build.py 保持一致）。"""

ROADMAP = [
    (
        "阶段一",
        "C++ 与编译器基础",
        "Modern C++ → 计算图 IR → SSA → 优化 Pass",
        [
            "搭建 CMake 工程，实现最小 Tensor",
            "Graph / Node / Value 与 Use-Def",
            "CFG、支配关系与活跃变量分析",
            "常量折叠、DCE、CSE 与 PassManager",
        ],
    ),
    (
        "阶段二",
        "MLIR 核心能力",
        "IR 结构 → mini Dialect → Shape 推导 → 算子融合",
        [
            "Operation / Region / Block 与类型系统",
            "ODS 定义 mini Dialect 与 Verifier",
            "Shape Inference / Canonicalization / Fold",
            "算子融合与多使用者约束",
        ],
    ),
    (
        "阶段三",
        "AI 计算图与图优化",
        "Layout → 冗余消除 → Cost Model → 数值验证",
        [
            "Shape、Stride、Broadcast 与动态 Shape",
            "Layout 转换与冗余算子消除",
            "融合流量、资源代价与 Cost Model",
            "浮点误差、INT8 量化与数值验证",
        ],
    ),
    (
        "阶段四",
        "Lowering、Tiling 与性能",
        "循环 IR → Tiling → 内存规划 → 自动调优",
        [
            "DialectConversion 与三重循环生成",
            "循环顺序、Tiling、Unroll 与实验",
            "生命周期、内存复用与 Double Buffering",
            "Auto-tuning、GFLOPS 与 Roofline",
        ],
    ),
    (
        "阶段五",
        "端到端编译与 Runtime",
        "LLVM → 统一编译入口 → Runtime → 回归体系",
        [
            "LLVM Dialect、LLVM IR 与 JIT / AOT",
            "统一 CLI、IR Dump 与端到端项目",
            "动态 Shape、特化、内存与异步模型",
            "随机测试、Pass 定位与性能回归",
        ],
    ),
    (
        "阶段六",
        "项目收口与面试转化",
        "扩展方向 → 性能归因 → 项目材料 → 最终验收",
        [
            "扩展方向设计、实现与验收",
            "性能基线、瓶颈分析与优化验证",
            "架构、Pass、Lowering 与复现材料",
            "面试标准回答与最终项目验收",
        ],
    ),
]
