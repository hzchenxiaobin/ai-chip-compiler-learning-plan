# 第 120 天技术校对报告

审阅对象：`tutorials/week-018/day-120/README.md`、`code/minic.py`、`code/run_all.sh`、`code/gemm.mlir`、`code/outputs/`（冻结产物）与 `images/` 三张 SVG。核实方式：在本机临时目录完整复跑 `run_all.sh`（25 PASS / 0 FAIL 复现成功，未触碰仓库冻结产物）；对 E103/退出码等断言用非特权用户（setpriv 降权）实测；对 clang/gcc 退出码语义核对 clang driver 源码（llvm release/20.x）与 GCC 官方文档（gcc/doc/invoke.texi）。以下原文引用均可在 README.md 中逐字找到。

## 【错误】

#### 1. “退出码 2＝用法错误，与 clang/gcc 同族”不成立——clang 与 gcc 的用法错误都退出 1
- **原文**：“0 成功／1 编译失败／2 用法错误——与 clang/gcc 同族”
- **依据**：本机 gcc 9.4.0 实测：`gcc --bogus-flag`、`gcc`（无输入）、`gcc ok.c -o`（缺参数）三种用法错误全部退出 1（编译错误也是 1）；GCC 官方文档（gcc/doc/invoke.texi，`-pass-exit-codes` 条目）明确“Normally the gcc program exits with the code of 1 if any phase of the compiler returns a non-success return code”，没有“2＝用法错误”的约定（2 留给致命错误，ICE 返回 4）。clang 同样：driver.cpp 中 `int Res = 1`，用法错误（BuildCompilation 出错）保持 1 退出。minic 的 0/1/2 实际同族的是 **Python argparse**（argparse 用法错误退出 2，minic 的 E105/E106 路径正是靠它）与部分 GNU 工具（grep/diff 以 2 表示 trouble），而非 clang/gcc。同一论断还出现在今日目标（“与 clang/gcc 同族、脚本可编程消费”）、§8 验收（“退出码 0/1/2 的语义与 clang/gcc 对应”）、图 1/图 2（“（clang/gcc 同族）”）及冻结的 report.txt 中，修改时需一并对齐。
- **置信度**：高（gcc 本机实测＋GCC 官方文档＋clang driver 源码三方一致；clang 未在本地安装，退出码结论来自其源码 `int Res = 1` 分支）。

#### 2. §3.3 “stages 7 条”与冻结产物不符：case-manifest 的 stages 实为 8 条
- **原文**：“stages 7 条、exit_code 0”
- **依据**：`outputs/case-manifest/manifest.json`（-O2 --tile 16,16,16）的 stages 数组实有 8 个对象：S0 读入、S3 `tile=(16,16,16)`、S1、S2、S3、S4、S5、S6。原因在 minic.py:228-235：`opt_level>=2` 时先追加一条 S3 tile 日志，再进入 S1~S6 阶段循环，所以 S3 出现两次。7 条只对 -O0 的 case-o0/case-o0-plain 成立（那里没有额外的 S3 tile 行）。TP4 断言 `len(m["stages"]) >= 7` 因此照样通过，掩盖了数字错误。
- **置信度**：高（直接清点冻结 JSON 与源码逻辑，两处一致）。

#### 3. “manifest 的 9 个字段”实为 11 个
- **原文**：“manifest 的 9 个字段”
- **依据**：冻结的 manifest.json 顶层键共 11 个：version、input、output_dir、opt_level、tile、emit、dump_ir、verify、stages、diags、exit_code。TP4 的 need 列表也只断言其中 8 个。§9 的“manifest.json（9 字段机器合同”同错。无论是按实际键数（11）还是按测试断言数（8），“9 个字段”都对不上。
- **置信度**：高（对冻结 JSON 逐键清点）。

#### 4. “每条四件套”对 W1xx 不成立：三条警告没有修复建议
- **原文**：“每条四件套：代码＋位置＋原因＋**修复建议**”
- **依据**：minic.py 的 DIAG_CODES 中 W101/W102/W103 是单个字符串，不是 (消息, 建议) 二元组；render() 对它们走无修复建议的分支，只输出一行（minic.py:63-67 与 77-88）。实测冻结的 `outputs/diag-w102.txt` 只有一行 `W102 [CLI] ...`，没有“修复建议：”。因此“7+6+3=16 条预定义、每条四件套”（§2 同口径）中 3 条 W 码缺第四件。图 1 的“每条带修复建议”同样沿用此说法。要么给 W 码补建议，要么把“每条”限定为 E 码。
- **置信度**：高（源码结构与冻结输出双重确认）。

#### 5. “八份诊断现场存档”实为 7 份
- **原文**：“E101/E102/E104a/E104b/E105/E107/W102 八份诊断现场存档”
- **依据**：所列名字本身就是 7 个，`code/outputs/` 下 diag-*.txt 也恰好 7 个文件（e101/e102/e104a/e104b/e105/e107/w102），没有第八份。§9 的“8 份诊断现场与 4 份 manifest 样本入档”同错（manifest 样本倒是确实是 4 份）。
- **置信度**：高（目录清单直接核对）。

#### 6. TP 分项统计与真机报告不符：TP1 实为 9 项、TP6 实为 1 项
- **原文**：“（TP1 帮助文本 8 项、TP2 退出码三态 3 项、TP3 诊断逐条触发 7 项、TP4 manifest 字段 2 项、TP5 开关与警告 3 项、TP6 合同快照 2 项）”
- **依据**：report.txt 的 [PASS] 行清点：TP1 有 9 行（8 个关键字 grep＋--version 各一行 PASS）、TP6 只有 1 行（“help.txt 含 10 个选项行（快照入档）”是 echo 说明，不是断言）。总数 25 恰好也对，但 8+3+7+2+3+2 的分法把 --version 从 TP1 挪到 TP6 凑数，与真实报告的 9/1 分布不符。图 3 描述（§5“图 3”行）同样写“TP1 帮助文本 8 项…TP6 合同快照 2 项（help.txt 入档、选项 ≥10）”。
- **置信度**：高（对 report.txt 逐行清点）。

#### 7. 实验 A 的“只读目录”对照不会触发 E103，而是未捕获崩溃退出 1
- **原文**：“对照 `-o` 指向只读目录（`chmod -w` 一个目录再试）”
- **依据**：E103 只在 `os.makedirs(ns.output_dir, exist_ok=True)` 抛 OSError 时触发（minic.py:190-194）；目录已存在时 makedirs 无论是否可写都静默成功。以非特权用户实测（setpriv 降权复现）：`-o` 指向 `chmod -w` 的已存在目录 → 校验通过、管道照跑，写 manifest 时抛 **未捕获的 PermissionError 栈回溯、退出码 1**（Python 未捕获异常默认 1），既不是 E103 也不是 2。只有“在只读父目录下新建子目录”才真正触发 E103 退出 2（同样实测通过）。按教程做这个对照实验的初学者会看到一个崩溃现场而不是结构化诊断。图 2 的“E103 目录可写?”也把“可创建”误写成了“可写”。
- **置信度**：高（本机降权实测两条路径各复现一次；注：root 身份会绕过权限检查，作者当时以普通用户运行macOS 亦同）。

#### 8. “E106 校验已就位”不成立：E106 从未被触发
- **原文**：“E106 校验已就位：`--emit xyz` 退出 2”
- **依据**：minic.py 中 E106 只出现在 DIAG_CODES 定义里，没有任何代码路径产生它；`--emit xyz` 由 argparse 的 `choices=["exec","obj","ir","dump"]` 拦截（实测输出 `argument --emit: invalid choice: 'xyz'`，退出 2，无 E106 结构化诊断）。E105 同样从不由 minic 自身报出，但 §3.2 如实说明了“由 argparse choices 先拦（报 invalid choice，语义同 E105）”；E106 却被描述成“校验已就位”，会误导读者以为存在 E106 的触发路径。
- **置信度**：高（grep 源码＋实测 --emit xyz 行为）。

#### 9. 练习 2“触发全部 7 条 E1xx”不可能：E106 无法触发
- **原文**：“故意触发全部 7 条 E1xx（E101/E102/E103/E104×2 种/E105/E107）”
- **依据**：E1xx 家族按 §3.2/图 1 共 7 条代码（E101~E107）；所列清单只有 6 个代码，把 E104 的两种形态各计一次才凑到 7 次触发事件，E106 被静默略过——而 E106 经 minic 无法触发（见上一条）。另外“数一数每条都有‘修复建议’行”对 E105 的 argparse 形态不成立：diag-e105.txt 是 usage＋`invalid choice`，没有修复建议行。
- **置信度**：高（E106 不可触发已实测；若原意“7 条”指 7 次触发事件，则与“E1xx ×7 条”的代码计数口径冲突，措辞需二选一）。

#### 10. “每次运行必产 manifest”与实现不符：用法错误路径不产 manifest
- **原文**：“minic 承诺每次运行必产 manifest 且字段稳定”
- **依据**：E1xx 致命路径在 parse_and_check 返回后 main 直接 EXIT_USAGE（minic.py:199-203、272-274），不写 manifest；实测 `./minic.py no-such.mlir -o out-test -q` 退出 2，无 manifest.json，连输出目录都未创建（makedirs 在 fatal 时被跳过）。E201（读入 OSError）路径同样在写 manifest 之前返回。结合 §5.1 的“CLI 行为（参数/诊断/退出码/manifest）已 100% 真实”，读者会以为失败运行也留有 manifest 可供 CI 定位；若合同本意是“成功运行必产”，应当写明，否则 D125 的对照脚本在失败样本身上会找不到文件。
- **置信度**：高（实测＋源码路径跟踪；“承诺”若解读为未来合同则属设计意图，但与当日“已 100% 真实”的表述组合起来构成事实误导）。

## 【存疑】

#### 1. “clang 用 -ffoo 前缀隔离实验选项”与 clang 实际惯例不符
- **原文**：“clang 用 `-ffoo` 前缀隔离实验选项”
- **依据**：clang/gcc 的 `-f` 前缀是庞大的常规选项家族（-ffast-math、-fno-strict-aliasing、-funroll-loops 等，长期稳定存在），并非实验选项隔离区；clang 真正用于实验/不稳定特性的是 `-fexperimental-` 前缀（如 -fexperimental-library、-fexperimental-new-constant-interpreter，见 Clang UsersManual 与命令行参考）。未在任何官方文档找到“-f 前缀用于隔离实验选项”的依据。若原意是“用前缀做命名空间隔离”，说法过于含混，建议改为 `-fexperimental-`。
- **置信度**：中（-fexperimental- 前缀的存在有官方文档佐证；但原句若按“前缀隔离”宽泛解读，属不严谨而非硬错误，故列存疑）。

## 【建议】

#### 1. §5.2 的 render() 摘录与真实实现不一致，照抄会在部分诊断码上崩溃
- **原文**：“msg, fix = DIAG_CODES[self.code]”
- **依据**：真实 render()（minic.py:77-88）先判 tuple/str 再用五个占位符（path/ext/value/detail/shape）调用 format；摘录版对 E101（模板占位符是 {path}）会 KeyError，对 W1xx（纯字符串模板）会解包 ValueError。摘录对紧邻的 E104 示例可用，但初学者把它当通用实现抄走会踩坑；建议标注“简化示意”或改贴真实分支。
- **置信度**：高（对两种代码路径分别推演确认）。

#### 2. W102 消息文案自相矛盾（“仍会生效”vs“仅写日志”）
- **原文**：“（-O0 下 tile 仅写日志不生效，警告提示）”
- **依据**：README 的描述是对的，但 minic.py 的 W102 模板是“-O0 下 --tile 仍会生效（Tiling 属于 O2+；O0 的 tile 仅写日志）”，冻结的 diag-w102.txt 同文——“仍会生效”与“仅写日志（即不生效）”出现在同一句里互相打架；建议改成“-O0 下 --tile 不生效（仅写日志）”。这是文案问题，不影响行为。
- **置信度**：高（模板原文直接核对）。

#### 3. stages 的乱序与 S3 重复值得在正文点明（下游消费坑）
- **原文**：“`manifest["stages"]` 是 `[{id, note}, ...]` 列表”
- **依据**：-O2+ 时 stages 的实际顺序是 S0→S3(tile)→S1→S2→S3→S4→S5→S6（minic.py:228-235 先记 tile 行再跑阶段循环），S3 出现两次且 id 不单调。正文只给了 -O0 的有序样例；D125 的对照实验脚本若假设 stages 有序或 id 唯一会被坑。建议在 §3.3 或常见错误里点一句，或把 tile 日志并入 S3 条目。
- **置信度**：高（冻结 case-ok/case-manifest 两个 JSON 都如此）。

#### 4. “约 30 条 op”实为“非注释行数”，口径失真
- **原文**：“[S0] 读入 gemm.mlir：38 行、约 30 条 op”
- **依据**：S0 的计数规则是“非空且不以 // 开头的行”（minic.py:224-226）：30＝38 行去掉 8 行注释，其中含 `}`、`func.func` 头、模块闭括等非 op 行；gemm.mlir 里真正的 MLIR op（func/arith/scf/memref）约 22 个。有“约”字兜底不构成错误，但说“30 个非注释行”或真按 op 计数会更准确，避免读者拿这个数去和 mlir-parse 的 op 统计对账。
- **置信度**：高（计数规则源码确认，op 数手工清点）。

#### 5. 验收清单里的“grep -e”坑在正文没有出处
- **原文**：“grep 模式以 - 开头要用 -e”
- **依据**：这个坑是真的——run_all.sh:28-29 的关键字表里就有 “-O”、“--tile”，不加 `-e` 会被 grep 当成选项解析而报错；但 §6 常见错误只讲了 shell 引号、四件套、混层、tuple→list 四件事，正文没有任何一段解释 grep -e，验收项却要求读者“知道”。建议在 §6 补一小条（或并入错误 3 的修复段）。
- **置信度**：高（README 全文检索无该坑的讲解；grep 行为属 POSIX 常识）。

#### 6. 所引 report.txt 首行时间戳与档案差 1 分钟
- **原文**：“第 120 天：minic CLI 骨架——合同测试报告 2026-11-14 21:05”
- **依据**：outputs/report.txt 首行实为 21:06。纯转写误差，不影响技术内容；下次重跑固化时同步即可，顺带可把“环境：Darwin arm64”两行重复的环境信息一并核对。
- **置信度**：高（两文件逐字比对）。

#### 7. “10 个选项各配 metavar 与默认值”说得过强
- **原文**：“10 个选项各配 metavar 与默认值”
- **依据**：--dump-ir、-q、--version、-h 是 store_true/version 动作，没有 metavar（help.txt 里它们后面也不带值）；带 metavar 的只有 -o/-O/--tile/--verify/--llvm-bin 共 5 个。建议改成“带值选项各配 metavar 与默认值”或“10 个选项各有默认行为”。
- **置信度**：高（对 build_parser 逐项核对）。
