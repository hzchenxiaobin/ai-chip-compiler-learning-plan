# 第 7 天技术校对报告

校对环境与验证方法：Linux aarch64（Ubuntu 20.04）· g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0，与教程 5 节声明的环境一致。在 `/tmp` 临时目录完整复跑了当天全部实验（未触碰仓库冻结构建产物）：`naive-tensor.cpp` 对照组输出与 5.3 节第一段引用块逐行一致（别名＋`free(): double free detected in tcache 2`、退出码 134）；ASan 版输出与第二段引用块的行号（37／38／60／69）、24 字节 region、退出码 1 逐项一致；动态链接 libasan 确实报 "ASan runtime does not come first in initial library list"，`-static-libasan` 的说法属实；`-DUSE_UNIQUE_PTR` 版与 `bugs/err_by_value.cpp` 的编译失败输出（含 `unique_ptr.h:689` 错误链、`err_by_value.cpp:20:33`）逐行一致；mini-tensor Debug 与 ASan 两种构建 `ctest` 全绿（`all 53 assertions passed`＋`all 12 assertions passed`，ASan 用时恰好 3.27＋3.27＝6.53 秒、LeakSanitizer 零报告）；5.4 实验一（去掉拷贝行）复现退出码 0。计划引用（第 8／9／57／59／60／78／99～101 天）、第 6 天作业签名、第 2～6 天交叉引用（第 5 天错误二／三、第 6 天 3.3 节）与三张已引用 SVG 的数值、图注均已核对。以下按严重程度分级。

## 【错误】

#### 1. 图 2 走查第 4 条：`Tensor(TensorDesc, Buffer)` 的“先检查、后转移”并不构成强异常保证
- **原文**：“构造（先检查 `need ≤ have`、后转移，强异常保证）”
- **依据**：强异常保证要求“操作要么完全成功、要么如同从没发生过”。但该构造函数的两个参数**按值**传入，按值形参在**调用边界**就完成初始化：`Buffer` 的拷贝被删除，具名对象只能 `std::move` 传入——构造函数体（以及 `check_fit`）还没开始执行，调用方的 `Buffer` 就已经被搬空。本机用当天仓库代码实测（临时目录）：`Buffer buf(24); TensorDesc d({2,3}, Float32, {5,1}); try { Tensor bad(std::move(d), std::move(buf)); } catch(...)` 抛出 `invalid_argument` 后，`buf.empty()` 为 **1**、`d.rank()` 为 **0**——调用方可见状态已经改变，“如同从没发生过”不成立。再把构造函数临时改成“先 move 进成员、再 check_fit”重跑，调用方观察到的结果（`buf.empty()==1`、`d.rank()==0`、不泄漏、`*this` 从未构造完成）与正式版**逐项相同**——两种函数体顺序对调用方没有可观察差别。“先检查后转移”的真实收益是别的：检查抛异常时**形参**还完好（错误信息能打印出 `shape=(2,3) strides=(5,1)`，两种顺序实测都能打印）、成员从未碰过资源。该论断源自第 6 天 3.3 节，第 6 天技术校对报告【错误】1 已用同型实验指出同一问题，本日图 2 走查第 4 条把它原样重复。要真正拿到强保证，签名应改为引用（如 `Tensor(const TensorDesc&, const Buffer&)`，校验通过后再转移进成员）。
- **置信度**：高（按值形参的初始化时序是 C++ 标准规定；结论经本机对当天仓库代码的双版本对照实验验证，实验在临时目录运行、未改动仓库文件）。

## 【存疑】
- 无。

## 【建议】

#### 1. `ctest --test-dir` 需要 CMake ≥ 3.20，与前置准备声明的“CMake ≥ 3.16”不匹配
- **原文**：“ctest --test-dir build --output-on-failure”
- **依据**：`--test-dir` 是 CMake 3.20 才引入的 ctest 选项，本日 5.3 节两处验收命令都在用它；而前置准备写的是“构建环境同前六天（CMake ≥ 3.16、Ninja、g++ 或 clang++）”，`CMakeLists.txt` 也写着 `cmake_minimum_required(VERSION 3.16)`。在满足声明下限的 3.16～3.19 环境里，`cmake` 配置与构建能成功、`ctest --test-dir` 会因未知参数失败，初学者会卡在验收第一步。建议注明运行命令需要 CMake ≥ 3.20，或补一句 `cd build && ctest` 的等价写法（与第 6 天技术校对报告建议 1 同源）。
- **置信度**：高（已核对 CMake 官方 3.20 发行说明“ctest(1) gained a --test-dir option to specify the directory in which to look for tests”；本机仅装有 3.20.5、无法用 3.16 实测，但选项引入版本有官方文档佐证）。

#### 2. “ASan 双栈报告”少算了一张栈：实际报告包含分配＋两次释放共三组栈回溯
- **原文**：“退出码 134／ASan 双栈报告／编译期拒绝”
- **依据**：本机复跑 ASan 版，报告实际包含三组栈回溯——“attempting double-free”（第二次释放，`a` 的析构，帧到 `naive-tensor.cpp:60`）、“freed by thread T0 here”（第一次释放，`b` 的析构，帧到 `:69`）、“previously allocated by thread T0 here”（`NaiveTensor(unsigned long)` 的 `new float[6]`，帧到 `:37`）；5.3 节自己引用的输出和第 9 节“ASan 给出分配／两次释放的完整解剖”也都显示三组。“双栈”若解读为“两次释放的两张栈”尚可自圆，但初读容易理解成“报告共两组栈回溯”。建议改成“三段栈回溯”或“分配＋两次释放的三张栈”。
- **置信度**：高（三组栈的事实经本机复现核对；“双栈”是否为刻意缩写存在解释空间，故列为建议）。

#### 3. ASan 输出的省略说明“前五行与上面相同”实为前六行
- **原文**：“……（前五行与上面相同，指针为 0xffff9b000b80）……”
- **依据**：本机复跑 ASan 版，报错之前打印了 6 行——创建 a／`a.data()`／拷出 b／指针同一块／执行 `b.data()[0] = 100` 之后／`main 结束：b 先析构、a 后析构……`——与 5.3 节第一段输出逐行相同（仅指针值不同）；“前五行”漏数了“main 结束”这一行。计数改成“前六行”即可与真实输出对上。
- **置信度**：高（复现输出逐行清点）。

#### 4. 5.3 节对第一段输出的行数概括“前四行是别名、最后一行是 double free”不准确
- **原文**：“两个死法先后兑现：前四行是**别名**——两个指针同一地址，改 `b` 变 `a`；最后一行是 **double free**——glibc 的 tcache 检测到重复释放，`SIGABRT`，退出码 134。”
- **依据**：引用块共 9 行：别名证据在第 2～5 行（两行地址逐字相同在中间，“改 `b` 变 `a`”是第 5 行），第 1 行是创建信息；double free 消息在第 7 行，其后还有“Aborted (core dumped)”和“exit code: 134”两行，“最后一行”实际是退出码行。“前四行”应说“前五行”（或第 2～5 行）、“最后一行”应说“倒数第三行”。仅影响与紧邻引用块的对照阅读，不影响技术结论。
- **置信度**：高（对引用块逐行清点，且本机复现的输出与引用块一致）。

#### 5. 错误三代码片段的注释“编译器在这一行拒绝”与真实报错位置不符
- **原文**：“Tensor by_value_add(Tensor a, Tensor b) {   // ← 编译器在这一行拒绝”
- **依据**：按第 6 节给出的命令实测（g++ 9.4.0），第一条 `error:` 出现在**调用点** `err_by_value.cpp:20:33`（`Tensor c = by_value_add(a, b);` 处——按值形参要从左值 `a`、`b` 拷贝初始化）；函数签名行（第 13 行）只出现在其后的 note（“initializing argument 1 of ...”）里。README 自己的“定位”文字说的是对的（“第一次犯错的调用点在 `err_by_value.cpp:20`……但病根在函数签名那一行”），但片段内的行尾注释会把读者引到签名行去找报错。建议把注释改成“← 病根在这一行（报错出现在调用点）”之类的说法。
- **置信度**：高（编译命令与输出均在本机复现）。

#### 6. “整体复制过来”与 day-006 工程的实际内容有出入：三个 bugs 反面教材没有带过来
- **原文**：“第 6 天工程的延续（整体复制过来）＋ 今天补的 add”
- **依据**：与 `tutorials/week-001/day-006/examples/mini-tensor` 逐文件 diff：src／tests 及两份 `CMakeLists.txt` 确实原样，但 day-006 的 `bugs/err_bad_desc.cpp`、`bugs/err_count.cpp`、`bugs/err_moved_from.cpp`（以及 `mini-tensor/README.md`、`build/`）都没有复制过来——day-007 的 `bugs/` 里只有 `err_by_value.cpp`（5.1 的目录树如实反映了这一点，树本身没有错）。从第 6 天一路做下来的读者若按“整体复制”处理自己的工程，`bugs/` 会多出三个文件、与 5.1 的树对不上。建议把括号改成“src／tests／CMakeLists 复制过来（第 6 天的三个 bugs 反面教材未带）”之类。
- **置信度**：高（diff 可复现）。
