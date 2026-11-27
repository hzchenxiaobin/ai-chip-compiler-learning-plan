# 第 27 天技术校对报告

## 【错误】

#### 1. order B 第 1 轮的死值清单漏了 %c0——实际 6 条死值，与同页 dce×6（14 → 8）对不上
- **原文**：“死值 %y、%w、%c2、%c3、%cm2 躺在图里——dce 在本轮第一位，此后再没人扫”
- **依据**：在临时目录用 Python 3.11.4 复跑 `code/pipeline.py` 的组件：order B（dce → cse → const-eval → simplify）第 1 轮结束的 14 条 IR 中，%c0 的唯一使用者 %a1 已被第 4 位的 algebraic-simplify 删除，%c0 无人使用——与 %y、%w、%c2、%c3、%cm2 同为死值，共 6 条（另有 %p 无人使用，但按副作用规则保留）。同页 [4] 的轮次表“第 2 轮：改动 6，语句 14 → 8（dce×6）”正是删 6 条的记录，14 − 5 ≠ 8，清单与轮次表自相矛盾；`code/pipeline.py` 第 1020 行的演示打印串与 images/03-example.svg 的 B 列“死值 %y %w %c2 %c3 %cm2 留场”是同一处漏项（%c0 的使用者 %a1 被 simplify 删除这一点，正文 3.2 节和 [4] 的“三个观察”段都已正确叙述）。
- **置信度**：高（程序化复跑 + 同页轮次表互证）

#### 2. 图 1 里程碑卡“3 个优化 Pass”与正文及同图顶部四张卡矛盾
- **原文**：“4. Pass 接口＋PassManager 调度台＋四个优化 Pass（Day 22–26，已完成）；”
- **依据**：images/01-overview.svg 底部“第一阶段（Day 1–28）收官”里程碑卡写“＋3 个优化 Pass＋组合到不动点”，而同一张图顶部四张卡列出的是 4 个优化 Pass（“Day 23/24 algebraic-simplify ＋ const-eval”与“Day 25/26 dce 反向清扫 ＋ cse 交换律合并”）；tutorials/week-004/overview.md 也写“调度台、四个优化 Pass 和不动点循环”，本篇第 9 节预告 Day 28 复盘时同样说“从分析到四个 Pass”。第一阶段实际交付 4 个优化 Pass，里程碑卡的计数应改为 4（或改为“3 个原样搬来＋今天新写的 CSE”这类不与上下文冲突的表述）。
- **置信度**：高（同一张图内部自证 + 两处正文互证）

## 【存疑】

#### 1. “与 Day 23/24/25 逐行同源”的表述过于绝对
- **原文**：“simplify/const-eval/dce 三个 Pass 的完整实现见 `code/pipeline.py`，与 Day 23/24/25 逐行同源。”
- **依据**：对 day-023/code/fold_pass.py、day-024/code/const_eval.py、day-025/code/dce.py 与本篇 code/pipeline.py 逐类 diff：algebraic-simplify 与 const-eval 的判断/动作逻辑逐行一致（仅 docstring 与注释改写）；DcePass 删掉了 Day 25 版本的 stats 记账行（visited／deleted／analysis_queries）；PassManager（正文称“原样搬来”）删掉了 log 条目中的 deps／deps_queried 字段、describe() 方法与若干打印行。改图契约（修改走方法、epoch +1、五种失败、bypass 绊线）确实未变、对图的行为相同，但“逐行同源／原样搬来”字面上不成立——读者 diff 会发现差异，可能误以为教程失实。
- **置信度**：高（diff 实测）；不影响“算法与契约一致”的实质结论

## 【建议】

#### 1. 图 1 说明把 Day 23/24 两个 Pass 合称“两个常量折叠 Pass”
- **原文**：“顶部四张卡是前 26 天的家底（图 IR＋分析、PassManager、两个常量折叠 Pass、dce＋cse），全部原样搬来”
- **依据**：algebraic-simplify 做的是恒等式消除（add(x,0)→x），在编译器术语里不属于常量折叠（const＋const 的编译期求值）；Day 24 的实现自述“const + const → 新 const——真正的常量计算（编译期求值）”，正是刻意与 Day 23 划界。合称“两个常量折叠 Pass”会削弱这组教程建立的区分，建议改为“代数化简＋常量求值”。
- **置信度**：高（术语口径）；属表述精度问题，不影响技术内容正确性

#### 2. 图 3 说明“从‘结果错误’降级成‘多跑一轮’”易误导
- **原文**：“FixpointRunner 把"坏顺序"的代价从"结果错误"降级成"多跑一轮"。”
- **依据**：本篇四个 Pass 全部保持语义（[3] 三组喂入语义对照全绿），任何顺序跑任何轮数都不会产出“结果错误”——坏顺序只跑一轮的代价是“残留冗余／未到不动点”（[4] 的 14 条残骸），不是错误结果。该措辞可能让初学者误以为 Pass 顺序影响正确性，与 [4] “顺序改变的是路径，不改变终点”的结论方向相悖；建议改成“从‘结果次优（残留冗余）’降级成‘多跑一轮’”。
- **置信度**：中（修辞层面的简化，技术事实无错，但与正文口径有张力）

#### 3. `pm.add(*self.passes)` 行的内联注释位置有误导
- **原文**：“pm.add(*self.passes)                # 每轮 run 都新建 AnalysisManager”
- **依据**：AnalysisManager 是在 `PassManager.run()` 内部新建的（code/pipeline.py 第 292 行 `self.am = AnalysisManager(graph)`），不在 `add()`；注释挂在 add 行上容易让读者以为挂载 Pass 时就建了 AM。正文 5.2 的解释（“每轮调用 `pm.run`，而 Day 22 的 `PassManager.run` 每次都新建 `AnalysisManager`”）是对的；code/pipeline.py 第 791 行的同款注释同样错位。
- **置信度**：高
