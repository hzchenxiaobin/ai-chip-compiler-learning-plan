#!/usr/bin/env python3
"""D111 第四阶段集成验收：从 mini.matmul 到冠军的一条命令。

第四阶段（D85~D112）的每一站都各自验收过；今天把它们串成一条流水线：

    S0 前端     mini 图 IR 解析（shape 推断＋语义校验；记法沿用 D53~D57）
    S1 Lowering 循环生成计划（D85~D90 任务单，由 kernel_gen.py 实现）
    S2 空间     候选生成（D106 值域剪枝：tile 池∩维度 ∪ 精确 tile × 6 顺序 × U）
    S3 闸门     资源过滤（D104 五项记账 ≤ 256 KiB 片上预算）
    S4 模型     Cost Model 预筛（D110：count_ops × 校准单价，零内核执行）
    S5 实测     编译 → 正确性门 → Benchmark（D107 协议；D108 的 top-K＋决赛）

血统纪律（D109 立的规矩）：kernel_gen.py / bench.py / cost_model.py 是 D110
（＝D108）的逐字节副本，今天零改动——集成日改被集成的模块，等于验收自己
刚改过的东西。D108 记录与 D109 探针 sha256 由 cost_model.py 的常量钉死。

用法：
    python3 pipeline.py --exp calibrate            # 校准落盘（全部报告共享）
    python3 pipeline.py --exp tune --ir inputs/matmul-bias-s1-64x64x64.mini
    python3 pipeline.py --ir inputs/xxx.mini       # --exp tune 的简写
    python3 pipeline.py --exp accept               # 验收实验（全测对照＋投毒＋一致性）
    python3 pipeline.py --exp self-test            # 断言自检
    python3 pipeline.py --exp env                  # 环境记录
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import os
import re
import sys
import time

from kernel_gen import KernelConfig, kernel_source, make_kernel
from bench import BenchSpec, Protocol, bench_one, capture_env, iso_now
import cost_model as cm

BAR = "=" * 78
HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "inputs")
OUTPUTS = os.path.join(HERE, "outputs")
RESULTS_PATH = os.path.join(OUTPUTS, "tune-results.jsonl")
SUMMARY_PATH = os.path.join(OUTPUTS, "tune-summary.json")
SCHEMA = "d111.tune-result/1"
SCHEMA_SUM = "d111.tune-summary/1"

SCREEN_PROTO = Protocol(warmup=3, repeats=7)     # D107/D108 筛选段同款
FINAL_PROTO = Protocol()                          # 3+21，决赛段同款
TOP_K = 5                                         # 模型预筛名额（D110 结论：≥2）
N_FINALISTS = 3                                   # 决赛名额（∪ 缺省）
DEFAULT_CFG = KernelConfig(32, 32, 32, "ijk", 1)  # 缺省候选：不调优也能跑

# ---- 空间口径（D106 的值域纪律，按 D111 的可测轴收窄）----
CURATED_TAIL_POOL = (32, 64, 96, 128, 160, 256)   # D106 CURATED_TAIL_POOL 原样
UNROLLS = (1, 2, 4)        # D110 展开税的账：U=8/16 在 CPython 只会垫底，不进池
ORDERS = tuple("".join(p) for p in itertools.permutations("ijk"))

# ---- 资源闸门口径（D104 五项记账，D111 的可测参数）----
DTYPE_BYTES = 4             # fp32（与 mini IR 声明、D104 记账一致）
ALIGN = 32                  # D104 默认对齐网格
BUDGET = 256 * 1024         # 片上预算 256 KiB（D104/D106 同款）


# ================================================================ S0 前端

class MiniError(SystemExit):
    """mini IR 解析/校验失败：带出错的行号与原因，fail-closed。"""


_FUNC_RE = re.compile(
    r"^func\s+@(\w+)\s*\((.*)\)\s*->\s*tensor<([\dx]+)xf32>\s*\{$")
_ARG_RE = re.compile(r"^%(\w+):\s*tensor<([\dx]+)xf32>$")
_OP_RE = re.compile(
    r"^%(\w+)\s*=\s*(mini\.\w+)\s+([%\w\s,]+?)\s*:\s*\(([\dx\s,]+?)\)"
    r"\s*->\s*([\dx]+)(.*)$")
_RET_RE = re.compile(r"^return\s+%(\w+)\s*:\s*tensor<([\dx]+)xf32>$")


def _shape(text):
    """'64x96' -> (64, 96)；非法则 None。"""
    try:
        return tuple(int(x) for x in text.split("x"))
    except ValueError:
        return None


@dataclasses.dataclass(frozen=True)
class MiniOp:
    result: str
    name: str          # mini.matmul / mini.add
    operands: tuple    # 形参名（去 %）
    ins: tuple         # 声明输入 shape
    out: tuple         # 声明输出 shape
    note: str


@dataclasses.dataclass(frozen=True)
class MiniProgram:
    """解析后的 mini 图 IR：函数签名＋算子序列＋推导出的工作负载。"""
    func: str
    args: dict         # 名 -> shape
    ret_shape: tuple
    ops: tuple
    path: str = ""

    @property
    def M(self):
        return self.workload()[1]

    def workload(self):
        """(op, M, N, K, dtype)。语义校验在这里做（D43 的 shape 推断纪律）。"""
        if len(self.ops) != 2 or self.ops[0].name != "mini.matmul" \
                or self.ops[1].name != "mini.add":
            raise MiniError(
                f"只支持『mini.matmul → mini.add bias 广播』的融合负载"
                f"（D53 的算子组）：实际算子序列 "
                f"{[op.name for op in self.ops]}")
        mm, add = self.ops
        # ---- mini.matmul：(M,K) × (K,N) -> (M,N)，K 必须咬合
        (am, ak), (bk, bn) = mm.ins
        if ak != bk:
            raise MiniError(f"mini.matmul 形状不咬合：A 的 K={ak} ≠ B 的 K={bk}")
        if mm.out != (am, bn):
            raise MiniError(f"mini.matmul 声明输出 {mm.out} ≠ 推导 {(am, bn)}")
        # ---- mini.add：bias (N,) 行广播到 (M,N)
        (lm, ln), (bw,) = add.ins
        if (lm, ln) != (am, bn):
            raise MiniError(f"mini.add 左操作数 {(lm, ln)} ≠ matmul 输出 {(am, bn)}")
        if bw != bn:
            raise MiniError(f"mini.add bias 长度 {bw} ≠ N={bn}（行广播要求）")
        if "broadcast" not in add.note:
            raise MiniError("mini.add 需要『broadcast row』标注（bias 行广播语义）")
        if add.out != (am, bn):
            raise MiniError(f"mini.add 声明输出 {add.out} ≠ 推导 {(am, bn)}")
        # ---- return 与签名
        if self.ret_shape != (am, bn):
            raise MiniError(f"return 类型 {self.ret_shape} ≠ 推导 {(am, bn)}")
        return "matmul_bias", am, bn, ak, "fp32"


def parse_mini(path: str) -> MiniProgram:
    """mini 图 IR 文本 → MiniProgram。逐行解析，fail-closed。"""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().splitlines()

    func = None
    args = {}
    ops = []
    ret = None
    opened = False
    for no, line in enumerate(raw, 1):
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        if not opened:
            m = _FUNC_RE.match(s)
            if not m:
                raise MiniError(f"{os.path.basename(path)}:{no} 期待 func 头，得到：{s}")
            fname, argtext, rettext = m.groups()
            for piece in argtext.split(","):
                am = _ARG_RE.match(piece.strip())
                if not am:
                    raise MiniError(f"{os.path.basename(path)}:{no} 形参格式不对：{piece.strip()}")
                shp = _shape(am.group(2))
                if not shp or len(shp) > 2 or any(d < 1 for d in shp):
                    raise MiniError(f"{os.path.basename(path)}:{no} 形参 shape 非法：{am.group(2)}")
                args[am.group(1)] = shp
            rs = _shape(rettext)
            if not rs or len(rs) != 2:
                raise MiniError(f"{os.path.basename(path)}:{no} 返回 shape 非法：{rettext}")
            ret_shape = rs
            func = fname
            opened = True
            continue
        if s == "}":
            opened = False
            continue
        m = _RET_RE.match(s)
        if m:
            ret = m.group(1)
            if _shape(m.group(2)) != ret_shape:
                raise MiniError(f"{os.path.basename(path)}:{no} return 类型与签名不符")
            continue
        m = _OP_RE.match(s)
        if not m:
            raise MiniError(f"{os.path.basename(path)}:{no} 无法解析的行：{s}")
        res, name, opstext, instext, outtext, note = m.groups()
        operands = tuple(x.strip().lstrip("%") for x in opstext.split(","))
        for op_name in operands:
            if op_name not in args and op_name not in {o.result for o in ops}:
                raise MiniError(f"{os.path.basename(path)}:{no} 操作数 %{op_name} 未定义")
        ins = tuple(_shape(x.strip()) for x in instext.split(","))
        out = _shape(outtext)
        if None in ins or out is None:
            raise MiniError(f"{os.path.basename(path)}:{no} shape 格式非法：{s}")
        if len(ins) != len(operands):
            raise MiniError(f"{os.path.basename(path)}:{no} 声明 shape 数 {len(ins)} ≠ 操作数 {len(operands)}")
        ops.append(MiniOp(res, name, operands, ins, out, note.strip().lstrip(",").strip()))
    if func is None:
        raise MiniError(f"{os.path.basename(path)} 没有 func 定义")
    if ret is None:
        raise MiniError(f"{os.path.basename(path)} 没有 return")
    if ret not in {o.result for o in ops}:
        raise MiniError(f"{os.path.basename(path)} return 的 %{ret} 不是任何算子的结果")
    # dtype 口径：本流水线的记账（D104 五项）与内核（CPython float）按 fp32 名义
    if "f32" not in raw[0] and any("xf16" in ln or "xbf16" in ln for ln in raw):
        raise MiniError("只支持 f32：五项记账与内核口径均为 fp32（D104）")
    prog = MiniProgram(func=func, args=args, ret_shape=ret_shape, ops=tuple(ops),
                       path=os.path.basename(path))
    prog.workload()          # 语义校验在解析时就做（fail-closed，D43 纪律）
    return prog


def shape_id_of(M, N, K):
    """对照 D108 的 shape 表：有基线的用同名 id，新 shape 标记 N。"""
    for sid, mm, nn, kk in cm.SHAPES:
        if (mm, nn, kk) == (M, N, K):
            return sid, True
    return f"N{M}x{N}x{K}", False


# ================================================================ S1 Lowering

def lowering_check(cfg: KernelConfig, M: int, N: int, K: int):
    """循环生成的结构证据：D85~D90 任务单里的每一项，在生成源码里找得到吗？

    语义证据不由这里给——每个被实测的候选都要过 bitwise 正确性门，
    门过了才说明『初始化＋循环＋写回』整条 lowering 语义正确。
    """
    src = kernel_source(cfg)
    d3 = cfg.order[-1]
    n_tiles = ((M + cfg.tm - 1) // cfg.tm) * ((N + cfg.tn - 1) // cfg.tn) \
        * ((K + cfg.tk - 1) // cfg.tk)
    clamps_bind = (M % cfg.tm or N % cfg.tn or K % cfg.tk) and n_tiles > 1
    store_pat = (re.search(r"C\[v\d\]\[v\d\] = c", src) is not None
                 if d3 == "k" else "+=" in src)
    items = [
        ("tile 外壳三重循环（D88）",
         all(f"for {v}0 in range" in src for v in "ijk")),
        ("边界钳制 min(i0+TM, M)（D90）",
         "min(i0 + TM, M)" in src and "min(j0 + TN, N)" in src and "min(k0 + TK, K)" in src),
        ("元素级 v1/v2/v3 循环（D88/D89）",
         "for v1 in range" in src and "for v2 in range" in src and "for v3 in range" in src),
        ("展开前奏 n = (hi-lo)-(hi-lo)%U（D96）",
         "n = " in src),
        ("尾部循环 range(lo+n, hi)（D95/D96）",
         re.search(r"for v3 in range\(\w+ \+ n,", src) is not None),
        ("累加/写回语句（D89 的 store）", bool(store_pat)),
    ]
    return items, n_tiles, clamps_bind, src


# ================================================================ S2+S3 空间与闸门

def align_up(n: int, a: int = ALIGN) -> int:
    return (n + a - 1) // a * a


def tile_bytes(tm: int, tn: int, tk: int):
    """D104 五项记账（D111 可测口径：fp32、single 缓冲、无 staging）：
    A=tm·tk、B=tk·tn、C=tm·tn、bias=tn，逐项 align_up 到 32B 网格。
    buffering/dtype 轴 kernel_gen 测不到（D108 的决定），不进配置。
    """
    d = DTYPE_BYTES
    a = align_up(tm * tk * d)
    b = align_up(tk * tn * d)
    c = align_up(tm * tn * d)
    bias = align_up(tn * d)
    return a + b + c + bias, (a, b, c, bias)


@dataclasses.dataclass
class SpaceStats:
    naive: int = 0
    raw: int = 0
    n_param_pruned: int = 0
    n_resource_pruned: int = 0
    survivors: int = 0
    tile_combos: int = 0
    param_examples: list = dataclasses.field(default_factory=list)
    resource_examples: list = dataclasses.field(default_factory=list)
    max_bytes: int = 0
    max_cfg: tuple = ()


def param_violation(cfg: KernelConfig):
    """跨轴参数约束（D106）：U > 最内层圈数 = 主循环 0 圈的死代码。"""
    inner = {"i": cfg.tm, "j": cfg.tn, "k": cfg.tk}[cfg.order[-1]]
    if cfg.unroll > inner:
        return f"U={cfg.unroll} > 最内层 {cfg.order[-1]} 的圈数 {inner}（死代码）"
    return None


def build_space(M: int, N: int, K: int, budget: int = BUDGET):
    """S2 值域剪枝 + 跨轴参数约束 + S3 资源闸门 → 幸存候选＋漏斗账本。"""
    pools = {d: [t for t in CURATED_TAIL_POOL if t <= dim]
             for d, dim in (("m", M), ("n", N), ("k", K))}
    combos = set(itertools.product(pools["m"], pools["n"], pools["k"]))
    combos.add((M, N, K))                      # 精确 tile（D108：单 tile 无外壳开销）
    combos = sorted(combos)

    st = SpaceStats()
    st.naive = M * N * K * len(ORDERS) * 16 * 2      # D106 naive_count 同式
    st.tile_combos = len(combos)
    st.raw = len(combos) * len(ORDERS) * len(UNROLLS)
    survivors = []
    for (tm, tn, tk) in combos:
        total, _parts = tile_bytes(tm, tn, tk)
        if total > st.max_bytes:
            st.max_bytes, st.max_cfg = total, (tm, tn, tk)
        for order in ORDERS:
            for u in UNROLLS:
                cfg = KernelConfig(tm, tn, tk, order, u)
                why = param_violation(cfg)          # 跨轴参数约束（D106）
                if why:
                    st.n_param_pruned += 1
                    if len(st.param_examples) < 3:
                        st.param_examples.append((cfg.describe(), why))
                    continue
                if total > budget:               # 资源闸门（D104）
                    st.n_resource_pruned += 1
                    if len(st.resource_examples) < 3:
                        st.resource_examples.append(
                            (f"{tm}×{tn}×{tk} {order} U={u}",
                             f"五项合计 {total:,} B 超预算 {total - budget:,} B"))
                    continue
                survivors.append(KernelConfig(tm, tn, tk, order, u))
    st.survivors = len(survivors)
    return survivors, st


# ================================================================ S4 模型预筛

def rank_by_model(M, N, K, cands, costs):
    """D110 Cost Model：count_ops × 单价 → 预测毫秒排序（零内核执行）。"""
    t0 = time.perf_counter()
    ranked = sorted(((cm.predict_ms(cm.count_ops(M, N, K, cfg), costs), cfg)
                     for cfg in cands), key=lambda t: t[0])
    ms = (time.perf_counter() - t0) * 1000.0
    return ranked, ms


TIE_EPS = 0.005       # 并列地带的展示阈值（预测差 <0.5% 视为模型分不出）


def select_topk(ranked, top_k):
    """top-K 名额：每个 (order,U) 家族只留预测最优的一个 tile 变体。

    动机（今天集成的真实发现）：tile 外壳开销摊薄后，同家族不同 tile 的预测趋同
    ——S2 的模型前 9 名全是 ikj U=1 的 tile 变体（极差 0.08%），近对 kij 被挤到
    第 10 名进不了名额。D110 的账说模型对近对的分辨率就是它自己的误差棒
    （+10~23%），同家族 tile 变体的差别更埋在误差棒里——模型分不出的差别，
    不该占用 recall@K 的名额。家族 = (循环顺序, 展开份数)：它决定内层语句
    家族与展开税，是语句行模型的真正分辨对象。
    返回 [(名次, 预测, cfg), ...]。
    """
    picked = []
    for rank, (pred, cfg) in enumerate(ranked, 1):
        if len(picked) >= top_k:
            break
        if not any(cfg.order == p.order and cfg.unroll == p.unroll
                   for _, _, p in picked):
            picked.append((rank, pred, cfg))
    return picked


# ================================================================ S5 编译＋验证＋实测

def compile_timed(cfg: KernelConfig):
    """编译（exec 生成源码）单独计时——『编译』是链路上被记账的一站。"""
    t0 = time.perf_counter()
    kernel = make_kernel(cfg)
    return kernel, (time.perf_counter() - t0) * 1000.0


def _decorate(rec, sid, stage, pred_ms, compile_ms, rank):
    rec = dict(rec)
    rec["schema"] = SCHEMA
    rec["d111"] = {"shape_id": sid, "stage": stage,
                   "model_pred_ms": round(pred_ms, 3) if pred_ms == pred_ms else None,
                   "compile_ms": round(compile_ms, 3), "model_rank": rank}
    return rec


def _append_jsonl(path, rec):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()


def _fmt_b(n):
    return f"{n:,} B"


# ================================================================ 主流程

def run_tune(path: str, top_k: int = TOP_K, verbose: bool = True,
             results_path: str | None = None, costs=None, calib_note: str = ""):
    """一条命令的完整流水线：mini 文本 → 冠军＋账本。返回 (report, summary)。"""
    env = capture_env()
    t_wall0 = time.perf_counter()

    # ---- S0 前端
    t0 = time.perf_counter()
    prog = parse_mini(path)
    op, M, N, K, dtype = prog.workload()
    parse_ms = (time.perf_counter() - t0) * 1000.0
    sid, has_base = shape_id_of(M, N, K)

    # ---- S1 Lowering 证据（拿缺省配置当样本）
    items, n_tiles, clamps_bind, _src = lowering_check(DEFAULT_CFG, M, N, K)

    # ---- S2+S3 空间与闸门
    t0 = time.perf_counter()
    cands, st = build_space(M, N, K)
    space_ms = (time.perf_counter() - t0) * 1000.0

    # ---- S4 模型预筛
    if costs is None:
        costs, calib_note = cm.get_costs()
    ranked, model_ms = rank_by_model(M, N, K, cands, costs)
    per_cand_us = model_ms / len(cands) * 1000.0 if cands else 0.0

    # ---- S5 编译＋验证＋实测
    spec = BenchSpec(M=M, N=N, K=K, seed=42)
    screen, screen_rows = [], []
    compile_ms_sum = 0.0
    bench_wall = 0.0
    for rank, pred, cfg in select_topk(ranked, top_k):
        kernel, cms = compile_timed(cfg)
        compile_ms_sum += cms
        rec = bench_one(cfg, spec, SCREEN_PROTO, env, kernel=kernel)
        bench_wall += rec["wall_ms"]
        if results_path:
            _append_jsonl(results_path, _decorate(rec, sid, "screen", pred, cms, rank))
        if rec["correctness"]["passed"]:
            screen.append((cfg, rec["stats_ms"]["median"], pred, rank))
        screen_rows.append((rank, cfg, pred, rec))

    screen.sort(key=lambda t: t[1])
    want = [c for c, *_ in screen[:N_FINALISTS]]
    if DEFAULT_CFG not in want and DEFAULT_CFG in cands:
        want.append(DEFAULT_CFG)
    final_rows = []
    final = []
    for cfg in want:
        pred = next((p for c, _, p, _ in screen if c == cfg), float("nan"))
        rank = next((r for c, _, _, r in screen if c == cfg), None)
        kernel, cms = compile_timed(cfg)
        compile_ms_sum += cms
        rec = bench_one(cfg, spec, FINAL_PROTO, env, kernel=kernel)
        bench_wall += rec["wall_ms"]
        if results_path:
            _append_jsonl(results_path, _decorate(rec, sid, "final", pred, cms, rank))
        if rec["correctness"]["passed"]:
            final.append((cfg, rec["stats_ms"]["median"]))
        final_rows.append((cfg, rec))
    final.sort(key=lambda t: t[1])
    champ_cfg, champ_ms = final[0]
    wall_ms = (time.perf_counter() - t_wall0) * 1000.0

    # ---- D108 基线对照（有基线的 shape；跨进程，只作参考）
    d108_line = ""
    d108_champ, d108_ms, agree = None, None, None
    measured_cfgs = [r[1] for r in screen_rows] + [c for c, _ in final_rows]
    if has_base:
        records = cm.load_d108()
        truth = cm.stage_truth(records, "final")
        base = sorted(truth[sid], key=lambda t: t[1])
        d108_champ, d108_ms = base[0][0].describe(), base[0][1]
        agree = champ_cfg == base[0][0]
        if agree:
            verdict = "同一配置"
        elif base[0][0] in measured_cfgs:
            verdict = ("不同配置：D108 冠军也实测了、同进程输了——近对次序随机器"
                       "状态互换（D107 漂移 ~8.6%，D110 同款现象）")
        else:
            verdict = ("不同配置：D108 冠军没进模型 top-5 名额（并列扎堆挤掉了近对，"
                       "见 S4 提示行）——recall@K 的多样性缺口，D112 复盘的素材")
        d108_line = f"D108 全测冠军 {d108_champ} = {d108_ms:.2f} ms → {verdict}"
        base_wall = cm.screen_wall_ms(records)[sid] + cm.final_wall_ms(records)[sid]
    else:
        base_wall = None

    # ---- 报告
    L = [BAR, f" D111 集成调优：{prog.path} → 一条流水线跑完 S0~S5", BAR,
         f" 环境：Python {env['python']}（{env['implementation']}），{env['system']}/{env['machine']}",
         f" 协议：screen {SCREEN_PROTO.describe()} / final {FINAL_PROTO.describe()}"
         f" / 门 = bitwise",
         f" 单价来源：{calib_note}", ""]

    L.append(f" [S0 前端] mini 图 IR 解析（{parse_ms:.1f} ms）")
    L.append(f"   func @{prog.func}：mini.matmul(A {M}x{K}, B {K}x{N}) -> {M}x{N}")
    L.append(f"              mini.add(mm, bias {N}) 广播 -> {M}x{N}   语义校验 ✓")
    L.append(f"   工作负载：{op} {M}×{N}×{K}（M×N×K），dtype {dtype}，"
             f"名义 FLOPs 2MNK = {2 * M * N * K:,}")
    L.append(f"   shape id：{sid}（{'有 D108 基线' if has_base else '新 shape，本次首测'}）")
    L.append("")

    L.append(" [S1 Lowering] 循环生成计划（D85~D90 任务单，kernel_gen 实现）")
    L.append("   输出初始化(D87)：C 以 bias 预填（alloc_c）—— mini.add 的落点")
    L.append(f"   tile 外壳(D88)＋边界钳制(D90)：缺省配置下 {n_tiles} 个 tile，"
             f"min 钳制{'咬合：' if clamps_bind else '不咬合（'}"
             f"{'维度对 tile 有余数' if clamps_bind else f'{M}/{N}/{K} 对 32 均整除'}"
             f"{'' if clamps_bind else '）'}")
    L.append("   循环体(D89)：load/mul/add/store，按最内层变量分六家族（D92）；"
             "展开(D96)：主循环步长 U＋尾部循环")
    ok_all = True
    for name, ok in items:
        ok_all &= ok
        L.append(f"     {'✓' if ok else '✗'} {name}")
    L.append("   语义证据：每个被实测候选过 bitwise 门（结构证据＋语义证据合龙）")
    L.append("")

    L.append(" [S2 候选空间] D106 值域剪枝")
    pm = [t for t in CURATED_TAIL_POOL if t <= M]
    pn = [t for t in CURATED_TAIL_POOL if t <= N]
    pk = [t for t in CURATED_TAIL_POOL if t <= K]
    L.append(f"   tile 池：M{pm} × N{pn} × K{pk} ∪ 精确 tile = {st.tile_combos} 组合；"
             f"顺序 {len(ORDERS)} 种；展开 U∈{UNROLLS}")
    L.append(f"   原始空间 {st.raw}（naive 枚举上限 {st.naive:,}：值域剪枝在生成之前"
             f"就砍掉 {st.naive - st.raw:,} 个，剩 {(st.raw / st.naive) * 100:.4f}%）")
    L.append("")

    L.append(f" [S3 资源闸门] D104 五项记账 ≤ {_fmt_b(BUDGET)}"
             f"（fp32·single·无 staging；{space_ms:.1f} ms）")
    L.append(f"   参数约束剪 {st.n_param_pruned}；资源剪 {st.n_resource_pruned}；"
             f"幸存 {st.survivors}")
    L.append(f"   最大占用 tile {st.max_cfg} = {_fmt_b(st.max_bytes)}"
             f"（占预算 {st.max_bytes / BUDGET * 100:.1f}%）")
    for name, why in st.resource_examples:
        L.append(f"     ✗ {name}：{why}")
    L.append("")

    L.append(" [S4 模型预筛] D110 Cost Model（零内核执行）")
    L.append(f"   {len(cands)} 个候选静态排序 {model_ms:.0f} ms"
             f"（{per_cand_us:.0f} µs/候选）→ 只实测 top-{top_k}")
    L.append(f"   名额规则：每个 (order,U) 家族只留预测最优的 tile 变体"
             f"（同家族差别埋在模型误差棒里）")
    L.append("            ——模型分不出的候选不占名额，把机会让给别的家族（recall@K）")
    for rank, pred, cfg in select_topk(ranked, top_k):
        L.append(f"     {rank:>2}. {cfg.describe():<26} 预测 {pred:7.1f} ms")
    tie_spread = (ranked[top_k - 1][0] - ranked[0][0]) / ranked[0][0] * 100 \
        if len(ranked) >= top_k else 0.0
    if tie_spread < 1.0:
        L.append(f"   ⚠ 并列地带：模型前 {top_k} 名的预测极差只有 {tie_spread:.1f}%"
                 f"（含被代表的家族兄弟）")
        L.append("     ——模型在这个地带没有分辨率，名次只能由同进程实测定")
    L.append("")

    L.append(" [S5 编译＋验证＋实测] D107 协议（门先于计时）")
    L.append(f"   编译（exec 生成源码）：{top_k + len(want)} 次，"
             f"合计 {compile_ms_sum:.1f} ms")
    L.append("   screen（3+7 过门）：" + "  ".join(
        f"{r[1].describe()}={'%.2f' % r[3]['stats_ms']['median'] if r[3]['correctness']['passed'] else 'REJECTED'}"
        for r in screen_rows))
    L.append("   final（3+21）：" + "  ".join(
        f"{c.describe()}={'%.2f' % rec['stats_ms']['median'] if rec['correctness']['passed'] else 'REJECTED'}"
        for c, rec in final_rows))
    L.append("")
    L.append(f"   冠军：{champ_cfg.describe()} = {champ_ms:.2f} ms"
             f"（缺省 {DEFAULT_CFG.describe()} 见决赛行）")
    if d108_line:
        L.append(f"   基线对照：{d108_line}")
    else:
        L.append("   基线对照：无 D108 基线（新 shape，本次为首次实测）")

    L.append("")
    L.append(f" [账本] 解析 {parse_ms:.1f} + 空间/闸门 {space_ms:.1f} + "
             f"模型 {model_ms:.0f} + 编译 {compile_ms_sum:.1f} + "
             f"实测 Σwall {bench_wall:.0f} = {wall_ms:.0f} ms（本进程全程）")
    if base_wall:
        L.append(f"        D108 全测基线 Σwall = {base_wall:.0f} ms（跨进程参考）→ "
                 f"提速 {base_wall / bench_wall:.1f}×；"
                 f"实测 {len(screen_rows) + len(final_rows)} 个 vs 基线全测")
    report = "\n".join(L)

    measured_all = {c.describe(): ms for c, ms, _, _ in screen}
    measured_all.update({c.describe(): ms for c, ms in final})
    summary = {
        "schema": SCHEMA_SUM,
        "input": prog.path,
        "shape_id": sid, "M": M, "N": N, "K": K,
        "has_d108_base": has_base,
        "n_space_raw": st.raw, "n_naive": st.naive,
        "n_param_pruned": st.n_param_pruned, "n_resource_pruned": st.n_resource_pruned,
        "n_survivors": st.survivors,
        "model_ms": round(model_ms, 1),
        "model_top5": [cfg.describe() for _, _, cfg in select_topk(ranked, top_k)],
        "champion": champ_cfg.describe(), "champion_ms": champ_ms,
        "measured_detail": sorted(measured_all.items(), key=lambda t: t[1]),
        "measured": len(screen_rows) + len(final_rows),
        "bench_wall_ms": round(bench_wall, 1),
        "wall_ms": round(wall_ms, 1),
        "d108_champion": d108_champ, "d108_champion_ms": d108_ms, "agree": agree,
        "timestamp": iso_now(),
    }
    if verbose:
        print(report)
    return report, summary


def save_summary(summary: dict):
    """追加式汇总：tune-summary.json（load-modify-save，跨 shape 共享）。"""
    data = {"schema": SCHEMA_SUM, "runs": []}
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    data["runs"] = [r for r in data["runs"] if r.get("input") != summary["input"]]
    data["runs"].append(summary)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


# ================================================================ 验收实验

def exp_accept() -> str:
    """三道验收：①同进程全测对照（recall 的硬标准）②投毒内核 ③D108 一致性。"""
    env = capture_env()
    costs, calib_note = cm.get_costs()
    out = [BAR, " D111 验收实验：集成流水线的三道硬标准", BAR,
           f" 单价来源：{calib_note}", ""]

    # ---- ① 32³ 全测 vs 引导（同进程，无漂移口实）
    mini32 = os.path.join(INPUTS, "matmul-bias-s0-32x32x32.mini")
    prog = parse_mini(mini32)
    _, M, N, K, _ = prog.workload()
    cands, st = build_space(M, N, K)
    spec = BenchSpec(M=M, N=N, K=K, seed=42)
    t0 = time.perf_counter()
    full = []
    full_stats = {}
    for cfg in cands:
        rec = bench_one(cfg, spec, SCREEN_PROTO, env)
        if rec["correctness"]["passed"]:
            full.append((cfg, rec["stats_ms"]["median"]))
            full_stats[cfg.describe()] = rec["stats_ms"]
    full_wall = (time.perf_counter() - t0) * 1000.0
    full.sort(key=lambda t: t[1])
    full_champ, full_ms = full[0]

    _, summ = run_tune(mini32, verbose=False, costs=costs, calib_note=calib_note)
    guided_champ = summ["champion"]
    hit = any(full_champ.describe() == nm for nm in summ["model_top5"])
    guided_med = dict(summ["measured_detail"])
    fc_in_guided = full_champ.describe() in guided_med

    # 可区分性判定（D107 规则）：差距 ≤ 2×MAD 就不许宣布排名
    gap_pct = ((guided_med.get(full_champ.describe(), full_ms) - summ["champion_ms"])
               / summ["champion_ms"] * 100) if fc_in_guided else float("nan")
    noise_pct = 2 * full_stats[full_champ.describe()]["mad"] \
        / full_stats[full_champ.describe()]["median"] * 100

    if full_champ.describe() == guided_champ:
        verdict = "冠军一致 ✓"
    elif fc_in_guided:
        if gap_pct <= noise_pct:
            note = f"差 {gap_pct:.1f}% ≤ 2×MAD 口径 {noise_pct:.1f}%——波动内不许排名（D107 规则）"
        else:
            note = (f"差 {gap_pct:.1f}% 超出波动 {noise_pct:.1f}%——先后测量阶段的近对互换，"
                    f"要裁决得靠交错 A/B（D110 的做法）")
        verdict = f"无漏 ✓（全测冠军在名额里、被实测过；{note}）"
    else:
        verdict = "真漏 ✗（全测冠军没进实测名单——recall 缺口）"

    out.append(" ① 同进程全测对照（32×32×32，18 个幸存候选全测 vs 引导 top-5）")
    out.append(f"   全测冠军：{full_champ.describe()} = {full_ms:.2f} ms"
               f"（Σwall {full_wall:.0f} ms，{len(cands)} 个候选 × 3+7）")
    out.append(f"   引导冠军：{guided_champ} = {summ['champion_ms']:.2f} ms"
               f"（实测 {summ['measured']} 个，bench Σwall {summ['bench_wall_ms']:.0f} ms）")
    out.append(f"   判定：{verdict}；全测冠军在模型 top-5 里："
               f"{'是 ✓（recall@5 命中）' if hit else '否 ✗'}")
    out.append(f"   读法：同进程对照没有跨进程漂移的口实——真漏才是漏；"
               f"提速 {full_wall / summ['bench_wall_ms']:.1f}×")
    out.append("")

    # ---- ② 投毒：no-tail 内核混进实测名单
    # 投毒要点：尾循环必须非空才毒得起来——32³ 的边界全被 U 整除，no-tail 与
    # 正常内核逐位相同（毒白投）。S3（90×96×64）的边界 tile（M 余 26）＋jki
    # 顺序（i 最内层）＋U=4 → 26 % 4 = 2，尾部真实存在。
    prog3 = parse_mini(os.path.join(INPUTS, "matmul-bias-s3-90x96x64.mini"))
    _, M3, N3, K3, _ = prog3.workload()
    spec3 = BenchSpec(M=M3, N=N3, K=K3, seed=42)
    poison_cfg = KernelConfig(32, 32, 32, "jki", 4)
    has_tail = any(e % poison_cfg.unroll
                   for e in (M3 % 32 or 32, N3 % 32 or 32, K3 % 32 or 32))
    assert has_tail, "投毒配置的尾循环为空——毒白投"
    kernel = make_kernel(poison_cfg, drop_tail=True)
    rec = bench_one(poison_cfg, spec3, SCREEN_PROTO, env, kernel=kernel)
    c = rec["correctness"]
    out.append(" ② 投毒验收：no-tail 内核混进 S5 实测名单（D96『跑得飞快、结果全错』）")
    out.append(f"   负载 S3 {M3}×{N3}×{K3}，配置 {poison_cfg.describe()}"
               f"（边界 tile 余 {M3 % 32}，尾部 {M3 % 32 % poison_cfg.unroll} 圈非空）")
    out.append(f"   {poison_cfg.describe()}/no-tail：passed={c['passed']}"
               f" max_abs_err={c['max_abs_err']:.3g}"
               f" stats={'None（被拒不计时）✓' if rec['stats_ms'] is None else '有！✗'}")
    assert c["passed"] is False and rec["stats_ms"] is None
    out.append("   集成流水线的门没有因为『集成』而豁免正确性——被拒照样留痕。")
    out.append("")

    # ---- ③ D108 一致性（跨进程，参考口径）
    out.append(" ③ D108 一致性（跨进程参考；D107 实测漂移 ~8.6%，近对会互换）")
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, encoding="utf-8") as fh:
            runs = json.load(fh)["runs"]
        for r in runs:
            if r["has_d108_base"]:
                out.append(f"   {r['shape_id']}：本流水线冠军 {r['champion']}"
                           f" vs D108 {r['d108_champion']} → "
                           f"{'同一配置 ✓' if r['agree'] else '不同配置（近对漂移，参考）'}")
            else:
                out.append(f"   {r['shape_id']}：新 shape 无基线，冠军 {r['champion']}"
                           f" = {r['champion_ms']:.2f} ms（首测）")
    else:
        out.append("   （先运行 --exp tune 生成 tune-summary.json）")
    out.append("")
    out.append(f" 验收环境：{iso_now()}")
    return "\n".join(out)


# ================================================================ 自检

def exp_self_test() -> str:
    checks = []

    def ok(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # ---- S0 前端
    tmp = os.path.join(OUTPUTS, "_selftest")
    os.makedirs(tmp, exist_ok=True)

    def write_mini(name, text):
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    good = write_mini("good.mini", """
func @matmul_bias(%A: tensor<64x64xf32>, %B: tensor<64x64xf32>, %bias: tensor<64xf32>) -> tensor<64x64xf32> {
  %mm = mini.matmul %A, %B    : (64x64, 64x64) -> 64x64
  %C  = mini.add %mm, %bias   : (64x64, 64) -> 64x96, broadcast row
  return %C : tensor<64x64xf32>
}
""")
    try:
        parse_mini(good)
        ok("前端：声明输出与推导不符被拒（64x96 ≠ 64x64）", False, "未抛出")
    except SystemExit:
        ok("前端：声明输出与推导不符被拒（64x96 ≠ 64x64）", True)

    good2 = write_mini("good2.mini", """
func @matmul_bias(%A: tensor<64x64xf32>, %B: tensor<64x64xf32>, %bias: tensor<64xf32>) -> tensor<64x64xf32> {
  %mm = mini.matmul %A, %B    : (64x64, 64x64) -> 64x64
  %C  = mini.add %mm, %bias   : (64x64, 64) -> 64x64, broadcast row
  return %C : tensor<64x64xf32>
}
""")
    prog = parse_mini(good2)
    ok("前端：合法程序解析出 (M,N,K)=(64,64,64)",
       prog.workload()[1:] == (64, 64, 64, "fp32"))

    bad_k = write_mini("badk.mini", """
func @f(%A: tensor<2x3xf32>, %B: tensor<4x5xf32>, %bias: tensor<5xf32>) -> tensor<2x5xf32> {
  %mm = mini.matmul %A, %B    : (2x3, 4x5) -> 2x5
  %C  = mini.add %mm, %bias   : (2x5, 5) -> 2x5, broadcast row
  return %C : tensor<2x5xf32>
}
""")
    try:
        parse_mini(bad_k)
        ok("前端：matmul 形状不咬合（K=3 vs 4）被拒", False, "未抛出")
    except SystemExit:
        ok("前端：matmul 形状不咬合（K=3 vs 4）被拒", True)

    bad_bias = write_mini("badbias.mini", """
func @f(%A: tensor<4x6xf32>, %B: tensor<6x5xf32>, %bias: tensor<4xf32>) -> tensor<4x5xf32> {
  %mm = mini.matmul %A, %B    : (4x6, 6x5) -> 4x5
  %C  = mini.add %mm, %bias   : (4x5, 4) -> 4x5, broadcast row
  return %C : tensor<4x5xf32>
}
""")
    try:
        parse_mini(bad_bias)
        ok("前端：bias 长度 ≠ N（4 vs 5）被拒", False, "未抛出")
    except SystemExit:
        ok("前端：bias 长度 ≠ N（4 vs 5）被拒", True)

    # 四份正式输入
    for f, want in [("matmul-bias-s1-64x64x64.mini", (64, 64, 64)),
                    ("matmul-bias-s2-96x96x96.mini", (96, 96, 96)),
                    ("matmul-bias-s3-90x96x64.mini", (90, 96, 64)),
                    ("matmul-bias-s4-160x160x160.mini", (160, 160, 160))]:
        p = parse_mini(os.path.join(INPUTS, f))
        ok(f"前端：{f} → {want}", p.workload()[1:4] == want)

    # ---- S1 Lowering 证据
    items, n_tiles, clamps, src = lowering_check(DEFAULT_CFG, 90, 96, 64)
    ok("Lowering：缺省配置六项结构证据齐",
       all(ok_ for _, ok_ in items), f"tiles={n_tiles} clamps={clamps}")
    ok("Lowering：S3（90×96×64）的 min 钳制会咬合", clamps is True)

    # ---- S2 空间
    c1, st1 = build_space(64, 64, 64)
    c2, st2 = build_space(64, 64, 64)
    ok("空间：确定性（两次生成逐项相等）", c1 == c2 and st1 == st2)
    ok("空间：缺省 32³ ijk U=1 在空间里", DEFAULT_CFG in c1)
    ok("空间：S1 原始空间 = 8 组合×6×3 = 144", st1.raw == 144, f"{st1.raw}")
    for M, N, K in [(64, 64, 64), (96, 96, 96), (90, 96, 64), (160, 160, 160)]:
        cands, st = build_space(M, N, K)
        bad_u = [c for c in cands
                 if c.unroll > {"i": c.tm, "j": c.tn, "k": c.tk}[c.order[-1]]]
        bad_b = [c for c in cands if tile_bytes(c.tm, c.tn, c.tk)[0] > BUDGET]
        ok(f"空间：{M}×{N}×{K} 全部幸存者 U ≤ 内层圈数且 ≤ 预算",
           not bad_u and not bad_b, f"{st.survivors} 个幸存")
    # 参数约束的点火验证（合成小 tile，生产空间 tile ≥ 32 点不着火）
    ok("空间：参数约束对 U > 内层圈数点火（合成 8³ tile U=16 被判死代码）",
       param_violation(KernelConfig(8, 8, 8, "kij", 16)) is not None
       and param_violation(KernelConfig(8, 8, 8, "kij", 4)) is None)
    # ---- S3 闸门
    total, parts = tile_bytes(160, 160, 160)
    ok("闸门：160³ tile 五项 = 102400×3 + 640 = 307,840 B > 256 KiB",
       total == 307840 and parts == (102400, 102400, 102400, 640),
       f"{total:,} B")
    _, st4 = build_space(160, 160, 160)
    ok("闸门：S4（160³）空间里资源剪 > 0（集成流水线真的在剪）",
       st4.n_resource_pruned > 0, f"剪 {st4.n_resource_pruned} 个")
    ok("闸门：精确 tile (90,96,64) 记账 = 82,560 B ≤ 预算",
       tile_bytes(90, 96, 64)[0] == 82560)

    # ---- S4 模型
    probes = cm.load_probes()
    costs, cn = cm.get_costs()
    for M, N, K in [(64, 64, 64), (160, 160, 160)]:
        cands, st = build_space(M, N, K)
        bound = cm.roofline_bound_ms(M, N, K, probes["A"]["value_gflops"])
        ranked, ms = rank_by_model(M, N, K, cands, costs)
        ok(f"模型：{M}×{N}×{K} 全部预测 ≥ Roofline 下界×0.9",
           all(p >= bound * 0.9 for p, _ in ranked),
           f"下界 {bound:.1f} ms，最小预测 {ranked[0][0]:.1f} ms")
        ok(f"模型：{M}×{N}×{K} 排序确定性", ranked == rank_by_model(M, N, K, cands, costs)[0])

    # 名额代表制：并列的家族兄弟只留一个，近对（不同 order）不被挤掉
    cands, st = build_space(96, 96, 96)
    ranked, _ = rank_by_model(96, 96, 96, cands, costs)
    picks = [cfg for _, _, cfg in select_topk(ranked, 5)]
    fams = [(c.order, c.unroll) for c in picks]
    ok("名额：S2 top-5 家族不重复（并列 tile 变体只留代表）", len(set(fams)) == len(fams),
       " × ".join(f"{c.order}U{c.unroll}" for c in picks))
    kij_in = any(c.order == "kij" for c in picks)
    ok("名额：S2 近对 kij 进了 top-5（D108 冠军不再被并列挤掉）", kij_in)

    # ---- S5 门＋编译
    spec = BenchSpec(13, 17, 19)
    rec = bench_one(DEFAULT_CFG, spec, SCREEN_PROTO, capture_env())
    ok("实测：缺省配置过 bitwise 门（Lowering 语义合龙）",
       rec["correctness"]["passed"] is True)
    kernel, cms = compile_timed(DEFAULT_CFG)
    ok("编译：exec 生成源码可计时（< 100 ms）", 0 < cms < 100, f"{cms:.2f} ms")

    # ---- 端到端（32³，不走文件系统缓存的小跑）
    p32 = write_mini("e2e.mini", """
func @matmul_bias(%A: tensor<32x32xf32>, %B: tensor<32x32xf32>, %bias: tensor<32xf32>) -> tensor<32x32xf32> {
  %mm = mini.matmul %A, %B    : (32x32, 32x32) -> 32x32
  %C  = mini.add %mm, %bias   : (32x32, 32) -> 32x32, broadcast row
  return %C : tensor<32x32xf32>
}
""")
    _, summ = run_tune(p32, verbose=False, costs=costs, calib_note=cn)
    ok("端到端：32³ mini 文本 → 冠军（一条调用内跑完 S0~S5）",
       summ["champion"] != "" and summ["champion_ms"] > 0,
       f"冠军 {summ['champion']} = {summ['champion_ms']:.2f} ms")

    # 输入血统（由 cost_model 常量钉死）
    try:
        cm.load_d108()
        ok("血统：results-d108.jsonl sha256 钉死（D108 基线可比）", True)
    except SystemExit as e:
        ok("血统：results-d108.jsonl sha256 钉死（D108 基线可比）", False, str(e))

    n_pass = sum(1 for _, good_, _ in checks if good_)
    lines = [BAR, f" D111 自检：{n_pass}/{len(checks)} 项通过", BAR]
    for name, good_, detail in checks:
        lines.append(f" {'✓' if good_ else '✗'} {name}" +
                     (f"  [{detail}]" if detail else ""))
    if n_pass != len(checks):
        lines.append(" 自检失败")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return "\n".join(lines)


# ================================================================ CLI

def exp_env() -> str:
    e = capture_env()
    return "\n".join([
        BAR, " 环境：D111 第四阶段集成验收", BAR,
        f" python: {e['python']}（{e['implementation']}）",
        f" system: {e['system']}/{e['machine']}，{e['cpu_count']} 逻辑核",
        f" cpu: {e['cpu_model']}",
        f" clock: {e['clock']}（分辨率 {e['clock_res_us']} µs）",
        f" 运行日期：{iso_now()}",
        " 依赖：零第三方；kernel_gen.py/bench.py/cost_model.py 为 D110 逐字节副本",
        " 输入：inputs/*.mini（mini 图 IR，4 份）",
        "       inputs/results-d108.jsonl（sha256 钉死，基线对照用）",
        "       inputs/probes-d109.json（sha256 钉死，Roofline 下界用）",
    ])


def exp_calibrate() -> str:
    """校准落盘（D110 纪律：先跑这份，其余报告共享同一份缓存）。"""
    os.makedirs(OUTPUTS, exist_ok=True)
    c = cm.calibrate()
    with open(cm.CALIB_CACHE, "w", encoding="utf-8") as fh:
        json.dump({"schema": "d110.calibration/1",
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "costs": dataclasses.asdict(c)}, fh, ensure_ascii=False, indent=1)
    return "\n".join([
        BAR, " D111 校准：16 根语句行单价落盘（cost_model.calibrate 原样）", BAR,
        f" 校准墙钟：{c.wall_ms:.0f} ms → outputs/calibration.json",
        f" j0={c.j0:.1f} k0={c.k0:.1f} i0={c.i0:.1f} ns（内层三家族）",
        f" ju={c.ju:.1f}（展开税 +{c.ju - c.j0:.1f}）loop={c.loop:.1f}"
        f" range3={c.range3:.1f} min3={c.min3:.1f} ns",
        " 全部后续实验（tune/accept/self-test）共享这份缓存，跨文件口径一致。",
    ])


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D111 第四阶段集成验收流水线")
    ap.add_argument("--exp", default=None,
                    help="calibrate/tune/accept/self-test/env（给 --ir 时默认 tune）")
    ap.add_argument("--ir", default=None, help="mini 图 IR 输入文件")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    args = ap.parse_args()

    os.makedirs(OUTPUTS, exist_ok=True)
    if args.ir and not args.exp:
        args.exp = "tune"
    if args.exp == "tune" and not args.ir:
        print("tune 需要 --ir 指定 mini 输入", file=sys.stderr)
        return 2

    if args.exp == "calibrate":
        print(exp_calibrate())
    elif args.exp == "tune":
        _, summary = run_tune(args.ir, top_k=args.top_k,
                              results_path=RESULTS_PATH)
        save_summary(summary)
    elif args.exp == "accept":
        print(exp_accept())
    elif args.exp == "self-test":
        print(exp_self_test())
    elif args.exp == "env":
        print(exp_env())
    else:
        print(f"未知实验：{args.exp!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
