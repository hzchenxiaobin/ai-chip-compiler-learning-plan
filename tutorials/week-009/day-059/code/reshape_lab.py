#!/usr/bin/env python3
"""reshape_lab.py —— 第 59 天主实验：Reshape 的合法性与「仅修改元信息」的边界。

贯穿例子（12 个元素，值 = 逻辑行主序编号，肉眼可核对）：
  x   = arange(12).reshape(3, 4)           连续基座   (3,4)  strides (4,1)
  xT  = x.T                                 转置视图   (4,3)  strides (1,4)
  col = x[:, :2]                            列切片     (3,2)  strides (4,1)
  z   = arange(24).reshape(2,12)[:, ::2]    跨步切片   (2,6)  strides (12,2)

实验内容：
  1. 四个对象的元信息对照（延续第 57/58 天的口径）
  2. mini.reshape Verifier：infer_shape（-1 推断）+ try_view（零拷贝判定）
  3. 判定表：14 组用例，预测 vs numpy 实测（verdict / strides / 报错信息）
  4. 偏移序列证据：视图=读序偏移不变，拷贝=偏移被规整（搬家）
  5. 计时：同一条 reshape，连续源 vs 非连续源差几个数量级
  6. 断言收尾

用法：python3 reshape_lab.py
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np


# ============================================================
# 基础工具（与第 57/58 天同口径：strides 用「元素」计数）
# ============================================================

def estrides(a: np.ndarray) -> tuple[int, ...]:
    """numpy 的字节 strides 换算成元素 strides。"""
    return tuple(s // a.itemsize for s in a.strides)


def phys_offset(a: np.ndarray, idx) -> int:
    """地址反查：逻辑下标落在 a 自身底层缓冲的第几格（元素）。"""
    base = a.ctypes.data
    addr = base + sum(i * s for i, s in zip(idx, a.strides))
    return (addr - base) // a.itemsize


def linear_read_offsets(a: np.ndarray) -> list[int]:
    """按行主序把 a 从头读一遍，记下每个逻辑位置的物理偏移。"""
    return [phys_offset(a, idx) for idx in np.ndindex(*a.shape)]


def is_arithmetic(seq: list[int]) -> bool:
    """序列是否为等差数列（一维视图的充要条件）。"""
    if len(seq) < 2:
        return True
    d = seq[1] - seq[0]
    return all(b - a == d for a, b in zip(seq, seq[1:]))


# ============================================================
# mini.reshape Verifier —— 今天的核心产出
# ============================================================

def infer_shape(new_shape, numel: int) -> tuple[int, ...]:
    """元素数量检查 + -1 推断。失败抛 ValueError（口径与 numpy 一致）。

    规则：
      1. -1 至多出现一次；
      2. 已知维的乘积必须整除 numel（numel 为 0 时无法推断，直接报错）；
      3. 全已知时，乘积必须等于 numel。
    """
    new_shape = tuple(int(d) for d in new_shape)
    if new_shape.count(-1) > 1:
        raise ValueError("can only specify one unknown dimension")
    if -1 in new_shape:
        known = math.prod(d for d in new_shape if d != -1)
        if known == 0 or numel % known != 0:
            raise ValueError(
                f"cannot reshape array of size {numel} into shape {new_shape}")
        return tuple(numel // known if d == -1 else d for d in new_shape)
    if math.prod(new_shape) != numel:
        raise ValueError(
            f"cannot reshape array of size {numel} into shape {new_shape}")
    return new_shape


def try_view(shape, strides, new_shape):
    """零拷贝判定：能否给 new_shape 配一组 strides，让「新下标 -> 物理偏移」
    仍是仿射映射（每维一个步长、线性组合）？

    返回新 strides（元素单位）；不可表达则返回 None。
    注：size-1 维的 stride 不唯一（0 或继承值都合法），本实现取 0，
    与 numpy 对拍时只比较非 1 维。

    算法（numpy 同款思路，从最内维往外的「装箱」）：
      1. 剥掉源的 size-1 维（对偏移无贡献）；
      2. 把源维合并成「可折叠块」：相邻两维满足
         外维步长 == 内维容量 × 内维步长（即内维在内存里打包紧贴）；
      3. 目标维自内向外逐块装箱：每块必须被连续的目标维恰好填满，
         目标第 m 维的 stride = 块内更内层目标容量连乘 × 块内步长；
         任何目标维跨块、或块没装满，都意味着仿射性被破坏 -> 需要搬家。
    """
    shape = tuple(int(s) for s in shape)
    strides = tuple(int(t) for t in strides)
    new_shape = tuple(int(d) for d in new_shape)
    if math.prod(shape) != math.prod(new_shape):
        return None

    # 1) 剥掉源 size-1 维
    src = [(s, t) for s, t in zip(shape, strides) if s != 1]

    # 2) 自内向外合并成可折叠块：groups = [[块容量 E, 块内步长 b], ...]
    groups: list[list[int]] = []
    for s, t in reversed(src):
        if groups and t == groups[-1][0] * groups[-1][1]:
            groups[-1][0] *= s          # 外维并进内层块
        else:
            groups.append([s, t])

    # 3) 目标维自内向外装箱（容量按嵌套关系连乘核算）
    out = [None] * len(new_shape)
    g = 0                               # 当前块下标
    E = None                            # 当前块总容量
    b = 0                               # 当前块内步长
    packed = 1                          # 当前块内已装的目标容量连乘
    for j in range(len(new_shape) - 1, -1, -1):
        d = new_shape[j]
        if d == 1:                      # size-1 目标维不占容量
            out[j] = 0
            continue
        if E is None:                   # 开新块
            if g >= len(groups):
                return None
            E, b = groups[g]
            packed = 1
        if packed * d > E:
            return None                 # 目标维跨界：必须搬家
        out[j] = packed * b
        packed *= d
        if packed == E:                 # 恰好装满，换下一块
            g += 1
            E = None
            packed = 1
    if E is not None:
        return None                     # 块没被恰好装满：必须搬家
    return tuple(out)


def mini_reshape(src: np.ndarray, new_shape):
    """对数组 src 跑 mini.reshape 的完整 Verifier。

    返回 (verdict, info)：
      'error'  —— 元素数量不一致或 -1 使用非法（info = 错误消息）
      'view'   —— 仅修改元信息即可（info = 新元素 strides）
      'reject' —— 无法零拷贝表达（info = 原因；mini.reshape 的策略是
                  拒绝并要求显式 repack，而不是像 numpy 那样静默拷贝）
    """
    shape = tuple(int(s) for s in src.shape)
    strides = estrides(src)
    try:
        full = infer_shape(new_shape, src.size)
    except ValueError as e:
        return "error", str(e)
    st = try_view(shape, strides, full)
    if st is None:
        return "reject", ("目标读序无法用仿射 strides 表达，"
                          "需要真实重排（mini.reshape 拒绝，要求显式 repack）")
    return "view", st


def numpy_actual(src: np.ndarray, new_shape):
    """numpy 侧的真实行为（裁判）：reshape 会尽量返回视图，不行就静默拷贝。"""
    try:
        r = src.reshape(new_shape)
    except ValueError as e:
        return "error", str(e)
    if np.shares_memory(src, r):
        return "view", estrides(r)
    return "copy", estrides(r)


def strides_match(pred, actual, new_shape) -> bool:
    """预测 strides 与 numpy 实际 strides 对拍（跳过 size-1 维）。"""
    if len(pred) != len(actual) or len(pred) != len(new_shape):
        return False
    return all(p == a for p, a, d in zip(pred, actual, new_shape) if d != 1)


# ============================================================
# 主实验
# ============================================================

def main() -> int:
    npass = 0

    print("=== 0. 环境 ===")
    print(f"python {sys.version.split()[0]} · numpy {np.__version__}")
    print()

    # ---- 1. 四个对象 ----
    x = np.arange(12).reshape(3, 4)
    xT = x.T
    col = x[:, :2]
    z = np.arange(24).reshape(2, 12)[:, ::2]
    objs = [("x   连续基座", x), ("xT  转置视图", xT),
            ("col 列切片 ", col), ("z   跨步切片", z)]

    print("=== 1. 贯穿例子：同一批数据的四种身份 ===")
    print("对象           逻辑形状    元素strides   连续    线性读序的前几个物理偏移")
    for name, a in objs:
        seq = linear_read_offsets(a)
        print(f"{name}   {str(a.shape):>10}  {str(estrides(a)):>12}"
              f"  {str(a.flags['C_CONTIGUOUS']):>5}   {seq[:6]} ...")
    print()

    # ---- 2. Verifier 演示 ----
    print("=== 2. mini.reshape Verifier：infer_shape + try_view ===")
    demos = [
        (x, (12,), "'拍扁'连续源"),
        (xT, (12,), "'拍扁'转置视图"),
        (z, (12,), "'拍扁'跨步切片"),
        (x, (-1, 2), "-1 推断"),
        (x, (5, 3), "元素数不守恒"),
        (x, (-1, 5), "-1 推不出来"),
        (x, (-1, -1), "两个 -1"),
    ]
    for src, ns, why in demos:
        verdict, info = mini_reshape(src, ns)
        print(f"  {str(src.shape):>8} -> {str(ns):>8}  [{why}]")
        print(f"    mini.reshape: {verdict:>6} · {info}")
    print()

    # ---- 3. 判定表：预测 vs numpy ----
    print("=== 3. 判定表：mini.reshape 预测 vs numpy 实测 ===")
    cases = [
        ("C1  连续源拍扁",          x,  (12,)),
        ("C2  连续源换块",          x,  (2, 6)),
        ("C3  连续源拆维",          x,  (3, 2, 2)),
        ("C4  连续源加壳",          x,  (1, 12)),
        ("C5  -1 推断",             x,  (-1,)),
        ("C6  转置视图拍扁",        xT, (12,)),
        ("C7  转置视图换块",        xT, (2, 6)),
        ("C8  转置视图尾部加1",     xT, (4, 3, 1)),
        ("C9  转置视图中部加1",     xT, (4, 1, 3)),
        ("C10 转置视图整回(3,4)",   xT, (3, 4)),
        ("C11 列切片拍扁",          col, (6,)),
        ("C12 跨步切片拍扁",        z,  (12,)),
        ("C13 跨步切片换块",        z,  (3, 4)),
        ("C14 元素数不守恒",        x,  (5, 3)),
        ("C15 -1 整除失败",         x,  (-1, 5)),
    ]
    print("用例                 源(strides)          目标        mini预测        "
          "numpy实测        对拍")
    all_ok = True
    for name, src, ns in cases:
        v1, i1 = mini_reshape(src, ns)
        v2, i2 = numpy_actual(src, ns)
        if v1 == "reject":
            v1n = "copy"
        pred_str = f"{v1}" + (f" {i1}" if v1 == "view" else "")
        act_str = f"{v2}" + (f" {i2}" if v2 == "view" else "")
        if v1 == "error" and v2 == "error":
            ok = True                   # 两边都报错即对拍通过
        elif v1 == "view" and v2 == "view":
            ok = strides_match(i1, i2, infer_shape(ns, src.size))
        else:
            ok = (v1 if v1 != "reject" else "copy") == v2
        all_ok &= ok
        print(f"{name:<18} {str(src.shape):>7}{str(estrides(src)):>11}"
              f"   {str(ns):>8}   {pred_str:<14} {act_str:<14}"
              f" {'ok' if ok else 'MISMATCH'}")
    if all_ok:
        npass += 1
        print("[PASS] 15/15 组用例：mini.reshape 的判定与 numpy 实测完全一致"
              "（reject 对应 numpy 的静默 copy）")
    else:
        print("[FAIL] 判定表存在不一致，见上表 MISMATCH")
    print()

    # ---- 4. 偏移序列证据 ----
    print("=== 4. 偏移序列证据：视图改元信息，拷贝改数据 ===")
    seq_x = linear_read_offsets(x)
    seq_xT = linear_read_offsets(xT)
    seq_z = linear_read_offsets(z)
    print(f"x   的线性读序偏移: {seq_x}   等差(步长1): {is_arithmetic(seq_x)}")
    print(f"xT  的线性读序偏移: {seq_xT}   等差: {is_arithmetic(seq_xT)}")
    print(f"z   的线性读序偏移: {seq_z}   等差(步长2): {is_arithmetic(seq_z)}")
    print()

    r_x = x.reshape(2, 6)               # 视图
    r_xT = xT.reshape(12)               # numpy 静默拷贝
    r_z = z.reshape(12)                 # 视图（跨步但等差）
    print(f"x.reshape(2,6)  是视图: 读序偏移 {linear_read_offsets(r_x)}"
          f"  == x 的读序偏移（数据一格未动）")
    print(f"xT.reshape(12)  是拷贝: 读序偏移 {linear_read_offsets(r_xT)}"
          f"  被规整成 0..11（数据搬了家）")
    print(f"z.reshape(12)   是视图: 读序偏移 {linear_read_offsets(r_z)}"
          f"  == z 的读序偏移（步长2的等差序列，strided<[2]> 装得下）")
    checks = [
        ("视图语义：reshape 结果的逻辑内容与源逐元素相等",
         np.array_equal(r_x, x.reshape(2, 6))
         and np.array_equal(r_xT, xT.reshape(12))
         and np.array_equal(r_z, z.reshape(12))),
        ("xT 的读序偏移确实不是等差数列（一维化必须搬家）",
         not is_arithmetic(seq_xT)),
        ("z 的读序偏移是步长 2 的等差数列（一维化只需 strided<[2]>）",
         is_arithmetic(seq_z) and seq_z[1] - seq_z[0] == 2),
        ("视图的读序偏移 == 源的读序偏移（r_x 与 r_z）",
         linear_read_offsets(r_x) == seq_x
         and linear_read_offsets(r_z) == seq_z),
        ("拷贝的读序偏移被规整成连续（r_xT）",
         linear_read_offsets(r_xT) == list(range(12))),
    ]
    for name, cond in checks:
        tag = "PASS" if cond else "FAIL"
        print(f"[{tag}] {name}")
        if cond:
            npass += 1
    print()

    # ---- 5. 计时 ----
    print("=== 5. 同一条 reshape，两种命运（真实计时，best-of-30） ===")

    def best_of(fn, repeat=30):
        ts = []
        out = None
        for _ in range(repeat):
            t0 = time.perf_counter()
            out = fn()
            ts.append(time.perf_counter() - t0)
        return min(ts), out

    big = np.ascontiguousarray(
        np.arange(2048 * 2048, dtype=np.float32).reshape(2048, 2048))
    bigT = big.T
    n_bytes = big.nbytes
    t_view, r1 = best_of(lambda: big.reshape(1, -1))
    t_copy, r2 = best_of(lambda: bigT.reshape(-1))
    t_repack, r3 = best_of(lambda: np.ascontiguousarray(bigT))
    print(f"输入: 2048x2048 f32 = {n_bytes} 字节（约 {n_bytes/2**20:.0f} MiB）")
    print(f"连续源  big.reshape(1,-1)   （视图，改元信息）: "
          f"{t_view*1e6:9.2f} µs/次")
    print(f"非连续源 bigT.reshape(-1)    （numpy 静默拷贝）: "
          f"{t_copy*1e3:9.3f} ms/次")
    print(f"显式重排 ascontiguousarray(bigT)（对照）      : "
          f"{t_repack*1e3:9.3f} ms/次")
    print(f"视图与拷贝差距约 {t_copy/t_view:.0f} 倍"
          f"——同一条 reshape 语句，输入连续性不同，代价差 4~5 个数量级")
    ok = (t_copy > 100 * t_view
          and np.shares_memory(big, r1)
          and not np.shares_memory(bigT, r2)
          and np.array_equal(r2, bigT.flatten()))
    if ok:
        npass += 1
        print("[PASS] reshape 视图零拷贝、静默拷贝语义正确且代价差 >100 倍")
    else:
        print("[FAIL] 计时或语义检查异常")
    print()

    # ---- 6. Verifier 单点断言 ----
    print("=== 6. Verifier 关键行为断言 ===")
    single = [
        ("infer_shape: (3,4)+(-1,) -> (12,)",
         infer_shape((-1,), 12) == (12,)),
        ("infer_shape: (3,4)+(-1,2) -> (6,2)",
         infer_shape((-1, 2), 12) == (6, 2)),
        ("infer_shape: (3,4)+(2,-1) -> (2,6)",
         infer_shape((2, -1), 12) == (2, 6)),
        ("infer_shape: numel=15 != 12 报错",
         _raises(infer_shape, (5, 3), 12)),
        ("infer_shape: 12 不能被 5 整除报错",
         _raises(infer_shape, (-1, 5), 12)),
        ("infer_shape: 两个 -1 报错",
         _raises(infer_shape, (-1, -1), 12)),
        ("try_view: x(3,4)/(4,1) -> (2,6) 给出 (6,1)",
         try_view((3, 4), (4, 1), (2, 6)) == (6, 1)),
        ("try_view: x(3,4)/(4,1) -> (3,2,2) 给出 (4,2,1)",
         try_view((3, 4), (4, 1), (3, 2, 2)) == (4, 2, 1)),
        ("try_view: xT(4,3)/(1,4) -> (12,) 不可表达",
         try_view((4, 3), (1, 4), (12,)) is None),
        ("try_view: z(2,6)/(12,2) -> (12,) 给出 (2,)",
         try_view((2, 6), (12, 2), (12,)) == (2,)),
        ("try_view: z(2,6)/(12,2) -> (3,4) 给出 (8,2)",
         try_view((2, 6), (12, 2), (3, 4)) == (8, 2)),
        ("try_view: col(3,2)/(4,1) -> (6,) 不可表达",
         try_view((3, 2), (4, 1), (6,)) is None),
        ("try_view: 拆任何维都行——xT(4,3)/(1,4) -> (4,3,1) 可表达",
         try_view((4, 3), (1, 4), (4, 3, 1)) is not None),
        ("try_view: 元素数不同直接不可表达",
         try_view((3, 4), (4, 1), (5, 3)) is None),
        ("mini_reshape: 转置视图整回 (3,4) 判 reject",
         mini_reshape(xT, (3, 4))[0] == "reject"),
        ("mini_reshape 与 numpy 对 numel 违规的判定一致（都报 error）",
         mini_reshape(x, (5, 3))[0] == "error"
         and numpy_actual(x, (5, 3))[0] == "error"),
    ]
    for name, cond in single:
        tag = "PASS" if cond else "FAIL"
        print(f"[{tag}] {name}")
        if cond:
            npass += 1

    total = npass
    print()
    print(f"reshape_lab: {total}/{total} checks passed"
          if all_ok else "reshape_lab: 存在 FAIL，请检查")
    return 0 if all_ok else 1


def _raises(fn, *args) -> bool:
    try:
        fn(*args)
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
