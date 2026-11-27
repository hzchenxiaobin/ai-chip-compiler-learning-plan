# 第 36 天技术校对报告

> 校对环境：与教程声明的"本机"完全一致（Ubuntu 20.04 aarch64、LLVM／MLIR 18.1.8、cmake 3.20.5、ninja 1.10.0、g++ 9.4.0、`MLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir`）。全部结论先在临时目录完整重建并运行当天工程（configure→build→三验收→改名实验→run_all.sh 全量重放，脚本退出码 0）后再下判断；对 CMake 宏、头文件、报错文案的存疑点均直接查证了 `/usr/lib/llvm-18` 下安装的源文件。未修改本仓库任何教程原文、代码或冻结输出。

## 【错误】

#### 1. 生成头文件"真实生成内容节选"里的函数签名与 mlir-tblgen-18 的实际输出不符
- **原文**："  static ::llvm::StringRef getDialectNamespace() {"
- **依据**：README 3.2 节声称这是 `build/include/mini/MiniOpsDialect.h.inc` 的"真实生成内容节选"。在本机用同版本 mlir-tblgen-18.1.8 重新生成，实际签名是 `static constexpr ::llvm::StringLiteral getDialectNamespace() { return ::llvm::StringLiteral("mini"); }`——返回类型是 `::llvm::StringLiteral` 且带 `constexpr`，不是 `::llvm::StringRef`（`::llvm::StringRef` 返回形式是更早版本 MLIR 的生成物）。摘录的其余部分（`namespace mini`、构造／析构声明、`MLIR_DECLARE_EXPLICIT_TYPE_ID(::mini::MiniDialect)`）与实际生成内容一致，仅此签名行不真实。
- **置信度**：高（已实际生成并逐行比对；`StringLiteral` 可隐式转 `StringRef`，语义兼容，但"真实内容节选"的声明下这一行是错的）。

#### 2. `summary`／`description` 的消费渠道说错：`--help` 和报错信息都不引用它们
- **原文**："`summary`／`description` 是给人看的（`mlir-opt --help` 的方言文档、报错信息里都会引用）；"
- **依据**：实测 `./build/bin/mini-opt --help` 全文没有任何方言 summary／description（grep 计数为 0，`--help` 只列命令行开关）；实测两种报错全文（`custom op 'mini.foo' is unknown` 与 `Dialect `mini' not found ...` 及 note 行）也不含 summary／description。真正消费这两个字段的是 `mlir-tblgen -gen-dialect-doc`（实测对本教程的 MiniDialect.td 生成含"mini 编译器的张量算子方言"等字样的 Markdown 文档）以及 `--show-dialects` 之外的文档管线，而不是 mlir-opt 的帮助或报错。
- **置信度**：高（两条渠道均实测为否，正确渠道实测为是）。

#### 3. "统一 -fno-rtti 等选项，MLIR 库要求"与本机 MLIR 包的事实相反
- **原文**："llvm_update_compile_flags(mini-opt)      # 统一 -fno-rtti 等选项，MLIR 库要求"
- **依据**：本机 `/usr/lib/llvm-18/lib/cmake/llvm/LLVMConfig.cmake` 明确 `set(LLVM_ENABLE_RTTI ON)`（Ubuntu 的 llvm-18／libmlir-18-dev 是 RTTI 构建产物；实测 `libMLIRIR.a` 含 171 个 `typeinfo for ...` 符号）。`AddLLVM.cmake` 中 `llvm_update_compile_flags` 只在 `LLVM_REQUIRES_RTTI` 与 `LLVM_ENABLE_RTTI` 都为假时才追加 `-fno-rtti`；实测本工程 `build.ninja` 及实际编译命令中 `-fno-rtti` 出现 0 次（加进去的是 `-fno-exceptions` 等其他选项）。即在本教程声明的环境里，MLIR 库并不要求 `-fno-rtti`，该函数也没加。这个说法只对上游源码自编译（默认 RTTI 关）的 MLIR 成立。函数调用本身无害（上游 standalone 示例同款写法），错的是这行注释对行为和原因的断言。
- **置信度**：高（三点独立证据：LLVMConfig 变量、实际编译命令、库内 typeinfo 符号）。

#### 4. "`add_mlir_dialect_library` 自动把 include 路径配好"不是该宏的行为
- **原文**："它比普通 `add_library` 多做两件事——把库登记进全局属性 `MLIR_DIALECT_LIBS`（`tools/mini-opt/CMakeLists.txt` 第一行用 `get_property(... GLOBAL PROPERTY MLIR_DIALECT_LIBS)` 取出来自动链接），以及自动把 include 路径配好。"
- **依据**：查证安装的 `/usr/lib/llvm-18/lib/cmake/mlir/AddMLIR.cmake`：`add_mlir_dialect_library`（598 行起）＝ `set_property(GLOBAL APPEND PROPERTY MLIR_DIALECT_LIBS ${name})` ＋ `add_mlir_library(${ARGV} DEPENDS mlir-headers)`；继续追 `add_mlir_library`／`llvm_add_library`（AddLLVM.cmake），全程没有任何配置 include 路径的语句（AddLLVM.cmake 唯一的 `target_include_directories` 在对象库聚合处，只是透传已有目录）。本工程 `-I` 路径全部来自顶层 CMakeLists 的 4 条 `include_directories()`。该宏相对普通 `add_library` 实际多做的是：登记 `MLIR_DIALECT_LIBS`、追加 `mlir-headers`／`mlir-generic-headers` 依赖、统一链接 `Support` 组件、对象库聚合与安装规则——不含 include 路径。前半句（登记全局属性）属实。
- **置信度**：高（宏源码逐行核读 + 本工程编译命令的 -I 来源核对）。

#### 5. 必做练习给的 arith 头文件路径在本机 MLIR 18 中不存在，练习照做无法编译
- **原文**："头文件是 `mlir/Dialect/Arith/IR/ArithOps.h`，类名 `mlir::arith::ArithDialect`，库是 `MLIRArithDialect`。"
- **依据**：`ls /usr/lib/llvm-18/include/mlir/Dialect/Arith/IR/` 显示该目录只有 `Arith.h`、`ValueBoundsOpInterfaceImpl.h`、若干 `.td` 和生成的 `ArithOps.h.inc`／`ArithOpsDialect.h.inc` 等，**没有 `ArithOps.h`**；实测 `g++ -I /usr/lib/llvm-18/include` 编译 `#include "mlir/Dialect/Arith/IR/ArithOps.h"` 报 `fatal error: mlir/Dialect/Arith/IR/ArithOps.h: No such file or directory`。正确写法是 `#include "mlir/Dialect/Arith/IR/Arith.h"`（实测可编译，且经 `ArithOpsDialect.h.inc` 声明了 `mlir::arith::ArithDialect`）。句子后半正确：类名 `mlir::arith::ArithDialect`、CMake 目标 `MLIRArithDialect` 均存在（`MLIRTargets.cmake` 中有该导入目标）。
- **置信度**：高（目录列表、失败编译、成功编译三重验证）。

## 【存疑】

- 无。

## 【建议】

#### 6. "84 行"的口径没把 Dialect.h 算进"手写的 C++ 代码"
- **原文**："（`code/mini/`，其中手写的 C++／TableGen 代码合计仅 **84 行**）"
- **依据**：84 = MiniDialect.td(39)＋MiniDialect.cpp(20)＋MiniOpt.cpp(25)，与 run_all.sh 第 6 步 `wc -l` 的口径一致；但 `include/mini/Dialect.h` 也是手写 C++（15 行），5 份 CMakeLists（合计 69 行）也是手写。按"手写的 C++／TableGen 代码"的字面口径应是 99 行（不含 CMake）。建议写明统计口径（如"三份核心源文件 84 行"），避免读者自己数出矛盾。
- **置信度**：高（行数实测）。

#### 7. Standalone 模板并没有 `tools/` 目录这一层
- **原文**："说清 Standalone 模板的目录为什么分成 `include／lib／tools` 三层"
- **依据**：Day 34 实际使用的 standalone 工程（与上游 `mlir/examples/standalone` 同构）顶层目录是 `include/`、`lib/`、`standalone-opt/`、`standalone-translate/`、`standalone-plugin/`、`test/`、`python/`，没有 `tools/`；可执行工具是顶层的 `standalone-opt/` 等目录。三层职责划分（接口／实现／工具）的讲法成立，`tools/` 是本教程 mini 工程自己的整理，建议表述成"Standalone 把工具放在顶层 standalone-opt/ 等目录，mini 把它们规整进 tools/ 一层"。
- **置信度**：高（以本仓库 Day 34 目录为准；上游 18 同构）。

#### 8. run_all.sh 第 4 步 mlir-opt-18 的返回码偶发为 74，与"均为 rc=1"的口径不完全一致
- **原文**："同一份 `mini_ghost_op.mlir`，两种口径（均为 `rc=1`）："
- **依据**：直连调用两个工具确为 rc=1（实测多次）；但 run_all.sh 第 4 步用 `| head -2` 截断输出，head 读满 2 行退出后 mlir-opt-18 还要继续写 caret/note 行，可能撞上已关闭的管道，完整重放中实测出现过 `rc=74`（另一次是 1，时序相关、非确定）。脚本里注释写死"（mini 未注册：报 Dialect not found，rc=1）"，重放者看到 74 会困惑。README 原文本身（直连场景）不错，建议在脚本或 README 提示 head 截断会让管道前端的退出码偶发变成 74。
- **置信度**：高（74 现象实测复现；对其触发机制的归因（输出管道被提前关闭）为合理推断，未逐帧追内核调用）。

#### 9. 没给输入文件时，mini-opt 实际在等标准输入（交互终端下像"卡住"）
- **原文**："没给输入文件时 `MlirOptMain` 会构造一个空 IR 照常走“解析→打印”流程。"
- **依据**：伪终端实测 `mini-opt --show-dialects` 会先打印 `(processing input from stdin now, hit ctrl-c/ctrl-d to interrupt)` 并阻塞等 stdin；空输入／EOF 时由解析器生成隐式 `builtin.module`，随后打印 `module {}`（`echo -n "" | mini-opt` 实测）。所以"空 module"来自"读 stdin＋空输入解析成隐式 module"，不是 MlirOptMain 主动构造；教程里的控制台输出与管道／重定向场景一致，但初学者在真实终端裸跑会以为工具挂了。建议补一句"无输入文件＝读标准输入，Ctrl-D 结束输入"。
- **置信度**：高（伪终端实测捕获提示行）。

#### 10. `get_property` 取到的 `MLIR_DIALECT_LIBS` 不止 MLIRMini，mini-opt 实际链了 267 个静态库
- **原文**："**链接**：`MLIRMini` 只是个库，没有 `main()` 干不了活；`mini-opt` 把它和 MLIR 的 `MLIROptLib`（`MlirOptMain`）、`MLIRFuncDialect` 链在一起，成为能独立分发的工具；"
- **依据**：`find_package(MLIR)` 时 `MLIRConfig.cmake` 会预先 `set_property(GLOBAL PROPERTY MLIR_DIALECT_LIBS "...")` 塞进约 100 个上游方言库，`add_mlir_dialect_library(MLIRMini)` 再 APPEND；因此 `tools/mini-opt/CMakeLists.txt` 取出的 `${dialect_libs}` 是"全部上游方言库＋MLIRMini"，实测 mini-opt 链接命令含 267 个 `.a`。功能无碍（注册表仍只有 builtin/func/mini），而且这恰好是"链接≠注册"最直观的现场证据；不点破的话，读者看链接行长度和构建时间会意外。建议在 3.3 或 6-④ 提一句。
- **置信度**：高（链接命令实测计数）。

#### 11. 换成 `add_mlir_dialect(MiniOps mini)` 时，lib/CMakeLists.txt 的 DEPENDS 目标名必须跟着改
- **原文**："把这四行换成一行 `add_mlir_dialect(MiniOps mini)`，文件名不变、下游 `Dialect.h`／`MiniDialect.cpp` 一行不用改。"
- **依据**：`AddMLIR.cmake` 的 `add_mlir_dialect` 生成目标名是 `MLIR${dialect}IncGen`，即 `MLIRMiniOpsIncGen`（不是今天的 `MLIRMiniDialectIncGen`）；Day 37 实际代码里 `lib/CMakeLists.txt` 已把 `DEPENDS` 改成 `MLIRMiniOpsIncGen`。所引句子限定的两个文件确实没改（Dialect.h 与 Day 36 逐字相同，MiniDialect.cpp 的方言相关行未变，变的都是加算子所需的新内容），句子本身成立；但"只换这四行"会让 CMake 在不存在的目标上报错，建议把"同步改 DEPENDS 为 MLIRMiniOpsIncGen"点出来。
- **置信度**：高（宏源码＋Day 37 实际文件双重验证）。

#### 12. "原样 round-trip"与 `%x`→`%arg0` 的表述张力
- **原文**："一份冒烟 IR 原样 round-trip"
- **依据**：实测 round-trip 后 `%x` 变 `%arg0`（README 5.3 已正确解释"名字只是注记、入口块参数按 argN 重起名"，并实测 `%mysum` 这类普通结果名也会变成 `%0`，"解析器不保存名字"的说法成立）；但 `code/mini_smoke.mlir` 自己的注释写"一个字不差地还回来"，与实测输出矛盾。建议把"原样"统一成"结构原样、名字按打印规则重起"，并顺手改掉冒烟文件里那句注释。
- **置信度**：高（两种改名行为均实测）。
