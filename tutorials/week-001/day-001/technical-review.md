# 第 1 天技术校对报告

审阅环境与教程第 5 节声明环境完全一致：Linux aarch64（Ubuntu 20.04.5）· g++ 9.4.0 · CMake 3.20.5 · Ninja 1.10.0。configure、构建、运行、ctest、两个对照实验、第 6 节三个常见错误和 3.1 节手工 g++ 命令均在临时目录用同版本工具链逐条复现；CMake 行为另查证 cmake.org 官方 3.20 文档与 Release Notes，不凭印象下结论。代码块与 examples/compiler-playground/ 下的仓库文件逐字符比对，全部一致。

## 【错误】
#### 1. 5.3 节对 6 个构建步骤的分类计数与它自己贴出的输出不符
- **原文**：“真实输出——6 个步骤正好对应图 2：2 个编译、1 个打包、3 个链接（测试和主程序都链接 `libgreet.a`）：”
- **依据**：紧接着贴出的输出实际包含 3 行 `Building CXX object`（greet.cpp.o、test_greet.cpp.o、main.cpp.o）、1 行 ar 归档（`Linking CXX static library`）和 2 行可执行文件链接（`Linking CXX executable`），正确说法是“3 个编译、1 个打包、2 个链接”。我在同版本工具链上复现构建，同样得到 3+1+2。原文把 test_greet.cpp 的编译漏数了，又多算了一个链接：若把 [2/6] 归档行按 ninja 日志前缀算作“链接”，“1 个打包”就与它重复计数，2+1+3 也不再对应 6 个互不重叠的步骤。括注“测试和主程序都链接 `libgreet.a`”本身正确。另注：[5/6]/[6/6] 两条链接的先后顺序在两次运行间可能互换（ninja 就绪边的调度顺序），属正常现象，不算错误。
- **置信度**：高（教程自贴输出逐行可数，本地复现一致）。

#### 2. 5.1 节展示的 apt 安装命令装不出能执行 5.3 节命令的 CMake 版本
- **原文**：“安装依赖（Ubuntu/Debian；我在本机实际执行了第二条）：”
- **依据**：Ubuntu 20.04（教程第 5 节声明且本机确认的平台）apt 源提供的 cmake 是 3.16.3（`apt-cache policy cmake`：Candidate 3.16.3-1ubuntu1.20.04.1），而 5.3、5.4 和工程 README 使用的 `ctest --test-dir` 是 CMake 3.20 新增选项（官方 3.20 Release Notes CTest 节原文：“ctest(1) gained a --test-dir option to specify the directory in which to look for tests”）。读者照本节唯一展示的 apt 命令装好依赖后，到 5.3 节 `ctest --test-dir build` 会因未知参数直接失败。教程环境的 CMake 3.20.5 实际来自手工安装（本机为 /opt/buildtools/cmake-3.20.5-linux-aarch64，非 apt 包），“我在本机实际执行了第二条”所指的“第二条”命令在正文中并不存在，读者无从选择。建议补出第二种安装途径（pip／Kitware APT 源／官方二进制）或注明 CMake ≥ 3.20 要求，并给出 `cd build && ctest` 兼容写法。
- **置信度**：高（apt 候选版本本机核实，--test-dir 引入版本查证官方 Release Notes）。

#### 3. 错误三对 add_test 注册机制的表述与 CMake 实际行为相反
- **原文**：“`add_test` 只会注册到最近的祖先”
- **依据**：CMake 3.20 官方文档：enable_testing() 语义是 “Enable testing for current directory and below”，且 “should be in the source directory root because ctest expects to find a test file in the build directory root”。实际机制是 add_test 把测试命令写进**当前目录**的 CTestTestfile.cmake，由顶层 CTestTestfile.cmake 通过 `subdirs("tests")` 逐级**向下包含**，不存在 add_test 向祖先注册的路径。本机实验（CMake 3.20.5）：把 enable_testing() 移入 tests/CMakeLists.txt 后，build/CTestTestfile.cmake 不再生成，测试只出现在 build/tests/CTestTestfile.cmake——从 build/ 运行 ctest 报 “No tests were found!!!”，从 build/tests/ 运行却能把测试跑通，证明注册发生在 add_test 所在目录而非任何祖先。教程给出的修复动作（enable_testing() 放顶层）本身正确，需要改的只是括号里的机制解释，可改为“enable_testing() 只对当前目录及以下生效，顶层没调用它时构建根目录不会生成 CTestTestfile.cmake，ctest 从根目录收集不到测试”。
- **置信度**：中（按字面读“注册到最近的祖先”是明确错误且有实验反证；若作者本意是“最近的启用了 testing 的目录（含自身）”，方向仍说反了——是顶层测试文件向下收集，不是 add_test 向上注册）。

## 【存疑】
- 无。

## 【建议】
#### 1. 未提示 assert 会被 Release 构建的 NDEBUG 整体删除
- **原文**：“不引入外部测试框架，用 `assert` 保持零依赖”
- **依据**：assert 在定义 NDEBUG 时被预处理器删除，而 CMake 配置 `-DCMAKE_BUILD_TYPE=Release` 会自动加 -DNDEBUG。实测复现：把 greet.cpp 的返回值改错后按 Release 重建，ctest 仍显示 “100% tests passed”，测试二进制还照常打印 “all 3 greet tests passed”——断言全部消失，第 1 天“测试把关”的承诺在 Release 配置下静默失效。学习计划后续做性能实验必然切 Release，这个坑值得当天用一句话提醒（例如“跑这些 assert 测试别用 Release，或改用 EXPECT 宏风格的框架”）。
- **置信度**：高（已实验复现）。

#### 2. 必做练习的引导问题把默认预期说反了
- **原文**：“为什么不用动 `CMakeLists.txt`（或需要动哪里）”
- **依据**：练习要求让 farewell.cpp “进 greet 库”，而库的源清单写死在 src/CMakeLists.txt 的 `add_library(greet STATIC greet.cpp)` 一行；不改这一行，farewell.cpp 根本不参与编译，链接必然得到第 6 节错误一同款 undefined reference（机制已复现）。tests/ 与顶层 CMakeLists 确实无需改动。验收问题以“为什么不用动”开头，会把初学者引向“不该动”的答案，建议改成“需要动哪个 CMakeLists.txt 的哪一行、为什么另外两个不用动”。
- **置信度**：高（add_library 源清单行为明确，与已复现的错误一同机制）。

#### 3. “比较文件时间戳”的表述不完整
- **原文**：“`ninja` 读这份清单，比较文件时间戳，只重跑受影响的步骤”
- **依据**：ninja 判定重建还会比较每条规则的命令行本身。实测：源文件时间戳全部不变，仅重新 configure 修改 CMAKE_CXX_FLAGS（编译命令行变化），6 个步骤即全部重跑（[1/6]…[6/6]）。第 1 天不展开可以接受，但后续一旦改警告选项或 C++ 标准就会遇到“没改代码却全量重编”的困惑，建议补半句“（命令行变了也会重编）”。
- **置信度**：高（已实验复现）。

#### 4. 错误三的“定位”启发式覆盖不了它自己列出的第二个成因
- **原文**：“进 `build` 目录看有没有生成 `CTestTestfile.cmake`；没有就是注册环节断了”
- **依据**：错误三把“（或在它之前就 `add_subdirectory(tests)`）”列为成因，但本机实验显示这种写法下 build/CTestTestfile.cmake 照常生成（内容还含 `subdirs("tests")`），真正缺失的是 build/tests/CTestTestfile.cmake。按句面“没有生成才是断了”去排查，读者会看到文件存在却依然 No tests were found!!! 而卡住。建议补一句“再确认 build/tests/ 下有没有 CTestTestfile.cmake”。
- **置信度**：高（已实验复现）。
