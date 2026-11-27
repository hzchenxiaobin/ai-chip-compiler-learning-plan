# 第 34 天技术校对报告

> 校对环境：Ubuntu 20.04.5 arm64，MLIR/LLVM 18.1.8（`mlir-18-tools`/`libmlir-18-dev`/`llvm-18-dev` 1:18.1.8-11~20.04.2，`lit` 18.1.8，`cmake` 3.20.5）。全部结论基于本机复跑（全新构建于 `/tmp`、`run_all.sh` 全量重放、对照上游 llvm-project release/18.x 源码逐文件 diff、mlir-tblgen 反证实验、伪插件加载实验），未修改仓库内任何教程原文、代码或冻结输出。

## 【错误】

#### 1. ".td 一共三份"的说法与实际文件数不符，且"3 张菜谱 → 7 份 .inc"的映射不成立
- **原文**：“- **一个最小例子**：整个方言只有三个 `.td`，职责各管一层：”
- **依据**：`code/standalone/include/Standalone/` 实际有 **4** 份 `.td`：`StandaloneDialect.td`、`StandaloneOps.td`、`StandalonePasses.td`、`StandaloneTypes.td`（`ls` 即可复核）。被遗漏的 `StandaloneTypes.td` 恰恰生成 §3.2 列出的 7 份 `.inc` 中的两份——`StandaloneOpsTypes.h.inc` 和 `StandaloneOpsTypes.cpp.inc`（本机全新构建日志 `[5]`/`[7]` 步即生成这两份；`mlir-tblgen` 亦确认二者由该 `.td` 的 `--gen-typedef-*` 产出）。因此 §3.2"把上面三张菜谱译成 7 份 .inc"的对应关系对不上；§1 的"3 份 `.td`（TableGen 声明）"、§2 的"3 份 `.td`"、§8 验收"3 份 `.td`（Dialect／Ops／Passes）"同为此错。读者按"3 份 .td"去对 ninja 日志的 7 个 `.inc` 目标时，有 2 个无从归属。
- **置信度**：高（文件清单与构建日志直接可查）。

#### 2. 手写 C++"一共三份"、目录清单"3 份 .td ＋ 3 份 .h"与实际不符
- **原文**：“    ├── lib/Standalone/        # 3 份手写 .cpp（§3.3 的胶水都在这）”
- **依据**：`lib/Standalone/` 实际有 **4** 份 `.cpp`：`StandaloneDialect.cpp`、`StandaloneOps.cpp`、`StandalonePasses.cpp`、`StandaloneTypes.cpp`（全新构建日志 `[11/20] Building CXX object ... StandaloneTypes.cpp.o` 即为被遗漏的第 4 份）。同理 §5.1 的上一行“include/Standalone/    # 3 份 .td ＋ 3 份 .h”实为 **4 份 .td ＋ 4 份 .h**；§3.3 的“必须手写，一共三份”、§1 的“3 份手写 C++”、§8 的“3 份手写 C++ 各负责什么”均少计了 `StandaloneTypes.cpp`（其内容正是 `registerTypes()` 与 `GET_TYPEDEF_CLASSES` 展开——§3.3 引用的 `initialize()` 里那行 `registerTypes();` 的实现就在这份文件里）。
- **置信度**：高（`ls lib/Standalone/` 与构建日志直接可查）。

#### 3. "registry.insert 了几个，--show-dialects 就列几个"与本教程自身输出矛盾
- **原文**：“`main()` 里 `registry.insert` 了几个，这里就列几个——昨天"户口登记处"的可视化。”
- **依据**：`standalone-opt.cpp` 的 `main()` 只 `insert` 了 **3** 个方言（standalone、arith、func，见 §3.3 自己贴出的代码），而 `--show-dialects` 实际输出 4 个（`arith,builtin,func,standalone`，本机复跑及 `--help` 头部均含 `builtin`）。原因：MLIR 18 的 `DialectRegistry` 构造函数无条件注册 builtin——上游 release/18.x `mlir/lib/IR/Dialect.cpp:176`：`DialectRegistry::DialectRegistry() { insert<BuiltinDialect>(); }`。按原句"插几个列几个"去数会得出 3≠4 的矛盾，且容易让初学者误以为 `builtin` 需要手工 `insert`。
- **置信度**：高（源码与本机输出双重验证）。

#### 4. 错误 A 的第三种修复方案 `-allow-unregistered-dialect` 对本篇输入并不生效
- **原文**：“- **修复**：三选一——用 `standalone-opt`（路 A）；加 `--load-dialect-plugin=.../StandalonePlugin.so`（路 B）；或加 `-allow-unregistered-dialect`（Day 33 说过的调试后门，Pass 不生效，仅救急）。”
- **依据**：本机实测 `mlir-opt-18 foo_demo.mlir -allow-unregistered-dialect` **仍报同样错误、退出码 1**（`Dialect 'standalone' not found for custom op 'standalone.foo'`）。原因：`standalone.foo %arg0 : i32` 是**自定义（pretty）语法**，解析器必须查到已注册的 op 才能调度其自定义解析函数，未注册方言时 `-allow-unregistered-dialect` 也无从解析；该旗标只对**generic 形式**生效——把输入改写成 `"standalone.foo"(%arg0) : (i32) -> i32` 后加该旗标可正常通过（本机实测 exit=0）。而错误 A 的"现象"正是 custom 形式的 `foo_demo.mlir`，把该旗标列为三选一的修复会误导读者以为加上就能过。
- **置信度**：高（正反两个实验均在本机复现）。

#### 5. "保持上游原状/上游 out-of-tree 工程（保持原状交付）"与交付树的实际修改不符
- **原文**：“└── standalone/                # 上游 out-of-tree 工程（保持原状交付）”
- **依据**：与 llvm-project release/18.x `mlir/examples/standalone` 逐文件 diff，交付树有 **2 处**非上游修改：① `test/CMakeLists.txt` 把上游末行的 `add_subdirectory(CAPI)` 注释掉并加了中文说明；② `test/CAPI/lit.local.cfg` 由上游的 `config.suffixes.add(".c")` 改为 `config.unsupported = True` 并加中文说明。其余文件（含全部 `.td`、`lib/Standalone/*.cpp`、两个工具入口、测试 `.mlir`）与上游逐字节一致。这不只是措辞问题：观察点 5 的"6 个测试（5 通过＋1 Unsupported）"正是依赖跳过 CAPI 后的计数——上游原状在本环境（Ubuntu 包无 `MLIR_INSTALL_AGGREGATE_OBJECTS` 聚合对象）连配置都过不去。第 6 行“保持上游原状”、§5.4 (8f)“交付的源码树保持上游原状”、§8“还原为上游原状”应改为如实说明"为适配 Ubuntu 官方包跳过了 CAPI 测试，其余保持上游原状"。
- **置信度**：高（与上游 release/18.x 的 diff 直接验证）。

#### 6. 图 1、图 2 及图 2 的替代文本写成"前 4 步"，与正文"前 7 步"及真实构建日志矛盾；图 2 的 `[2/20]` 步名也与日志不符
- **原文**：“2. **建**：`cmake`＋`ninja` 构建出 `standalone-opt`，构建日志前 7 步全是生成 `.inc`（§5.2）；”
- **依据**：正文的"前 7 步"正确（本机全新构建 `[1/20]`～`[7/20]` 全为 `.inc` 生成，`[8/20]` 才开始编译 C++，与 §5.2 日志一致）。但同一篇 README 内部自相矛盾：第 230 行图 2 的替代文本写“附生成的 Verifier 代码片段与真实 ninja 日志前 4 步”；`images/01-overview.svg` 内文案为“mlir-tblgen 在构建前 4 步自动生成 .inc”；`images/02-mechanism.svg` 内文案为“真实 ninja 日志（前 4 步全是生成）”。另外 `02-mechanism.svg` 把 `[2/20]` 标注为“…OpsDialect.cpp.inc”，而真实日志与 §5.2 自己的日志中 `[2/20]` 是 `StandaloneOps.cpp.inc`、`StandaloneOpsDialect.cpp.inc` 是 `[3/20]`。"前 7 步"是本篇反复强调的观察点（今日目标、§2、§5.2、§8 共 4 处），图内写 4 会让对照阅读的读者对不上账。
- **置信度**：高（SVG 文案已逐字提取比对，构建日志本机复跑验证）。

#### 7. "standalone-plugin.cpp 只暴露一个 extern "C" 入口"与文件实际内容不符
- **原文**：“- **为什么两条路都要会**：自己的工程随便重编（路 A，秒级增量编译）；但给别人的工具加能力——比如让没重编过的 `mlir-opt-18` 认识 `standalone.foo`——只能走插件。**对应到技术上是**：路 B 的 `standalone-plugin.cpp` 只暴露一个 `extern "C"` 入口，把和路 A **同一份**注册代码装进函数指针：”
- **依据**：`standalone-plugin.cpp` 实际有 **两个** `extern "C"` 入口：`mlirGetDialectPluginInfo`（供 `--load-dialect-plugin` 用）和 `mlirGetPassPluginInfo`（供 `--load-pass-plugin` 用）。lit 官方测试 `test/Standalone/standalone-pass-plugin.mlir` 的 RUN 行用的恰是 `--load-pass-plugin`——即本篇让读者跑的 `check-standalone`（观察点 5、8d/8e）会执行到这第二个入口。按"只暴露一个入口"去读源码会对不上；另外"同一份注册代码"也应加限定——插件里只 `insert` 了 `StandaloneDialect` 并 `registerPasses()`，比路 A `main()` 少了 `arith`、`func` 两个方言（这也是插件路只加载方言、不预置 arith/func 的原因之一，输入里出现 `arith`/`func` op 时两者行为并非完全等价）。
- **置信度**：高（源码直接可见；`--load-pass-plugin` 的测试在本机 `check-standalone` 中通过）。

## 【存疑】

#### 1. "插件版本必须和宿主工具的 MLIR 版本匹配（API 版本号 MLIR_PLUGIN_API_VERSION 就是合同号），版本错位加载即崩"——结论方向对，但机制与行为表述过于绝对
- **原文**：“`mlir-opt-18 --load-dialect-plugin=StandalonePlugin.so` 加载后，系统工具与本工程工具行为完全一致（§5.3 实验 7，本机双跑对照过，输出逐字节相同）。将来 CANN 生态里给 `aicpu`／`ascend` 方言扩工具，走的正是这套机制。**类比的边界**：插件不是万能外挂——插件版本必须和宿主工具的 MLIR 版本匹配（API 版本号 `MLIR_PLUGIN_API_VERSION` 就是合同号），版本错位加载即崩。”
- **依据**：分两种"错位"验证：(a) `MLIR_PLUGIN_API_VERSION` 号不同——本机构造 apiVersion=999 的伪 `.so` 实测加载，得到的是**优雅拒绝**而非崩溃：`Failed to load dialect plugin from '...'. Request ignored.`（对应上游 `mlir/lib/Tools/Plugins/DialectPlugin.cpp:40-45` 的 `Wrong API version on plugin ...` StringError，宿主继续运行）；(b) MLIR 版本不同但 API 号相同——查证 MLIR 16/17/18 的 `MLIR_PLUGIN_API_VERSION` **均为 1**，即"合同号"跨版本不变、挡不住"MLIR 17 插件喂给 MLIR 18 宿主"这种最常见的错位，此时确有崩溃/未定义行为风险。因此"版本错位加载即崩"在 (b) 场景成立、在 (a) 场景不成立；"API 版本号就是合同号"作为版本匹配的保障也被高估了（它是粗粒度接口握手，不是 MLIR 发行版本号）。另注："输出逐字节相同"部分本机已复核为真（插件路 vs 自带工具 diff 为空）。
- **置信度**：中（两个分支行为均有实证；仅"即崩"何时发生随错位种类而异，无法穷举验证，故不入【错误】）。

## 【建议】

#### 1. round-trip 的实际输出包了一层 `module {}`，与"输出见 foo_demo.mlir 内容本身"略有出入
- **原文**：“**观察点 2——round-trip**：`standalone-opt foo_demo.mlir` 原样吐回（生成的 parse 读进来、生成的 print 写出去，一来一回没走样，输出见 `foo_demo.mlir` 内容本身）。注意 `: i32` 只标注操作数，结果类型由 `inferReturnTypes` 照抄（§3.2）。”
- **依据**：本机实测输出为 `module { func.func @main(...) { ... } }`——`MlirOptMain` 把输入解析进顶层 ModuleOp，打印时多出 `module {` 包装。op 一级确实"没走样"，但"输出见 foo_demo.mlir 内容本身"严格说少了一层包装；初学者逐行对照时会发现首尾多两行。建议改为"输出＝输入外加一层 module 包装"。
- **置信度**：高（本机输出直接可查，影响很小）。

#### 2. "把声明展开成上千行 C++"——本工程实测 7 份 .inc 共 760 行
- **原文**：“- **一个类比**：米其林中央厨房。菜谱（`.td`）只描述"这道菜有 `i32` 输入、`i32` 输出、不含麸质（无副作用）"；中央厨房（`mlir-tblgen`）照菜谱批量预制半成品（`.inc`）；门店厨师（手写 C++）只做菜谱覆盖不了的收尾——摆盘、开店、挂招牌。**对应到技术上是**：TableGen 是 LLVM 的领域特定语言，MLIR 用它**结构化地**描述 op 的名字、操作数／结果类型约束、trait（如 `Pure`）、通用语法格式；`mlir-tblgen` 在**构建期**把声明展开成上千行 C++。”
- **依据**：`wc -l` 实测 7 份 `.inc` 合计 760 行（最大单份 `StandaloneOps.cpp.inc` 240 行）。"上千行"是形容真实多算子方言的惯用说法，但针对本工程单算子示例略有夸大，"数百行/近千行"更贴切。
- **置信度**：高（行数直接可查，仅量级措辞问题）。

#### 3. "run_all.sh（本篇所有命令都在里面）"——两种 Pass 写法中直连旗标那种不在脚本里
- **原文**：“├── run_all.sh                 # 一键重放全部 8 组实验（本篇所有命令都在里面）”
- **依据**：`run_all.sh` 实验 5/8 只用 `--pass-pipeline="builtin.module(standalone-switch-bar-foo)"` 写法；观察点 4 的写法一（直连旗标 `--standalone-switch-bar-foo`）未出现在脚本任何位置。两种写法输出确实逐字节相同（本机 diff 验证），功能上无缺失，但"所有命令都在里面"的表述与事实有出入。
- **置信度**：高（脚本全文已核对，影响很小）。

#### 4. "SameOperandsAndResultType 让生成器自动实现『结果类型照抄操作数』，所以书写格式里结果不需要写类型"——前半句经实验证实，"所以"的因果链可再精确
- **原文**：“这解释了一个 Day 30 遗留的小谜题：`%0 = standalone.foo %arg0 : i32` 结尾的 `: i32` 明明标注的是**操作数**，结果 `%0` 的类型从哪来？——`SameOperandsAndResultType` 让生成器自动实现"结果类型照抄操作数"，所以书写格式里结果不需要写类型。”
- **依据**：用 `mlir-tblgen` 做对照实验：带 `SameOperandsAndResultType` 时 `inferReturnTypes` 生成 `operands[0].getType()`（照抄操作数）✅；**去掉该 trait 重新生成，`inferReturnTypes` 依然存在**，只是改为 `odsBuilder.getIntegerType(32)`（按 `.td` 的 `I32` 推常量类型），且 `InferTypeOpInterface::Trait` 照样挂在 op 上。即"书写格式里结果不需要写类型"的根本原因是 `assemblyFormat` 触发生成的 `InferTypeOpInterface`（有无该 trait 都成立），`SameOperandsAndResultType` 决定的是推断规则为"照抄操作数"。建议把"所以"一句拆开表述，避免读者以为去掉 trait 后 pretty form 就必须写结果类型。
- **置信度**：高（tblgen 正反对照实验直接验证；仅因果表述精度问题，不影响主体结论）。

#### 5. "户口登记处 MLIRContext，登记动作就发生在这几行"——registry.insert（注册）与 Dialect 加载进 Context（加载）宜作区分
- **原文**：“工具入口 `standalone-opt/standalone-opt.cpp` 的 `main()` 干三件事：注册全部上游 Pass ＋ 本方言 Pass；建 `DialectRegistry` 并 `insert` 本方言与 `arith`、`func`；交给 `MlirOptMain`——**昨天说的"户口登记处 `MLIRContext`"，登记动作就发生在这几行**：”
- **依据**：`main()` 里 `registry.insert<...>` 注册进的是**局部变量 `DialectRegistry`**（注册的是各方言的构造器）；`MLIRContext` 要到 `MlirOptMain` 内部处理输入时才创建，并在构造时把 registry 拷入、按需惰性加载方言（上游 `MLIRContext.cpp` "Pre-populate the registry ... Ensure the builtin dialect is always pre-loaded"）。§6 错误 A 报错 note 里附的官方 FAQ 链接讲的正是 registered/loaded/dependent 三态区别。建议此处补一句"注册（registry）≠ 加载（context，解析到才加载）"，与后文 `--show-dialects` 的"Available（已注册）"呼应更准确。
- **置信度**：中（术语精度问题，教学简化可接受；MLIR 官方 FAQ 明确区分两态，读者若按字面理解"insert 即入 context"会在 Day 35 概念图串联时产生偏差）。
