#!/usr/bin/env python3
"""第 164 天：动态 Shape 与 Runtime 的两份标准回答。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

ANSWERS = {
"动态 Shape 难在哪里": """## 结论
  不只是把常量改成变量——是一串涟漪（六件事）＋三件配套；动态化的
  完整成本是「整个 Runtime 层」。
## 机制
  六件事：签名 ?占位→shape 读回→动态 alloc→循环边界→验证参数化→
  性能语义收缩（优化空间缩小——实测 fmul 18→2）。
  三件套：特化（拿性能 fmul 2→18）＋回退（兜正确）＋池化（管内存）。
## 项目例子（本仓库实测）
  D128 的动态签名：同一语义 icmp slt 常量4 vs SSA%29——一份 .ll 吃
  三种 shape（24.5/6.0/58.0 全对）；但 O2 优化空间收缩（fmul 18→2）；
  D129 特化补回（2→18）；D133 的标准回答沉淀。
## 限制
  动态版的头部开销 +9%（extractvalue 17→23）；优化保守——两全靠
  特化＋缓存＋回退三件套（PyTorch 2.x 同思路）。
""",
"哪些决策应放到运行期": """## 结论
  没有标准答案只有显式选择——每个决策点在光谱上（COMPILE 固化/
  RUNTIME 动态/协作），判据是性能/灵活性权衡＋配套成本。
## 机制
  类比：预制菜（静态·快但菜单死）vs 现炒（动态·灵活但慢）vs 中央
  厨房（JIT 特化＋缓存＋回退——两全但要建整套体系）。
## 项目例子（本仓库实测）
  D127 的 11 决策点审计：minic 是纯静态派（COMPILE×4）＋一周翻转
  五格（Shape→RUNTIME、Kernel→SPLIT、释放→RUNTIME、恢复→RUNTIME、
  缓存→雏形）；每格翻转配实测（D128 的三种 shape/D129 的 2→18/
  D131 的 99% 复用）。
## 限制
  每格翻转有涟漪与配套成本（D133 的标准回答）；「保持」也是决策
  （教学取舍的显式记录——3 格不动的理由）。
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, (q, a) in enumerate(ANSWERS.items()):
        open(os.path.join(OUT, f"answer-{i}.md"), "w").write(f"# {q}\\n\\n{a}")
        for seg in ("## 结论", "## 机制", "## 项目例子", "## 限制"):
            assert seg in a
    print("两份标准回答：六件事＋三件套｜11 决策点＋翻转五格")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
