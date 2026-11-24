#!/usr/bin/env python3
"""第 81 天：INT8 量化基础 —— Per-tensor 量化/反量化工具 + 边界单元测试 + 五个实验。

运行方式：
    python3 quant_lab.py

内容：
  * 量化库：round_half_away / compute_qparams / quantize / dequantize
  * 单元测试：12 个边界用例（端点还原、0 精确、饱和、舍入上界、全零、回绕…）
  * 实验 1：贯穿例子手算 vs 代码（对称 / 非对称）
  * 实验 2：边界值与饱和
  * 实验 3：偏斜数据上对称 vs 非对称（档位利用率 + 误差）
  * 实验 4：离群点 vs 分位数校准
  * 实验 5：INT8 MatMul 预览（INT32 累加 + 反量化 + 溢出演示）

只依赖 numpy 和标准库。
"""

import numpy as np

QMIN, QMAX = -128, 127          # 有符号 INT8 的取值范围
SMIN, SMAX = -127, 127          # 对称量化只用 255 档（-128 没有 +128 配对，闲置）


# ---------------------------------------------------------------------------
# 量化库
# ---------------------------------------------------------------------------

def round_half_away(x):
    """四舍五入（.5 远离零）—— C 语言 round() / TFLite 参考实现的口径。

    numpy 默认的 np.round 是 banker's rounding（.5 取偶）：
        np.round(0.5)=0, np.round(2.5)=2, round_half_away(0.5)=1, (2.5)=3
    两种口径混用会让同一组 (scale, zp) 在不同框架下差 1 个码（实验 2 有实测）。
    """
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def compute_qparams(xmin, xmax, symmetric=False, ensure_zero=True):
    """从校准范围 [xmin, xmax] 计算 per-tensor 的 (scale, zero_point)。

    非对称：scale = (xmax - xmin) / 255，zp = round(QMIN - xmin / scale)
    对称：  scale = max(|xmin|, |xmax|) / 127，zp = 0

    ensure_zero=True 时把 0 纳入校准范围（PyTorch MinMaxObserver 的做法）：
    既保证 float 0 精确映射到整数档，也保证 zp 不会超出 int8 范围。
    返回 (scale, zp)；全零范围返回 (1.0, 0) 防止除零。
    """
    if ensure_zero:
        xmin, xmax = min(xmin, 0.0), max(xmax, 0.0)
    if symmetric:
        amax = max(abs(xmin), abs(xmax))
        return (1.0, 0) if amax == 0.0 else (amax / 127.0, 0)
    if xmax <= xmin:                       # ensure_zero 后只剩 [0, 0] 一种可能
        return 1.0, 0
    scale = (xmax - xmin) / (QMAX - QMIN)
    zp = int(np.clip(round_half_away(QMIN - xmin / scale), QMIN, QMAX))
    return float(scale), zp


def quantize(x, scale, zp, qmin=QMIN, qmax=QMAX):
    """量化：q = clip(round(x / scale) + zp, qmin, qmax)，返回 int8。

    最后的 clip 就是饱和（saturation）：校准范围外的值被夹到边界档，
    而不是任由 astype(int8) 溢出回绕（127 + 1 会变成 -128，见实验 2）。
    """
    q = round_half_away(np.asarray(x, dtype=np.float64) / scale) + zp
    return np.clip(q, qmin, qmax).astype(np.int8)


def dequantize(q, scale, zp):
    """反量化：x_hat = scale * (q - zp)。"""
    return scale * (np.asarray(q, dtype=np.float64) - zp)


def quantize_tensor(x, symmetric=False, ensure_zero=True):
    """一步到位：校准 -> 取 (scale, zp) -> 量化。返回 (q, scale, zp)。"""
    x = np.asarray(x, dtype=np.float64)
    scale, zp = compute_qparams(float(x.min()), float(x.max()), symmetric, ensure_zero)
    qmin, qmax = (SMIN, SMAX) if symmetric else (QMIN, QMAX)
    return quantize(x, scale, zp, qmin, qmax), scale, zp


def rel_frobenius(actual, golden):
    """相对 Frobenius 误差：||C - G||_F / ||G||_F（Day 79/80 的整矩阵口径）。"""
    a = np.asarray(actual, dtype=np.float64)
    g = np.asarray(golden, dtype=np.float64)
    return float(np.linalg.norm(a - g) / np.linalg.norm(g))


def levels_used(q):
    """档位利用率：量化结果实际用到的不同整数档数。"""
    return len(np.unique(q))


# ---------------------------------------------------------------------------
# 单元测试（assert 版，无需 pytest）
# ---------------------------------------------------------------------------

def run_unit_tests():
    print("单元测试：per-tensor 量化/反量化的 12 个边界用例")

    # T1 校准端点能还原：xmin -> QMIN、xmax -> QMAX（误差 <= 1 格）
    x = np.array([0.0, 0.5, 1.0, 2.0, 3.5])
    s, zp = compute_qparams(0.0, 3.5)
    assert quantize(3.5, s, zp) == QMAX and quantize(0.0, s, zp) == QMIN
    print(f"  T01 PASS  端点映射：0.0 -> q={QMIN}，3.5 -> q={QMAX}")

    # T2 float 0 精确还原（ensure_zero 的意义）
    assert dequantize(quantize(0.0, s, zp), s, zp) == 0.0
    print(f"  T02 PASS  ensure_zero：x=0 反量化误差恰为 0")

    # T3 舍入误差上界：范围内值 |x_hat - x| <= scale（半格舍入 + zp 取整半格）
    rng = np.random.default_rng(81)
    xr = rng.uniform(0.0, 3.5, 10000)
    err = np.abs(dequantize(quantize(xr, s, zp), s, zp) - xr)
    assert err.max() <= s + 1e-12
    print(f"  T03 PASS  舍入上界：max|err|={err.max():.6f} <= scale={s:.6f}")

    # T4 饱和：超出校准范围的值被夹到边界档，误差 = 到边界的距离
    q_big = quantize(5.0, s, zp); q_small = quantize(-2.0, s, zp)
    assert q_big == QMAX and q_small == QMIN
    assert abs(dequantize(q_big, s, zp) - 5.0) == 5.0 - 3.5
    print(f"  T04 PASS  饱和：5.0 -> {dequantize(q_big, s, zp)}（夹到 qmax），-2.0 -> 0（夹到 qmin）")

    # T5 忘记 clip 会回绕：不饱和的 236 落进 int8 变 -20，5.0 被还原成 1.48
    q_raw = round_half_away(5.0 / s) + zp            # = 236，超出 int8
    assert np.int8(q_raw) == -20
    print(f"  T05 PASS  回绕：无 clip 时 q={q_raw:.0f} -> int8 变 {np.int8(q_raw)}，"
          f"5.0 -> {s * (np.int8(q_raw) - zp):.2f}（符号翻转灾难）")

    # T6 对称量化：zp=0，档位限制在 [-127, 127]
    ss, szp = compute_qparams(-2.5, 3.5, symmetric=True)
    qs = quantize([-2.5, 3.5, 0.0], ss, szp, SMIN, SMAX)
    assert szp == 0 and qs.min() >= SMIN and qs.max() <= SMAX
    print(f"  T06 PASS  对称：scale={ss:.6f}, zp=0, q 落在 [{SMIN},{SMAX}]")

    # T7 全零张量不除零
    sz, z_zp = compute_qparams(0.0, 0.0)
    assert dequantize(quantize(np.zeros(4), sz, z_zp), sz, z_zp).max() == 0.0
    print(f"  T07 PASS  全零：scale={sz}, zp={z_zp}，不崩溃且还原为 0")

    # T8 zp 始终在 int8 范围内（ensure_zero=True 的保证）
    for lo, hi in [(0.1, 3.7), (-50.0, -1.0), (-8.0, 0.02), (2.0, 2.0), (-1.0, 100.0)]:
        _, z = compute_qparams(lo, hi)
        assert QMIN <= z <= QMAX, (lo, hi, z)
    print(f"  T08 PASS  zp 合法：5 组边界范围（含全正/全负）的 zp 都在 [{QMIN},{QMAX}]")

    # T9 不含 0 的范围 + ensure_zero=False：zp 被 clamp，max 端丢一格
    s9, zp9 = compute_qparams(0.1, 3.7, ensure_zero=False)
    assert zp9 == QMIN                                  # -135 被 clamp 回 -128
    x9 = dequantize(quantize(3.7, s9, zp9), s9, zp9)
    assert x9 < 3.7                                     # max 端被迫饱和
    print(f"  T09 PASS  clamp：范围 [0.1,3.7] 不含 0 时 zp={zp9}，3.7 只能还原到 {x9:.4f}")

    # T10 量化结果是 int8 且值域合法
    q10 = quantize_tensor(rng.uniform(-3, 3, 512), symmetric=True)[0]
    assert q10.dtype == np.int8 and q10.min() >= SMIN and q10.max() <= SMAX
    print(f"  T10 PASS  dtype：量化输出 dtype={q10.dtype}，值域 [{q10.min()},{q10.max()}]")

    # T11 round_half_away 与 np.round 的口径差异（.5 处）
    assert round_half_away(np.array([0.5, 2.5, -0.5]))[0] == 1
    assert list(np.round([0.5, 2.5, -0.5])) == [0.0, 2.0, -0.0]
    print(f"  T11 PASS  舍入口径：0.5 -> {int(round_half_away(np.array([0.5]))[0])}（half-away）"
          f" vs np.round -> {int(np.round(0.5))}（half-even）")

    # T12 往返一致性：dequant(quant(x)) 的误差 <= scale（对两种方案都成立）
    for sym in (False, True):
        q, s12, z12 = quantize_tensor(x, symmetric=sym)
        e12 = np.abs(dequantize(q, s12, z12) - x).max()
        assert e12 <= s12 + 1e-12
    print(f"  T12 PASS  往返：对称/非对称的 max|err| 都 <= scale")
    print("  12/12 通过\n")


# ---------------------------------------------------------------------------
# 实验 1：贯穿例子 —— 手算 vs 代码
# ---------------------------------------------------------------------------

def exp1_running_example():
    print("实验 1：贯穿例子 x = [0, 0.5, 1.0, 2.0, 3.5]（ReLU 输出风格的偏斜数据）")
    x = np.array([0.0, 0.5, 1.0, 2.0, 3.5])
    for name, sym in (("非对称", False), ("对称", True)):
        q, s, zp = quantize_tensor(x, symmetric=sym)
        xh = dequantize(q, s, zp)
        err = np.abs(xh - x)
        print(f"  -- {name} per-tensor --")
        print(f"  scale = {s:.6f}, zero_point = {zp}, 档位范围 "
              f"[{'-127, 127' if sym else '-128, 127'}]（{255 if sym else 256} 档）")
        print(f"  q      = {list(int(v) for v in q)}")
        print(f"  反量化 = {[f'{v:.4f}' for v in xh]}")
        print(f"  误差   = {[f'{v:.4f}' for v in err]}  max = {err.max():.4f}，"
              f"用了 {levels_used(q)} 个不同档\n")
    print("  手算对照（非对称）：scale = 3.5/255 = 0.013725，zp = round(-128 - 0/s) = -128")
    print("    0.5 -> round(0.5/0.013725) - 128 = 36 - 128 = -92；反量化 0.013725*(-92+128) = 0.4941\n")


# ---------------------------------------------------------------------------
# 实验 2：边界值与饱和
# ---------------------------------------------------------------------------

def exp2_boundary():
    print("实验 2：边界值与饱和（校准范围 [0, 3.5]）")
    s, zp = compute_qparams(0.0, 3.5)
    probes = [(-2.0, "范围外·下"), (0.0, "校准端点·min"), (1.75, "范围正中"),
              (3.5, "校准端点·max"), (3.6, "刚出界"), (5.0, "范围外·上")]
    for v, tag in probes:
        q = int(quantize(v, s, zp))
        xh = dequantize(q, s, zp)
        print(f"  {tag:12s} x={v:5.2f} -> q={q:4d} -> x_hat={xh:.4f}   误差={abs(xh - v):.4f}")
    print("  解读：范围内误差 <= scale/2 = 0.0069；范围外被夹到边界档，误差 = 到边界的距离\n")


# ---------------------------------------------------------------------------
# 实验 3：偏斜数据上 对称 vs 非对称
# ---------------------------------------------------------------------------

def exp3_sym_vs_asym():
    print("实验 3：对称 vs 非对称（4096 个随机数，种子 81）")
    rng = np.random.default_rng(81)
    for name, data in (("偏斜数据（ReLU 后，uniform(0,4)）", rng.uniform(0.0, 4.0, 4096)),
                       ("对称数据（uniform(-4,4)）", rng.uniform(-4.0, 4.0, 4096))):
        print(f"  -- {name} --")
        for scheme, sym in (("非对称", False), ("对称", True)):
            q, s, zp = quantize_tensor(data, symmetric=sym)
            xh = dequantize(q, s, zp)
            err = np.abs(xh - data)
            used = levels_used(q)
            total = 255 if sym else 256
            print(f"    {scheme}: scale={s:.5f}  max|err|={err.max():.5f}  rms={np.sqrt((err**2).mean()):.5f}"
                  f"  档位 {used}/{total}（{used/total*100:.0f}%）")
        print()
    print("  解读：偏斜数据上对称方案只用一半档位、误差约 2 倍；对称数据上两者几乎打平\n")


# ---------------------------------------------------------------------------
# 实验 4：离群点 vs 分位数校准
# ---------------------------------------------------------------------------

def exp4_outlier():
    print("实验 4：一个离群点能毁掉整把刻度尺（4096 个 uniform(-1,1) + 一个 100.0）")
    rng = np.random.default_rng(81)
    base = rng.uniform(-1.0, 1.0, 4096)
    x = np.append(base, 100.0)

    # 策略 A：min-max 校准（离群点进范围）
    sA, zpA = compute_qparams(float(x.min()), float(x.max()))
    # 策略 B：99.9% 分位数校准（离群点交给饱和）
    lo, hi = np.percentile(x, 0.05), np.percentile(x, 99.95)
    sB, zpB = compute_qparams(float(lo), float(hi))
    print(f"  策略 A min-max   ：范围 [{x.min():.1f}, {x.max():.1f}]  scale = {sA:.5f}")
    print(f"  策略 B 99.9% 分位：范围 [{lo:.3f}, {hi:.3f}]  scale = {sB:.5f}（A 的 {sA/sB:.0f} 分之一）")
    for tag, s, zp in (("A", sA, zpA), ("B", sB, zpB)):
        q = quantize(base, s, zp)                      # 只对 4096 个正常值统计误差
        err = np.abs(dequantize(q, s, zp) - base)
        print(f"    策略 {tag}：4096 个正常值的 max|err| = {err.max():.4f}，rms = {np.sqrt((err**2).mean()):.4f}")
    q_out = quantize(100.0, sB, zpB)
    print(f"    策略 B 里那个 100.0：q = {int(q_out)}（饱和到 qmax），还原值 = "
          f"{dequantize(q_out, sB, zpB):.3f} —— 被牺牲的离群点\n")


# ---------------------------------------------------------------------------
# 实验 5：INT8 MatMul 预览（对称量化 + INT32 累加）
# ---------------------------------------------------------------------------

def exp5_int8_matmul():
    print("实验 5：INT8 MatMul 预览 —— Day 79/80 的贯穿例子")
    A = np.array([[0.1, 0.2, 0.3], [1.0, 2.0, 3.0]])
    B = np.array([[0.4, 1.0], [0.5, 2.0], [0.6, 3.0]])
    golden = np.asarray(A, dtype=np.float64) @ np.asarray(B, dtype=np.float64)

    Qa, sa, za = quantize_tensor(A, symmetric=True)
    Qb, sb, zb = quantize_tensor(B, symmetric=True)
    acc32 = Qa.astype(np.int32) @ Qb.astype(np.int32)   # INT8 输入 -> INT32 累加
    C = sa * sb * acc32                                  # 对称方案反量化只需乘 sa*sb
    print(f"  A/B 对称量化：sa = {sa:.6f}，sb = {sb:.6f}，za = zb = 0")
    print(f"  Qa =\n{Qa}\n  Qb =\n{Qb}")
    print(f"  INT32 累加结果 Qa@Qb =\n{acc32}")
    print(f"  反量化 C = sa*sb*(Qa@Qb) =\n{np.round(C, 4)}")
    print(f"  FP64 golden =\n{golden}")
    print(f"  max_abs = {np.abs(C - golden).max():.4f}，rel_F = {rel_frobenius(C, golden):.4f}")

    rng = np.random.default_rng(7)                       # 和 Day 80 实验 3 同一套口径
    Ar = rng.uniform(-1, 1, (64, 64)); Br = rng.uniform(-1, 1, (64, 64))
    gr = np.asarray(Ar, dtype=np.float64) @ np.asarray(Br, dtype=np.float64)
    Qar, sar, _ = quantize_tensor(Ar, symmetric=True)
    Qbr, sbr, _ = quantize_tensor(Br, symmetric=True)
    Cr = sar * sbr * (Qar.astype(np.int32) @ Qbr.astype(np.int32))
    print(f"  随机 64x64 对照：rel_F = {rel_frobenius(Cr, gr):.4f}"
          f"（Day 80 实测 fp16 入·fp32 累对 FP64 golden 约 1e-4~1e-3 量级）")

    print("\n  -- 累加器位宽：为什么必须是 INT32 --")
    demo_a = np.array([[127, 127]], dtype=np.int8)
    demo_b = np.array([[127], [127]], dtype=np.int8)
    print(f"  [[127,127]] @ [[127],[127]]：真值 = 127*127*2 = {127*127*2}")
    print(f"    int8 累加（numpy int8@int8 实测）  = {int((demo_a @ demo_b)[0][0])}  <- 溢出回绕，灾难")
    print(f"    int32 累加（显式 cast 后实测）      = {int((demo_a.astype(np.int32) @ demo_b.astype(np.int32))[0][0])}")
    print(f"  容量账：单项最大 127*127 = {127*127}；int16 累加在 K=3 就可能溢出，"
          f"int32 要 K={2**31 // (127*127)} 全满项才溢出")

    print("\n  -- 字节账（nbytes 实测，512x512 矩阵） --")
    big = np.zeros((512, 512))
    for dt in (np.float32, np.float16, np.int8):
        print(f"    {str(dt.__name__):8s} {big.astype(dt).nbytes/1024/1024:.2f} MiB")
    print()


# ---------------------------------------------------------------------------

def main():
    run_unit_tests()
    exp1_running_example()
    exp2_boundary()
    exp3_sym_vs_asym()
    exp4_outlier()
    exp5_int8_matmul()


if __name__ == "__main__":
    main()
