#!/usr/bin/env python3
"""第 15 周测试（D99~D104 六天，12 题，自动判分）。

覆盖：Tensor 生命周期（D99）、缓冲区复用（D100）、片上空间估算（D101）、
数据搬运与依赖（D102）、双缓冲与流水线（D103）、资源约束过滤（D104）。
全部答案的数字均来自本周 tutorials/day-099 ~ day-104 的真实运行记录。

用法：
  python3 weekly_test.py            # 交互答题（stdin 逐题输入）
  python3 weekly_test.py --demo     # 播放一份故意含 2 处错误的样例答卷
  python3 weekly_test.py --explain  # 打印参考答案与讲解
"""

from __future__ import annotations

import argparse
import sys

# 每题：(出处, 题干, 选项列表或 None(数值题), 正确答案索引/数值, 讲解)
QUESTIONS = [
    ("D99",
     "闭区间 [def, last_use] 的活跃区间里，图输入张量 x（只被第 1 个算子读）"
     "的定义点算几？",
     ["0（图前就算存活）", "1（被读的那一步）", "2（图结束）", "不算存活"],
     0,
     "图输入在步骤 0 就存在：x 的区间是 [0, 1]——出生不等你用（D99 main-first.txt）。"),
    ("D99",
     "D99 同一张 4 算子图，『主干优先』和『捷径优先』两种执行顺序的峰值分别是 "
     "320 / 416 元素。两种顺序改变的是张量的什么？",
     ["张量本身的形状", "张量的活跃区间（谁和谁同时活着）", "算子的计算结果",
      "参数的常驻大小"],
     1,
     "执行顺序一变，def/last_use 全变：捷径优先让 s 活得久，峰值从 320 涨到 416。"),
    ("D100",
     "两个张量想共享同一块片外缓冲区，下列哪个条件『不是』必须的？",
     ["活跃区间不重叠", "偏移按对齐网格取整", "别名组内偏移一致", "形状必须完全相同"],
     3,
     "形状不必相同——首次适应只要放得下就行（D100：128 B 的 x 住进 512 B 房间的尾部）。"),
    ("D100",
     "D100 三种放置策略 H1 按定义点 / H2 按尺寸降序 / H3 按最后使用点，"
     "工作区分别是多少（峰值下界 1280 B）？",
     ["1920 / 1408 / 1280", "1280 / 1408 / 1920", "1408 / 1280 / 1920",
      "1920 / 1280 / 1408"],
     0,
     "H3『早退房优先』把 1280 B 摊到理论下界：早死的张量先安排，后来的能蹭上房间。"),
    ("D101",
     "双缓冲把哪些片上项 ×2？",
     ["全部五项都 ×2", "只把 DMA 流入项（A tile / B tile）×2",
      "只把 C tile ×2", "只把 bias ×2"],
     1,
     "A/B 是搬运工反复搬进来的（要乒乓），C 是常驻累加器、bias 是常驻切片，都恒 ×1。"),
    ("D101",
     "64³ fp32·double +bias 的片上合计是多少（对齐 32 B，预算 256 KiB）？",
     ["49,408 B", "82,176 B", "65,792 B", "98,304 B"],
     1,
     "A 16,384×2 + B 16,384×2 + C 16,384 + bias 256 = 82,176 B，利用率 31.3%。"),
    ("D102",
     "同步点 S2 的依赖类型和含义是？",
     ["RAW：计算等搬运完工", "WAR：覆盖槽位前，等上一批读者算完",
      "RAW：写回等累加完工", "WAR：写回完工后 C 槽才许复用"],
     1,
     "S1=搬运→计算（RAW），S2=计算→搬运（WAR），S3=计算→写回（RAW），S4=写回→复用（WAR）。"),
    ("D102",
     "单缓冲下块 (0,0) 总耗时 16.5078 µs，其中 8×(Load 1 + Compute 1)=16 µs 的主体是什么？",
     ["搬运和计算各干各的（重叠）", "轮流值班：搬一圈、算一圈，完全串行",
      "DMA 引擎故障", "写回占了 16 µs"],
     1,
     "单缓冲一个槽：算完才能搬下一圈——448 µs 的 S2 白等就是这么攒出来的。"),
    ("D103",
     "跨块预取流水线的内核总时长 545.5 µs，距理想重叠下界（max(DMA忙,计算忙)=544.5 µs）还差多少？",
     ["33.5 µs", "1 µs", "64 µs", "0.5 µs"],
     1,
     "只差最后一块写回前的 1 µs 排空：全 kernel 唯一一趟无货可搬。"),
    ("D103",
     "双缓冲之后，关于同步点 S2 哪句是对的？",
     ["S2 被彻底消灭，不再存在", "S2 的依赖还在，但不再让 DMA 白等"
      "（448 µs → 0）",
      "S2 从 RAW 变成了 WAR", "S2 只在 k=0 出现"],
     1,
     "距离从 1 拉到 2：S2 还有 510 条边，只是全部被流水线内部消化。"),
    ("D104",
     "过滤器遇到 dtype_in=\"fp16x\"（不在支持表里）会怎么做（fail-closed）？",
     ["猜成最接近的 fp16 继续编译", "自动四舍五入到 fp32",
      "拒绝并返回 BAD_PARAM，消息里列出全部可选值", "静默跳过这个候选"],
     2,
     "不认识的输入一律拒绝、绝不猜默认值——错误越早停下，离第一现场越近。"),
    ("D104",
     "128³ fp32·double 被拒（328,192 B，超 66,048 B）。三条出路里哪条『省的空间最多』？",
     ["退单缓冲（197,120 B）", "降 dtype 到 bf16（197,120 B）",
      "缩 tile 到 64³（82,176 B）", "三条出路省得一样多"],
     2,
     "缩 tile 剩 82,176 B 最宽裕——但代价轴是空间：片上复用变差，HBM 流量上升。"),
]

# 样例答卷：第 3、8 题故意答错，用于演示判分（--demo）
DEMO_ANSWERS = [0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 2, 2]


def run(answers=None, explain=False):
    out = []
    correct = 0
    out.append("=" * 74)
    out.append("第 15 周测试：D99 生命周期 → D104 资源过滤（共 12 题）")
    out.append("=" * 74)
    for i, (day, stem, opts, ans, note) in enumerate(QUESTIONS):
        out.append(f"\n第 {i + 1:2d} 题 [{day}]  {stem}")
        if opts:
            for j, o in enumerate(opts):
                out.append(f"    {'ABCD'[j]}) {o}")
        else:
            out.append("    （数值题，直接输入数字）")
        if explain:
            label = f"{'ABCD'[ans]}" if opts else str(ans)
            out.append(f"    参考答案：{label}")
            out.append(f"    讲解：{note}")
            continue
        given = answers[i] if answers is not None else None
        if given is None:
            while True:
                line = input("你的答案：").strip().upper()
                if opts:
                    if line and line[0] in "ABCD":
                        given = "ABCD".index(line[0])
                        break
                else:
                    try:
                        given = float(line)
                        break
                    except ValueError:
                        pass
                print("  请输入 A/B/C/D 或数字。")
        label = f"{'ABCD'[ans]}" if opts else str(ans)
        given_label = f"{'ABCD'[given]}" if opts else str(given)
        ok = given == ans
        correct += ok
        out.append(f"    你的答案：{given_label}   "
                   f"{'✓ 正确' if ok else f'✗ 错误，正确是 {label}'}")
        if not ok:
            out.append(f"    讲解：{note}")
    if not explain:
        out.append("\n" + "-" * 74)
        out.append(f"得分：{correct}/12",)
        if correct == 12:
            out.append("评价：全对——生命周期、复用、容量、搬运、流水线、闸门六关全通，"
                       "第 15 周闭环。")
        elif correct >= 9:
            out.append("评价：主线在手。错题翻对应日期的 outputs/ 复核一遍数字。")
        else:
            out.append("评价：建议按错题出处回读 D99~D104 的 README 第 5 节再战一次。")
    print("\n".join(out))
    return correct


def main():
    ap = argparse.ArgumentParser(description="第 15 周测试")
    ap.add_argument("--demo", action="store_true", help="播放样例答卷（含 2 处错误）")
    ap.add_argument("--explain", action="store_true", help="打印参考答案与讲解")
    args = ap.parse_args()
    if args.explain:
        run(explain=True)
    elif args.demo:
        print("（--demo：播放一份故意含 2 处错误的样例答卷，演示判分）")
        run(DEMO_ANSWERS)
    else:
        run()


if __name__ == "__main__":
    main()
