#!/usr/bin/env python3
"""cast_elim_lab.py —— 第 67 天主实验：Cast 消除。

任务（来自学习计划第 67 天）：
  学习：无操作 Cast、精度扩展、精度缩减和符号语义；
  实践：只消除输入输出类型完全一致的 Cast；暂不做可能改变数值的合并；
  产出：Cast 消除 Pattern 和类型反例（测试在 test_cast_elim.py）。

今天的核心判据（比昨天的 numel 还简单，但边界更锋利）：
  类型 = 位宽 × 类别（浮点/整数）× 符号/格式。
  「无操作 Cast」当且仅当 in_dtype == out_dtype（类型完全一致）→ 消除；
  其余四类——精度扩展（f16→f32）、精度缩减（f32→f16）、符号语义（i8↔ui8）、
  域翻转（f32↔i32）——今天全部保留（其中「先缩后扩」的链合并是明天的
  领地，今天只做数值终审：0.1 走一圈回来会变成 0.0999755859375）。

合法性边界（直接复用昨天 P1 的结论）：
  恒等消除 Cast(x, T) 且 type(x) == T → x：
    删除的是 op 自身；%c 被整体替换成 %x（两者值相等）；
    replaceAllUses 把全部使用者改道 → 不需要唯一使用者检查。
  昨天的 P1（恒等 reshape 消除）就是今天 Pattern 的直接原型。

数值现场（本机 numpy 1.26.4 实测，2026-11-12）：
  0.1 的三重人格：f32 = 0.10000000149011612（0x3DCCCCCD）
                  f16 = 0.0999755859375（0x2E66）
                  bf16(截断) = 0.099609375（0x3DCC0000）
  f32→f16→f32 回环：0.1 ≠ 0.0999755859375（信息单向门）
  f16→f32→f16 回环：1002 个值（含 ±inf/NaN）全部原样（安全方向）
  i32(300)→i8 = 44（回绕）；i8(-1)→ui8 = 255（0xFF 的两副面孔）
  0.5 的假阴性：f32→f16→f32 恰好相等（2 的幂——测试值不能只挑好值）

MLIR 侧的真实事实（本机 LLVM 18.1.8 实测，2026-11-12）：
  ① arith.extf f32 to f32：Verifier 直接拒绝（"cast incompatible"）——
     arith 把 cast 按方向拆成 extf/truncf/extsi/extui/trunci，方向化的
     家族表达不出「无操作扩展」，同型 no-op 在源头就进不了 IR；
  ② arith.bitcast f32 to f32：合法，--canonicalize 消除为 return %arg0；
  ③ truncf∘extf（f16→f32→f16，数学上恒等）：原样保留 2 个 op——
     stock 管道没有浮点回环折叠（要自己写）；
  ④ extf∘truncf（f32→f16→f32，有损）：原样保留（正确拒绝）；
  ⑤ trunci∘extsi（i8→i32→i8，恒等）：消除为 return %arg0——整数回环有折叠；
  ⑥ extsi∘trunci（i32→i8→i32，有损）：原样保留（正确拒绝）；
  ⑦ bitcast 链 f32→i32→f32：消除为 return %arg0（双射重解释）；
  ⑧ bitcast i8 to ui8：类型 ui8 不存在——MLIR 整数是 signless 的，
     符号在操作（extsi/extui）里而不在类型里。
  结论：stock 的规则是「拼图」而不是「原则」——整数回环有、浮点回环没有；
  mini 的判据一刀切：type(x) == T 才消除，其余交给数值对拍看守。

用法：python3 cast_elim_lab.py   （在 code/ 目录下；输出另存 outputs/）
"""

from __future__ import annotations

import platform
import random
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


# ============================================================
# 类型系统：六种 dtype + 五分类 + 语义（convert）
# ============================================================

DTYPE_INFO = {
    "f32":  dict(bits=32, kind="float", signed=None),
    "f16":  dict(bits=16, kind="float", signed=None),
    "bf16": dict(bits=16, kind="float", signed=None),
    "i32":  dict(bits=32, kind="int", signed=True),
    "i8":   dict(bits=8, kind="int", signed=True),
    "ui8":  dict(bits=8, kind="int", signed=False),
}
DTYPES = list(DTYPE_INFO.keys())

CLASS_NAME = {
    "identity": "无操作",
    "widen": "精度扩展",
    "narrow": "精度缩减",
    "signflip": "符号语义",
    "reformat": "同宽异格式",
    "domainflip": "域翻转",
}


def classify_cast(in_t: str, out_t: str) -> str:
    """五分类（今天的学习产出）：
    identity  in == out（类型完全一致）→ 今天的消除对象
    widen     值集扩大、信息不丢（f16→f32、i8→i32）
    narrow    值集缩小、可能丢信息（f32→f16、i32→i8）
    signflip  同宽整数换符号（i8↔ui8，位不变、值解释变）
    reformat  同宽浮点换格式（f16↔bf16，尾数/指数位宽重新分配）
    domainflip 浮点↔整数（f32↔i32，0.5 → 0）
    """
    if in_t == out_t:
        return "identity"
    ki, ko = DTYPE_INFO[in_t]["kind"], DTYPE_INFO[out_t]["kind"]
    if ki != ko:
        return "domainflip"
    if ki == "float":
        if in_t == "f32":
            return "narrow"
        if out_t == "f32":
            return "widen"
        return "reformat"
    bi, bo = DTYPE_INFO[in_t]["bits"], DTYPE_INFO[out_t]["bits"]
    if bo > bi:
        return "widen"
    if bo < bi:
        return "narrow"
    return "signflip"


NP_OF = {"f32": np.float32, "f16": np.float16, "i32": np.int32,
         "i8": np.int8, "ui8": np.uint8}


def to_bf16(arr) -> np.ndarray:
    """f32 → bf16（截断版仿真：低 16 位清零）。
    numpy 1.26 没有原生 bfloat16，用位运算模拟硬件最朴素的 truncation
    舍入；存成「低 16 位为零的 f32」——值集上与 bf16 一致（类型的账记在
    op.in_dtype/out_dtype 上，不由数组 dtype 猜测——0.125 这类好值的
    低 16 位本来也是 0，靠位模式猜类型会认错）。"""
    a = np.array(arr, dtype=np.float32, copy=False)
    if not a.flags["C_CONTIGUOUS"]:
        a = np.ascontiguousarray(a)
    return (a.view(np.uint32) & np.uint32(0xFFFF0000)).view(np.float32)


def convert(arr, out_t: str) -> np.ndarray:
    """值语义转换（对应框架里 tensor.to(dtype) / tosa.cast）。"""
    if out_t == "bf16":
        return to_bf16(arr)
    if arr.dtype == np.float32 and out_t in ("f32", "f16", "i32", "i8",
                                             "ui8"):
        return arr.astype(NP_OF[out_t])
    if out_t == "f32":
        return arr.astype(np.float32)
    return arr.astype(NP_OF[out_t])


def verify_cast(in_t: str, out_t: str) -> list[str]:
    """两关 Verifier：cast 的合法性判据在类型不在形状（对比昨天的 numel）。
    C1 dtype 都认识；C2 组合必须是受支持的转换（mini 六型全组合都支持，
    真实硬件要看 ISA——这条留给真实编译器的 Verifier 查表）。"""
    errs: list[str] = []
    if in_t not in DTYPE_INFO:
        errs.append(f"[C1] 未知输入 dtype = {in_t!r}")
    if out_t not in DTYPE_INFO:
        errs.append(f"[C1] 未知输出 dtype = {out_t!r}")
    return errs


# ============================================================
# mini 图 IR：MiniCastOp + 图 + 使用计数 + 数值执行
# ============================================================

@dataclass
class MiniCastOp:
    """mini.cast Operation（文本格式仿第 64-66 天）：
    %c = mini.cast %in from=f32 to=f16 : (2x3x4xf32) -> (2x3x4xf16)
    cast 是逐元素类型转换，shape 保持不变。"""
    result_id: str
    input_id: str
    shape: tuple
    in_dtype: str
    out_dtype: str

    def print_ir(self) -> str:
        in_t = "x".join(str(d) for d in self.shape) + "x" + self.in_dtype
        out_t = "x".join(str(d) for d in self.shape) + "x" + self.out_dtype
        return (f"{self.result_id} = mini.cast {self.input_id} "
                f"from={self.in_dtype} to={self.out_dtype} "
                f": ({in_t}) -> ({out_t})")


@dataclass
class MiniGraph:
    """极简计算图：ops 顺序列表 + 返回值列表（返回值也算使用者）。
    input_dtypes 可显式声明入参类型——bf16 用 f32 仿真时必须声明，
    否则 verify 无法区分「f32 值恰好低位为零」和「真正的 bf16」。"""
    ops: list = field(default_factory=list)
    returns: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)    # value id -> ndarray
    input_dtypes: dict = field(default_factory=dict)

    def infer_dtype(self, vid: str) -> str:
        if vid in self.input_dtypes:
            return self.input_dtypes[vid]
        rev = {np.dtype(np.float32): "f32", np.dtype(np.float16): "f16",
               np.dtype(np.int32): "i32", np.dtype(np.int8): "i8",
               np.dtype(np.uint8): "ui8"}
        return rev.get(np.asarray(self.inputs[vid]).dtype, "?")

    def use_count(self, value_id: str) -> int:
        n = sum(1 for op in self.ops if op.input_id == value_id)
        if value_id in self.returns:
            n += 1
        return n

    def users_of(self, value_id: str) -> list:
        users = [op for op in self.ops if op.input_id == value_id]
        if value_id in self.returns:
            users.append("func.return")
        return users

    def verify(self) -> list[str]:
        errs = []
        known = set(self.inputs.keys())
        dtypes = {vid: self.infer_dtype(vid) for vid in self.inputs}
        shapes = {vid: np.asarray(arr).shape
                  for vid, arr in self.inputs.items()}
        for op in self.ops:
            if op.input_id not in known:
                errs.append(f"[G1] {op.result_id} 的输入 {op.input_id} 无定义")
                continue
            errs += verify_cast(op.in_dtype, op.out_dtype)
            if op.in_dtype != dtypes[op.input_id]:
                errs.append(f"[G3] {op.result_id} 声明输入类型 {op.in_dtype} "
                            f"与生产者实际类型 {dtypes[op.input_id]} 不一致")
            if tuple(op.shape) != tuple(shapes[op.input_id]):
                errs.append(f"[G3] {op.result_id} 声明形状 {op.shape} "
                            f"与生产者实际形状 {shapes[op.input_id]} 不一致")
            known.add(op.result_id)
            dtypes[op.result_id] = op.out_dtype
            shapes[op.result_id] = tuple(op.shape)
        for r in self.returns:
            if r not in known:
                errs.append(f"[G2] 返回值 {r} 无定义")
        return errs

    def print_ir(self) -> str:
        lines = []
        for vid, arr in self.inputs.items():
            lines.append(f"  {vid} : shape {arr.shape} dtype "
                         f"{arr.dtype}（func 入参，值可由 numpy 提供可见性）")
        for op in self.ops:
            lines.append(f"  {op.print_ir()}")
        lines.append(f"  func.return {', '.join(self.returns)}")
        return "\n".join(lines)

    def replace_all_uses(self, old: str, new: str) -> None:
        for op in self.ops:
            if op.input_id == old:
                op.input_id = new
        self.returns = [new if r == old else r for r in self.returns]

    def erase(self, result_id: str) -> None:
        self.ops = [op for op in self.ops if op.result_id != result_id]

    def eval(self) -> tuple:
        """数值执行：按 ops 顺序求值，返回 returns 对应的 ndarray 元组。"""
        env = dict(self.inputs)
        for op in self.ops:
            env[op.result_id] = convert(env[op.input_id], op.out_dtype)
        return tuple(env[r] for r in self.returns)


# ============================================================
# Pattern（今天的正式产出）＋ 反面教材
# ============================================================

def eliminate_identity_cast(graph: MiniGraph) -> bool:
    """Pattern：无操作 Cast 消除（今天的唯一正式 Pattern）。

    Cast(x, T) 且 type(x) == T → x。
    合法性论证（昨天 P1 的结论原样复用）：
      - 被删除的只有 op 自身；它的结果被替换成输入（两者值相等）；
      - replaceAllUses 把 %c 的全部使用者改道到 %x——多使用者无妨；
      - 所以不需要「唯一使用者」检查。
    判据是 dtype 全等（位宽、类别、符号/格式一项不同都不行）——
    只比位宽的版本见 eliminate_bitwidth_cast_bug（反面教材）。
    """
    for op in list(graph.ops):
        if classify_cast(op.in_dtype, op.out_dtype) != "identity":
            continue
        graph.replace_all_uses(op.result_id, op.input_id)
        graph.erase(op.result_id)
        return True            # 本轮只做一次，留给 PassManager 迭代
    return False


def eliminate_bitwidth_cast_bug(graph: MiniGraph) -> bool:
    """反面教材（不进任何管道）：只比位宽的「无操作」判据。

    它会把 i8→ui8（符号语义）、f16→bf16（同宽异格式）、f32→i32（域翻转）
    全部当 no-op 消除——第 5 节场景 F 用数值对拍当场揭穿：
    i8(-1) 应该变成 ui8(255)，消除后却还是 -1。
    """
    for op in list(graph.ops):
        if (DTYPE_INFO[op.in_dtype]["bits"]
                != DTYPE_INFO[op.out_dtype]["bits"]):
            continue
        graph.replace_all_uses(op.result_id, op.input_id)
        graph.erase(op.result_id)
        return True
    return False


PATTERNS = [("P eliminate_identity_cast", eliminate_identity_cast)]


def run_passes(graph: MiniGraph, patterns, max_rounds=10):
    """PassManager：迭代跑到不动点，返回 (轮数, 应用次数)。"""
    rounds, applied = 0, 0
    while True:
        changed = False
        for name, pat in patterns:
            if pat(graph):
                changed = True
                applied += 1
        rounds += 1
        if not changed or rounds >= max_rounds:
            return rounds, applied


# ============================================================
# MLIR 侧：cast 家族在 stock 管道里的真实裁决
# ============================================================

def find_mlir_opt() -> str | None:
    for cand in (shutil.which("mlir-opt"), "/usr/lib/llvm-18/bin/mlir-opt"):
        if cand and Path(cand).exists() and Path(cand).stat().st_mode & 0o111:
            return cand
    return None


def run_mlir_opt(ir_text: str, extra_args: list[str]) -> tuple[int, str, str]:
    exe = find_mlir_opt()
    if exe is None:
        return -1, "", "mlir-opt 不可用"
    p = subprocess.run([exe, *extra_args, "-"], input=ir_text,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


CAST_OPS = ("arith.extf", "arith.truncf", "arith.extsi", "arith.extui",
            "arith.trunci", "arith.bitcast")


def count_casts(text: str) -> int:
    return sum(text.count(op) for op in CAST_OPS)


EXTF_SAME_IR = """module {
  func.func @extf_same(%x: f32) -> f32 {
    %r = arith.extf %x : f32 to f32
    return %r : f32
  }
}
"""

BITCAST_UI8_IR = """module {
  func.func @bitcast_ui8(%x: i8) -> ui8 {
    %b = arith.bitcast %x : i8 to ui8
    return %b : ui8
  }
}
"""

TRUNC_EXT_IR = """module {
  func.func @trunc_ext(%x: f16) -> f16 {
    %e = arith.extf %x : f16 to f32
    %t = arith.truncf %e : f32 to f16
    return %t : f16
  }
}
"""

EXT_TRUNC_IR = """module {
  func.func @ext_trunc(%x: f32) -> f32 {
    %t = arith.truncf %x : f32 to f16
    %e = arith.extf %t : f16 to f32
    return %e : f32
  }
}
"""

TRUNCSI_EXTSI_IR = """module {
  func.func @truncsi_extsi(%x: i8) -> i8 {
    %e = arith.extsi %x : i8 to i32
    %t = arith.trunci %e : i32 to i8
    return %t : i8
  }
}
"""

EXTSI_TRUNC_IR = """module {
  func.func @extsi_trunc(%x: i32) -> i32 {
    %t = arith.trunci %x : i32 to i8
    %e = arith.extsi %t : i8 to i32
    return %e : i32
  }
}
"""

BITCAST_SAME_IR = """module {
  func.func @bitcast_same(%x: f32) -> f32 {
    %r = arith.bitcast %x : f32 to f32
    return %r : f32
  }
}
"""

BITCAST_CHAIN_IR = """module {
  func.func @bitcast_chain(%x: f32) -> f32 {
    %b1 = arith.bitcast %x : f32 to i32
    %b2 = arith.bitcast %b1 : i32 to f32
    return %b2 : f32
  }
}
"""


# ============================================================
# 主实验
# ============================================================

def main() -> int:
    rng = random.Random(67)

    print("=" * 66)
    print("第 67 天主实验：Cast 消除（类型全等判据 + 符号语义 + 方向终审）")
    print("=" * 66)

    print("\n== 0. 环境与主线 ==")
    print(f"python  {platform.python_version()}")
    print(f"numpy   {np.__version__}")
    print(f"arch    {platform.machine()}")
    mlir_opt = find_mlir_opt()
    if mlir_opt:
        ver = subprocess.run([mlir_opt, "--version"], capture_output=True,
                             text=True).stdout.splitlines()
        print(f"mlir-opt {mlir_opt}（{(ver or ['?'])[0]}）")
    else:
        print("mlir-opt 不可用")
    print("主线：什么才是「无操作 Cast」——类型全等的唯一判据、四类反例的"
          "数值证据、位宽陷阱的反面教材、回环链的方向终审与 MLIR 实测。")

    B32 = np.array([[0.1, 0.5, 2.75], [-3.25, 100.0, 0.0]],
                   dtype=np.float32).reshape(2, 3)      # 贯穿例子
    B8 = np.array([[-1, 0, 127], [-128, 5, 42]], dtype=np.int8).reshape(2, 3)

    # ---- 1. 现场一：MLIR stock 管道对 cast 家族的裁决 ----
    print("\n== 1. 现场一：cast 家族交给 --canonicalize，stock 管道动不动？==")
    if mlir_opt:
        cases = [
            ("① extf f32→f32（无操作扩展）", EXTF_SAME_IR, "extf_same",
             "reject"),
            ("② bitcast f32→f32（无操作重解释）", BITCAST_SAME_IR,
             "bitcast_same", "elim"),
            ("③ truncf∘extf f16→f32→f16（安全回环）", TRUNC_EXT_IR,
             "trunc_ext", "keep2"),
            ("④ extf∘truncf f32→f16→f32（有损回环）", EXT_TRUNC_IR,
             "ext_trunc", "keep2"),
            ("⑤ trunci∘extsi i8→i32→i8（安全回环）", TRUNCSI_EXTSI_IR,
             "truncsi_extsi", "elim"),
            ("⑥ extsi∘trunci i32→i8→i32（有损回环）", EXTSI_TRUNC_IR,
             "extsi_trunc", "keep2"),
            ("⑦ bitcast 链 f32→i32→f32（双射回环）", BITCAST_CHAIN_IR,
             "bitcast_chain", "elim"),
            ("⑧ bitcast i8→ui8（符号进类型？）", BITCAST_UI8_IR,
             "bitcast_ui8", "reject"),
        ]
        for title, ir, stem, expect in cases:
            code, canon, errtext = run_mlir_opt(ir, ["--canonicalize"])
            if code == 0:
                (OUT / f"{stem}.canon.mlir").write_text(canon,
                                                        encoding="utf-8")
                n = count_casts(canon)
                ret0 = "return %arg0" in canon
                verdict = ("消除为 return %arg0" if n == 0 and ret0 else
                           f"原样保留 {n} 个 cast op")
            else:
                (OUT / f"{stem}.reject.txt").write_text(errtext,
                                                        encoding="utf-8")
                verdict = ("Verifier 拒绝（exit=%d）" % code)
            print(f"  {title}")
            print(f"    --canonicalize {verdict}")
            if code != 0:
                first = [ln for ln in errtext.splitlines() if "error:" in ln]
                print(f"    {first[0].strip() if first else '(见 outputs/)'}")
        print("  对照读法：②⑦ bitcast 的同型/双射回环会被消除；⑤ 整数回环"
              "（trunci∘extsi）有折叠；")
        print("            ③ 浮点回环（truncf∘extf）stock 没有这条规则——"
              "数学上恒等也要自己写；")
        print("            ④⑥ 有损方向一律原样保留（正确）；①⑧ 表达不出"
              "的 op 直接被 Verifier 拦在门外。")

        _, c1, e1 = run_mlir_opt(EXTF_SAME_IR, ["--canonicalize"])
        check("① extf f32→f32 被 Verifier 拒绝（方向化家族表达不出 no-op）",
              "cast incompatible" in e1)

        _, c2, _ = run_mlir_opt(BITCAST_SAME_IR, ["--canonicalize"])
        check("② bitcast f32→f32 消除为 return %arg0",
              count_casts(c2) == 0 and "return %arg0" in c2)

        _, c3, _ = run_mlir_opt(TRUNC_EXT_IR, ["--canonicalize"])
        check("③ truncf∘extf（安全回环）stock 原样保留 2 个 op（无此规则）",
              count_casts(c3) == 2)

        _, c4, _ = run_mlir_opt(EXT_TRUNC_IR, ["--canonicalize"])
        check("④ extf∘truncf（有损回环）原样保留 2 个 op（正确拒绝）",
              count_casts(c4) == 2)

        _, c5, _ = run_mlir_opt(TRUNCSI_EXTSI_IR, ["--canonicalize"])
        check("⑤ trunci∘extsi（安全回环）消除为 return %arg0",
              count_casts(c5) == 0 and "return %arg0" in c5)

        _, c7, _ = run_mlir_opt(BITCAST_CHAIN_IR, ["--canonicalize"])
        check("⑦ bitcast 链 f32→i32→f32 消除为 return %arg0",
              count_casts(c7) == 0 and "return %arg0" in c7)

        _, _, e8 = run_mlir_opt(BITCAST_UI8_IR, ["--canonicalize"])
        check("⑧ ui8 类型不存在：MLIR 整数 signless，符号在 op 不在类型",
              "signless" in e8 or "ui8" in e8)
    else:
        print("  mlir-opt 不可用，现场一降级为「预期输出，尚未执行」")

    # ---- 2. 类型分类与数值现场 ----
    print("\n== 2. 五分类：一个 dtype 对一张脸 ==")
    pairs = [
        ("f32", "f32"), ("f16", "f16"), ("bf16", "bf16"), ("i8", "i8"),
        ("f16", "f32"), ("bf16", "f32"), ("i8", "i32"), ("ui8", "i32"),
        ("f32", "f16"), ("f32", "bf16"), ("i32", "i8"),
        ("f16", "bf16"), ("bf16", "f16"),
        ("i8", "ui8"), ("ui8", "i8"),
        ("f32", "i32"), ("i32", "f32"),
    ]
    print("  in → out      分类          今日裁决")
    for i, o in pairs:
        cls = classify_cast(i, o)
        verdict = "消除" if cls == "identity" else "保留"
        print(f"  {i:>4} → {o:<4}  {CLASS_NAME[cls]:<6}"
              f"（{cls:<10}）  {verdict}")
    check("五分类覆盖 17 个 dtype 对：identity 4 个、其余 13 个全保留",
          sum(1 for i, o in pairs
              if classify_cast(i, o) == "identity") == 4
          and all(classify_cast(i, o) in
                  ("identity", "widen", "narrow", "signflip", "reformat",
                   "domainflip") for i, o in pairs))

    print("\n== 3. 数值现场：0.1 的三重人格 + 0xFF 的两副面孔 ==")
    a32 = np.float32(0.1)
    a16 = np.float16(a32)
    abf = to_bf16(a32)
    print(f"  f32(0.1)  = {float(a32)!r:<22} bits 0x{a32.view(np.uint32):08X}")
    print(f"  f16(f32(0.1))  = {float(a16)!r:<22} bits 0x{a16.view(np.uint16):04X}"
          f"（10 位尾数）")
    print(f"  bf16(f32(0.1)) = {float(abf)!r:<22} "
          f"bits 0x{int(abf.view(np.uint32)):08X}"
          f"（7 位尾数，截断）")
    print(f"  回环 f32→f16→f32  == 原值？ {np.float32(a16) == a32}"
          f"（{float(a32)!r} ≠ {float(np.float32(a16))!r}）")
    check("f32→f16→f32 回环改变数值（0.1 的现场）",
          np.float32(np.float16(a32)) != a32)

    half = np.float32(0.5)
    print(f"  假阴性现场：f32(0.5) 回环 == 原值？ "
          f"{np.float32(np.float16(half)) == half}"
          f"（2 的幂在 f16 里精确——测试值不能只挑好值）")
    check("0.5 的回环恰好相等（假阴性陷阱的实证）",
          np.float32(np.float16(half)) == half)

    i300 = np.int32(300).astype(np.int8)
    print(f"  i32(300) → i8 = {int(i300)}（回绕 300-256）；"
          f"回 i32 = {int(i300.astype(np.int32))}")
    check("i32→i8 回绕丢高位（300 → 44）", int(i300) == 44)

    m1 = np.int8(-1)
    u255 = m1.astype(np.uint8)
    print(f"  i8(-1) → ui8 = {int(u255)}；位都是 0xFF："
          f"{m1.view(np.uint8):#04x} == {u255.view(np.uint8):#04x}")
    print(f"  但值不等：np.array_equal(-1i8, 255ui8) = "
          f"{np.array_equal(np.array(-1, np.int8), np.array(255, np.uint8))}"
          f"——位宽相同的两副面孔")
    check("i8→ui8 位不变值变（0xFF = -1 或 255）",
          int(u255) == 255 and m1.view(np.uint8) == u255.view(np.uint8)
          and not np.array_equal(np.array(-1, np.int8),
                                 np.array(255, np.uint8)))

    # ---- 4. mini 侧：Pattern 的现场 ----
    print("\n== 4. mini 侧：无操作 Cast 消除的现场 ==")
    print("Pattern：Cast(x, T) 且 type(x) == T → x——不需要唯一使用者检查"
          "（昨天 P1 原型）")

    print("\n场景 A（identity 多使用者：%r 被 %a、%b 两个消费者用 → 照样消除）：")
    gA = MiniGraph(
        ops=[MiniCastOp("%r", "%in", (2, 3), "f32", "f32"),
             MiniCastOp("%a", "%r", (2, 3), "f32", "f16"),
             MiniCastOp("%b", "%r", (2, 3), "f32", "i32")],
        returns=["%a", "%b"],
        inputs={"%in": B32})
    print(gA.print_ir())
    print(f"  %r 的使用者数 = {gA.use_count('%r')}（%a、%b 各一）——Pattern 不看这个")
    before = gA.eval()
    rounds, applied = run_passes(gA, PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gA.print_ir())
    check("A：identity 消除不看使用者数（op 数 3→2），%a/%b 全部改道读 %in",
          len(gA.ops) == 2 and gA.ops[0].input_id == "%in"
          and gA.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(gA.eval(), before)))

    print("\n场景 B（identity 单跳直返 → 整体消除为 return %in）：")
    gB = MiniGraph(
        ops=[MiniCastOp("%c", "%in", (2, 3), "f32", "f32")],
        returns=["%c"],
        inputs={"%in": B32})
    before = gB.eval()
    rounds, applied = run_passes(gB, PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gB.print_ir())
    check("B：identity 单跳整体消除（op 数 1→0，return %in）",
          len(gB.ops) == 0 and gB.returns == ["%in"]
          and np.array_equal(gB.eval()[0], before[0]))

    print("\n场景 C（混合图：identity + 精度扩展 + 精度缩减 → 只消 identity）：")
    gC = MiniGraph(
        ops=[MiniCastOp("%a", "%in", (2, 3), "f32", "f32"),
             MiniCastOp("%b", "%a", (2, 3), "f32", "f16"),
             MiniCastOp("%c", "%b", (2, 3), "f16", "f32")],
        returns=["%c"],
        inputs={"%in": B32})
    print(gC.print_ir())
    before = gC.eval()
    rounds, applied = run_passes(gC, PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gC.print_ir())
    print("  %a 消除后 %b 直读 %in；%b（f32→f16 扩展）和 %c（f16→f32 缩减）"
          "原样保留——f32→f16→f32 链是「先缩后扩」，合并会改数值（第 6 节）")
    check("C：混合图只消 identity（op 数 3→2），widen/narrow 原样保留",
          len(gC.ops) == 2 and gC.ops[0].input_id == "%in"
          and gC.ops[0].out_dtype == "f16" and gC.ops[1].out_dtype == "f32"
          and np.array_equal(gC.eval()[0], before[0]))

    print("\n场景 D（连续两个 identity：f32→f32→f32 → 迭代到 0）：")
    gD = MiniGraph(
        ops=[MiniCastOp("%a", "%in", (2, 3), "f32", "f32"),
             MiniCastOp("%b", "%a", (2, 3), "f32", "f32")],
        returns=["%b"],
        inputs={"%in": B32})
    before = gD.eval()
    rounds, applied = run_passes(gD, PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次（每轮消一个）：")
    print(gD.print_ir())
    check("D：连续 identity 迭代消除（op 数 2→0，2 次应用 + 1 轮不动点确认）",
          len(gD.ops) == 0 and applied == 2 and rounds == 3
          and np.array_equal(gD.eval()[0], before[0]))

    print("\n场景 E（四类反例单跳：widen/narrow/signflip/domainflip → 全保留）：")
    gE = MiniGraph(
        ops=[MiniCastOp("%w", "%in", (2, 3), "f32", "f16"),
             MiniCastOp("%n", "%in", (2, 3), "f32", "bf16"),
             MiniCastOp("%d", "%in", (2, 3), "f32", "i32"),
             MiniCastOp("%s", "%inp", (2, 3), "i8", "ui8")],
        returns=["%w", "%n", "%d", "%s"],
        inputs={"%in": B32, "%inp": B8})
    print(gE.print_ir())
    before = gE.eval()
    rounds, applied = run_passes(gE, PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gE.print_ir())
    print("  四个 op 分别是精度扩展（f16）、精度缩减（bf16）、域翻转（i32）、"
          "符号语义（ui8）——没有一个是 identity，全保留")
    check("E：四类反例全保留（op 数 4→4，零应用）且数值不变",
          len(gE.ops) == 4 and applied == 0
          and all(np.array_equal(a, b) for a, b in zip(gE.eval(), before)))

    print("\n场景 F（反面教材：只比位宽的 buggy 版在 i8→ui8 上翻车）：")
    gF = MiniGraph(
        ops=[MiniCastOp("%u", "%in", (2, 3), "i8", "ui8")],
        returns=["%u"],
        inputs={"%in": B8})
    before = gF.eval()
    gF_ok = MiniGraph(
        ops=[MiniCastOp("%u", "%in", (2, 3), "i8", "ui8")],
        returns=["%u"],
        inputs={"%in": B8})
    run_passes(gF_ok, PATTERNS)
    print(f"  正确版（dtype 全等）：op 数 1→{len(gF_ok.ops)}，"
          f"返回值 dtype {gF_ok.eval()[0].dtype}，"
          f"值[0,0] = {int(gF_ok.eval()[0][0, 0])}")
    while eliminate_bitwidth_cast_bug(gF):
        pass
    after = gF.eval()
    print(f"  buggy 版（只比位宽）：op 数 1→{len(gF.ops)}，"
          f"返回值 dtype {after[0].dtype}，值[0,0] = {int(after[0][0, 0])}")
    print(f"  数值对拍：正确版 == 优化前 {np.array_equal(gF_ok.eval()[0], before[0])}；"
          f"buggy 版 == 优化前 {np.array_equal(after[0], before[0])}"
          f"（-1 应该变成 255，buggy 版还是 -1）")
    check("F：正确判据保留 i8→ui8（值 255 不变）；位宽判据当场翻车（255 → -1）",
          len(gF_ok.ops) == 1 and np.array_equal(gF_ok.eval()[0], before[0])
          and len(gF.ops) == 0 and not np.array_equal(after[0], before[0]))

    gF2 = MiniGraph(
        ops=[MiniCastOp("%i", "%in", (2, 3), "f32", "i32")],
        returns=["%i"],
        inputs={"%in": B32})
    before2 = gF2.eval()
    while eliminate_bitwidth_cast_bug(gF2):
        pass
    check("F2：位宽判据同样放过 f32→i32（0.1/0.5 变成 0）——位宽不是类型",
          len(gF2.ops) == 0 and not np.array_equal(gF2.eval()[0], before2))

    # ---- 5. 判定表 + 随机压力对拍 ----
    print("\n== 5. 判定表：17 个 dtype 对，优化前后数值对拍 ==")
    print("  in → out      分类          优化后op数  数值对拍")
    all_ok = True
    for i, o in pairs:
        cls = classify_cast(i, o)
        if DTYPE_INFO[i]["kind"] == "int":
            if i == "i32":
                x = np.array([[-128, -1, 127], [255, 300, 42]],
                             dtype=np.int32)
            else:
                x = B8.astype(NP_OF[i])
        else:
            x = B32.astype(NP_OF.get(i, np.float32))
            if i == "bf16":
                x = to_bf16(x)
        g = MiniGraph(ops=[MiniCastOp("%c", "%in", (2, 3), i, o)],
                      returns=["%c"], inputs={"%in": x},
                      input_dtypes={"%in": i})
        before = g.eval()
        run_passes(g, PATTERNS)
        expect = 0 if cls == "identity" else 1
        ok = (len(g.ops) == expect and g.verify() == []
              and values_equal(g.eval()[0], before[0]))
        all_ok &= ok
        print(f"  {i:>4} → {o:<4}  {CLASS_NAME[cls]:<6}"
              f"（{cls:<10}）  {len(g.ops):>6}      "
              f"{'ok' if ok else 'MISMATCH'}")
    check("判定表 17/17：identity → 0 op，其余 → 1 op，数值全不变", all_ok)

    print("\n随机压力对拍（300 组随机 dtype 链，链长 1..5，六型全组合；"
          "值域非负有界（int 0..127 / float 0.125..8.125）——回绕与负值的"
          "翻车现场由判定表和场景 F 承担）：")
    rand_ok, ops_before, ops_after = 0, 0, 0
    nrng = np.random.default_rng(67)

    def random_input(dtype, n=6):
        if DTYPE_INFO[dtype]["kind"] == "int":
            return nrng.integers(0, 128, size=n).astype(NP_OF[dtype])
        v = nrng.integers(0, 32, size=n) * 0.25 + 0.125
        if dtype == "f16":
            return v.astype(np.float16)
        if dtype == "bf16":
            return to_bf16(v)
        return v.astype(np.float32)

    for _ in range(300):
        start = rng.choice(DTYPES)
        L = rng.randint(1, 5)
        chain = [rng.choice(DTYPES) for _ in range(L)]
        x = random_input(start).reshape(2, 3)
        ops_, cur = [], start
        ids = ["%in"] + [f"%t{k}" for k in range(L)]
        for k, tgt in enumerate(chain):
            ops_.append(MiniCastOp(ids[k + 1], ids[k], (2, 3), cur, tgt))
            cur = tgt
        g = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": x},
                      input_dtypes={"%in": start})
        before = g.eval()
        run_passes(g, PATTERNS)
        after = g.eval()
        expect = sum(1 for k, tgt in enumerate(chain)
                     if chain[k] != ([start] + chain)[k])
        ops_before += L
        ops_after += len(g.ops)
        if (values_equal(after[0], before[0]) and g.verify() == []
                and len(g.ops) == expect):
            rand_ok += 1
    check(f"随机对拍 {rand_ok}/300：数值不变、Verifier 通过、"
          f"op 数 = 非 identity 跳数", rand_ok == 300)
    n_identity_total = ops_before - ops_after
    print(f"  300 组共 {ops_before} 个初始 cast op，消除 {n_identity_total} 个"
          f" identity，保留 {ops_after} 个类型变换——保留的每个都有类型理由")

    # ---- 6. 回环终审：方向决定安全 ----
    print("\n== 6. 回环终审：信息只往窄的方向丢（方向决定安全）==")
    print("  回环链                  数值现场                                    裁决")
    trials = []

    x16 = np.concatenate([nrng.standard_normal(1000).astype(np.float16),
                          np.array([np.inf, -np.inf, np.nan],
                                   dtype=np.float16)])
    rt16 = x16.astype(np.float32).astype(np.float16)
    ok16 = np.array_equal(rt16, x16, equal_nan=True)
    trials.append(("f16→f32→f16", "1003 个值（含 ±inf/NaN）全部原样", ok16,
                   "安全：f16 值集 ⊆ f32"))

    x32 = np.concatenate([nrng.standard_normal(1000).astype(np.float32),
                          np.array([np.inf, -np.inf, 1e-8],
                                   dtype=np.float32)])
    rt32 = x32.astype(np.float16).astype(np.float32)
    n_diff = int(np.count_nonzero(rt32 != x32))
    trials.append(("f32→f16→f32", f"1003 个值里 {n_diff} 个变了"
                   f"（0.1 → 0.0999755859375）", not np.array_equal(rt32, x32),
                   "有损：f16 值集 ⊄ f32"))

    xi8 = np.array([-128, -1, 0, 127], dtype=np.int8)
    rti8 = xi8.astype(np.int32).astype(np.int8)
    trials.append(("i8→i32→i8", "[-128,-1,0,127] 全部原样",
                   np.array_equal(rti8, xi8), "安全：符号扩展保低位"))

    xi32 = np.array([-128, -1, 0, 127, 255, 300], dtype=np.int32)
    rti32 = xi32.astype(np.int8).astype(np.int32)
    trials.append(("i32→i8→i32", "[255→-1, 300→44] 高位丢了",
                   not np.array_equal(rti32, xi32), "有损：截断丢高位"))

    xbf = np.float32(0.1)
    rtbf = to_bf16(xbf)
    trials.append(("f32→bf16→f32", "0.1 → 0.099609375（截断版 bf16）",
                   float(rtbf) != float(xbf), "有损：尾数 24 → 7 位"))

    m = np.array([-128, -1, 0, 127], dtype=np.int8)
    rtsign = m.astype(np.uint8).astype(np.int8)
    trials.append(("i8→ui8→i8", "[-128..127] 双射回原（mod 256）",
                   np.array_equal(rtsign, m),
                   "安全：同宽双射（但今天也不合并）"))

    xf = np.array([0.5, 2.75, -3.25], dtype=np.float32)
    rtf = xf.astype(np.int32).astype(np.float32)
    trials.append(("f32→i32→f32", "[0.5, 2.75, -3.25] → [0, 2, -3]",
                   not np.array_equal(rtf, xf), "有损：小数部分蒸发"))

    for name, scene, unsafe_flag, why in trials:
        print(f"  {name:<14}  {scene:<44}  {why}")
    check("方向终审：先窄后宽 ≠ 恒等（f32→f16→f32、i32→i8→i32、"
          "f32→bf16→f32、f32→i32→f32 全部改变数值）",
          trials[1][2] and trials[3][2] and trials[4][2] and trials[6][2])
    check("方向终审：先宽后窄回到子集才安全（f16→f32→f16、i8→i32→i8）"
          "——即便如此，今天也只做 identity，回环合并留给以后",
          trials[0][2] and trials[2][2])
    check("方向终审：同宽双射（i8→ui8→i8）数学上安全，"
          "但需要逐对证明——mini 的保守边界把它一并挡在门外",
          trials[5][2])

    # ---- 7. 汇总 ----
    print()
    print("=" * 66)
    print(f"汇总：PASS {PASS} / FAIL {FAIL}")
    print("=" * 66)
    return 0 if FAIL == 0 else 1


def values_equal(a, b) -> bool:
    """数值对拍（NaN 视为相等——identity 消除不改变位模式，位模式对拍见测试）。"""
    if a.shape != b.shape:
        return False
    if a.dtype.kind == "f" and b.dtype.kind == "f":
        return np.array_equal(a, b, equal_nan=True)
    return np.array_equal(a, b)


if __name__ == "__main__":
    raise SystemExit(main())
