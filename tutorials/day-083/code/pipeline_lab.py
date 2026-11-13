#!/usr/bin/env python3
"""pipeline_lab.py —— 第 83 天（第三阶段集成验收）主实验。

把第三阶段四周的积木拼成一台「图优化小编译器」：

    输入图（含 Q/DQ、Transpose、Reshape 链、MatMul、Bias、Relu）
        ↓ 闸0  合法性检查（Day 12/39/59/60/64 的 Verifier）
        ↓ 闸1  QDQ 清理   —— Day 82 规则表上岗：R04 常量折叠 / R03 幂等尾对
        ↓ 闸2  布局简化   —— Day 64/65：transpose(const) 折叠、互逆对消除、排列合并
        ↓ 闸3  Reshape 合并 —— Day 66：reshape(reshape(x)) → reshape(x)
             （闸1~3 在不动点循环里反复跑，Day 69 的教训：机会是上一轮创造出来的）
        ↓ 闸4  融合 + Cost Model —— Day 50~54 合法性、Day 71~76 收益判断
        ↓ 终验  两层口径：位等价（优化不得引入任何数值变化，容差=0）
                    ＋ FP64 golden（Day 79 工具 + Day 78 误差账本 atol）

贯穿例子（11 个节点）：
    %x(2,12) → reshape(24,) → reshape(4,6) ─┐
    const W_t(3,6) → Q → DQ → transpose ┄┄→ matmul → add(bias) → relu → return
优化后 5 个节点：
    %x → reshape(4,6) → fused_matmul_bias_relu(const Ŵᵀ, const b)

数值纪律（不编数字）：
  - 位等价的结构保证：编译期折叠复用执行器的同一套 v_* 数值内核（fp32），
    融合算子严格按 fp32 的 matmul→add→relu 复刻——口径就是语义；
  - 权重/激活的量化 scale 全部取 2 的幂：除法是精确的，fp32 与 fp64 的
    round 永远落在同一格（量化图 golden 对比的已知坑，见正文 6.4）；
  - golden 的 atol 不用 Day 79 的固定表，而是按 Day 78 的累加误差账本
    逐图计算：(2K+2)·eps32·max Σ|a·b|。

运行：python3 pipeline_lab.py   （在 code/ 目录下）
输出：全部测试与实验打印到终端，并归档到 outputs/（IR 对照 + 完整报告）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = 0
FAIL = 0

EPS32 = 2.0 ** -23
QMIN, QMAX = -128, 127


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ============================================================
# 形状工具（Day 16/60/64 约定的直接复用）
# ============================================================

def numel(shape) -> int:
    n = 1
    for d in shape:
        n *= int(d)
    return n


def valid_perm(p) -> bool:
    return sorted(p) == list(range(len(p)))


def t_shape(shape, perm) -> tuple:
    """Day 64 约定：out_shape[i] = in_shape[perm[i]]（与 np.transpose 一致）。"""
    return tuple(shape[perm[i]] for i in range(len(perm)))


def compose_perm(p1, p2) -> tuple:
    """T_{p2}(T_{p1}(x)) = T_r(x)，r[i] = p1[p2[i]]（Day 65 的排列合并）。"""
    return tuple(p1[p2[i]] for i in range(len(p2)))


def broadcast_shape(a, b):
    """Day 60 规则：右对齐比较，维度相等或为 1 扩展；不兼容返回 None。"""
    ra, rb = list(a)[::-1], list(b)[::-1]
    out = []
    for i in range(max(len(ra), len(rb))):
        da = ra[i] if i < len(ra) else 1
        db = rb[i] if i < len(rb) else 1
        if da == db or db == 1:
            out.append(da)
        elif da == 1:
            out.append(db)
        else:
            return None
    return tuple(out[::-1])


# ============================================================
# mini 图 IR（Day 69 的 Op/Graph 扩展 Q/DQ 与 fused 算子）
# ============================================================

@dataclass
class Op:
    kind: str                          # arg/const/quantize/dequantize/transpose/
                                       # reshape/matmul/add/relu/fused_matmul_bias_relu
    inputs: list = field(default_factory=list)
    name: str = ""
    # --- 属性 ---
    shape: tuple = ()                  # arg
    value: np.ndarray | None = None    # const（统一存 fp32）
    scale: float = 0.0                 # quantize/dequantize
    zp: int = 0                        # quantize/dequantize
    perm: tuple = ()                   # transpose
    new_shape: tuple = ()              # reshape
    out_shape: tuple | None = None     # 形状推导结果


class Graph:
    def __init__(self, name: str):
        self.name = name
        self.ops: list[Op] = []
        self.returns: list[str] = []
        self._n = 0

    # ---------- 构图 API（追加即拓扑序，Day 16 的保证） ----------

    def _fresh(self) -> str:
        self._n += 1
        return f"%{self._n}"

    def add(self, kind: str, inputs=(), name: str = "", **kw) -> str:
        nm = name or self._fresh()
        self.ops.append(Op(kind=kind, inputs=list(inputs), name=nm, **kw))
        return nm

    def arg(self, shape, name: str = "") -> str:
        nm = name or self._fresh()
        return self.add("arg", (), name=nm, shape=tuple(shape))

    def const(self, value) -> str:
        v = np.asarray(value, dtype=np.float32)
        return self.add("const", (), value=v)

    def quantize(self, x: str, scale: float, zp: int) -> str:
        return self.add("quantize", [x], scale=float(scale), zp=int(zp))

    def dequantize(self, x: str, scale: float, zp: int) -> str:
        return self.add("dequantize", [x], scale=float(scale), zp=int(zp))

    def transpose(self, x: str, perm) -> str:
        return self.add("transpose", [x], perm=tuple(perm))

    def reshape(self, x: str, new_shape) -> str:
        return self.add("reshape", [x], new_shape=tuple(new_shape))

    def matmul(self, a: str, b: str) -> str:
        return self.add("matmul", [a, b])

    def add_op(self, a: str, b: str) -> str:
        return self.add("add", [a, b])

    def relu(self, x: str) -> str:
        return self.add("relu", [x])

    def fused_matmul_bias_relu(self, a: str, b: str, bias: str) -> str:
        return self.add("fused_matmul_bias_relu", [a, b, bias])

    # ---------- 图查询 ----------

    def producers(self) -> dict[str, Op]:
        return {op.name: op for op in self.ops}

    def use_counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for op in self.ops:
            for i in op.inputs:
                c[i] = c.get(i, 0) + 1
        for r in self.returns:
            c[r] = c.get(r, 0) + 1
        return c

    def op(self, name: str) -> Op:
        for o in self.ops:
            if o.name == name:
                return o
        raise KeyError(name)

    # ---------- 改写原语（Day 45/51 的使用者迁移） ----------

    def rewire(self, old: str, new: str) -> None:
        for op in self.ops:
            op.inputs = [new if i == old else i for i in op.inputs]
        self.returns = [new if r == old else r for r in self.returns]

    def remove(self, name: str) -> None:
        self.ops = [op for op in self.ops if op.name != name]

    def replace(self, old: Op, new: Op) -> None:
        """在 old 的拓扑位置放入 new，并把 old 的使用者迁移到 new。"""
        idx = self.ops.index(old)
        self.ops[idx] = new
        self.rewire(old.name, new.name)

    def copy(self) -> "Graph":
        g = Graph(self.name)
        g.ops = [Op(**{k: (list(v) if k == "inputs" else v) for k, v in
                       ((f, getattr(op, f)) for f in
                        ("kind", "inputs", "name", "shape", "value", "scale",
                         "zp", "perm", "new_shape", "out_shape"))})
                 for op in self.ops]
        g.returns = list(self.returns)
        g._n = self._n
        return g

    # ---------- 形状推导 + Verifier（Day 39/59/60/64 汇合） ----------

    def infer_shapes(self) -> tuple[dict[str, tuple], list[str]]:
        shapes: dict[str, tuple] = {}
        errors: list[str] = []
        for op in self.ops:
            def need(nm):
                if nm not in shapes:
                    errors.append(f"{op.name}: 输入 {nm} 未在此前定义（拓扑序破坏）")
                    return None
                return shapes[nm]

            if op.kind == "arg":
                s = tuple(op.shape)
            elif op.kind == "const":
                s = tuple(op.value.shape)
            elif op.kind in ("quantize", "dequantize"):
                s = need(op.inputs[0]) or ()
                if op.kind == "quantize" and not (op.scale > 0):
                    errors.append(f"{op.name}: quantize 需要 scale > 0，得到 {op.scale}")
            elif op.kind == "transpose":
                if not valid_perm(op.perm):
                    errors.append(f"{op.name}: 非法排列 {op.perm}")
                    s = ()
                else:
                    a = need(op.inputs[0])
                    s = t_shape(a, op.perm) if a is not None else ()
            elif op.kind == "reshape":
                a = need(op.inputs[0])
                if a is not None and numel(a) != numel(op.new_shape):
                    errors.append(f"{op.name}: reshape 元素数不符 {a}→{op.new_shape}"
                                  f"（{numel(a)} ≠ {numel(op.new_shape)}）")
                s = tuple(op.new_shape)
            elif op.kind == "matmul":
                a, b = need(op.inputs[0]), need(op.inputs[1])
                if a is not None and b is not None:
                    if len(a) != 2 or len(b) != 2:
                        errors.append(f"{op.name}: matmul 只支持二维，得到 {a} @ {b}")
                        s = ()
                    elif a[1] != b[0]:
                        errors.append(f"{op.name}: matmul 内维不匹配 {a} @ {b}")
                        s = ()
                    else:
                        s = (a[0], b[1])
                else:
                    s = ()
            elif op.kind == "add":
                a, b = need(op.inputs[0]), need(op.inputs[1])
                if a is not None and b is not None:
                    s = broadcast_shape(a, b)
                    if s is None:
                        errors.append(f"{op.name}: 无法广播 {a} + {b}")
                        s = ()
                else:
                    s = ()
            elif op.kind == "relu":
                s = need(op.inputs[0]) or ()
            elif op.kind == "fused_matmul_bias_relu":
                a, b, bias = (need(op.inputs[0]), need(op.inputs[1]),
                              need(op.inputs[2]))
                if None not in (a, b, bias):
                    if len(a) != 2 or len(b) != 2 or a[1] != b[0]:
                        errors.append(f"{op.name}: 融合算子内维不匹配 {a} @ {b}")
                        s = ()
                    else:
                        s = broadcast_shape((a[0], b[1]), bias)
                        if s is None:
                            errors.append(f"{op.name}: bias 无法广播到 {(a[0], b[1])}")
                            s = ()
                else:
                    s = ()
            else:
                errors.append(f"{op.name}: 未知算子类型 {op.kind}")
                s = ()
            op.out_shape = s
            shapes[op.name] = s
        return shapes, errors

    def verify(self) -> list[str]:
        _, errors = self.infer_shapes()
        for r in self.returns:
            if r not in {op.name for op in self.ops}:
                errors.append(f"返回值 {r} 未定义")
        return errors

    # ---------- 数值执行（fp32 运行 / fp64 golden 共用同一条路） ----------

    def run(self, feed: dict, dtype=np.float32) -> list[np.ndarray]:
        env: dict[str, np.ndarray] = {}
        for op in self.ops:
            if op.kind == "arg":
                # 输入先落 fp32 格（图的输入类型是 tensor<...xf32>），
                # golden 通道再把格子上的值升到 fp64 —— Day 79 的「入乡随俗」：
                # 对比的只剩计算误差，不混入输入舍入
                v32 = np.asarray(feed[op.name], dtype=np.float32)
                env[op.name] = v32 if dtype is np.float32 else v32.astype(dtype)
            elif op.kind == "const":
                env[op.name] = op.value.astype(dtype)
            elif op.kind == "quantize":
                env[op.name] = v_quantize(env[op.inputs[0]], op.scale, op.zp, dtype)
            elif op.kind == "dequantize":
                env[op.name] = v_dequantize(env[op.inputs[0]], op.scale, op.zp, dtype)
            elif op.kind == "transpose":
                env[op.name] = np.transpose(env[op.inputs[0]], op.perm)
            elif op.kind == "reshape":
                env[op.name] = np.reshape(env[op.inputs[0]], op.new_shape)
            elif op.kind == "matmul":
                env[op.name] = np.matmul(env[op.inputs[0]], env[op.inputs[1]])
            elif op.kind == "add":
                env[op.name] = env[op.inputs[0]] + env[op.inputs[1]]
            elif op.kind == "relu":
                env[op.name] = np.maximum(env[op.inputs[0]], dtype(0))
            elif op.kind == "fused_matmul_bias_relu":
                a, b, bias = (env[op.inputs[0]], env[op.inputs[1]],
                              env[op.inputs[2]])
                # 严格按 fp32 的 matmul→add→relu 复刻——口径就是语义（位等价的根基）
                env[op.name] = np.maximum(np.matmul(a, b) + bias, dtype(0))
            else:
                raise ValueError(op.kind)
        return [env[r] for r in self.returns]

    # ---------- IR 文本（Day 41 风格） ----------

    def dump_ir(self) -> str:
        shapes, errs = self.infer_shapes()
        args = [op for op in self.ops if op.kind == "arg"]
        ret_s = ", ".join(f"{r}: {fmt_type(shapes.get(r))}" for r in self.returns)
        lines = [f"func @{self.name}("
                 + ", ".join(f"{a.name}: {fmt_type(a.shape)}" for a in args)
                 + f") -> ({ret_s}) {{"]
        for op in self.ops:
            lines.append("  " + fmt_op(op, shapes))
        lines.append("  return " + ", ".join(self.returns))
        lines.append("}")
        return "\n".join(lines)


def fmt_type(shape) -> str:
    if shape is None or (isinstance(shape, tuple) and None in shape):
        return "tensor<?>"
    return "tensor<" + "x".join(str(d) for d in shape) + "xf32>"


def fmt_op(op: Op, shapes: dict[str, tuple]) -> str:
    n = op.name
    s = fmt_type(op.out_shape)
    if op.kind == "arg":
        return f"{n} = arg : {fmt_type(op.shape)}"
    if op.kind == "const":
        v = op.value.reshape(-1)
        head = ", ".join(fmt_val(x) for x in v[:4])
        tail = ", …" if v.size > 4 else ""
        return f"{n} = const shape={list(op.value.shape)} values=[{head}{tail}] : {s}"
    if op.kind in ("quantize", "dequantize"):
        return (f"{n} = {op.kind} {op.inputs[0]} "
                f"{{scale={op.scale:.6g}, zp={op.zp}}} : {s}")
    if op.kind == "transpose":
        return f"{n} = transpose {op.inputs[0]} perm={list(op.perm)} : {s}"
    if op.kind == "reshape":
        return f"{n} = reshape {op.inputs[0]} new_shape={list(op.new_shape)} : {s}"
    if op.kind == "matmul":
        return f"{n} = matmul {op.inputs[0]}, {op.inputs[1]} : {s}"
    if op.kind == "add":
        return f"{n} = add {op.inputs[0]}, {op.inputs[1]} : {s}"
    if op.kind == "relu":
        return f"{n} = relu {op.inputs[0]} : {s}"
    if op.kind == "fused_matmul_bias_relu":
        return (f"{n} = fused_matmul_bias_relu "
                f"{op.inputs[0]}, {op.inputs[1]}, {op.inputs[2]} : {s}")
    return f"{n} = {op.kind} : {s}"


def fmt_val(x: float) -> str:
    return f"{x:g}"


# ============================================================
# 数值内核：执行器与编译期折叠共用（位等价的结构保证）
# ============================================================

def v_quantize(x, scale: float, zp: int, dtype=np.float32):
    """Day 81 公式：q = clip(round(x/s) + zp, -128, 127)。"""
    q = np.round(x / scale) + zp
    return np.clip(q, QMIN, QMAX)


def v_dequantize(q, scale: float, zp: int, dtype=np.float32):
    """Day 81 公式：x̂ = s·(q − zp)。"""
    return scale * (q - zp)


# ============================================================
# 验证工具（Day 79 口径 + Day 78 误差账本）
# ============================================================

def check_close(actual, golden, rtol: float, atol: float):
    """统一误差检查：|a−g| ≤ atol + rtol·|g|（Day 79 的 check_close 口径）。"""
    a, g = np.asarray(actual, dtype=np.float64), np.asarray(golden, dtype=np.float64)
    diff = np.abs(a - g)
    tol = atol + rtol * np.abs(g)
    ok = bool(np.all(diff <= tol))
    max_abs = float(diff.max()) if diff.size else 0.0
    denom = np.maximum(np.abs(g), 1e-30)
    max_rel = float((diff / denom).max()) if diff.size else 0.0
    return ok, max_abs, max_rel


def matmul_atol(x64, w64) -> float:
    """Day 78 的累加误差账本，逐图计算 golden 的 atol：
    每个乘积一次舍入、每次累加一次舍入，量级都不超过 S = max Σ|a·b|，
    取 (2K+2)·eps32·S 作为 fp32 matmul+bias 的绝对误差上界。"""
    S = float(np.max(np.abs(np.abs(x64) @ np.abs(w64))))
    K = x64.shape[-1]
    return (2 * K + 2) * EPS32 * S


def ulp_distance_fp32(actual, golden):
    """Day 79 的 ULP 指标（float32 单调整数轴）。只作观察，不作门槛——
    带消去的累加在近零输出处会差几万格，那是刻度问题不是错误。"""
    a = np.asarray(actual, dtype=np.float32)
    g = np.asarray(golden, dtype=np.float32)  # golden 就近舍入到 fp32 格子
    ua = a.view(np.uint32).astype(np.uint64)
    ug = g.view(np.uint32).astype(np.uint64)
    half = np.uint64(1 << 31)
    mask = np.uint64((1 << 32) - 1)

    def mono(u):
        neg = (np.uint64(1 << 32) - u) & mask
        pos = u + half
        return np.where(u >= half, neg, pos)

    d = np.abs(mono(ua).astype(np.int64) - mono(ug).astype(np.int64))
    return int(d.max()) if d.size else 0


def verify_bit_exact(g1: Graph, g2: Graph, feeds: list[dict]):
    """位等价：两张图在同一组输入上 fp32 逐位相等（容差 = 0）。"""
    max_diff = 0.0
    for feed in feeds:
        o1 = g1.run(feed, np.float32)
        o2 = g2.run(feed, np.float32)
        for a, b in zip(o1, o2):
            if not np.array_equal(a, b):
                d = float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64))))
                max_diff = max(max_diff, d)
                return False, max_diff
    return True, 0.0


# ============================================================
# 机器假设卡（Day 73 同款）+ 融合收益（Day 72/76 的账本）
# ============================================================

@dataclass(frozen=True)
class Machine:
    name: str = "toy-core v0"
    regfile_bytes: int = 64 * 1024
    sram_bytes: int = 192 * 1024
    itemsize: int = 4                  # fp32

    @property
    def onchip_bytes(self) -> int:
        return self.regfile_bytes + self.sram_bytes


@dataclass
class CostReport:
    m: int
    k: int
    n: int
    delta_b: int          # 融合省掉的中间流量（字节）
    workset: int          # 融合核工作集（字节）
    spill: bool
    decision: str
    notes: str = ""


def fusion_cost(a_shape, b_shape, machine: Machine) -> CostReport:
    """Day 72 的 ΔB 账本：消去 mm_out、add_out 两个中间张量，
    每个省一次写＋一次读：ΔB = 2 × 2 × M·N × 4 字节 = 16·M·N。
    Day 73 的工作集：A + B + out + bias；spill 硬门槛沿用 Day 76。"""
    M, K = a_shape
    K2, N = b_shape
    assert K == K2
    delta_b = 2 * 2 * M * N * machine.itemsize
    workset = (M * K + K * N + M * N + N) * machine.itemsize
    spill = workset > machine.onchip_bytes
    if spill:
        decision = "拒绝（工作集超过片上容量，需先 Tiling——第四阶段）"
    else:
        decision = "融合" if delta_b > 0 else "拒绝（无收益）"
    return CostReport(M, K, N, delta_b, workset, spill, decision)


# ============================================================
# 闸1：QDQ 清理（Day 82 规则表的安全子集：R04 / R03 / R07 报警）
# ============================================================

def same_qparams(a: Op, b: Op) -> bool:
    return a.scale == b.scale and a.zp == b.zp


def pass_qdq_cleanup(g: Graph, audit: list, tag: str,
                     reported: set | None = None) -> None:
    reported = reported if reported is not None else set()

    def log(msg: str):
        audit.append(f"[{tag}] {msg}")

    while True:
        acted = False
        for op in list(g.ops):
            if op.kind != "dequantize":
                continue
            prod = g.producers()
            q = prod.get(op.inputs[0])
            if q is None or q.kind != "quantize":
                continue
            uses = g.use_counts()
            if not same_qparams(q, op):
                key = ("R07", op.name)
                if key not in reported:
                    reported.add(key)
                    log(f"报警 R07 @ {op.name}：Q(scale={q.scale:.6g}, zp={q.zp}) → "
                        f"DQ(scale={op.scale:.6g}, zp={op.zp}) 参数不一致（requant），"
                        f"这对不动，其余照常——坏图本身要在上游修")
                continue
            if uses[q.name] > 1:
                key = ("R08", op.name)
                if key not in reported:
                    reported.add(key)
                    log(f"拒绝 R08 @ {op.name}：码 {q.name} 还有别的使用者，删除即断链")
                continue
            src = prod.get(q.inputs[0])
            if src is not None and src.kind == "const":
                # R04：DQ(Q(const)) → const（编译期折叠，值逐位不变）
                folded = v_dequantize(v_quantize(src.value, q.scale, q.zp),
                                      q.scale, q.zp)
                new = Op(kind="const", name=g._fresh(), value=folded)
                g.replace(op, new)
                g.remove(q.name)
                if g.use_counts().get(src.name, 0) == 0:
                    g.remove(src.name)
                log(f"R04 @ {new.name}：DQ(Q({src.name})) 折叠成常量"
                    f"（scale={q.scale:.6g}, zp={q.zp}，编译期算完，值逐位不变）")
                acted = True
                break
            if (src is not None and src.kind == "dequantize"
                    and same_qparams(src, q)):
                # R03：同参 DQ→Q→DQ 尾对，值已在格点上，删尾对 bit-exact
                donor = src.name
                g.rewire(op.name, donor)
                g.remove(op.name)
                g.remove(q.name)
                log(f"R03 @ {op.name}：{q.name} 的输入 {donor} 是同参 DQ 的输出"
                    f"（值已在格点），删掉 Q→DQ 尾对，bit-exact")
                acted = True
                break
            # R06：裸 Q→DQ 单对——CONDITIONAL，登记不动（Day 82 的口径）
            key = ("R06", op.name)
            if key not in reported:
                reported.add(key)
                log(f"登记 R06 @ {op.name}：裸 Q→DQ（输入 {q.inputs[0]} 不保证在格点），"
                    f"删除=取消该边量化，属策略决定——管道不越权")
        if not acted:
            return


# ============================================================
# 闸2：布局简化（Day 64/65 的常量折叠版 + 排列合并）
# ============================================================

def pass_const_layout_fold(g: Graph, audit: list, tag: str) -> None:
    while True:
        acted = False
        for op in list(g.ops):
            if op.kind != "transpose":
                continue
            prod = g.producers()
            src = prod.get(op.inputs[0])
            if src is None or src.kind != "const":
                continue
            uses = g.use_counts()
            folded = np.transpose(src.value, op.perm)   # 与执行器同一个 numpy 调用
            new = Op(kind="const", name=g._fresh(), value=folded)
            g.replace(op, new)
            if uses.get(src.name, 0) == 1 and g.use_counts().get(src.name, 0) == 0:
                g.remove(src.name)
            audit.append(f"[{tag}] 转置常量折叠 @ {new.name}："
                         f"transpose({src.name}, {list(op.perm)}) → 常量"
                         f"（权重搬进编译期，运行时少一次数据移动）")
            acted = True
            break
        if not acted:
            return


def pass_transpose_merge(g: Graph, audit: list, tag: str) -> None:
    while True:
        acted = False
        for op in list(g.ops):
            if op.kind != "transpose":
                continue
            prod = g.producers()
            t1 = prod.get(op.inputs[0])
            if t1 is None or t1.kind != "transpose":
                continue
            if g.use_counts().get(t1.name, 0) > 1:
                continue                     # 中间转置还有别的使用者，保守不动
            r = compose_perm(t1.perm, op.perm)
            if r == tuple(range(len(r))):
                g.rewire(op.name, t1.inputs[0])
                g.remove(op.name)
                g.remove(t1.name)
                audit.append(f"[{tag}] 互逆对消除：transpose(transpose({t1.inputs[0]})) "
                             f"复合排列 = 恒等，两个都删（Day 65）")
            else:
                new = Op(kind="transpose", inputs=[t1.inputs[0]], name=g._fresh(),
                         perm=r)
                g.replace(op, new)
                g.remove(t1.name)
                audit.append(f"[{tag}] 排列合并：复合排列 {list(r)}，"
                             f"两个转置并成一个（Day 65）")
            acted = True
            break
        if not acted:
            return


# ============================================================
# 闸3：Reshape 合并（Day 66）
# ============================================================

def pass_reshape_merge(g: Graph, audit: list, tag: str) -> None:
    while True:
        acted = False
        for op in list(g.ops):
            if op.kind != "reshape":
                continue
            prod = g.producers()
            r1 = prod.get(op.inputs[0])
            if r1 is None or r1.kind != "reshape":
                continue
            if g.use_counts().get(r1.name, 0) > 1:
                audit.append(f"[{tag}] 拒绝合并 reshape 链：中间结果 {r1.name} "
                             f"还有别的使用者（Day 66 的边界）")
                continue
            new = Op(kind="reshape", inputs=[r1.inputs[0]], name=g._fresh(),
                     new_shape=op.new_shape)
            g.replace(op, new)
            g.remove(r1.name)
            audit.append(f"[{tag}] Reshape 合并 @ {new.name}："
                         f"reshape(reshape({r1.inputs[0]})) → 一次到 {list(op.new_shape)}"
                         f"（纯元信息改写，元素数与数据都不动）")
            acted = True
            break
        if not acted:
            return


# ============================================================
# 不动点清理循环（Day 69 的教训：上一轮的改写会创造下一轮的机会）
# ============================================================

def run_cleanup(g: Graph, max_rounds: int = 8):
    audit: list[str] = []
    reported: set = set()          # 登记/报警类条目只记一次，避免空转刷屏
    rounds = 0
    for r in range(1, max_rounds + 1):
        before = len(g.ops)
        n_audit = len(audit)
        pass_qdq_cleanup(g, audit, f"第{r}轮·QDQ清理", reported)
        pass_const_layout_fold(g, audit, f"第{r}轮·布局简化")
        pass_transpose_merge(g, audit, f"第{r}轮·布局简化")
        pass_reshape_merge(g, audit, f"第{r}轮·Reshape合并")
        rounds = r
        if len(g.ops) == before and len(audit) == n_audit:
            break
    return audit, rounds


# ============================================================
# 闸4：MatMul+Bias+Relu 融合（Day 50~54 合法性 + Day 74~76 收益）
# ============================================================

def pass_fuse_matmul_bias_relu(g: Graph, machine: Machine, audit: list) -> None:
    for relu_op in list(g.ops):
        if relu_op.kind != "relu":
            continue
        prod = g.producers()
        uses = g.use_counts()
        add_op = prod.get(relu_op.inputs[0])
        if add_op is None or add_op.kind != "add":
            continue
        if uses.get(add_op.name, 0) > 1:
            audit.append(f"[融合] 拒绝：{add_op.name} 的输出还有别的使用者，"
                         f"删掉中间会断链（Day 52 的边界）")
            continue
        mm = None
        bias_name = None
        for cand, other in ((add_op.inputs[0], add_op.inputs[1]),
                            (add_op.inputs[1], add_op.inputs[0])):
            p = prod.get(cand)
            if p is not None and p.kind == "matmul":
                mm, bias_name = p, other
                break
        if mm is None:
            continue
        if uses.get(mm.name, 0) > 1:
            audit.append(f"[融合] 拒绝：{mm.name} 的输出被 {uses[mm.name]} 个节点使用，"
                         f"融合会夺走其他消费者的输入（Day 52）")
            continue
        shapes, _ = g.infer_shapes()
        mm_shape = shapes.get(mm.name)
        bias_shape = shapes.get(bias_name)
        if mm_shape is None or bias_shape is None:
            continue
        M, N = mm_shape
        # bias 形状门：只接受 ()、(N,)、(1,N)——"给每列加一个数"
        if bias_shape not in ((), (N,), (1, N)):
            audit.append(f"[融合] 拒绝：bias 形状 {bias_shape} 不是 bias 式的"
                         f"（只接受 ()、({N},)、(1,{N})；add 本身合法，"
                         f"但融合核只实现了列广播——Day 74 的合法/收益分家）")
            continue
        # 收益门：Day 72/76 的账本
        a_shape = shapes.get(mm.inputs[0])
        b_shape = shapes.get(mm.inputs[1])
        rep = fusion_cost(a_shape, b_shape, machine)
        audit.append(f"[融合] 候选 {mm.name}→{add_op.name}→{relu_op.name}："
                     f"结构合法（单使用者 ✓ bias {bias_shape} ✓）；"
                     f"ΔB = 16·M·N = {rep.delta_b} B，工作集 {rep.workset} B "
                     f"{'≤' if not rep.spill else '>'} 片上 {machine.onchip_bytes} B"
                     f"{'，无 spill' if not rep.spill else '，spill'} → {rep.decision}")
        if rep.spill or rep.delta_b <= 0:
            continue
        new = Op(kind="fused_matmul_bias_relu",
                 inputs=[mm.inputs[0], mm.inputs[1], bias_name],
                 name=g._fresh())
        g.replace(relu_op, new)
        g.remove(add_op.name)
        g.remove(mm.name)
        audit.append(f"[融合] 执行：{mm.name}+{add_op.name}+{relu_op.name} → {new.name}"
                     f"（fused_matmul_bias_relu，fp32 口径严格复刻 matmul→add→relu）")
        return      # 一张图只融合第一组（示例管道；多组候选留给练习）


# ============================================================
# 管道总装：五道闸 + 三次验证
# ============================================================

class PipelineError(RuntimeError):
    pass


def optimize(g: Graph, machine: Machine | None = None) -> dict:
    machine = machine or Machine()
    audit: list[str] = []
    g0 = g.copy()

    # 闸0：合法性检查——先验合法再动手
    errs = g0.verify()
    if errs:
        raise PipelineError("闸0 未通过：" + "；".join(errs))
    audit.append(f"[闸0] 合法性检查通过（{len(g0.ops)} 个节点，Shape 全部可推导）")

    ir_original = g0.dump_ir()

    # 闸1~3：清理不动点
    clean_audit, rounds = run_cleanup(g0)
    audit += clean_audit
    errs = g0.verify()
    if errs:
        raise PipelineError("清理后验证未通过：" + "；".join(errs))
    audit.append(f"[闸1~3] 清理不动点：{rounds} 轮收敛，"
                 f"剩 {len(g0.ops)} 个节点，改写后 Shape 复推通过")
    ir_cleanup = g0.dump_ir()
    n_cleanup = len(g0.ops)

    # 闸4：融合（合法性 + Cost Model）
    pass_fuse_matmul_bias_relu(g0, machine, audit)
    errs = g0.verify()
    if errs:
        raise PipelineError("融合后验证未通过：" + "；".join(errs))
    audit.append(f"[闸4] 融合完成，终图 {len(g0.ops)} 个节点，验证通过")
    ir_final = g0.dump_ir()

    return {"graph": g0, "audit": audit, "ir_original": ir_original,
            "ir_cleanup": ir_cleanup, "ir_final": ir_final,
            "n_cleanup": n_cleanup}


# ============================================================
# 贯穿例子：主图（11 节点）与变体（13 节点，尾部多一对激活 QDQ）
# ============================================================

# scale 全部取 2 的幂：除法精确 → fp32/fp64 的 round 落在同一格（见 6.4）
W_SCALE = 2.0 ** -7            # 1/128，覆盖 max|W| = 0.75（0.75/127 ≈ 0.0059）
A_SCALE = 2.0 ** -3            # 1/8，覆盖激活上限（码 ≤ 127×1/8 由数据保证）

X_FLAT = [1.5, -0.5, 2.0, 0.0, -1.0, 0.5, 0.25, 1.25, -0.75, 0.75, 2.0, -1.5,
          -0.25, 0.0, 0.5, 1.0, -2.0, 0.75, 1.75, -1.25, 0.25, -0.5, 0.0, 1.0]

W_T = [[0.3, -0.25, 0.125, -0.5, 0.25, 0.0],
       [-0.125, 0.7, 0.5, -0.25, 0.0, 0.375],
       [0.25, 0.5, -0.625, 0.125, 0.25, -0.55]]   # (N=3, K=6)；0.3/0.7/-0.55
                                                    # 不在 1/128 格点上——QDQ 会把它们靠档

BIAS = [0.125, -0.25, 0.5]


def build_main_graph() -> Graph:
    """贯穿图：x(2,12) 与 权重(3,6) 汇入一条 GEMM 尾巴。

    x ─reshape(24,)─reshape(4,6)─┐
    W_t(3,6) ─Q─DQ─transpose(1,0)┴─matmul─add(bias)─relu─ret
    """
    g = Graph("main")
    x = g.arg((2, 12), name="%x")
    cw = g.const(W_T)
    q = g.quantize(cw, W_SCALE, 0)
    dq = g.dequantize(q, W_SCALE, 0)
    t = g.transpose(dq, (1, 0))
    r1 = g.reshape(x, (24,))
    r2 = g.reshape(r1, (4, 6))
    mm = g.matmul(r2, t)
    cb = g.const(BIAS)
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    g.returns = [ru]
    return g


def build_variant_graph() -> Graph:
    """变体：主图尾部多一对激活 QDQ（QAT 风格的输出量化边）。
    预期：R04/转置折叠/reshape 合并/融合照常，尾部 QDQ 判 R06 登记不动。"""
    g = Graph("variant")
    x = g.arg((2, 12), name="%x")
    cw = g.const(W_T)
    q = g.quantize(cw, W_SCALE, 0)
    dq = g.dequantize(q, W_SCALE, 0)
    t = g.transpose(dq, (1, 0))
    r1 = g.reshape(x, (24,))
    r2 = g.reshape(r1, (4, 6))
    mm = g.matmul(r2, t)
    cb = g.const(BIAS)
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    qa = g.quantize(ru, A_SCALE, -128)
    dqa = g.dequantize(qa, A_SCALE, -128)
    g.returns = [dqa]
    return g


def build_random_graph(rng: np.random.Generator):
    """随机图：与主图同构，M/K/N/数据随机；权重 scale 取 2 的幂（码精确）。"""
    M, K, N = [int(v) for v in rng.integers(1, 9, size=3)]
    g = Graph("rand")
    x = g.arg((1, M * K), name="%x")
    w = rng.uniform(-1.0, 1.0, size=(N, K))
    s = 2.0 ** math.ceil(math.log2(max(np.max(np.abs(w)), 1e-6) / 127.0))
    cw = g.const(w)
    q = g.quantize(cw, s, 0)
    dq = g.dequantize(q, s, 0)
    t = g.transpose(dq, (1, 0))
    r1 = g.reshape(x, (M * K,))
    r2 = g.reshape(r1, (M, K))
    mm = g.matmul(r2, t)
    cb = g.const(rng.uniform(-0.5, 0.5, size=N))
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    g.returns = [ru]
    data = {"%x": rng.uniform(-2.0, 2.0, size=(1, M * K))}
    return g, data


# ============================================================
# 单元测试 T01~T12
# ============================================================

def unit_tests() -> None:
    hr("单元测试：五道闸各自的正例与反例（12 个用例）")

    # T01 Verifier：matmul 内维不匹配
    g = Graph("t01")
    a = g.arg((2, 3))
    b = g.arg((2, 4))
    g.returns = [g.matmul(a, b)]
    errs = g.verify()
    check("T01 Verifier 拒绝内维不匹配的 matmul",
          any("内维" in e for e in errs), f"错误信息: {errs[0] if errs else ''}")

    # T02 Verifier：reshape 元素数不符
    g = Graph("t02")
    a = g.arg((2, 3))
    g.returns = [g.reshape(a, (7,))]
    errs = g.verify()
    check("T02 Verifier 拒绝元素数不符的 reshape",
          any("元素数" in e for e in errs), f"错误信息: {errs[0] if errs else ''}")

    # T03 Verifier：非法排列
    g = Graph("t03")
    a = g.arg((2, 3, 4))
    g.returns = [g.transpose(a, (0, 0, 1))]
    errs = g.verify()
    check("T03 Verifier 拒绝非法 transpose 排列",
          any("排列" in e for e in errs), f"错误信息: {errs[0] if errs else ''}")

    # T04 转置互逆对消除（3D，(1,0,2)∘(1,0,2) = 恒等）
    g = Graph("t04")
    rng = np.random.default_rng(4)
    x = g.arg((2, 3, 4))
    t1 = g.transpose(x, (1, 0, 2))
    t2 = g.transpose(t1, (1, 0, 2))
    g.returns = [t2]
    g2 = g.copy()
    audit, _ = run_cleanup(g2)
    feed = {"%1": rng.standard_normal((2, 3, 4))}
    ok, _ = verify_bit_exact(g, g2, [feed])
    check("T04 互逆转置对被消除（复合排列=恒等，bit-exact）",
          len(g2.ops) == 1 and ok and any("互逆" in a for a in audit),
          f"{len(g.ops)}→{len(g2.ops)} 节点")

    # T05 非互逆对合并成一个（复合排列 (1,2,0)）
    g = Graph("t05")
    x = g.arg((2, 3, 4))
    t1 = g.transpose(x, (1, 0, 2))
    t2 = g.transpose(t1, (0, 2, 1))
    g.returns = [t2]
    g2 = g.copy()
    audit, _ = run_cleanup(g2)
    feed = {"%1": rng.standard_normal((2, 3, 4))}
    ok, _ = verify_bit_exact(g, g2, [feed])
    n_t = sum(1 for o in g2.ops if o.kind == "transpose")
    check("T05 非互逆转置对合并成一个（复合排列，bit-exact）",
          n_t == 1 and len(g2.ops) == 2 and ok
          and g2.ops[1].perm == (1, 2, 0),
          f"复合排列 {g2.ops[1].perm if len(g2.ops) > 1 else '-'}")

    # T06 reshape 链合并 + 多使用者反例
    g = Graph("t06")
    x = g.arg((2, 3))
    r1 = g.reshape(x, (6,))
    r2 = g.reshape(r1, (3, 2))
    g.returns = [r2]
    g2 = g.copy()
    audit, _ = run_cleanup(g2)
    feed = {"%1": rng.standard_normal((2, 3))}
    ok, _ = verify_bit_exact(g, g2, [feed])
    merged = len(g2.ops) == 2 and g2.ops[1].kind == "reshape"
    g3 = g.copy()
    g3.returns = [r2, r1]                    # 中间结果也被导出
    g4 = g3.copy()
    run_cleanup(g4)
    kept = sum(1 for o in g4.ops if o.kind == "reshape") == 2
    check("T06 reshape 链合并 bit-exact；中间多使用者时保守保留",
          merged and ok and kept,
          f"合并后 {len(g2.ops)} 节点；多使用者时保留 {len(g4.ops)} 节点")

    # T07 QDQ：R04 常量折叠 bit-exact；R07 requant 报警且不改图
    g = Graph("t07")
    cw = g.const(W_T)
    q = g.quantize(cw, W_SCALE, 0)
    dq = g.dequantize(q, W_SCALE, 0)
    g.returns = [dq]
    g2 = g.copy()
    audit, _ = run_cleanup(g2)
    folded = (len(g2.ops) == 1 and g2.ops[0].kind == "const")
    ok, _ = verify_bit_exact(g, g2, [{}])
    g3 = Graph("t07r")
    cw = g3.const(W_T)
    q = g3.quantize(cw, W_SCALE, 0)
    dq = g3.dequantize(q, 2.0 ** -6, 0)      # 参数不一致 → requant
    g3.returns = [dq]
    g4 = g3.copy()
    audit2, _ = run_cleanup(g4)
    alarm = any("R07" in a for a in audit2)
    unchanged = len(g4.ops) == len(g3.ops)
    check("T07 DQ(Q(const)) 判 R04 折叠 bit-exact；参数不一致判 R07 报警不动",
          folded and ok and alarm and unchanged,
          f"折叠后 {len(g2.ops)} 节点；requant 图 {len(g3.ops)}→{len(g4.ops)} 节点")

    # T08 QDQ：R03 幂等尾对删除 bit-exact；裸对 R06 登记
    g = Graph("t08")
    x = g.arg((8,))
    q1 = g.quantize(x, 0.25, -128)
    dq1 = g.dequantize(q1, 0.25, -128)
    q2 = g.quantize(dq1, 0.25, -128)
    dq2 = g.dequantize(q2, 0.25, -128)
    g.returns = [dq2]
    g2 = g.copy()
    audit, _ = run_cleanup(g2)
    feed = {"%1": rng.uniform(0, 60, size=(8,))}
    ok, _ = verify_bit_exact(g, g2, [feed])
    r03 = any("R03" in a for a in audit)
    g3 = Graph("t08b")
    x = g3.arg((8,))
    q = g3.quantize(x, 0.25, -128)
    dq = g3.dequantize(q, 0.25, -128)
    g3.returns = [dq]
    g4 = g3.copy()
    audit2, _ = run_cleanup(g4)
    r06 = any("R06" in a for a in audit2) and len(g4.ops) == 3
    check("T08 同参尾对判 R03 删除 bit-exact；裸对判 R06 登记不动",
          ok and r03 and r06 and len(g2.ops) == 3,
          f"尾对删除 {len(g.ops)}→{len(g2.ops)} 节点；裸对保留 {len(g4.ops)} 节点")

    # T09 融合正例：合法性 + 收益 + bit-exact
    g = Graph("t09")
    a = g.arg((2, 3))
    b = g.arg((3, 2))
    mm = g.matmul(a, b)
    cb = g.const([0.25, -0.5])
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    g.returns = [ru]
    g2 = g.copy()
    audit: list[str] = []
    pass_fuse_matmul_bias_relu(g2, Machine(), audit)
    feed = {"%1": rng.standard_normal((2, 3)), "%2": rng.standard_normal((3, 2))}
    ok, _ = verify_bit_exact(g, g2, [feed])
    fused = any(o.kind == "fused_matmul_bias_relu" for o in g2.ops)
    db = any("ΔB = 16·M·N = 64 B" in a for a in audit)
    check("T09 matmul+bias+relu 融合：结构+收益双门通过，bit-exact",
          fused and ok and db, f"{len(g.ops)}→{len(g2.ops)} 节点")

    # T10 融合反例：matmul 输出多使用者
    g = Graph("t10")
    a = g.arg((2, 3))
    b = g.arg((3, 2))
    mm = g.matmul(a, b)
    cb = g.const([0.25, -0.5])
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    g.returns = [ru, mm]                     # mm 还被图输出使用
    g2 = g.copy()
    audit = []
    pass_fuse_matmul_bias_relu(g2, Machine(), audit)
    check("T10 matmul 输出多使用者时拒绝融合（Day 52 边界）",
          not any(o.kind == "fused_matmul_bias_relu" for o in g2.ops)
          and any("拒绝" in a for a in audit), f"{len(g.ops)}→{len(g2.ops)} 节点")

    # T11 融合反例：bias 不是 bias 式形状（add 合法，但融合核只实现列广播）
    g = Graph("t11")
    a = g.arg((2, 3))
    b = g.arg((3, 2))
    mm = g.matmul(a, b)
    cb = g.const(rng.standard_normal((2, 2)))
    ad = g.add_op(mm, cb)
    ru = g.relu(ad)
    g.returns = [ru]
    g2 = g.copy()
    audit = []
    pass_fuse_matmul_bias_relu(g2, Machine(), audit)
    check("T11 bias 形状 (2,2) 时 add 合法但拒绝融合（合法/收益分家，Day 74）",
          not any(o.kind == "fused_matmul_bias_relu" for o in g2.ops)
          and any("bias 形状" in a for a in audit), f"{len(g.ops)}→{len(g2.ops)} 节点")

    # T12 端到端：主图 11→5，位等价 + golden 全通过，IR 归档
    g = build_main_graph()
    res = optimize(g)
    gopt = res["graph"]
    feeds = [{"%x": np.array(X_FLAT).reshape(2, 12)}]
    ok, _ = verify_bit_exact(g, gopt, feeds)
    golden = g.run(feeds[0], np.float64)[0]
    actual = gopt.run(feeds[0], np.float32)[0]
    x64 = np.asarray(feeds[0]["%x"], dtype=np.float64).reshape(4, 6)
    w64 = v_dequantize(v_quantize(np.asarray(W_T, dtype=np.float64),
                                  W_SCALE, 0), W_SCALE, 0).T
    atol = matmul_atol(x64, w64)
    ok2, max_abs, max_rel = check_close(actual, golden, rtol=1e-5, atol=atol)
    n0, n1 = len(g.ops), len(gopt.ops)
    check("T12 主图端到端：11→5 节点，位等价 + golden 双通过",
          n0 == 11 and n1 == 5 and ok and ok2,
          f"位等价={ok}，golden max|diff|={max_abs:.3g}（账本 atol={atol:.3g}）")


# ============================================================
# 实验 E1~E5
# ============================================================

def exp1_pipeline() -> dict:
    hr("实验 1：贯穿图全管道——审计日志 + 节点数 + IR 对照")
    g = build_main_graph()
    res = optimize(g)
    print(f"  输入图 {len(g.ops)} 个节点 → 清理后 {res['n_cleanup']} "
          f"→ 终图 {len(res['graph'].ops)} 个节点")
    print("  审计日志（每道闸做了什么、为什么）：")
    for line in res["audit"]:
        print("   " + line)
    print("\n  --- 优化前 IR（11 节点）---")
    print("\n".join("  " + l for l in res["ir_original"].splitlines()))
    print("\n  --- 清理后 IR（闸1~3 不动点）---")
    print("\n".join("  " + l for l in res["ir_cleanup"].splitlines()))
    print("\n  --- 终图 IR（闸4 融合后，5 节点）---")
    print("\n".join("  " + l for l in res["ir_final"].splitlines()))
    (OUT / "ir-00-original.txt").write_text(res["ir_original"] + "\n")
    (OUT / "ir-01-after-cleanup.txt").write_text(res["ir_cleanup"] + "\n")
    (OUT / "ir-02-after-fusion.txt").write_text(res["ir_final"] + "\n")
    (OUT / "audit-log.txt").write_text("\n".join(res["audit"]) + "\n")
    return res


def worst_ratio(actual, golden, rtol: float, atol: float) -> float:
    """容差占用比：max |a−g| / (atol + rtol·|g|)。< 1 即通过，
    它同时回答『离门槛还有多远』。"""
    a, g = np.asarray(actual, np.float64), np.asarray(golden, np.float64)
    tol = atol + rtol * np.abs(g)
    return float(np.max(np.abs(a - g) / np.maximum(tol, 1e-300))) if a.size else 0.0


def exp2_verify(res: dict) -> None:
    hr("实验 2：两层验证——位等价（容差=0）与 FP64 golden（误差账本）")
    g = build_main_graph()
    gopt = res["graph"]
    w64 = v_dequantize(v_quantize(np.asarray(W_T, np.float64), W_SCALE, 0),
                       W_SCALE, 0).T

    feed0 = {"%x": np.array(X_FLAT).reshape(2, 12)}
    ok, _ = verify_bit_exact(g, gopt, [feed0])
    golden = g.run(feed0, np.float64)[0]
    actual = gopt.run(feed0, np.float32)[0]
    atol0 = matmul_atol(feed0["%x"].astype(np.float64).reshape(4, 6), w64)
    okc, max_abs, max_rel = check_close(actual, golden, rtol=1e-5, atol=atol0)
    ulp = ulp_distance_fp32(actual, golden)
    print("  第一层 位等价（优化 vs 原图，容差=0）：")
    print(f"    固定输入: np.array_equal = {ok}")
    print(f"    输出（4×3）: {[' '.join(f'{v:.4f}' for v in row) for row in actual]}")
    print("  第二层 FP64 golden（Day 79 工具 + Day 78 账本 atol）：")
    print(f"    max|diff| = {max_abs:.3g}，max ULP = {ulp} → 检查 "
          f"{'通过' if okc else '未通过'}")
    print(f"    账本 atol = (2K+2)·eps32·max Σ|a·b| = {atol0:.3g}")
    print("    （dyadic 数据让 fp32 与 fp64 逐位一致——先用零误差数据校准工具本身）")

    rng = np.random.default_rng(83)
    print("\n  随机输入压测（固定权重，3 组 × 10000 个输入）：")
    all_eq, worst_abs, worst_ratio_, worst_ulp = True, 0.0, 0.0, 0
    for b in range(3):
        xs = rng.uniform(-2, 2, size=(10000, 24))
        feeds = [{"%x": xs[i].reshape(2, 12)} for i in range(10000)]
        ok, _ = verify_bit_exact(g, gopt, feeds)
        all_eq = all_eq and ok
        m_abs = m_ratio = 0.0
        m_ulp = 0
        for i in range(10000):
            gold = g.run(feeds[i], np.float64)[0]      # 原图 fp64 语义做参考
            act = gopt.run(feeds[i], np.float32)[0]
            x64 = xs[i].astype(np.float32).astype(np.float64).reshape(4, 6)
            atol = matmul_atol(x64, w64)
            _, a_, _ = check_close(act, gold, 1e-5, atol)
            m_abs = max(m_abs, a_)
            m_ratio = max(m_ratio, worst_ratio(act, gold, 1e-5, atol))
            m_ulp = max(m_ulp, ulp_distance_fp32(act, gold))
        worst_abs, worst_ratio_ = max(worst_abs, m_abs), max(worst_ratio_, m_ratio)
        worst_ulp = max(worst_ulp, m_ulp)
        print(f"    批{b + 1}: 位等价={ok}，golden max|diff|={m_abs:.3g}，"
              f"最坏容差占用比={m_ratio:.3f}，max ULP={m_ulp}")
    print(f"  汇总：3×10000 位等价={all_eq}；golden 最坏 |diff|={worst_abs:.3g}，"
          f"最坏容差占用比={worst_ratio_:.3f}（<1 即通过，离门槛还有十倍余量）")


def exp3_cost() -> None:
    hr("实验 3：融合收益账本——ΔB、工作集与 Shape 放大")
    m = Machine()
    print(f"  机器假设卡（Day 73 同款）：寄存器堆 {m.regfile_bytes // 1024} KiB + "
          f"SRAM {m.sram_bytes // 1024} KiB = 片上 {m.onchip_bytes // 1024} KiB，fp32")
    print("  ΔB = 2 个中间张量 ×（1 写 + 1 读）× M·N × 4 B = 16·M·N（Day 72）")
    print("  工作集 = (M·K + K·N + M·N + N) × 4 B（Day 73）\n")
    print(f"  {'Shape (M,K,N)':<20}{'ΔB':>14}{'工作集':>14}{'spill':>7}  决策")
    for (M, K, N) in [(4, 6, 3), (64, 64, 64), (1024, 1024, 1024)]:
        r = fusion_cost((M, K), (K, N), m)
        print(f"  {str((M, K, N)):<20}{fmt_b(r.delta_b):>14}{fmt_b(r.workset):>14}"
              f"{'是' if r.spill else '否':>7}  {r.decision}")
    print("\n  主图 (4,6,3)：ΔB=192 B 是小钱，真正的意义有两笔——")
    print("  ① 运行时算子 8 → 2（q/dq/transpose/两次 reshape/matmul/add/relu"
          " → reshape+fused）：")
    print("     权重的量化、反量化、转置全部搬进编译期（常量折叠），运行时不再执行")
    print("  ② 决策可解释：每一步融合/拒绝都有一行审计（什么 Shape、多少字节、"
          "哪个门槛），")
    print("     Shape 放大到 1024³ 时 ΔB=16 MiB，但工作集 12.6 MB 顶爆片上 256 KiB——")
    print("     这时才轮到 Tiling 出场（第四阶段），管道不抢跑")


def fmt_b(n: float) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.2f} MiB"
    if n >= 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n} B"


def exp4_random() -> None:
    hr("实验 4：随机 stress——50 张随机图，位等价 + golden 双口径")
    rng = np.random.default_rng(83)
    n_bit = n_gold = 0
    worst_abs = worst_ratio_ = 0.0
    worst_ulp = 0
    node_pairs = []
    for i in range(50):
        g, data = build_random_graph(rng)
        res = optimize(g)
        gopt = res["graph"]
        ok, _ = verify_bit_exact(g, gopt, [data])
        n_bit += ok
        golden = g.run(data, np.float64)[0]
        actual = gopt.run(data, np.float32)[0]
        # 从终图里找回折叠后的权重（const 已经是 Ŵᵀ）和真实 (M, K)
        wcon = [o for o in gopt.ops if o.kind == "const" and o.value.ndim == 2][0]
        rcon = [o for o in gopt.ops if o.kind == "reshape"][0]
        w64 = wcon.value.astype(np.float64)
        x64r = (np.asarray(data["%x"]).astype(np.float32)
                .astype(np.float64).reshape(rcon.new_shape))
        bound = matmul_atol(x64r, w64)
        okc, a_, _ = check_close(actual, golden, rtol=1e-5, atol=bound)
        n_gold += okc
        worst_abs = max(worst_abs, a_)
        worst_ratio_ = max(worst_ratio_, worst_ratio(actual, golden, 1e-5, bound))
        worst_ulp = max(worst_ulp, ulp_distance_fp32(actual, golden))
        node_pairs.append((len(g.ops), len(gopt.ops)))
        if not ok or not okc:
            print(f"    [第{i}图] 失败：位等价={ok} golden={okc}")
    print(f"  50 张随机图（M,K,N ∈ [1,8]，seed=83）：")
    print(f"    位等价（容差=0）: {n_bit}/50")
    print(f"    golden（rtol=1e-5 + 账本 atol）: {n_gold}/50")
    print(f"    实测最坏 |diff| = {worst_abs:.3g}，最坏容差占用比 = "
          f"{worst_ratio_:.3f}，最坏 ULP = {worst_ulp}")
    print(f"    节点数：原图 {min(p[0] for p in node_pairs)}~"
          f"{max(p[0] for p in node_pairs)} → "
          f"终图 {min(p[1] for p in node_pairs)}~"
          f"{max(p[1] for p in node_pairs)}")


def exp5_variant() -> None:
    hr("实验 5：变体图——尾部多一对激活 QDQ，先预测再验证")
    g = build_variant_graph()
    print("  变体 = 主图 + relu → Q(1/8, zp=-128) → DQ → return（QAT 输出量化边）")
    print("  预测：R04/转置折叠/reshape 合并/融合 照常；尾部裸 QDQ 判 R06 登记；")
    print("        13 节点 → 7 节点（arg/reshape/Ŵᵀ/bias/fused/Q/DQ）")
    res = optimize(g)
    gopt = res["graph"]
    print(f"\n  实测：{len(g.ops)} → {len(gopt.ops)} 个节点")
    for line in res["audit"]:
        print("   " + line)
    kinds = [o.kind for o in gopt.ops]
    feed = {"%x": np.array(X_FLAT).reshape(2, 12)}
    ok, _ = verify_bit_exact(g, gopt, [feed])
    print(f"  终图算子序列: {kinds}")
    print(f"  位等价（容差=0）: {ok}")
    out = gopt.run(feed, np.float32)[0]
    print(f"  输出（激活量化后，4×3）: {[' '.join(f'{v:.4f}' for v in row) for row in out]}")
    (OUT / "ir-03-variant.txt").write_text(res["ir_final"] + "\n")
    print("  （对比主图输出：量化把激活放上了 1/8 的格点——R06 的'删除=悄悄取消量化'" )
    print("   正是 Day 82 的结论：管道登记不越权）")


# ============================================================
# main
# ============================================================

def main() -> int:
    print("第 83 天：第三阶段集成验收 —— 图优化小编译器")
    print(f"环境：Python {__import__('sys').version.split()[0]}，"
          f"numpy {np.__version__}")
    unit_tests()
    res = exp1_pipeline()
    exp2_verify(res)
    exp3_cost()
    exp4_random()
    exp5_variant()
    hr("汇总")
    print(f"单元测试：{PASS}/{PASS + FAIL} 通过")
    print(f"产物：outputs/ir-00-original.txt、ir-01-after-cleanup.txt、")
    print(f"      ir-02-after-fusion.txt、ir-03-variant.txt、audit-log.txt")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
