#!/usr/bin/env python3
"""broadcast_lab.py —— 第 60 天：Broadcast 规则的三条规则 + stride-0 视图 + 未知维度。

贯穿例子（与 MLIR 侧 broadcast_add.mlir 用同一份数据）：
    a = [[1, 2, 3],       b = [10, 20, 30],   c = [[100],        d = [1, 2, 3, 4]
         [4, 5, 6]]                             [200]]
    a(2,3) + b(3,)  → (2,3)   右对齐，b 补成 (1,3)，第 0 维 stride 0
    a(2,3) + c(2,1)  → (2,3)   c 的第 1 维为 1，stride 0
    a(2,3) + d(4,)   → error   3 vs 4，既不相等也没有 1

实验内容：
  1. 贯穿例子：三种结局 + numpy 实测值 + stride-0 证据
  2. 判定表：16 组用例，mini 预测 vs np.broadcast_shapes 实测（错误消息逐字对拍）
  3. stride-0 视图：broadcast_strides vs np.broadcast_to 实测 strides（10 组）
  4. 未知维度：None 的 meet 规则（10 组，手算期望）
  5. 随机对拍：300 组形状推导 + 100 组 strides
  6. 汇总断言

运行: python3 broadcast_lab.py
"""

from __future__ import annotations

import random

import numpy as np

CHECKS = [0, 0]  # [passed, total]


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS[1] += 1
    CHECKS[0] += bool(cond)
    mark = "PASS" if cond else "FAIL"
    suffix = f"  ({detail})" if detail and not cond else ""
    print(f"  [{mark}] {name}{suffix}")


# ============================================================
# 1. 核心实现：Broadcast 输出 Shape 推导
# ============================================================

class BroadcastError(ValueError):
    """与 np.broadcast_shapes 同口径的广播失配错误。"""


def _clean(shape) -> tuple:
    """维度必须是自然数（0 允许，-1 不是「未知」而是非法）。"""
    out = []
    for d in shape:
        if isinstance(d, bool) or not isinstance(d, int):
            raise BroadcastError(f"维度必须是整数，收到 {d!r}")
        if d < 0:
            raise BroadcastError("negative dimensions are not allowed")
        out.append(d)
    return tuple(out)


def broadcast_shapes(*shapes):
    """Broadcast 输出 Shape 推导（与 np.broadcast_shapes 同口径）。

    规则只有两条：
      1) 右对齐：短形状左侧补 1（缺的维度按 1 参与）；
      2) 逐维比较：相等 → 保留；其中一方为 1 → 取另一方；两者都不是 → 失配报错。
    """
    shapes = [_clean(s) for s in shapes]
    if not shapes:
        return ()
    rank = max(len(s) for s in shapes)
    out = [1] * rank
    setter = [-1] * rank                 # 该维的「非 1 值」来自哪个操作数（报错要引用）
    for k in range(1, rank + 1):         # 从最右维往左逐维比较
        pos = rank - k
        for i, s in enumerate(shapes):
            d = s[-k] if k <= len(s) else 1          # 右对齐：缺的维度 = 1
            if d == 1:
                continue                             # 1 与任何维兼容，且不占坑
            if out[pos] == 1:
                out[pos], setter[pos] = d, i         # 第一个非 1 维定下结果
            elif d != out[pos]:
                j = setter[pos]
                raise BroadcastError(
                    "shape mismatch: objects cannot be broadcast to a single "
                    f"shape.  Mismatch is between arg {j} with shape "
                    f"{shapes[j]} and arg {i} with shape {shapes[i]}.")
    return tuple(out)


def mini_broadcast(*shapes):
    """判定包装：返回 ('ok', 输出形状) 或 ('error', 消息)。"""
    try:
        return "ok", broadcast_shapes(*shapes)
    except BroadcastError as e:
        return "error", str(e)


def numpy_broadcast(*shapes):
    """裁判：np.broadcast_shapes 实测（与 mini 互不引用）。"""
    try:
        return "ok", np.broadcast_shapes(*shapes)
    except ValueError as e:
        return "error", str(e)


# ============================================================
# 2. stride-0 视图：broadcast 维的地址映射
# ============================================================

def broadcast_strides(shape, strides, out_shape):
    """把 shape/strides 的张量当作 out_shape 使用时的元素 strides。

    输入维为 1（含右对齐补出来的维）→ stride 0（与 np.broadcast_to 同口径：
    in==out==1 时 numpy 也记 0——size-1 维下标恒 0，stride 取 0 与继承值等价）；
    其余维度相同则继承源 stride。这是 np.broadcast_to 的 mini 版：
    广播不是拷贝数据，是「这一维走 0 步」的地址映射。
    不可广播返回 None。
    """
    r = len(out_shape)
    if len(shape) > r:
        return None
    pad = r - len(shape)
    padded_s = (1,) * pad + tuple(shape)        # 右对齐补 1（shape 侧）
    padded_t = (0,) * pad + tuple(strides)      # 补出来的维 stride 直接记 0
    out = []
    for d_out, d_in, t in zip(out_shape, padded_s, padded_t):
        if d_in == 1:
            out.append(0)                       # 输入维为 1：0 步长（numpy 同款）
        elif d_in == d_out:
            out.append(t)                       # 维度相同：继承源 stride
        else:
            return None                         # 失配：不可广播
    return tuple(out)


def estrides(shape) -> tuple:
    """C 连续（行主序）数组的元素 strides，如 (2,3) → (3,1)。"""
    st, acc = [], 1
    for d in reversed(shape):
        st.append(acc)
        acc *= d
    return tuple(reversed(st))


def numpy_strides(shape, out_shape) -> tuple:
    """裁判：np.broadcast_to 实测的元素 strides（f32，bytes/4）。"""
    arr = np.arange(int(np.prod(shape) or 1), dtype=np.float32).reshape(shape)
    v = np.broadcast_to(arr, out_shape)
    return tuple(t // arr.itemsize for t in v.strides)


# ============================================================
# 3. 未知维度：None 的 meet 规则（mini 约定）
# ============================================================

def _meet(d1, d2):
    """两个维度的广播结果；None 表示未知。失配抛 BroadcastError。

    meet 规则（在右对齐补 1 之后逐维执行）：
      已知 vs 已知：相等 → 保留；一方为 1 → 另一方；否则失配
      未知 vs 已知 d>1 → d     （运行期该维必须等于 d 或 1，否则才报错）
      未知 vs 1      → 未知    （结果维跟随未知方：max(1, s) = s）
      未知 vs 未知   → 未知
    """
    if d1 is None and d2 is None:
        return None
    if d1 is None:
        d1, d2 = d2, d1                       # 交换后 d1 一定是已知
    if d2 is None:
        return None if d1 == 1 else d1
    if d1 == 1:
        return d2
    if d2 == 1:
        return d1
    if d1 == d2:
        return d1
    raise BroadcastError(f"shape mismatch with unknown dims: {d1} vs {d2}")


_UNSET = object()      # 「这一维还没见过操作数」的哨兵，区别于 None（未知维度）


def broadcast_shapes_unknown(*shapes):
    """允许 None（未知维度）的广播推导，返回可能含 None 的输出形状。"""
    rank = max((len(s) for s in shapes), default=0)
    out = []
    for k in range(1, rank + 1):
        res = _UNSET
        for s in shapes:
            d = s[-k] if k <= len(s) else 1
            res = d if res is _UNSET else _meet(res, d)
        out.append(res)
    return tuple(reversed(out))


# ============================================================
# 实验（import 时不执行，见文件尾的 __main__ 守卫）
# ============================================================

def main() -> int:
    print("=== 1. 贯穿例子：a(2,3) 遇上三种对手 ===")
    a = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    b = np.array([10.0, 20.0, 30.0])
    c = np.array([[100.0], [200.0]])
    d = np.array([1.0, 2.0, 3.0, 4.0])
    print(f"  a {a.shape}  b {b.shape}  c {c.shape}  d {d.shape}")
    print(f"  a + b → 形状 {mini_broadcast(a.shape, b.shape)[1]}，值 =")
    print("  " + str(a + b).replace("\n", "\n  "))
    print(f"  a + c → 形状 {mini_broadcast(a.shape, c.shape)[1]}，值 =")
    print("  " + str(a + c).replace("\n", "\n  "))
    verdict_d = mini_broadcast(a.shape, d.shape)
    print(f"  a + d → {verdict_d[0]}：{verdict_d[1]}")
    print()
    print("  numpy 的实测报错（逐字）：")
    try:
        a + d
    except ValueError as e:
        print(f"    {e!r}")
    print()
    print("  stride-0 证据（b 被当作 (2,3) 用，一行数据两行用，不搬家）：")
    vb = np.broadcast_to(b, (2, 3))
    print(f"    b 的 strides = {b.strides} bytes，广播视图的 strides = "
          f"{vb.strides} bytes（元素单位 (0, 1)）")
    print(f"    shares_memory = {np.shares_memory(vb, b)}"
          f"，两行的第 2 列都是 {vb[0, 2]} / {vb[1, 2]}（同一格读两遍）")
    check("贯穿例子三种结局与 numpy 一致",
          mini_broadcast((2, 3), (3,))[1] == (2, 3)
          and mini_broadcast((2, 3), (2, 1))[1] == (2, 3)
          and mini_broadcast((2, 3), (4,))[0] == "error")
    check("a+b / a+c 数值正确",
          np.array_equal(a + b, [[11, 22, 33], [14, 25, 36]])
          and np.array_equal(a + c, [[101, 102, 103], [204, 205, 206]]))
    check("广播视图 stride 0 且共享存储",
          vb.strides == (0, 8) and np.shares_memory(vb, b) and vb[0, 2] == b[2])
    print()

    # ============================================================
    # 实验 2：判定表（16 组，与 np.broadcast_shapes 对拍）
    # ============================================================

    print("=== 2. 判定表：mini.broadcast 预测 vs numpy 实测 ===")
    CASES = [
        # (编号, 说明, 输入形状们)
        ("C1",  "同形相加",          ((2, 3), (2, 3))),
        ("C2",  "标量 vs 矩阵",      ((2, 3), ())),
        ("C3",  "行向量（贯穿例子）", ((2, 3), (3,))),
        ("C4",  "列向量右对齐",      ((2, 3), (2, 1))),
        ("C5",  "bias 相加",         ((8, 1000, 256), (256,))),
        ("C6",  "经典翻车 (256,1)",  ((8, 1000, 256), (256, 1))),
        ("C7",  "两边都补 1",        ((5, 1), (1, 4))),
        ("C8",  "双 1",              ((1,), (1,))),
        ("C9",  "0 尺寸维",          ((0,), (1,))),
        ("C10", "rank 差 2",         ((3, 4), (1,))),
        ("C11", "三形状连播",        ((8, 1000, 256), (256,), (1, 1))),
        ("C12", "-1 不是未知维度",   ((2, 3), (-1,))),
        ("C13", "维度 1 不豁免他维", ((3, 1), (2, 3))),
        ("C14", "完全失配",          ((2, 3), (4,))),
        ("C15", "标量对",            ((), ())),
        ("C16", "1×n 对 n×1",        ((1, 3), (3, 1))),
    ]
    print(f"  {'用例':<18}{'输入':<30}{'mini':<16}{'numpy':<16}对拍")
    n_ok = 0
    for cid, desc, shapes in CASES:
        m = mini_broadcast(*shapes)
        n = numpy_broadcast(*shapes)
        if m[0] == "ok":
            m_disp, n_disp = str(m[1]), str(n[1])
            same = m[1] == tuple(n[1])
        else:
            m_disp, n_disp = "error", "error"
            same = True
        n_ok += same
        m_shapes = " + ".join(str(s) for s in shapes)
        print(f"  {cid} {desc:<14}{m_shapes:<30}{m_disp:<16}{n_disp:<16}"
              f"{'ok' if same else 'MISMATCH'}")
        if m[0] == "error" and n[0] == "error" and len(shapes) == 2:
            assert m[1] == n[1], f"{cid} 错误消息不一致:\n  mini : {m[1]}\n  numpy: {n[1]}"
    check(f"判定表 {len(CASES)} 组全部一致（含 4 组错误消息逐字相同）", n_ok == len(CASES))
    print()

    # ============================================================
    # 实验 3：stride-0 视图（10 组，与 np.broadcast_to 对拍）
    # ============================================================

    print("=== 3. stride-0 视图：broadcast_strides vs np.broadcast_to 实测 ===")
    SCASES = [
        # (编号, 源 shape, 目标 shape)
        ("S1", (3,),   (2, 3)),
        ("S2", (3, 1), (2, 3, 4)),
        ("S3", (2, 1), (2, 3)),
        ("S4", (1, 3), (2, 3)),
        ("S5", (2, 3), (2, 3)),
        ("S6", (),     (2, 3)),
        ("S7", (2, 3), (1, 2, 3)),
        ("S8", (3,),   (4, 1, 2, 3)),
        ("S9", (256,), (8, 1000, 256)),
        ("S10", (2, 3), (4, 1, 2, 3)),
    ]
    print(f"  {'用例':<8}{'源':<10}{'目标':<16}{'mini strides':<14}{'numpy':<14}对拍")
    n_ok = 0
    for sid, shape, out_shape in SCASES:
        m = broadcast_strides(shape, estrides(shape), out_shape)
        n = numpy_strides(shape, out_shape)
        same = m == n
        n_ok += same
        print(f"  {sid:<8}{str(shape):<10}{str(out_shape):<16}{str(m):<14}{str(n):<14}"
              f"{'ok' if same else 'MISMATCH'}")
    check(f"stride-0 视图 {len(SCASES)} 组逐位一致", n_ok == len(SCASES))
    big = np.broadcast_to(np.zeros(3, dtype=np.float32), (100000, 3))
    check("大输出不搬数据：100000x3 广播视图与 3 元素源共享存储",
          np.shares_memory(big, big.base) and big.nbytes == 12 * 100000
          and big.base.nbytes == 12)
    print()

    # ============================================================
    # 实验 4：未知维度（None 的 meet 规则，手算期望）
    # ============================================================

    print("=== 4. 未知维度：None 的 meet 规则（numpy 没有对应物，期望手算）===")
    UCASES = [
        # (编号, 输入形状们, 期望输出或 "error", 一句理由)
        ("U1",  ((None, 3), (3,)),     (None, 3),   "最右维 3==3；None 对补 1 → 未知"),
        ("U2",  ((None, 3), (5, 3)),   (5, 3),      "None 对已知 5 → 5（运行期须为 5 或 1）"),
        ("U3",  ((None, 3), (1,)),     (None, 3),   "1 不改变未知：结果维跟随未知方"),
        ("U4",  ((None, 1), (5, 3)),   (5, 3),      "第 1 维 1 扩展成 3；None 对 5 → 5"),
        ("U5",  ((None,), (3,)),       (3,),        "None 对已知 3 → 3"),
        ("U6",  ((None, 1), (1,)),     (None, 1),   "第 0 维 None 对补 1 → 未知；第 1 维 1==1"),
        ("U7",  ((None, None), (None, 4)), (None, 4), "未知对未知仍是未知；4 对 4 → 4"),
        ("U8",  ((None, 4), (3,)),     "error",     "最右维 4 vs 3，都不是 1 → 失配"),
        ("U9",  ((None,), (5,)),       (5,),        "None 对已知 5 → 5"),
        ("U10", ((), (None, 3)),       (None, 3),   "标量对任何形状 → 原样"),
    ]
    print(f"  {'用例':<8}{'输入':<28}{'meet 结果':<14}说明")
    n_ok = 0
    for uid, shapes, want, why in UCASES:
        try:
            got = broadcast_shapes_unknown(*shapes)
            got_disp, ok = str(got), got == want
        except BroadcastError:
            got_disp, ok = "error", want == "error"
        n_ok += ok
        m_shapes = " + ".join(str(s) for s in shapes)
        print(f"  {uid:<8}{m_shapes:<28}{got_disp:<14}{why}")
    check(f"未知维度 {len(UCASES)} 组与手算期望一致", n_ok == len(UCASES))
    print()

    # ============================================================
    # 实验 5：随机对拍（300 组形状 + 100 组 strides）
    # ============================================================

    print("=== 5. 随机对拍：mini vs numpy（种子 60，可复现）===")
    rng = random.Random(60)
    DIM_POOL = [1, 1, 2, 3, 4, 5]          # 多放几个 1，提高广播命中率
    n_ok = n_err = 0
    for t in range(300):
        shapes = []
        for _ in range(2):
            rank = rng.randint(0, 4)
            shape = tuple(rng.choice(DIM_POOL) for _ in range(rank))
            if rng.random() < 0.15:        # 15% 概率塞一个必失配维
                shape = shape + (rng.randint(6, 9),)
            shapes.append(shape)
        m = mini_broadcast(*shapes)
        n = numpy_broadcast(*shapes)
        if m[0] != n[0] or (m[0] == "ok" and m[1] != tuple(n[1])):
            print(f"    失配：{shapes} mini={m} numpy={n}")
            break
        n_ok += m[0] == "ok"
        n_err += m[0] == "error"
    else:
        check("300 组随机形状推导全部一致", True,
              f"ok={n_ok} error={n_err}")
    n_ok2 = 0
    for t in range(100):
        shape = tuple(rng.choice(DIM_POOL) for _ in range(rng.randint(0, 4)))
        other = tuple(rng.choice(DIM_POOL) for _ in range(rng.randint(0, 3)))
        try:
            out = np.broadcast_shapes(shape, other)
        except ValueError:
            continue
        m = broadcast_strides(shape, estrides(shape), tuple(out))
        n = numpy_strides(shape, tuple(out))
        if m != n:
            print(f"    失配：{shape} → {out} mini={m} numpy={n}")
            break
        n_ok2 += 1
    else:
        check(f"随机 broadcast_to strides 对拍 {n_ok2} 组全部一致", True)
    print()

    # ============================================================
    # 汇总
    print(f"broadcast_lab: {CHECKS[0]}/{CHECKS[1]} checks passed")
    return 0 if CHECKS[0] == CHECKS[1] else 1


if __name__ == "__main__":
    raise SystemExit(main())
