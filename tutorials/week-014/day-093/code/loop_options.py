#!/usr/bin/env python3
"""第 93 天：参数化循环生成——把循环选择从代码常量收进编译配置 LoopOptions。

学习计划（第 93 天）：
  学习：把循环顺序、Tile 等选择从代码常量变成编译配置。
  实践：定义 LoopOptions，支持循环顺序、Tile 尺寸和展开因子。
  产出：配置结构、参数校验和默认值。

昨天（Day 92）的 LoopOrderPattern 已经把「顺序」做成构造参数——但一个裸
参数没有结构：没有默认值台账、拼错只能靠 assert 崩溃、配了没生效也没人报
错。今天把它收进一个正式的编译配置对象（frozen dataclass，三个字段）：

    LoopOptions(order, tile, unroll)
      order  (i,j,k) 循环顺序（外→内）——今天就被 Day 92 的 Pattern 消费
      tile   (tile_m, tile_n, tile_k) 块尺寸；None = 不 tiling（Day 94 消费）
      unroll 展开因子；1 = 不展开（Day 96 消费）

四道校验门（fail-closed：不认识的输入当场拒绝，拒绝猜测）：
  ① 类型门    字段必须是正确的类型（序列 / 正整数，bool 也不许冒充 int）
  ② 取值门    order ∈ i/j/k 的 6 种排列；tile、unroll 为正整数
  ③ 形状门    已知 Shape 时检查整除性（块>维度 → error；不整除 → warn）
  ④ 消费门    校验通过 ≠ 已经生效：tile/unroll 的 lowering 在 Day 94/96，
               今天拒绝运行，绝不静默忽略

检查套件（真实运行，本机未安装 MLIR，与 Day 57~92 同口径）：
  LO1  配置结构与默认值：默认齐全、frozen 不可变、序列化往返、replace 派生
  LO2  参数校验电池：17 个坏输入逐个被拒，报错家族正确且可定位
  LO3  默认值语义：缺省自动补齐；「未设置」与「显式设置」可区分
  LO4  端到端：6 种顺序配置真的驱动生成（op 数 / C 流量 / 位等价）
  LO5  形状感知校验：整除 / 越界 / 动态 Shape 三种口径的实测
  LO6  fail-closed 消费：tile / unroll 被第④道门明确拒绝（点名 Day 94/96）

用法：
    python3 loop_options.py                            # LO1~LO6 全跑，写 outputs/
    python3 loop_options.py --battery                  # 校验电池明细（17 个坏输入）
    python3 loop_options.py --preset ikj               # 跑一个 preset 端到端
    python3 loop_options.py --show "order=ikj,tile=2x2x3"  # 解析→校验→尝试运行

产出（outputs/）：
    options-table.txt     配置结构表：字段/类型/默认值/校验门/消费方（计划点名的交付物）
    validate-battery.txt  参数校验电池：每个坏输入的实际报错（真实运行）
    presets-run.txt       端到端实测：6 种顺序 × op 数/流量/位等价/缓存缺失 ＋ fail-closed 段
    shape-check.txt       形状感知校验：整除/越界/动态三种口径的 findings
"""

from __future__ import annotations

import argparse
import itertools
import platform
import sys
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "day-092" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import order_pass as od   # noqa: E402  Day 92 工程——只取不改（LoopOrderPattern 的家）
import shape_pass as sp   # noqa: E402  Day 90 工程——只取不改（IR 内核/执行器/EXPECTED_BODY）

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

SEED = 93          # 第 93 天自己的输入种子（可复现）
M, K, N = 2, 3, 2  # 贯穿例：2×3 乘 3×2 → 2×2（与 Day 92 同形状，种子不同）
SIM_SHAPE = od.SIM_SHAPE   # (16,16,16)：缓存缺失列的回放形状（Day 92 口径）

PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"：{detail}" if detail else ""))
    return ok


def env_line():
    return (f"环境：{platform.system()} {platform.machine()}, "
            f"Python {platform.python_version()}, numpy {np.__version__}; "
            f"本机未安装 MLIR（Day 57~92 口径：Python 复刻 DialectConversion 语义仿真）")


# ============================================================
# 错误家族：一个基类，调用方一把抓住
# ============================================================

class LoopOptionsError(Exception):
    """LoopOptions 相关错误的基类：驱动器 catch 这一个就够。"""


class OptionsValidationError(LoopOptionsError):
    """第①②道门（类型/取值）或解析层的拒绝。"""


class OptionsNotConsumedError(LoopOptionsError):
    """第④道门：校验通过，但今天的 lowering 不消费这个字段。"""


# ============================================================
# 字段规整与校验（构造层：一道门，两个入口——构造器和 parse 共用）
# ============================================================

IVS = ("i", "j", "k")


def _norm_order(order):
    """接受 'ikj' / 'i-k-j' / ('i','k','j')；规整成 tuple 并校验（取值门）。"""
    if isinstance(order, str):
        order = tuple(order.replace("-", "").replace(",", "").replace(" ", ""))
    elif isinstance(order, (tuple, list)):
        order = tuple(str(v) for v in order)
    else:
        raise OptionsValidationError(
            f"order 必须是 i/j/k 的序列（如 'ikj' 或 ('i','k','j')），拿到 {order!r}")
    if len(order) != 3:
        raise OptionsValidationError(
            f"order 必须恰好 3 个归纳变量（外→内），拿到 {order}（{len(order)} 个）")
    for v in order:
        if v not in IVS:
            raise OptionsValidationError(
                f"order 里出现不认识的循环变量 {v!r}（合法：i、j、k）")
    if len(set(order)) != 3:
        raise OptionsValidationError(
            f"order 里的归纳变量重复了：{order}（每个恰好出现一次）")
    return order


def _norm_tile(tile):
    """None 或 3 个正整数（类型门＋取值门；bool 不许冒充 int）。"""
    if tile is None:
        return None
    if not isinstance(tile, (tuple, list)):
        raise OptionsValidationError(
            f"tile 必须是 3 个正整数的序列或 None，拿到 {tile!r}")
    if len(tile) != 3:
        raise OptionsValidationError(
            f"tile 必须恰好 3 个分量 (tile_m, tile_n, tile_k)，拿到 {tile}（{len(tile)} 个）")
    for name, v in zip(("tile_m", "tile_n", "tile_k"), tile):
        if isinstance(v, bool) or not isinstance(v, int):
            raise OptionsValidationError(
                f"{name} 必须是正整数，拿到 {v!r}（{type(v).__name__}）")
        if v < 1:
            raise OptionsValidationError(f"{name} 必须是正整数（≥1），拿到 {v}")
    return tuple(tile)


def _norm_unroll(unroll):
    """正整数（类型门＋取值门）。"""
    if isinstance(unroll, bool) or not isinstance(unroll, int):
        raise OptionsValidationError(
            f"unroll 必须是正整数，拿到 {unroll!r}（{type(unroll).__name__}）")
    if unroll < 1:
        raise OptionsValidationError(f"unroll 必须是正整数（≥1），拿到 {unroll}")
    return unroll


# ============================================================
# LoopOptions：今天的主角——结构、校验、默认值三合一
# ============================================================

@dataclass(frozen=True)
class LoopOptions:
    """循环生成配置（第 93 天交付物）。

    设计要点：
      · frozen：配置一经生成不可变——编译到一半不许换配置；
        要改用 dataclasses.replace 生成新对象。
      · 字段类型全部不可变（tuple / None / int）：避开 Python 可变默认值陷阱。
      · 默认值 = 「什么都不做」：i-j-k 教科书顺序、不 tiling、不展开——
        空配置串跑出来的行为与 Day 89~92 完全一致（LO1/LO4 验证）。
      · 校验在 __post_init__ 里做：构造器和 parse 两个入口共用同一道门。
    """

    order: tuple[str, str, str] = ("i", "j", "k")
    tile: tuple[int, int, int] | None = None
    unroll: int = 1

    def __post_init__(self):
        object.__setattr__(self, "order", _norm_order(self.order))
        object.__setattr__(self, "tile", _norm_tile(self.tile))
        object.__setattr__(self, "unroll", _norm_unroll(self.unroll))

    # ---------- 序列化：往返 ----------

    def to_config_string(self):
        """最小规范形：只写出与默认值不同的字段；全默认 → 空串。

        （真实编译器的「无 flag = 默认行为」语义。）
        """
        kv = []
        if self.order != _DEFAULT.order:
            kv.append(f"order={'-'.join(self.order)}")
        if self.tile is not None:
            kv.append("tile=" + "x".join(str(t) for t in self.tile))
        if self.unroll != _DEFAULT.unroll:
            kv.append(f"unroll={self.unroll}")
        return ",".join(kv)

    def describe(self):
        """人类可读的配置台账（编译器开跑前打印自己的配置——可审计）。"""
        def tag(cur, default):
            return "显式设置" if cur != default else "默认值"
        tile_s = "<未设置>" if self.tile is None else "x".join(str(t) for t in self.tile)
        return "\n".join([
            "LoopOptions（第 93 天 · 循环生成配置）",
            f"  order  = {'-'.join(self.order)}（外→内；{tag(self.order, _DEFAULT.order)}）",
            f"  tile   = {tile_s}（块尺寸 tile_m×tile_n×tile_k；{tag(self.tile, _DEFAULT.tile)}）",
            f"  unroll = {self.unroll}（展开因子；{tag(self.unroll, _DEFAULT.unroll)}）",
            f"  最小规范形：{self.to_config_string() or '（全默认）'}",
        ])

    # ---------- 两个入口：配置串 / 字典（都 fail-closed）----------

    @classmethod
    def parse(cls, text):
        """配置字符串 → LoopOptions：'order=i-k-j,tile=2x2x3,unroll=2'。

        键值对用逗号分隔；未知键、重复键、缺 '=' 都当场报错——拒绝猜测。
        """
        opts, seen = {}, {}
        text = text.strip()
        if not text:
            return cls()
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise OptionsValidationError(
                    f"配置项必须是「键=值」，拿到 {part!r}（缺 '='）")
            key, _, val = part.partition("=")
            key, val = key.strip(), val.strip()
            if key not in ("order", "tile", "unroll"):
                raise OptionsValidationError(
                    f"不认识的配置项「{key}」（合法键：order / tile / unroll）——拒绝猜测")
            if key in seen:
                raise OptionsValidationError(
                    f"配置项「{key}」出现两次：{seen[key]!r} 和 {val!r}——以哪个为准？拒绝猜测")
            seen[key] = val
            if key == "order":
                opts["order"] = val
            elif key == "tile":
                if val.lower() in ("none", "off"):
                    opts["tile"] = None
                else:
                    try:
                        opts["tile"] = tuple(int(p) for p in val.lower().split("x"))
                    except ValueError:
                        raise OptionsValidationError(
                            f"tile 的每个分量必须是正整数，拿到 {val!r}") from None
            else:
                try:
                    opts["unroll"] = int(val)
                except ValueError:
                    raise OptionsValidationError(
                        f"unroll 必须是正整数，拿到 {val!r}") from None
        return cls(**opts)

    @classmethod
    def from_dict(cls, d):
        """字典 → LoopOptions（未知键当场拒绝，绝不 filter 掉）。"""
        if not isinstance(d, dict):
            raise OptionsValidationError(
                f"from_dict 需要一个 dict，拿到 {type(d).__name__}")
        unknown = set(d) - {"order", "tile", "unroll"}
        if unknown:
            raise OptionsValidationError(
                f"不认识的配置项：{sorted(unknown)}（合法键：order / tile / unroll）——拒绝猜测")
        return cls(**d)

    # ---------- 第③道门：形状感知校验 ----------

    def validate_for_shape(self, m=None, k=None, n=None):
        """已知 Shape 时检查整除性。返回 findings 列表，每条 = (级别, 说明)。

        级别口径：
          error = 块比维度还大——任何 lowering 都救不了，必须改配置
          warn  = 不整除 → 需要尾部处理（Day 95 的范围；Day 94 先保证整除场景）
          ok    = 检查通过（整除场景正是 Day 94 的首选测试点）
          info  = 形状未知（动态 Shape）→ 跳过——宁可不猜（Day 90 口径）
        """
        findings = []
        if self.tile is not None:
            for tname, tval, dname, dval in (
                    ("tile_m", self.tile[0], "M", m),
                    ("tile_n", self.tile[1], "N", n),
                    ("tile_k", self.tile[2], "K", k)):
                if dval is None:
                    findings.append(("info",
                                     f"{dname} 未知（动态 Shape）：跳过 {tname} 的整除性检查——宁可不猜（Day 90 口径）"))
                elif tval > dval:
                    findings.append(("error",
                                     f"{tname}={tval} > {dname}={dval}：块比维度还大，没有意义"))
                elif dval % tval != 0:
                    findings.append(("warn",
                                     f"{tname}={tval} 不整除 {dname}={dval}：需要尾部处理（Day 95 的范围；Day 94 先保证整除场景）"))
                else:
                    findings.append(("ok",
                                     f"{tname}={tval} 整除 {dname}={dval}：整除场景，Day 94 的首选测试点"))
        if self.unroll != 1:
            inner = self.order[2]
            trip = {"i": m, "j": n, "k": k}[inner]
            if trip is None:
                findings.append(("info",
                                 f"最内层 {inner} 的 trip 未知（动态 Shape）：跳过展开整除检查"))
            elif trip % self.unroll != 0:
                findings.append(("warn",
                                 f"unroll={self.unroll} 不整除最内层 {inner} 的 trip {trip}：展开会剩尾巴（Day 96 处理余数）"))
            else:
                findings.append(("ok",
                                 f"unroll={self.unroll} 整除最内层 {inner} 的 trip {trip}"))
        if not findings:
            findings.append(("ok", "tile 未设置、unroll=1：没有需要形状检查的字段"))
        return findings

    # ---------- 第④道门：消费门 ----------

    def consume_guard(self):
        """校验通过 ≠ 已经生效。

        今天（Day 93）的 lowering 只消费 order；tile / unroll 即使通过了
        前三道门也要在这里被明确拒绝——绝不静默忽略（悄悄丢配置比报错
        危险得多：用户以为生效了，实际跑的是没改的 IR）。

        返回放行附注列表（如 tile=1x1x1 的平凡块说明）；要拒绝就抛
        OptionsNotConsumedError。
        """
        problems, notes = [], []
        if self.tile is None:
            pass
        elif self.tile == (1, 1, 1):
            notes.append("tile=1x1x1 是平凡块（数学上等于不分块）：按「不启用」处理")
        else:
            problems.append(
                f"tile={'x'.join(str(t) for t in self.tile)} 通过了校验（第①~③道门），"
                f"但 Tiling 的 lowering 是 Day 94 的内容——今天拒绝运行，绝不静默忽略")
        if self.unroll != 1:
            problems.append(
                f"unroll={self.unroll} 通过了校验（第①~②道门），"
                f"但展开 lowering 是 Day 96 的内容——今天拒绝运行，绝不静默忽略")
        if problems:
            raise OptionsNotConsumedError("；".join(problems))
        return notes


_DEFAULT = LoopOptions()   # 全默认参照（describe / to_config_string 用）

# preset 一览：真实编译器的「-O2 / -O3」式命名配置
PRESETS = {
    "default": LoopOptions(),                        # 全默认：i-j-k，不 tiling，不展开
    "ikj": LoopOptions(order=("i", "k", "j")),       # Day 92 实测：512B 缓存下的赢家
    "jik": LoopOptions(order=("j", "i", "k")),       # Day 92 实测：1KB 下的第二名（k 仍在内层）
    "jki": LoopOptions(order=("j", "k", "i")),       # Day 92 实测：512B 下缺失最多的顺序
    "tile-16": LoopOptions(tile=(16, 16, 16)),       # 16³ 三维全整除：校验全过，Day 94 才消费
    "unroll-2": LoopOptions(unroll=2),               # 校验全过，Day 96 才消费
}


# ============================================================
# 配置驱动的端到端：四道门 → Day 92 的 Pattern → 解释执行
# ============================================================

def run_with_options(options, m=M, k=K, n=N, seed=SEED):
    """按一份 LoopOptions 跑完「四道门→生成→执行」，带回真实访存日志。

    门的顺序有讲究：第③道门（形状门）先跑——error 级 findings 当场拒绝，
    warn 级转为附注；然后第④道门（消费门），不过就抛
    OptionsNotConsumedError（fail-closed）。都过了才装配 Day 92 的
    LoopOrderPattern——所以消费门开口说「通过了第①~③道门」时是真的。
    """
    notes = []
    findings = options.validate_for_shape(m, k, n)
    errors = [msg for lv, msg in findings if lv == "error"]
    if errors:
        raise OptionsValidationError(
            "第③道门（形状门）拒绝：" + "；".join(errors))
    notes += [f"形状检查（warn）：{msg}" for lv, msg in findings if lv == "warn"]
    notes += options.consume_guard()
    run = od.run_order(options.order, m, k, n, seed=seed)
    streams, traffic, reuse = od.measured_streams(run, m, k, n)
    return dict(options=options, run=run, streams=streams, traffic=traffic,
                reuse=reuse, notes=notes)


def seq_compact(seq):
    """op 名称序列的紧凑表示：连排同名合并成 name×n。"""
    parts, last, cnt = [], None, 0
    for nm in seq:
        if nm == last:
            cnt += 1
        else:
            if last:
                parts.append(f"{last}×{cnt}" if cnt > 1 else last)
            last, cnt = nm, 1
    if last:
        parts.append(f"{last}×{cnt}" if cnt > 1 else last)
    return " → ".join(parts)


def measure_orders():
    """6 种顺序配置的完整实测（小例＋16³），presets-run.txt 与图 4 的数据源。"""
    rows = []
    for o in od.ORDERS:
        opt = LoopOptions(order=o)
        r = run_with_options(opt)
        ops = len(list(r["run"]["func"].walk()))
        seq = [op.name for op in r["run"]["func"].walk()]
        eq = bool(np.array_equal(r["run"]["C"], r["run"]["ref"]))
        sim = od.run_order(o, *SIM_SHAPE, seed=SEED)
        m32 = od.cache_sim(sim["interp"].access_log, *SIM_SHAPE, lines=32)["misses"]
        m64 = od.cache_sim(sim["interp"].access_log, *SIM_SHAPE, lines=64)["misses"]
        rows.append(dict(order=o, name=od.oname(o), cfg=opt.to_config_string() or "（全默认）",
                         inner=o[2], ops=ops, seq=seq, eq=eq, traffic=r["traffic"],
                         m32=m32, m64=m64))
    return rows


# ============================================================
# LO1：配置结构与默认值
# ============================================================

def lo1_structure():
    print("\n—— LO1 配置结构与默认值 ——")
    d = LoopOptions()
    check("LO1a 每个字段都有文档默认值",
          d.order == ("i", "j", "k") and d.tile is None and d.unroll == 1,
          "order=i-j-k（Day 89~92 的教科书顺序）｜tile=None（不 tiling）｜unroll=1（不展开）"
          "——默认行为 = Day 92 的默认跑法")
    frozen_ok = False
    try:
        d.order = ("i", "k", "j")   # type: ignore[misc]
    except FrozenInstanceError:
        frozen_ok = True
    check("LO1b frozen：配置一经生成不可变", frozen_ok,
          "半路改字段 = 编译到一半换配置——禁止；要改用 replace() 生成新对象（LO1d）")
    o = LoopOptions(order=("i", "k", "j"), tile=(2, 2, 3), unroll=2)
    check("LO1c 序列化往返：parse(to_config_string()) == 自己",
          LoopOptions.parse(o.to_config_string()) == o,
          f"最小规范形 {o.to_config_string()!r}：只写与默认不同的字段")
    o2 = replace(o, unroll=1)
    check("LO1d dataclasses.replace 生成派生配置（原对象不动）",
          o2.unroll == 1 and o.unroll == 2 and o2.order == o.order,
          "改配置 = 复制一份新的；原配置还在，审计有源头")
    desc = LoopOptions(order=("i", "k", "j")).describe()
    check("LO1e describe() 列出全部字段并标注 默认/显式",
          all(s in desc for s in ("order", "tile", "unroll", "显式设置", "默认值")),
          "编译器开跑前打印自己的配置——「用户要的」和「程序默认的」分得清")


# ============================================================
# LO2：参数校验电池（17 个坏输入逐个被拒）
# ============================================================

BAD_CASES = [
    ("order='ikm'：不认识 m", lambda: LoopOptions(order="ikm"), "循环变量"),
    ("order='iij'：归纳变量重复", lambda: LoopOptions(order="iij"), "重复"),
    ("order=('i','j')：只有 2 个", lambda: LoopOptions(order=("i", "j")), "恰好 3 个归纳变量"),
    ("order=42：类型不对", lambda: LoopOptions(order=42), "序列"),
    ("tile=(0,2,2)：0 不是正整数", lambda: LoopOptions(tile=(0, 2, 2)), "正整数"),
    ("tile=(2,-1,2)：负数", lambda: LoopOptions(tile=(2, -1, 2)), "正整数"),
    ("tile=(2,2)：分量不够", lambda: LoopOptions(tile=(2, 2)), "恰好 3 个分量"),
    ("tile=(1.5,2,2)：float 不是维度", lambda: LoopOptions(tile=(1.5, 2, 2)), "正整数"),
    ("tile=(True,2,2)：bool 冒充 int", lambda: LoopOptions(tile=(True, 2, 2)), "正整数"),
    ("unroll=0：展开 0 次没意义", lambda: LoopOptions(unroll=0), "正整数"),
    ("unroll='x'：不是整数", lambda: LoopOptions(unroll="x"), "正整数"),
    ("parse('foo=1')：未知键", lambda: LoopOptions.parse("foo=1"), "不认识的配置项"),
    ("parse('order=ikj,order=kij')：同一键两次", lambda: LoopOptions.parse("order=ikj,order=kij"), "出现两次"),
    ("parse('unroll')：缺 '='", lambda: LoopOptions.parse("unroll"), "缺 '='"),
    ("parse('tile=2xXx3')：分量不是整数", lambda: LoopOptions.parse("tile=2xXx3"), "正整数"),
    ("parse('tile=2x2x3x4')：分量太多", lambda: LoopOptions.parse("tile=2x2x3x4"), "恰好 3 个分量"),
    ("parse('order=')：值是空的", lambda: LoopOptions.parse("order="), "恰好 3 个归纳变量"),
]


def run_battery(verbose=False):
    """逐个喂坏输入：必须抛 OptionsValidationError，且报错含定位片段。"""
    lines, all_ok = [], True
    for desc, thunk, frag in BAD_CASES:
        try:
            thunk()
            line, ok = f"!! 漏网：{desc}（居然构造成功）", False
        except OptionsValidationError as e:
            line, ok = f"✗ 拒绝：{desc}  →  {e}", frag in str(e)
        except Exception as e:                       # noqa: BLE001  错误家族不对也算失败
            line, ok = f"!! 报错家族不对：{desc} → {type(e).__name__}: {e}", False
        all_ok &= ok
        lines.append(line)
        if verbose:
            print(line)
    return all_ok, lines


def lo2_battery():
    print("\n—— LO2 参数校验电池：17 个坏输入逐个被拒（fail-closed） ——")
    ok, lines = run_battery(verbose=False)
    check("LO2 17 个坏输入全部被 OptionsValidationError 拒绝（报错含定位片段）", ok,
          "类型门 6 例（序列/float/bool/分量数…）＋取值门 5 例（未知变量/重复/非正…）"
          "＋解析层 6 例（未知键/键重复/缺 =/坏值）；明细见 outputs/validate-battery.txt")
    (OUT / "validate-battery.txt").write_text(
        "\n".join(["LoopOptions 参数校验电池（真实运行）", env_line(), "",
                  f"坏输入 {len(BAD_CASES)} 个；判定标准：必须抛 OptionsValidationError，"
                  "且报错里含定位片段（能看出错在哪个字段、为什么）", "",
                  *lines, "",
                  f"汇总：{'17/17 全部按预期拒绝' if ok else '存在漏网或报错家族错误（见 !! 行）'}",
                  "对照：宽容式实现（把不认识的键 filter 掉、把坏值改成默认值）会吞掉以上全部错误"]) + "\n",
        encoding="utf-8")


# ============================================================
# LO3：默认值语义——缺省补齐、显式可辨
# ============================================================

def lo3_defaults():
    print("\n—— LO3 默认值语义：缺省补齐、显式可辨 ——")
    o = LoopOptions.parse("order=ikj")
    check("LO3a 缺省字段自动落到默认值", o.tile is None and o.unroll == 1,
          "只写 order=ikj → tile=None、unroll=1（省略 ≠ 显式设置）")
    check("LO3b 空串 = 全默认", LoopOptions.parse("") == LoopOptions(),
          "空配置串 → 不带任何旗子 → 默认行为（真实编译器的「无 flag = 默认」语义）")
    check("LO3c 「未设置」与「显式平凡」是两个值",
          LoopOptions() != LoopOptions(tile=(1, 1, 1)),
          "tile=None 与 tile=1x1x1 行为都是不 tiling，但值不同、describe 分别标（默认）/（显式）"
          "——审计能分清「用户要的」和「程序默认的」")
    check("LO3d describe 区分默认/显式",
          "显式设置" in LoopOptions(tile=(1, 1, 1)).describe(),
          "tile=1x1x1 会被标成显式设置，附注它是平凡块（consume_guard）")
    perms = list(itertools.permutations("ijk"))
    six_ok = True
    for p in perms:
        try:
            LoopOptions(order=p)
        except LoopOptionsError:
            six_ok = False
    check("LO3e order 的合法空间恰好 6 个（3!），全部可构造", six_ok and len(perms) == 6,
          "6 种排列（外→内）都能构造；「第 7 种排列」不存在——取值门在门口挡住")


# ============================================================
# LO4：端到端——配置真的驱动生成
# ============================================================

def lo4_end_to_end(rows):
    print("\n—— LO4 端到端：6 种顺序配置驱动生成（小例 2×3@3×2 种子 93 ＋ 16³ 回放） ——")
    ok_ops = all(r["ops"] == (18 if r["inner"] == "k" else 21) for r in rows)
    check("LO4a 六种顺序全部端到端：op 数 k 内层 18 / k 外层 21", ok_ops,
          "与 Day 92 口径一致：结构是数据，换的只是装配顺序（清零 nest ＋3）")
    ok_eq = all(r["eq"] for r in rows)
    check("LO4b 6/6 与同序参考位等价", ok_eq,
          "配置换的是装配顺序，k 处处升序 → 舍入顺序不变——换序不换数（Day 92 结论由配置触发）")
    check("LO4c default 配置复现 Day 89/90 的 18 op 结构（op 序列逐项相同）",
          rows[0]["seq"] == list(sp.EXPECTED_BODY),
          "空配置 = Day 89~92 的默认跑法——配置层不改变默认行为")
    ok_tr = True
    for r in rows:
        t = r["traffic"]
        if r["inner"] == "k":
            ok_tr &= (t["c_loads"] == 0 and t["c_stores"] == M * N and t["init_stores"] == 0)
        else:
            ok_tr &= (t["c_loads"] == M * N * K and t["c_stores"] == M * N * K
                      and t["init_stores"] == M * N)
    check("LO4d C 流量与 Day 92 公式一致", ok_tr,
          "k 内层 0L+4S；k 外层 12L+12S＋4 清零（2×3@3×2）——配置切换的是真实访存行为")
    check("LO4e 同一份语义、两份 IR：default 与 ikj 的 op 序列不同、结果都位等价",
          rows[0]["seq"] != rows[1]["seq"] and rows[0]["eq"] and rows[1]["eq"],
          "这就是「配置是数据」的直接证据：改一个字段值，得到另一份 IR、同一个答案")


def write_presets_run(rows):
    L = ["LoopOptions 端到端实测（配置 → 生成 → 解释执行 → 真实日志）", env_line(), "",
         f"贯穿小例：A({M},{K})@B({K},{N}) → C({M},{N})，种子 {SEED}（流量/op 数在此测量）",
         f"缓存列：A{SIM_SHAPE[0]}×{SIM_SHAPE[1]}@B{SIM_SHAPE[1]}×{SIM_SHAPE[2]} 真实轨迹回放，",
         "  直接映射、行 16B、矩阵间隔 1 行（Day 92 口径）：miss@512B（32 行）/ miss@1KB（64 行）", "",
         f"{'顺序':<8}{'最小规范形':<14}{'最内':<4}{'op数':<6}{'C流量(小例)':<16}{'位等价':<6}"
         f"{'miss@512B':<10}{'miss@1KB':<9}"]
    for r in rows:
        t = r["traffic"]
        cflow = (f"{t['c_loads']}L+{t['c_stores']}S"
                 + (f"+{t['init_stores']}清" if t["init_stores"] else ""))
        L.append(f"{r['name']:<8}{r['cfg']:<14}{r['inner']:<4}{r['ops']:<6}{cflow:<16}"
                 f"{'✓' if r['eq'] else '✗':<6}{r['m32']:<10}{r['m64']:<9}")
    L += ["",
          "op 序列对照（「配置是数据」的直接证据——同样的积木，不同的装配）：",
          f"  order=i-j-k（{rows[0]['ops']} op）：{seq_compact(rows[0]['seq'])}",
          f"  order=i-k-j（{rows[1]['ops']} op）：{seq_compact(rows[1]['seq'])}",
          "",
          "读表：① op 数与 C 流量只由「k 在不在最内层」决定（18/21、4 写 vs 28 访问）；",
          "② miss 列与 Day 92 的 order-table.txt 逐格一致——今天换的是「配置从哪来」，不是行为口径；",
          "③ 最小规范形一列就是 LoopOptions.to_config_string()：全默认是一份合法配置。"]
    (OUT / "presets-run.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


# ============================================================
# LO5：形状感知校验（第③道门）
# ============================================================

def lo5_shape():
    print("\n—— LO5 形状感知校验：整除 / 越界 / 动态三种口径 ——")
    cases = []   # (标签, options, shape, findings)

    cases.append(("tile=2x2x3 @ A(2,3)@B(3,2)：三维全整除",
                  LoopOptions(tile=(2, 2, 3)), (M, K, N),
                  LoopOptions(tile=(2, 2, 3)).validate_for_shape(M, K, N)))
    cases.append(("tile=2x2x2 @ A(2,3)@B(3,2)：tile_k 不整除 K=3",
                  LoopOptions(tile=(2, 2, 2)), (M, K, N),
                  LoopOptions(tile=(2, 2, 2)).validate_for_shape(M, K, N)))
    cases.append(("tile=4x4x4 @ A(2,3)@B(3,2)：块比维度还大",
                  LoopOptions(tile=(4, 4, 4)), (M, K, N),
                  LoopOptions(tile=(4, 4, 4)).validate_for_shape(M, K, N)))
    cases.append(("tile=16x16x16 @ A(16,16)@B(16,16)：Day 94 的首选测试点",
                  LoopOptions(tile=(16, 16, 16)), SIM_SHAPE,
                  LoopOptions(tile=(16, 16, 16)).validate_for_shape(*SIM_SHAPE)))
    cases.append(("unroll=4、order 默认（k 内层，trip=K=16）：整除",
                  LoopOptions(unroll=4), SIM_SHAPE,
                  LoopOptions(unroll=4).validate_for_shape(*SIM_SHAPE)))
    cases.append(("unroll=3、order 默认（k 内层，trip=K=16）：不整除",
                  LoopOptions(unroll=3), SIM_SHAPE,
                  LoopOptions(unroll=3).validate_for_shape(*SIM_SHAPE)))
    cases.append(("unroll=3、order=i-k-j（最内层换成 j，trip=N=16）：不整除",
                  LoopOptions(order=("i", "k", "j"), unroll=3), SIM_SHAPE,
                  LoopOptions(order=("i", "k", "j"), unroll=3).validate_for_shape(*SIM_SHAPE)))
    cases.append(("tile=4x4x4、Shape 全未知（动态）：跳过",
                  LoopOptions(tile=(4, 4, 4)), (None, None, None),
                  LoopOptions(tile=(4, 4, 4)).validate_for_shape(None, None, None)))

    def lv(fs, level):
        return [m for l, m in fs if l == level]

    fs1 = cases[0][3]
    check("LO5a 整除场景全绿（tile=2x2x3 @ 2×3·3×2；tile=16x16x16 @ 16³）",
          all(l == "ok" for l, _ in fs1) and all(l == "ok" for l, _ in cases[3][3]),
          "三维全部整除——这正是 Day 94 实现 Tiling 时首选的测试场景")
    fs2 = cases[1][3]
    check("LO5b 不整除 → warn 并点名尾部处理的归属日",
          any("Day 95" in m for m in lv(fs2, "warn"))
          and any("Day 96" in m for m in lv(cases[5][3], "warn"))
          and any("Day 96" in m for m in lv(cases[6][3], "warn")),
          "tile_k=2 ∤ K=3 → Day 95（尾部）；unroll=3 ∤ trip 16 → Day 96（余数）"
          "——warn 把「谁将来管这件事」写在报错里")
    check("LO5c 块大于维度 → error（tile_m=4 > M=2）",
          any("比维度还大" in m for m in lv(cases[2][3], "error")),
          "块比矩阵还大：任何 lowering 都救不了，只能改配置")
    check("LO5d 动态 Shape → info 跳过（宁拒不猜）",
          all("宁可不猜" in m for m in lv(cases[7][3], "info")),
          "形状未知时不假装检查过——与 Day 90「动态宁拒不猜」同一条原则")
    check("LO5e 展开的整除检查吃 order 语义：ikj 的最内层是 j（trip N）不是 k",
          any("最内层 j" in m for m in lv(cases[6][3], "warn")),
          "同是 unroll=3 @ 16³，i-j-k 查 K、i-k-j 查 N——形状门不是孤立的类型检查")

    L = ["LoopOptions 形状感知校验（第③道门）findings（真实运行）", env_line(), ""]
    for label, opt, shape, fs in cases:
        shp = ("×".join("?" if v is None else str(v) for v in shape))
        L.append(f"〔{label}〕配置：{opt.to_config_string() or '（全默认）'}；Shape：{shp}")
        for l, m in fs:
            L.append(f"    [{l:<5}] {m}")
        L.append("")
    L.append("级别口径：error=改配置才能救｜warn=能用但要尾部处理（Day 95/96 的范围）｜"
             "ok=整除场景（Day 94 首选测试点）｜info=动态 Shape 跳过（宁拒不猜）")
    (OUT / "shape-check.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


# ============================================================
# LO6：fail-closed 消费——校验通过 ≠ 已经生效
# ============================================================

def lo6_fail_closed():
    print("\n—— LO6 fail-closed 消费：校验通过 ≠ 已经生效 ——")
    o = PRESETS["tile-16"]
    gates_ok = (o.tile == (16, 16, 16)
                and all(l != "error" and l != "warn"
                        for l, _ in o.validate_for_shape(*SIM_SHAPE)))
    msg = ""
    blocked = False
    try:
        run_with_options(o, *SIM_SHAPE)
    except LoopOptionsError as e:
        blocked = isinstance(e, OptionsNotConsumedError)
        msg = str(e)
    check("LO6a tile=16x16x16 过了前三道门，被第④道门拒绝（点名 Day 94）",
          gates_ok and blocked and "Day 94" in msg,
          f"实际报错：{msg}")
    o2 = PRESETS["unroll-2"]
    msg2, blocked2 = "", False
    try:
        run_with_options(o2)
    except OptionsNotConsumedError as e:
        blocked2, msg2 = True, str(e)
    check("LO6b unroll=2 同样被拒（点名 Day 96）", blocked2 and "Day 96" in msg2,
          f"实际报错：{msg2}")
    r = run_with_options(LoopOptions(tile=(1, 1, 1)))
    ops = len(list(r["run"]["func"].walk()))
    check("LO6c tile=1x1x1 是平凡块：放行并附注（不是静默忽略）",
          ops == 18 and bool(np.array_equal(r["run"]["C"], r["run"]["ref"]))
          and any("平凡块" in s for s in r["notes"]),
          "；".join(r["notes"]) + "——附注让「为什么没生效」有案可查")
    with open(OUT / "presets-run.txt", "a", encoding="utf-8") as f:
        f.write("\n".join([
            "",
            "—— fail-closed 消费实录（第④道门：校验通过 ≠ 已经生效） ——",
            f"tile-16（tile=16x16x16，16³ 三维整除，第①~③道门全过）：",
            f"  ✗ OptionsNotConsumedError: {msg}",
            f"unroll-2（unroll=2，第①~②道门全过）：",
            f"  ✗ OptionsNotConsumedError: {msg2}",
            "tile=1x1x1（平凡块，数学上等于不分块）：",
            "  ✓ 放行，附注：" + "；".join(r["notes"]),
            "",
            "原则：宁可拒绝运行，不可静默忽略——用户以为配置生效、实际跑的是没改的 IR，",
            "这比任何报错都危险。Day 94 实现 TilingPattern 后，第④道门对 tile 放行。"]) + "\n")


# ============================================================
# 配置结构表（计划点名的交付物：结构 / 校验 / 默认值）
# ============================================================

def write_options_table():
    d = _DEFAULT
    L = ["LoopOptions 配置结构表（第 93 天交付物：配置结构、参数校验和默认值）", env_line(), "",
         f"构造默认值：LoopOptions() → order={'-'.join(d.order)}, tile=<未设置>, unroll={d.unroll}",
         "合法 order 全集（恰好 6 = 3!）："
         + " / ".join("-".join(p) for p in itertools.permutations("ijk")), "",
         "=" * 78,
         "字段 order —— 循环顺序（外→内）",
         "=" * 78,
         "  类型     : tuple[str, str, str]",
         "  默认值   : ('i', 'j', 'k')——Day 89~92 的教科书顺序（k 最内层，寄存器累加）",
         "  合法取值 : 恰好 6 种：i/j/k 的全部排列",
         "  校验门   : ①类型门（必须是序列）②取值门（3 个、各不相同、∈ {i,j,k}）",
         "  消费方   : 今天（Day 93）——直接喂给 Day 92 的 LoopOrderPattern(order=...)",
         "  示例     : LoopOptions(order='ikj')；parse('order=i-k-j')",
         "",
         "=" * 78,
         "字段 tile —— Tiling 块尺寸 (tile_m, tile_n, tile_k)",
         "=" * 78,
         "  类型     : tuple[int, int, int] | None",
         "  默认值   : None = 不做 Tiling（最小规范形里整个字段省略）",
         "  合法取值 : None，或 3 个正整数（≥1）；tile=(1,1,1) 是平凡块（= 不分块）",
         "  校验门   : ①类型门（分量是 int，bool/float 都拒）②取值门（长度 3、正数）",
         "             ③形状门（块 > 维度 → error；不整除 → warn，尾部处理是 Day 95 范围）",
         "  消费方   : Day 94（基础 Tiling）——今天第④道门拒绝运行，绝不静默忽略",
         "  示例     : LoopOptions(tile=(16,16,16))；parse('tile=2x2x3')",
         "",
         "=" * 78,
         "字段 unroll —— 循环展开因子",
         "=" * 78,
         "  类型     : int",
         "  默认值   : 1 = 不展开",
         "  合法取值 : 正整数（≥1）",
         "  校验门   : ①类型门（int，bool 拒）②取值门（≥1）",
         "             ③形状门（不整除最内层 trip → warn，展开余数是 Day 96 范围）",
         "  消费方   : Day 96（展开与向量化）——今天第④道门拒绝运行",
         "  示例     : LoopOptions(unroll=4)？——先校验，Day 96 才生效",
         "",
         "=" * 78,
         "四道校验门（fail-closed：不认识的输入当场拒绝，拒绝猜测）",
         "=" * 78,
         "  ① 类型门 : 字段类型正确（序列 / int；bool 不许冒充 int，float 不许冒充维度）",
         "  ② 取值门 : order ∈ 6 种排列；tile / unroll 为正整数；解析层拒绝未知键/重复键/缺 '='",
         "  ③ 形状门 : 已知 Shape 时查整除性（块>维度 error；不整除 warn 并点名归属日；动态跳过 info）",
         "  ④ 消费门 : 校验通过 ≠ 已经生效——今天只消费 order；tile/unroll 明确拒绝（点名 Day 94/96）",
         "",
         "=" * 78,
         "preset 一览（命名配置，真实编译器的 -O2 / -O3 式入口）",
         "=" * 78]
    for name, o in PRESETS.items():
        try:
            o.consume_guard()
            runnable = "✓ 今天可端到端"
        except OptionsNotConsumedError as e:
            runnable = f"✗ {e}"
        L.append(f"  {name:<9} {o.to_config_string() or '（全默认）':<22} {runnable}")
    L += ["",
          "两个入口共用同一道门：构造器 LoopOptions(...) 与解析层 parse()/from_dict()",
          "的校验代码是同一段（__post_init__）——不存在「字符串入口查得松」的旁路。"]
    (OUT / "options-table.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    check("LO0 配置结构表已写入 outputs/options-table.txt（结构/校验/默认值三合一）",
          (OUT / "options-table.txt").stat().st_size > 1500,
          "3 个字段 × 类型/默认/合法值/校验门/消费方 ＋ 四道门说明 ＋ preset 一览")


# ============================================================
# 交互模式：--show / --preset / --battery
# ============================================================

def show_mode(text):
    print(f"配置串：{text!r}")
    try:
        o = LoopOptions.parse(text)
    except OptionsValidationError as e:
        print(f"✗ 解析/校验：{e}")
        return
    print(o.describe())
    print(f"\n形状感知校验（A({M},{K})@B({K},{N})，第③道门）：")
    for l, m in o.validate_for_shape(M, K, N):
        print(f"  [{l}] {m}")
    try:
        r = run_with_options(o)
    except LoopOptionsError as e:
        print(f"\n✗ {e}")
        return
    run, t = r["run"], r["traffic"]
    print(f"\n✓ 端到端（A({M},{K})@B({K},{N})，种子 {SEED}）："
          f"{len(list(run['func'].walk()))} op；C 流量 {t['c_loads']}L+{t['c_stores']}S"
          + (f"（清零 {t['init_stores']}S）" if t["init_stores"] else "")
          + f"；与同序参考位等价 = {bool(np.array_equal(run['C'], run['ref']))}")
    for s in r["notes"]:
        print(f"  附注：{s}")


def preset_mode(name):
    o = PRESETS[name]
    print(f"preset 「{name}」：{o.to_config_string() or '（全默认）'}")
    print(o.describe())
    print(f"\n形状感知校验（A({M},{K})@B({K},{N})，第③道门）：")
    for l, m in o.validate_for_shape(M, K, N):
        print(f"  [{l}] {m}")
    try:
        r = run_with_options(o)
    except LoopOptionsError as e:
        print(f"\n✗ {e}")
        return
    run, t = r["run"], r["traffic"]
    print(f"\n✓ 端到端（A({M},{K})@B({K},{N})，种子 {SEED}）："
          f"{len(list(run['func'].walk()))} op；C 流量 {t['c_loads']}L+{t['c_stores']}S"
          + (f"（清零 {t['init_stores']}S）" if t["init_stores"] else "")
          + f"；与同序参考位等价 = {bool(np.array_equal(run['C'], run['ref']))}")
    sim = od.run_order(o.order, *SIM_SHAPE, seed=SEED)
    for ln in (32, 64):
        s = od.cache_sim(sim["interp"].access_log, *SIM_SHAPE, lines=ln)
        print(f"  缓存回放（16³，{ln * 16}B 直接映射）：缺失 {s['misses']}（命中率 {s['hit_rate']:.1%}）")


def run_all():
    print("第 93 天 · 参数化循环生成：把循环顺序、Tile、展开因子从代码常量收进 LoopOptions")
    print(env_line())
    lo1_structure()
    write_options_table()
    lo2_battery()
    lo3_defaults()
    rows = measure_orders()
    lo4_end_to_end(rows)
    write_presets_run(rows)
    lo5_shape()
    lo6_fail_closed()
    print()
    print(f"—— 检查测试 {PASS} PASS / {FAIL} FAIL ——")
    print("options-table.txt / validate-battery.txt / presets-run.txt / shape-check.txt 已写入 outputs/")
    return FAIL == 0


def main():
    ap = argparse.ArgumentParser(description="第 93 天：参数化循环生成（LoopOptions）")
    ap.add_argument("--show", metavar="CONFIG",
                    help='解析→校验→尝试端到端，如 "order=ikj,tile=2x2x3"')
    ap.add_argument("--preset", choices=sorted(PRESETS), help="跑一个 preset 端到端")
    ap.add_argument("--battery", action="store_true", help="校验电池明细（17 个坏输入的真实报错）")
    args = ap.parse_args()
    if args.battery:
        ok, _ = run_battery(verbose=True)
        print(f"\n汇总：{'17/17 全部按预期拒绝' if ok else '存在漏网或报错家族错误'}")
        sys.exit(0 if ok else 1)
    if args.show:
        show_mode(args.show)
    elif args.preset:
        preset_mode(args.preset)
    else:
        sys.exit(0 if run_all() else 1)


if __name__ == "__main__":
    main()
