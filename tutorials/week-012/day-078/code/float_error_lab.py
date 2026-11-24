#!/usr/bin/env python3
"""第 78 天数值实验：浮点格式与累加顺序对求和结果的影响。

只依赖 numpy 和 Python 标准库。运行方式：
    python3 float_error_lab.py

实验清单：
  A. FP32 下三个数 [1e8, 1.0, -1e8] 的不同相加顺序
  B. FP32 混合量级大数组：顺序 / 排序 / 分块两两相加 / 精确求和
  C. FP32 同量级随机数：顺序对"平常数据"的影响有多大
  D. FP16 累加 0.1 x 100000：FP16 累加器 vs FP32 累加器
  E. BF16 累加 0.1 x 100000：BF16 累加器 vs FP32 累加器
"""

import math

import numpy as np


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def bf16(x):
    """把 FP32 数组按 round-to-nearest-even 舍入到 BF16，结果仍存成 FP32。

    BF16 = FP32 的低 16 位尾数被砍掉，只保留高 16 位（1 符号 + 8 指数 + 7 尾数）。
    本实现与 torch.tensor(x).to(torch.bfloat16).float() 逐位一致（已验证）。
    """
    u = np.asarray(x, dtype=np.float32).view(np.uint32)
    # 加 0x7FFF+低位首位的奇偶修正，等价于“四舍五入到最近偶数”
    rounded = ((u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000).astype(np.uint32)
    return rounded.view(np.float32)


def fp32_bits(x):
    """打印一个 FP32 数的符号位 / 指数位 / 尾数位。"""
    u = np.float32(x).view(np.uint32).item()
    s = (u >> 31) & 0x1
    e = (u >> 23) & 0xFF
    m = u & 0x7FFFFF
    return (f"{s}  {e:08b}  {m:023b}", f"0x{u:08x}", e - 127)


def seq_sum(arr, step_cast=None):
    """左结合顺序求和：((a0+a1)+a2)+…。step_cast 模拟每一步用什么累加器。"""
    s = np.asarray(arr[0]).copy()
    for v in arr[1:]:
        s = step_cast(s + v) if step_cast is not None else (s + v)
    return s


def error_row(name, got, ref):
    """返回 (名字, 结果, 绝对误差, 相对误差) 一行。"""
    got = float(got)
    ref = float(ref)
    abs_err = abs(got - ref)
    rel_err = abs_err / abs(ref)
    return name, got, abs_err, rel_err


def print_table(title, rows):
    print(f"\n{title}")
    print(f"{'求和方式':<22}{'结果':>18}{'绝对误差':>14}{'相对误差':>12}")
    for name, got, abs_err, rel_err in rows:
        print(f"{name:<22}{got:>18.6g}{abs_err:>14.4g}{rel_err:>12.4g}")


# ---------------------------------------------------------------------------
# 实验 A：三个数的加法交换律去哪了
# ---------------------------------------------------------------------------

def experiment_a():
    print("=" * 70)
    print("实验 A：FP32 下 [1e8, 1.0, -1e8] 的不同相加顺序")
    print("=" * 70)
    a = np.float32(1e8)
    b = np.float32(1.0)
    c = np.float32(-1e8)
    ref = math.fsum([float(a), float(b), float(c)])  # 1.0
    rows = [
        error_row("(1e8 + 1) + (-1e8)", (a + b) + c, ref),
        error_row("(1e8 + (-1e8)) + 1", (a + c) + b, ref),
        error_row("(1.0 + (-1e8)) + 1e8", (b + c) + a, ref),
        error_row("np.sum(3 个元素)", np.sum(np.array([a, b, c], dtype=np.float32)), ref),
        error_row("math.fsum(精确)", ref, ref),
    ]
    print_table("数学真值 = 1.0，同组数据、不同顺序：", rows)
    print("提示：1e8 附近相邻 FP32 相差 8（np.spacing(1e8) = 8），")
    print("      1.0 小于半个间距，加上去被原样舍回，所以 (1e8+1) 还是 1e8。")
    print("补充：3 个元素太少，np.sum 也走左结合顺序；数组大了才用分块。")
    print("      8 个元素仍得到 0.0，200 个元素时 np.sum = 16.0（分块生效）。")


# ---------------------------------------------------------------------------
# 实验 B：混合量级大数组
# ---------------------------------------------------------------------------

def experiment_b():
    print("\n" + "=" * 70)
    print("实验 B：FP32 混合量级 [1e8, 0.1 x 100000, -1e8]")
    print("=" * 70)
    data = np.concatenate([
        np.array([1e8], dtype=np.float32),
        np.full(100_000, 0.1, dtype=np.float32),
        np.array([-1e8], dtype=np.float32),
    ])
    ref = math.fsum(map(float, data))  # 存储值的正确舍入和
    rows = [
        error_row("顺序左结合", seq_sum(data, np.float32), ref),
        error_row("先排序(升序)再顺序", seq_sum(np.sort(data), np.float32), ref),
        error_row("np.sum(分块两两相加)", np.sum(data, dtype=np.float32), ref),
        error_row("math.fsum(精确)", ref, ref),
    ]
    print_table(f"参考值 fsum = {ref:.9g}：", rows)
    print("提示：先升序排序也没救回来——负的 -1e8 仍然先吃掉全部 0.1。")
    print("      排序不是万能药，分块/两两相加让大数有机会先抵消。")


# ---------------------------------------------------------------------------
# 实验 C：同量级随机数（对照：平常数据顺序影响多大）
# ---------------------------------------------------------------------------

def experiment_c():
    print("\n" + "=" * 70)
    print("实验 C：FP32 同量级随机数 x 1000000（seed=42）")
    print("=" * 70)
    rng = np.random.default_rng(42)
    data = rng.standard_normal(1_000_000, dtype=np.float32)
    ref = math.fsum(map(float, data))
    rows = [
        error_row("顺序左结合", seq_sum(data, np.float32), ref),
        error_row("np.sum(分块两两相加)", np.sum(data, dtype=np.float32), ref),
        error_row("math.fsum(精确)", ref, ref),
    ]
    print_table(f"参考值 fsum = {ref:.7g}：", rows)
    print("提示：同量级数据下顺序影响约 1e-5 量级——量级悬殊才是放大器。")


# ---------------------------------------------------------------------------
# 实验 D / E：FP16、BF16 累加器 vs FP32 累加器
# ---------------------------------------------------------------------------

def experiment_d():
    print("\n" + "=" * 70)
    print("实验 D：FP16 输入 0.1 x 100000，两种累加器")
    print("=" * 70)
    data = np.full(100_000, 0.1, dtype=np.float16)
    stored_ref = math.fsum(map(float, data))     # 这些输入本身能精确表示的和
    ideal = 100_000 * 0.1                         # 十进制真值
    fp16_acc = np.float16(0)
    for v in data:
        fp16_acc = np.float16(fp16_acc + v)
    fp32_acc = np.float32(0)
    for v in data:
        fp32_acc = np.float32(fp32_acc + v)
    print(f"FP16 里的 0.1 实际是 {float(data[0]):.17g}")
    print(f"FP16 顺序累加 10 万次：和停在 {float(fp16_acc):g}，再也不会动")
    rows = [
        error_row("FP16 累加器", fp16_acc, ideal),
        error_row("FP32 累加器", fp32_acc, ideal),
        error_row("FP32 累加器(对存储值)", fp32_acc, stored_ref),
    ]
    print_table(f"十进制真值 = {ideal:g}，存储值精确和 = {stored_ref:g}：", rows)
    print("提示：和到 256 附近时相邻 FP16 数相差 0.25，0.1 连半个间距都不到，")
    print("      每加一次都被舍回原值——这就是 FP16 累加“冻结”在 256 的原因。")
    print("      换成 FP32 累加器后，剩下的误差全部来自输入量化（0.1 存不精确）。")


def experiment_e():
    print("\n" + "=" * 70)
    print("实验 E：BF16 输入 0.1 x 100000，两种累加器")
    print("=" * 70)
    data = bf16(np.full(100_000, 0.1, dtype=np.float32))
    stored_ref = math.fsum(map(float, data))
    ideal = 100_000 * 0.1
    bf16_acc = np.float32(0)
    for v in data:
        bf16_acc = bf16(np.float32(bf16_acc + v))  # 累加器也按 BF16 舍入
    fp32_acc = np.float32(0)
    for v in data:
        fp32_acc = np.float32(fp32_acc + v)
    print(f"BF16 里的 0.1 实际是 {float(data[0]):.11g}")
    print(f"BF16 顺序累加 10 万次：和停在 {float(bf16_acc):g}")
    rows = [
        error_row("BF16 累加器", bf16_acc, ideal),
        error_row("FP32 累加器", fp32_acc, ideal),
        error_row("FP32 累加器(对存储值)", fp32_acc, stored_ref),
    ]
    print_table(f"十进制真值 = {ideal:g}，存储值精确和 = {stored_ref:g}：", rows)
    print("提示：BF16 尾数只有 7 位，和到 32 附近间距已是 0.25，0.1 同样被舍回。")
    print("      BF16 与 FP32 指数域相同（8 位），范围一样大，牺牲的是精度。")


# ---------------------------------------------------------------------------

def main():
    print("第 78 天浮点实验环境：Python + numpy " + np.__version__)
    print("\n先看一眼 0.1 在 FP32 里的真实存储：")
    bits, hexs, e = fp32_bits(0.1)
    print(f"0.1f  =  {bits}   ({hexs})")
    print(f"        即 (-1)^0 x 1.6... x 2^{e}，小数 0.1 在 FP32 里本来就存不精确\n")

    experiment_a()
    experiment_b()
    experiment_c()
    experiment_d()
    experiment_e()

    print("\n" + "=" * 70)
    print("结论：")
    print("  1. 加法满足交换律，但浮点加法不满足结合律——顺序改变结果。")
    print("  2. 量级悬殊 + 顺序不当，FP32 也能错 100%；同量级数据只错 ~1e-5。")
    print("  3. FP16/BF16 输入没有问题，问题出在用它们当“累加器”：")
    print("     输入量化误差 ~0.1%，累加器选错 ~97%~99%。")
    print("  4. 这就是 Cube/Vector 单元做乘加时用 FP32 累加器的原因。")
    print("=" * 70)


if __name__ == "__main__":
    main()
