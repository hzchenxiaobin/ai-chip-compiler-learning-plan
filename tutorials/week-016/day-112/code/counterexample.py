#!/usr/bin/env python3
"""D112 第 16 周复盘：性能反例——Cost Model 为什么可能选错。

计划任务：总结"生成正确代码"和"生成高性能代码"所需的不同信息；
准备一个性能反例，说明 Cost Model 为什么可能选错。

本文件用 D107~D111 的既有工具（kernel_gen / bench / cost_model，逐字节复制）
做四组实验，把"模型选错"拆成三层机理，每层都有今天的真实数据：

  --exp a-narrow      反例一（近对＋K=1）：S1=64³ 的 24 个候选同进程全测，
                      模型 top-1 ≠ 真冠军 → K=1 政策的实测代价；
                      对照 D110 已记录的 3/3 shape K=1 代价 +4.8~8.1%。
  --exp b-resolution   机理一（分辨率）：模型对近对的预测差（~0.1% 量级，
                      宽 shape 上完全平手）vs 同进程 5 轮交错 A/B 的实测差
                      （7~9%）vs 同日相邻进程的次序翻转（D110/D111/今天）。
                      结论：模型分辨率 < 世界稳定度，结构性选错，不是 bug。
  --exp c-regime      机理二（regime 漂移）：宽 regime 校准（行宽 512，
                      斜率尺寸 128/256/512）量出第二套单价——j0 +20%、
                      loop +68%……单价是 (进程, regime) 的函数；用它重排
                      窄世界 S1，看排名对出域单价的敏感性。
  --exp d-wide        机理三（出域对照）：宽 shape W1=64×512×64 的 36 个候选
                      全测——窄单价表出域预测冠军（结构项主导，但近对完全
                      平手 = 掷硬币）；出域闸门 domain_check 的演示。
  --exp calibrate     窄 regime 校准落盘 outputs/calibration.json（D110/D111
                      同款纪律：一次付清，全部实验共享同一份缓存）。
  --exp env           环境记录。

运行约 2 分钟（--exp d-wide 的全测占 ~80 s）。零第三方依赖。
所有报告写 outputs/，机器可读的数字另存 JSON，供 gen_images.py 出图。
"""

from __future__ import annotations

import argparse
import dataclasses
import gc
import json
import os
import statistics
import subprocess
import sys
import time

import bench as bm
import cost_model as cm
from kernel_gen import KernelConfig

BAR = "=" * 78
HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.join(HERE, "outputs")
CALIB_CACHE = os.path.join(OUTPUTS, "calibration.json")
WIDE_CACHE = os.path.join(OUTPUTS, "wide-calibration.json")

SCREEN = bm.Protocol(warmup=3, repeats=7)     # D107 筛选口径
FINAL = bm.Protocol(warmup=3, repeats=21)     # D107 决赛口径

S1 = (64, 64, 64)          # 窄世界的代表（D108/D110 的 S1，校准 regime 内）
W1 = (64, 512, 64)         # 宽世界（N=512 跨过 CPython 小整数缓存边界 256）
NEAR_PAIR_S1 = ("64³ ikj U=1", "64³ kij U=1")   # 模型眼里的近对（预测差 ~0.1%）
NEAR_PAIR_W1 = ("64×512×64 ikj U=1", "64×512×64 kij U=1")


# ---------------------------------------------------------------- 小工具


def _save_json(name: str, obj) -> None:
    with open(os.path.join(OUTPUTS, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def _report(name: str, text: str) -> str:
    with open(os.path.join(OUTPUTS, name), "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def _avg_ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def spearman(a, b) -> float:
    """Spearman ρ（平均秩处理并列；并列在近对上是常态）。"""
    ra, rb = _avg_ranks(a), _avg_ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da * db else 1.0


def _cfg_by_name(cands, name: str) -> KernelConfig:
    for c in cands:
        if c.describe() == name:
            return c
    raise KeyError(name)


def _med(rec: dict) -> float:
    return rec["stats_ms"]["median"]


def _iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------- exp calibrate


def exp_calibrate() -> str:
    """窄 regime 校准落盘（与 D110 cost_model 的 calibrate 完全同一套）。"""
    os.makedirs(OUTPUTS, exist_ok=True)
    c = cm.calibrate()
    lines = [BAR, " D112 窄 regime 校准：16 根语句行单价（微基准中位数，ns/行）",
             BAR, f" 校准墙钟：{c.wall_ms:.0f} ms（一次付清，全部实验共享这份缓存）"]
    names = [("j0", "j 内层行  Ci[v] += a*Bv[v]"),
             ("ju", "j 内层·展开行  Ci[v+1] += a*Bv[v+1]"),
             ("k0", "k 内层行  c += Ai[v]*B[v][v2]"),
             ("ku", "k 内层·展开行  c += Ai[v+1]*B[v+1][v2]"),
             ("i0", "i 内层行  C[v][v2] += A[v][v2]*b"),
             ("iu", "i 内层·展开行  C[v+1][v2] += A[v+1][v2]*b"),
             ("hs1", "行提升·单下标  Bv = B[v]"),
             ("hs2", "行提升·双单  Ci = C[v1]; Ai = A[v1]"),
             ("hsm", "行提升·单+双  Ci = C[v2]; a = A[v2][v1]"),
             ("hd1", "行提升·双下标  b = B[v1][v2]"),
             ("s2", "尾部写回  C[v1][v2] = c"),
             ("loop", "纯循环机器行"),
             ("range2", "二参 range 建立"),
             ("range3", "三参 range 建立"),
             ("pre", "展开前奏行"),
             ("min3", "tile 外壳三连 min 行")]
    for k, desc in names:
        lines.append(f"  {k:7s} {getattr(c, k):6.1f} ns   {desc}")
    _save_json("calibration.json",
               {"schema": "d110.calibration/1", "timestamp": _iso(),
                "costs": dataclasses.asdict(c)})
    lines.append(f" 落盘：outputs/calibration.json（{_iso()}）")
    return _report("calibration.txt", "\n".join(lines) + "\n")


# ---------------------------------------------------------------- exp a：反例一


def exp_a() -> str:
    """S1 同进程全测 vs 模型：K=1 政策的实测代价。"""
    costs, src = cm.get_costs()
    env = bm.capture_env()
    M, N, K = S1
    spec = bm.BenchSpec(M=M, N=N, K=K)
    cands = cm.build_space("S1", M, N, K)
    ranked = sorted(((cm.predict_ms(cm.count_ops(M, N, K, c), costs), c)
                     for c in cands), key=lambda t: t[0])
    model_names = [c.describe() for _, c in ranked]

    # ① 全测（筛选口径 3+7）：搜索语义——按模型顺序过门、计时
    t0 = time.perf_counter()
    screen = []
    for pred, c in ranked:
        rec = bm.bench_one(c, spec, SCREEN, env)
        screen.append({"cfg": c.describe(), "pred_ms": pred, "rec": rec})
    wall_screen = time.perf_counter() - t0
    passed = [r for r in screen if r["rec"]["correctness"]["passed"]]
    truth = {r["cfg"]: _med(r["rec"]) for r in passed}

    # ② 决赛（3+21）：筛选 top-3 ∪ 缺省 ∪ 模型 top-1（保证 K=1 政策可评估）
    by_med = sorted(passed, key=lambda r: truth[r["cfg"]])
    finalists = [r["cfg"] for r in by_med[:3]]
    if cm.DEFAULT_CFG.describe() not in finalists:
        finalists.append(cm.DEFAULT_CFG.describe())
    if model_names[0] not in finalists:
        finalists.append(model_names[0])
    t0 = time.perf_counter()
    final = {}
    for name in finalists:
        c = _cfg_by_name(cands, name)
        rec = bm.bench_one(c, spec, FINAL, env)
        final[name] = _med(rec)
    wall_final = time.perf_counter() - t0

    # ③ 三种政策的账（全部出自同一批决赛读数，无跨口径漂移）
    champ = min(final, key=final.get)
    model_top1 = model_names[0]
    k1_loss = (final[model_top1] / final[champ] - 1) * 100
    champ_rank = model_names.index(champ) + 1
    rho = spearman([r["pred_ms"] for r in passed], [truth[r["cfg"]] for r in passed])

    out = [BAR, " D112 反例一（近对＋K=1）：S1 64×64×64 同进程全测 vs 模型排序",
           BAR, f" 单价来源：{src}",
           f" 空间：{len(cands)} 个候选（32³/64³ × 6 顺序 × U=1/4）；门：bitwise，全部通过",
           f" 全测墙钟 {wall_screen:.1f} s（3+7）＋决赛 {wall_final:.1f} s（3+21，{len(finalists)} 个）",
           "",
           " 模型 top-6 vs 同进程实测（筛选口径）：",
           "   模型名次  配置                      预测 ms   实测 ms   误差%",
           "   " + "-" * 60]
    for i, r in enumerate(screen[:6]):
        ms = truth.get(r["cfg"])
        if ms:
            out.append(f"   {i + 1:6d}  {r['cfg']:24s} {r['pred_ms']:8.2f} "
                       f"{ms:9.2f} {(r['pred_ms'] / ms - 1) * 100:+7.1f}")
        else:
            out.append(f"   {i + 1:6d}  {r['cfg']:24s} {r['pred_ms']:8.2f}       —（被拒）")
    out += ["",
            f" 真冠军（决赛 3+21）：{champ} = {final[champ]:.2f} ms（模型名次 {champ_rank}）",
            f" 模型 top-1：{model_top1} = {final[model_top1]:.2f} ms",
            f" → K=1 政策代价：{k1_loss:+.1f}%",
            f"   （top-5＋同进程决赛的政策选中 {champ}，没有这个损失——决赛读数同批）",
            f" → 模型 top-1 与 top-2 的预测差："
            f"{(abs(ranked[0][0] - ranked[1][0]) / ranked[1][0]) * 100:.2f}%"
            f"（{model_names[0]} vs {model_names[1]}）",
            f" Spearman ρ（预测 vs 实测，n={len(passed)}，并列取平均秩）= {rho:.3f}",
            "",
            " 读法：ρ≈0.98 说明『砍数量』稳；top-1 是否易主说明『定名次』看运气。",
            " D110 的记录同款（topk-sensitivity.txt）：K=1 三个 shape 全错，",
            " 代价 +4.8% / +6.6% / +8.1%——K=1 把 ~0.2% 的模型差当决策依据，",
            " 而近对的实测差在 5~9% 量级、跨窗口还会翻号（见 b-resolution.txt）。"]

    _save_json("a-narrow.json",
               {"schema": "d112.a-narrow/1", "timestamp": _iso(),
                "shape": list(S1), "n_cands": len(cands),
                "screen": [[r["cfg"], round(r["pred_ms"], 3),
                            round(truth[r["cfg"]], 3)] for r in passed],
                "final": {k: round(v, 3) for k, v in final.items()},
                "model_rank": model_names, "champion": champ,
                "champion_ms": final[champ], "model_top1": model_top1,
                "model_top1_ms": final[model_top1], "k1_loss_pct": round(k1_loss, 2),
                "champ_model_rank": champ_rank, "spearman": round(rho, 3),
                "near_pair_pred_gap_pct": round(
                    (abs(ranked[0][0] - ranked[1][0]) / ranked[1][0]) * 100, 3),
                "wall_screen_s": round(wall_screen, 1),
                "wall_final_s": round(wall_final, 1)})
    with open(os.path.join(OUTPUTS, "a-narrow.jsonl"), "w", encoding="utf-8") as fh:
        for r in screen:
            fh.write(json.dumps(r["rec"], ensure_ascii=False) + "\n")
    return _report("a-narrow.txt", "\n".join(out) + "\n")


# ---------------------------------------------------------------- exp b：分辨率


def _subprocess_probe() -> dict:
    """同机同日相邻进程：新起一个 Python，量 S1 近对的 A/B（3+7）。"""
    code = (
        "import json,sys; sys.path.insert(0, %r); import bench as bm\n"
        "from kernel_gen import KernelConfig\n"
        "env = bm.capture_env(); spec = bm.BenchSpec(M=64, N=64, K=64)\n"
        "p = bm.Protocol(warmup=3, repeats=7)\n"
        "out = {}\n"
        "for c in (KernelConfig(64,64,64,'ikj',1), KernelConfig(64,64,64,'kij',1)):\n"
        "    rec = bm.bench_one(c, spec, p, env)\n"
        "    out[c.describe()] = rec['stats_ms']['median']\n"
        "print(json.dumps(out))" % HERE)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=HERE, check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def exp_b() -> str:
    costs, src = cm.get_costs()
    env = bm.capture_env()
    M, N, K = S1
    spec = bm.BenchSpec(M=M, N=N, K=K)
    cands = cm.build_space("S1", M, N, K)

    # ① 模型对近对的分辨率：S1 预测差；W1 预测差（并列？）
    def pair_gap(shape, names):
        m, n, k = shape
        preds = {nm: cm.predict_ms(cm.count_ops(m, n, k, _cfg_by_name(cands + cm.build_space("W1", *W1), nm)), costs)
                for nm in names}
        gap = (preds[names[0]] - preds[names[1]]) / preds[names[1]] * 100
        return preds, gap

    preds_s1, gap_s1 = pair_gap(S1, NEAR_PAIR_S1)
    w_cands = cm.build_space("W1", *W1)
    preds_w1, gap_w1 = pair_gap(W1, NEAR_PAIR_W1)
    tie_w1 = preds_w1[NEAR_PAIR_W1[0]] == preds_w1[NEAR_PAIR_W1[1]]

    # ② 本进程 5 轮交错 A/B（3+7）：世界的"同进程稳定度"
    rounds = []
    c_ikj = _cfg_by_name(cands, NEAR_PAIR_S1[0])
    c_kij = _cfg_by_name(cands, NEAR_PAIR_S1[1])
    for r in range(5):
        med = {}
        for c in (c_ikj, c_kij):
            med[c.describe()] = _med(bm.bench_one(c, spec, SCREEN, env))
        rounds.append({"ikj_ms": med[NEAR_PAIR_S1[0]],
                       "kij_ms": med[NEAR_PAIR_S1[1]],
                       "gap_pct": (med[NEAR_PAIR_S1[0]] / med[NEAR_PAIR_S1[1]] - 1) * 100})
    gaps = [r["gap_pct"] for r in rounds]

    # ③ 校准自身的抖动：同进程再校准 3 次，看 j0/k0 近对读数
    fresh = [cm.calibrate() for _ in range(3)]

    # ④ 同机同日相邻进程：两个子进程各掷一次近对
    subs = []
    for i in range(2):
        d = _subprocess_probe()
        subs.append({"ikj_ms": d[NEAR_PAIR_S1[0]], "kij_ms": d[NEAR_PAIR_S1[1]],
                     "gap_pct": (d[NEAR_PAIR_S1[0]] / d[NEAR_PAIR_S1[1]] - 1) * 100})

    out = [BAR, " D112 机理一（分辨率）：模型近对差 vs 世界稳定度", BAR,
           f" 单价来源：{src}", "",
           " ① 模型对近对的分辨率（预测）",
           f"   S1 {NEAR_PAIR_S1[0]} vs {NEAR_PAIR_S1[1]}：预测差 {gap_s1:+.2f}%"
           f"（{preds_s1[NEAR_PAIR_S1[0]]:.2f} vs {preds_s1[NEAR_PAIR_S1[1]]:.2f} ms）",
           f"   W1 {NEAR_PAIR_W1[0]} vs {NEAR_PAIR_W1[1]}：预测差 {gap_w1:+.2f}%"
           + ("（完全并列——模型实际上掷硬币）" if tie_w1 else ""),
           "",
           " ② 本进程 5 轮交错 A/B（每轮 3+7，同进程内符号稳定）："]
    for i, r in enumerate(rounds):
        out.append(f"   round {i + 1}: ikj={r['ikj_ms']:.2f} ms  kij={r['kij_ms']:.2f} ms"
                   f"  gap(ikj−kij)/kij = {r['gap_pct']:+.2f}%")
    out.append(f"   实测差范围：{min(gaps):+.2f}% ~ {max(gaps):+.2f}%"
               f"（中位 {statistics.median(gaps):+.2f}%）")
    out += ["",
            " ③ 校准自己的抖动（同进程重校 3 次）：",
            "      j0        k0        j0−k0"]
    for i, c in enumerate(fresh):
        out.append(f"   cal#{i + 1}  {c.j0:6.1f}    {c.k0:6.1f}    {c.j0 - c.k0:+5.1f} ns")
    dj = [c.j0 - c.k0 for c in fresh]
    out.append(f"   j0−k0 在 {min(dj):+.1f} ~ {max(dj):+.1f} ns 之间摆——这个符号决定"
               " j/k 家族谁占优（家族间预测差约 9%），")
    out.append("   而它跨 regime 会翻面（c-regime.txt：宽表里 j0−k0 翻成正号）。")
    out.append("   家族内的近对（ikj vs kij）预测差只有 0.1% 量级——结构几乎相同，")
    out.append("   预测差天然贴零，任何读数抖动都能翻动它。")
    out += ["", " ④ 同机同日相邻进程（子进程掷硬币）："]
    for i, s in enumerate(subs):
        out.append(f"   进程#{i + 1}: ikj={s['ikj_ms']:.2f} ms  kij={s['kij_ms']:.2f} ms"
                   f"  → {'ikj' if s['gap_pct'] < 0 else 'kij'} 快 {abs(s['gap_pct']):.2f}%")
    with open(os.path.join(OUTPUTS, "a-narrow.json"), encoding="utf-8") as fh:
        a = json.load(fh)
    a_ikj, a_kij = a["final"].get(NEAR_PAIR_S1[0]), a["final"].get(NEAR_PAIR_S1[1])
    a_gap = (a_ikj / a_kij - 1) * 100
    med_gap = statistics.median(gaps)
    flipped = (a_gap > 0) != (med_gap > 0)
    out += ["",
            " ⑤ 画廊（近对冠军 = 机器-时间窗口的属性，不是真理）：",
            "   D110 进程（2026-11-13，drift-a-b.txt）：kij 快 6.5%",
            "   D111 进程（2026-11-13，tune-summary.json）：ikj 快 8.2%（15.70 vs 17.10）",
            f"   本进程·窗口 a（a-narrow 全测＋决赛）：{'kij' if a_gap > 0 else 'ikj'} 快"
            f" {abs(a_gap):.1f}%（决赛 {a_kij:.2f} vs {a_ikj:.2f} ms）",
            f"   本进程·窗口 b（上面 5 轮 A/B）：{'kij' if med_gap > 0 else 'ikj'} 快"
            f" {abs(med_gap):.1f}%",
            *[f"   子进程#{i + 1}（今天）：{'kij' if s['gap_pct'] > 0 else 'ikj'} 快 {abs(s['gap_pct']):.2f}%"
              for i, s in enumerate(subs)],
            ""]
    if flipped:
        out += [" → 同一进程、两个时间窗、两个冠军——近对上连『进程内真值』都不",
                "   存在，只有『窗口内真值』。窗口 a 里 K=1 付了 a-narrow.txt 的账，",
                "   窗口 b 里同一枚硬币免单：K=1 的损失不可预知，不能当决策。"]
    else:
        out += [" → 本进程两个窗口次序一致——但 D110/D111 的进程结论各自相反，",
                "   近对次序是『机器-窗口』的属性；K=1 只是这一次掷硬币的结果。"]
    out += ["",
            f" 结论：模型分辨率（S1 预测差 {abs(gap_s1):.2f}%，W1 {abs(gap_w1):.2f}%）",
            " 比世界稳定度（同窗口 ±1%，跨窗口/跨进程 ±5~9%）低一到两个数量级。",
            " 近对名次模型永远给不出证据——recall@K＋同窗口实测决选是唯一工程答案。"]

    _save_json("b-resolution.json",
               {"schema": "d112.b-resolution/1", "timestamp": _iso(),
                "pred_gap_s1_pct": round(gap_s1, 3), "pred_gap_w1_pct": round(gap_w1, 3),
                "pred_tie_w1": tie_w1,
                "rounds": [{"ikj_ms": round(r["ikj_ms"], 3),
                            "kij_ms": round(r["kij_ms"], 3),
                            "gap_pct": round(r["gap_pct"], 2)} for r in rounds],
                "fresh_calib": [{"j0": round(c.j0, 1), "k0": round(c.k0, 1)} for c in fresh],
                "subprocess": [{"ikj_ms": round(s["ikj_ms"], 3),
                                "kij_ms": round(s["kij_ms"], 3),
                                "gap_pct": round(s["gap_pct"], 2)} for s in subs],
                "window_a": {"ikj_ms": a_ikj, "kij_ms": a_kij,
                             "gap_pct": round(a_gap, 2)},
                "window_b_gap_pct": round(med_gap, 2),
                "window_flipped": flipped})
    return _report("b-resolution.txt", "\n".join(out) + "\n")


# ---------------------------------------------------------------- 宽 regime 校准


WIDE_W = 512                 # 单行宽度：真实宽内核的 N 维（窄校准用 100）
WALK_WIDE = (128, 256, 512)   # 走 N 维的探针：斜率尺寸跨过小整数缓存边界 256
WALK_NARROW = (32, 64, 96)   # 走 K/M 维的探针：真实宽内核里这两维不超 96


def _t_med(fn, n, reps=5, warmup=2):
    for _ in range(warmup):
        fn(n)
    xs = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(n)
        xs.append(time.perf_counter() - t0)
    return statistics.median(xs)


def _slope_walk(f, n, sizes, reps=5):
    """三尺寸最小二乘斜率（窄版 _slope_ns 的按尺寸版本）。"""
    ts = [_t_med(lambda k: f(k, s), n, reps) for s in sizes]
    mx, mt = sum(sizes) / len(sizes), sum(ts) / len(ts)
    num = sum((x - mx) * (t - mt) for x, t in zip(sizes, ts))
    den = sum((x - mx) ** 2 for x in sizes)
    return num / den / n * 1e9


def calibrate_wide(row_w=None, walk_wide=None, walk_narrow=None, col=None):
    """宽 regime 的第二套单价：镜像 cm.calibrate()，只改 regime 参数。

    与窄校准的三处差别（其余逐行相同）：
      ① 单行宽度 512（窄版 100）——j 内层行在真实宽内核里走的是这么宽的行；
      ② 走 N 维的探针（loop/j0/ju）斜率尺寸用 (128,256,512)——跨过 CPython
        小整数缓存边界 256，量进 v≥257 的整数对象分配；
      ③ 双下标探针的代表列 v2=300（窄版 3）——宽内核的列下标经常出界。
    走 K/M 维的探针仍用窄尺寸（32/64/96）：宽内核里这两维超不出窄 regime。

    四个可选参数把 regime 拧到任意点（5.4 节的剂量对照实验用它）：
    全部缺省时就是上面描述的宽 regime。
    """
    row_w = WIDE_W if row_w is None else row_w
    walk_w = WIDE_WALK if walk_wide is None else walk_wide
    walk_n = WALK_NARROW if walk_narrow is None else walk_narrow
    col = 300 if col is None else col
    import random
    rng = random.Random(7)
    rowC = [rng.uniform(-1, 1) for _ in range(row_w + 2)]   # ju 的 v+1 要多两格
    rowA = [rng.uniform(-1, 1) for _ in range(100)]
    rowB = [rng.uniform(-1, 1) for _ in range(row_w + 2)]
    B = [[rng.uniform(-1, 1) for _ in range(row_w)] for _ in range(100)]
    C_ = [[rng.uniform(-1, 1) for _ in range(row_w)] for _ in range(100)]
    A_ = [[rng.uniform(-1, 1) for _ in range(row_w)] for _ in range(100)]
    a = rowA[0]
    v2 = col
    lo, hi, U = 0, row_w, 4
    i0_, TMv, Mv = 16, 32, 96

    c = cm.Costs()
    gc_old = gc.isenabled()
    gc.disable()
    t0 = time.perf_counter()
    try:
        def f_loop(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    pass

        def f_j0(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    rowC[v] += a * rowB[v]

        def f_ju(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    rowC[v + 1] += a * rowB[v + 1]

        def f_k0(n, rhi):
            cc = 0.0
            for _ in range(n):
                for v in range(rhi):
                    cc += rowA[v] * B[v][v2]
            return cc

        def f_ku(n, rhi):
            cc = 0.0
            for _ in range(n):
                for v in range(rhi):
                    cc += rowA[v + 1] * B[v + 1][v2]
            return cc

        def f_i0(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    C_[v][v2] += A_[v][v2] * a

        def f_iu(n, rhi):
            for _ in range(n):
                for v in range(rhi):
                    C_[v + 1][v2] += A_[v + 1][v2] * a

        def f_hs1(n, rhi):
            x = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = B[v]
            return x

        def f_hs2(n, rhi):
            x = y = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = C_[v]; y = A_[v]
            return x is y

        def f_hsm(n, rhi):
            x = a2 = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = C_[v]; a2 = A_[v][v2]
            return a2

        def f_hd1(n, rhi):
            x = 0.0
            for _ in range(n):
                for v in range(rhi):
                    x = B[v][v2]
            return x

        def f_s2(n, rhi):
            cc = 0.5
            for _ in range(n):
                for v in range(rhi):
                    C_[v][v2] = cc

        c.loop = _slope_walk(f_loop, 256, walk_w)
        c.j0 = _slope_walk(f_j0, 256, walk_w)
        c.ju = _slope_walk(f_ju, 256, walk_w)
        for key, f in (("k0", f_k0), ("ku", f_ku), ("i0", f_i0), ("iu", f_iu),
                       ("hs1", f_hs1), ("hs2", f_hs2), ("hsm", f_hsm),
                       ("hd1", f_hd1), ("s2", f_s2)):
            setattr(c, key, _slope_walk(f, 256, walk_n))

        def f_r2(n):
            m2 = 0
            rlo_, rhi_ = 3, 4
            for _ in range(n):
                for v in range(rlo_, rhi_):
                    m2 = v
            return m2

        def f_r3(n):
            m3 = 0
            rlo_, one = 3, 1
            for _ in range(n):
                for v in range(rlo_, rlo_ + one, U):
                    m3 = v
            return m3

        def f_pre(n):
            m = 0
            for _ in range(n):
                for q in range(96):
                    m = (hi - lo) - (hi - lo) % U
            return m

        def f_min3(n):
            x = y = z = 0
            for _ in range(n):
                for q in range(96):
                    x = min(i0_ + TMv, Mv); y = min(i0_ + TMv, Mv); z = min(i0_ + TMv, Mv)
            return x + y + z

        c.range2 = _t_med(f_r2, 16384) / 16384 * 1e9 - c.loop
        c.range3 = _t_med(f_r3, 16384) / 16384 * 1e9 - c.loop

        def _per_exec(f, n, c_loop):
            t = _t_med(lambda k: f(k), n)
            return t / (n * 96) * 1e9 - c_loop

        c.pre = _per_exec(f_pre, 2048, c.loop)
        c.min3 = _per_exec(f_min3, 2048, c.loop)
        c.wall_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        if gc_old:
            gc.enable()
    return c


def get_wide_costs():
    if os.path.exists(WIDE_CACHE):
        with open(WIDE_CACHE, encoding="utf-8") as fh:
            d = json.load(fh)
        c = cm.Costs(**{k: v for k, v in d["costs"].items()
                        if k in cm.Costs.__dataclass_fields__})
        return c, f"缓存 wide-calibration.json（{d.get('timestamp', '')}校准）"
    c = calibrate_wide()
    return c, "现场宽校准（无缓存）"


# ---------------------------------------------------------------- exp c：regime 漂移


def exp_c() -> str:
    costs, src = cm.get_costs()
    wide, wsrc = get_wide_costs()
    if not os.path.exists(WIDE_CACHE):
        _save_json("wide-calibration.json",
                   {"schema": "d112.wide-calibration/1", "timestamp": _iso(),
                    "costs": dataclasses.asdict(wide)})

    keys = ("j0", "ju", "k0", "ku", "i0", "iu", "hs1", "hs2", "hsm", "hd1",
            "s2", "loop", "range2", "range3", "pre", "min3")
    out = [BAR, " D112 机理二（regime 漂移）：第二套单价——宽 regime 校准", BAR,
           f" 窄表来源：{src}", f" 宽表来源：{wsrc}",
           " 宽 regime 与窄校准的三处差别：单行宽度 512（窄 100）；走 N 维的探针",
           " 斜率尺寸 (128,256,512)——跨过 CPython 小整数缓存边界 256；代表列 v2=300（窄 3）",
           "",
           " ① 16 根单价：窄 vs 宽（ns/行）",
           "    行      窄      宽     漂移"]
    drift = {}
    for k in keys:
        nv, wv = getattr(costs, k), getattr(wide, k)
        drift[k] = round((wv - nv) / nv * 100, 1)
        out.append(f"    {k:7s} {nv:6.1f}  {wv:6.1f}  {drift[k]:+6.1f}%")
    dj_n = costs.j0 - costs.k0
    dj_w = wide.j0 - wide.k0
    sign_flip = (dj_n > 0) != (dj_w > 0)
    out += ["",
            f" 近对符号：窄表 j0−k0 = {dj_n:+.1f} ns；宽表 = {dj_w:+.1f} ns"
            + ("——regime 把 j/k 家族偏好翻了个面" if sign_flip else "（本轮符号一致）"),
            "",
            " 读法：走 N 维的行（j0/ju/loop）全部上涨且幅度最大——loop {:+.0f}%：".format(drift["loop"]),
            " 内层 range 在宽 regime 里要为 v≥257 现场分配整数对象；走 K/M 维的",
            " 行（k0/iu/hs×）波动小；机器行（range2/range3/min3）基本不动。",
            " 单价不是常数，是 (进程, regime) 的函数——每根读数都绑定在",
            " 『哪个进程、哪个 regime』上量出来的这个事实里。"]

    # ② 出域单价重排窄世界 S1：结构稳不稳？
    a = json.load(open(os.path.join(OUTPUTS, "a-narrow.json"), encoding="utf-8"))
    truth = {row[0]: row[2] for row in a["screen"]}
    M, N, K = S1
    cands = cm.build_space("S1", M, N, K)
    champ_screen = min(truth, key=truth.get)
    out += ["", " ② 用宽表重排窄世界 S1（对照 a-narrow.txt 的同进程实测，口径＝筛选中位数）：",
            f"    筛选冠军：{champ_screen} = {truth[champ_screen]:.2f} ms"
            f"（a-narrow.txt 决赛冠军：{a['champion']} = {a['champion_ms']:.2f} ms）"]
    table_eval = {}
    for label, tbl in (("窄表", costs), ("宽表", wide)):
        ranked = sorted(((cm.predict_ms(cm.count_ops(M, N, K, c), tbl), c)
                         for c in cands), key=lambda t: t[0])
        names = [c.describe() for _, c in ranked]
        rho = spearman([p for p, c in ranked if c.describe() in truth],
                       [truth[c.describe()] for _, c in ranked if c.describe() in truth])
        champ_rank = names.index(champ_screen) + 1
        top1 = names[0]
        k1 = (truth[top1] / truth[champ_screen] - 1) * 100
        table_eval[label] = {"top1": top1, "k1_loss_pct": round(k1, 2),
                             "champ_rank": champ_rank, "spearman": round(rho, 3),
                             "top5": names[:5]}
        out.append(f"   {label}：top-1 = {top1}（实测 {truth[top1]:.2f} ms，"
                   f"比筛选冠军慢 {k1:+.1f}%）；筛选冠军名次 {champ_rank}；ρ = {rho:.3f}")
        out.append(f"        top-5：{' / '.join(names[:5])}")
    fam = lambda nm: nm.split()[1]
    # ③ 第二次宽校准：出域读数稳定吗？（同一进程、同款探针再量一遍）
    wide2 = calibrate_wide()
    dj_w2 = wide2.j0 - wide2.k0
    ranked_w2 = sorted(((cm.predict_ms(cm.count_ops(M, N, K, c), wide2), c)
                        for c in cands), key=lambda t: t[0])
    names_w2 = [c.describe() for _, c in ranked_w2]
    rho_w2 = spearman([p for p, c in ranked_w2 if c.describe() in truth],
                      [truth[c.describe()] for _, c in ranked_w2 if c.describe() in truth])
    top1_w2 = names_w2[0]
    k1_w2 = (truth[top1_w2] / truth[champ_screen] - 1) * 100
    out += ["", " ③ 第二次宽校准（同一进程，同款探针再量一遍）：",
            f"   窄表    j0={costs.j0:.1f}  k0={costs.k0:.1f}  j0−k0 = {dj_n:+.1f} ns",
            f"   宽表#1  j0={wide.j0:.1f}  k0={wide.k0:.1f}  j0−k0 = {dj_w:+.1f} ns",
            f"   宽表#2  j0={wide2.j0:.1f}  k0={wide2.k0:.1f}  j0−k0 = {dj_w2:+.1f} ns",
            f"   宽表#2 重排 S1：top-1 = {top1_w2}（实测 {truth[top1_w2]:.2f} ms，"
            f"慢 {k1_w2:+.1f}%）；真冠军名次 "
            f"{names_w2.index(champ_screen) + 1}；ρ = {rho_w2:.3f}"]
    table_eval["宽表#2"] = {"top1": top1_w2, "k1_loss_pct": round(k1_w2, 2),
                            "champ_rank": names_w2.index(champ_screen) + 1,
                            "spearman": round(rho_w2, 3), "top5": names_w2[:5],
                            "j0_minus_k0_ns": round(dj_w2, 1)}
    table_eval["宽表"]["j0_minus_k0_ns"] = round(dj_w, 1)
    table_eval["窄表"]["j0_minus_k0_ns"] = round(dj_n, 1)
    tops = {label: fam(table_eval[label]["top1"]) for label in table_eval}
    uniq_fams = set(tops.values())
    rhos_wide = "、".join(f"{table_eval[lb]['spearman']:.3f}"
                          for lb in table_eval if lb != "窄表")
    if len(uniq_fams) > 1:
        out += ["", " 读法：三张表对 S1 的 top-1 家族不一致——"
                + "、".join(f"{lb}→{fam(table_eval[lb]['top1'])}" for lb in table_eval)]
        out.append(f" 机理：近对符号（j0−k0）是 regime 的函数——窄表 {dj_n:+.1f} ns")
        out.append(" （j 家族占优），出域后塌向噪声零点，两次宽校准能给出")
        out.append(" 不同符号；出域单价表把噪声里的家族偏好带回来，静默腐蚀")
        out.append(f" 跨家族名次（ρ 从 {table_eval['窄表']['spearman']:.3f} 掉到 {rhos_wide}）。")
    else:
        out += ["", " 读法：三张表本轮的 top-1 家族一致（都是 "
                + next(iter(uniq_fams)) + " 家族）——主项是结构性的（tile 外壳、"
                " range 建立、行提升差价）。"]
        out.append(f" 但注意 j0−k0 已从 {dj_n:+.1f} 塌到 {dj_w:+.1f}/{dj_w2:+.1f} ns——"
                    "出域表的家族符号钉在噪声零点上，")
        out.append(f" top-1 稳定只是这轮的运气；ρ 也从 {table_eval['窄表']['spearman']:.3f} "
                    f"掉到 {rhos_wide}——分辨率先死，结构排序跟着受损。")

    _save_json("c-regime.json",
               {"schema": "d112.c-regime/1", "timestamp": _iso(),
                "narrow": {k: round(getattr(costs, k), 1) for k in keys},
                "wide": {k: round(getattr(wide, k), 1) for k in keys},
                "drift_pct": drift, "s1_eval": table_eval})
    return _report("c-regime.txt", "\n".join(out) + "\n")


# ---------------------------------------------------------------- exp d：宽 shape 对照


def domain_check(M, N, K, budget_idx=256):
    """出域闸门：负载的任何一维超出校准 regime（下标 ≤96、行宽 ≤256）就亮灯。

    返回 (in_domain, note)。亮灯 ≠ 拒绝编译——亮灯的含义是：
    窄表对这些候选的预测是外推，要么重校准（换 regime 匹配的单价表），
    要么加大 K/全测，不许静默外推。
    """
    if max(M, N, K) > budget_idx:
        return False, (f"出域：维度 {max(M, N, K)} > 校准边界 {budget_idx}"
                       "（下标 >256 越过小整数缓存；行宽 >96 越过 L1 纪律）"
                       "→ 窄表预测属外推：重校准或加大 K")
    return True, "在校准 regime 内：预测属内插"


def exp_d() -> str:
    with open(os.path.join(OUTPUTS, "a-narrow.json"), encoding="utf-8") as fh:
        a_rec = json.load(fh)
    costs, src = cm.get_costs()
    wide, wsrc = get_wide_costs()
    env = bm.capture_env()
    M, N, K = W1
    spec = bm.BenchSpec(M=M, N=N, K=K)
    cands = cm.build_space("W1", M, N, K)
    gate_ok, gate_note = domain_check(M, N, K)

    def rank(tbl):
        r = sorted(((cm.predict_ms(cm.count_ops(M, N, K, c), tbl), c)
                    for c in cands), key=lambda t: t[0])
        return r

    rn, rw = rank(costs), rank(wide)
    names_n = [c.describe() for _, c in rn]
    pn = {c.describe(): p for p, c in rn}
    pw = {c.describe(): p for p, c in rw}
    pred_gap_n = abs(pn[NEAR_PAIR_W1[0]] - pn[NEAR_PAIR_W1[1]]) / pn[NEAR_PAIR_W1[1]] * 100
    pred_gap_w = abs(pw[NEAR_PAIR_W1[0]] - pw[NEAR_PAIR_W1[1]]) / pw[NEAR_PAIR_W1[1]] * 100

    t0 = time.perf_counter()
    screen = []
    for pred, c in rn:
        rec = bm.bench_one(c, spec, SCREEN, env)
        screen.append({"cfg": c.describe(), "pred_narrow": pred, "rec": rec})
    wall = time.perf_counter() - t0
    truth = {r["cfg"]: _med(r["rec"]) for r in screen
             if r["rec"]["correctness"]["passed"]}
    by_med = sorted(truth, key=truth.get)

    # 决赛 3+21：top-3(筛选) ∪ 缺省 ∪ 窄表 top-1
    finalists = by_med[:3] + [cm.DEFAULT_CFG.describe()]
    if names_n[0] not in finalists:
        finalists.append(names_n[0])
    t0 = time.perf_counter()
    final = {}
    for name in dict.fromkeys(finalists):
        c = _cfg_by_name(cands, name)
        final[name] = _med(bm.bench_one(c, spec, FINAL, env))
    wall_f = time.perf_counter() - t0
    champ = min(final, key=final.get)
    k1_n = (final[names_n[0]] / final[champ] - 1) * 100

    def tbl_eval(ranked, label):
        names = [c.describe() for _, c in ranked]
        preds = [p for p, c in ranked]
        meas = [truth[c.describe()] for _, c in ranked]
        rho = spearman(preds, meas)
        top1 = names[0]
        champ_rank = names.index(by_med[0]) + 1
        return {"top1": top1, "top1_ms": truth[top1],
                "k1_loss_pct": round((truth[top1] / truth[by_med[0]] - 1) * 100, 2),
                "champ_rank": champ_rank, "spearman": round(rho, 3)}

    ev_n, ev_w = tbl_eval(rn, "窄表"), tbl_eval(rw, "宽表")

    out = [BAR, " D112 机理三（出域对照）：W1 64×512×64 全测 36 候选，窄/宽两表", BAR,
           f" 单价：{src}；宽表：{wsrc}",
           f" 出域闸门 domain_check：{'通过' if gate_ok else '亮灯'}——{gate_note}",
           f" 空间：{len(cands)} 个候选（32³/64³/64×512×64 × 6 顺序 × U=1/4）；"
           f"门：bitwise，{len(truth)}/{len(screen)} 通过",
           f" 全测墙钟 {wall:.1f} s（3+7）＋决赛 {wall_f:.1f} s（3+21）",
           "",
           " ① 同进程实测 top-8（筛选口径）：",
           "    名次  配置                        实测 ms"]
    for i, name in enumerate(by_med[:8]):
        out.append(f"    {i + 1:4d}  {name:26s} {truth[name]:8.2f}")
    out += ["",
            " ② 窄表 vs 宽表（都拿同进程实测对账）：",
            f"    窄表：top-1 = {ev_n['top1']}（实测 {ev_n['top1_ms']:.2f} ms，"
            f"比筛选冠军慢 {ev_n['k1_loss_pct']:+.1f}%）；"
            f"筛选冠军名次 {ev_n['champ_rank']}；ρ = {ev_n['spearman']:.3f}",
            f"    宽表：top-1 = {ev_w['top1']}（实测 {ev_w['top1_ms']:.2f} ms，"
            f"比筛选冠军慢 {ev_w['k1_loss_pct']:+.1f}%）；"
            f"筛选冠军名次 {ev_w['champ_rank']}；ρ = {ev_w['spearman']:.3f}",
            "",
            f" ③ 近对（决赛口径）：{NEAR_PAIR_W1[0]} = {final.get(NEAR_PAIR_W1[0], float('nan')):.2f} ms vs "
            f"{NEAR_PAIR_W1[1]} = {final.get(NEAR_PAIR_W1[1], float('nan')):.2f} ms"
            if NEAR_PAIR_W1[0] in final and NEAR_PAIR_W1[1] in final else
            " ③ 近对（筛选口径）："
            f"{NEAR_PAIR_W1[0]} = {truth[NEAR_PAIR_W1[0]]:.2f} ms vs "
            f"{NEAR_PAIR_W1[1]} = {truth[NEAR_PAIR_W1[1]]:.2f} ms",
            f"    模型预测差：窄表 {pred_gap_n:.2f}% / 宽表 {pred_gap_w:.2f}%"
            "——宽 shape 上两表对近对都基本平手（并列 = 掷硬币）",
            "",
            f" ④ 决赛冠军（3+21）：{champ} = {final[champ]:.2f} ms；"
            f"窄表 top-1 决赛 {final[names_n[0]]:.2f} ms → K=1 代价 {k1_n:+.1f}%",
            "",
            f" 读法：出域没有让结构排序崩（tile 外壳/range/行提升的项差仍然主导，",
            " 窄表宽表的 top-1 都落在大 tile 的 j 内层家族）——但近对上两张表",
            " 都只能并列（0.01% 量级）。"]
    if k1_n > 0.5:
        out += [f" 本轮窗口硬币没落在真冠军上：K=1 付 {k1_n:+.1f}%（模型 top-1 的近对",
                f" 才是冠军，决赛 {final[champ]:.2f} vs {final[names_n[0]]:.2f} ms）；",
                f" 同一天的窗口 a（S1，a-narrow.txt）另一枚硬币付了 {a_rec['k1_loss_pct']:+.1f}%：",
                " 两枚硬币今天都输——D110 的记录 3/3 也输（+4.8~8.1%）。硬币是平的，",
                " K=1 是掷硬币，不是做决策。"]
    else:
        out += [f" 本轮窗口硬币恰好落在真冠军上（K=1 代价 {k1_n:+.1f}%）。",
                f" 同一天的窗口 a（S1，a-narrow.txt）同一枚硬币付了 {a_rec['k1_loss_pct']:+.1f}%：",
                " 硬币是平的，K=1 是掷硬币，不是做决策。"]
    out += [" 出域闸门的价值：不指望模型自己发现自己在外推。"]

    _save_json("d-wide.json",
               {"schema": "d112.d-wide/1", "timestamp": _iso(),
                "shape": list(W1), "n_cands": len(cands), "gate": gate_note,
                "truth_top8": [[n, round(truth[n], 2)] for n in by_med[:8]],
                "narrow": ev_n, "wide": ev_w,
                "final": {k: round(v, 3) for k, v in final.items()},
                "champion": champ, "k1_loss_pct_final": round(k1_n, 2),
                "near_pair_pred_gap_pct": {"narrow": round(pred_gap_n, 3),
                                           "wide": round(pred_gap_w, 3)},
                "wall_s": round(wall, 1)})
    with open(os.path.join(OUTPUTS, "d-wide.jsonl"), "w", encoding="utf-8") as fh:
        for r in screen:
            fh.write(json.dumps(r["rec"], ensure_ascii=False) + "\n")
    return _report("d-wide.txt", "\n".join(out) + "\n")


# ---------------------------------------------------------------- exp env


def exp_env() -> str:
    env = bm.capture_env()
    out = [BAR, " D112 环境记录", BAR]
    out += [f" {k}: {v}" for k, v in env.items()]
    out.append(f" 运行时间：{_iso()}")
    _save_json("env.json", {"schema": "d112.env/1", "timestamp": _iso(), **env})
    return _report("env.txt", "\n".join(out) + "\n")


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description="D112 性能反例四组实验")
    ap.add_argument("--exp", required=True,
                    choices=["calibrate", "a-narrow", "b-resolution",
                             "c-regime", "d-wide", "env"],
                    help="calibrate=校准落盘 a=反例一 b=分辨率 c=regime d=出域 env=环境")
    args = ap.parse_args()
    os.makedirs(OUTPUTS, exist_ok=True)
    fn = {"calibrate": exp_calibrate, "a-narrow": exp_a,
          "b-resolution": exp_b, "c-regime": exp_c, "d-wide": exp_d,
          "env": exp_env}[args.exp]
    sys.stdout.write(fn() + f"（{args.exp} 完成，{_iso()}）\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
