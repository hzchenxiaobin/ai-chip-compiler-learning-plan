#!/usr/bin/env python3
"""第 116 天：转换简单 Elementwise 算子——第一个端到端可执行算子。

真实工具链里，今天对应最终 Lowering 的算子层模式：
  M1  memref.load   -> 4 次 extractvalue + 2 乘 2 加 + getelementptr + llvm.load
  M2  memref.store  -> 同一条地址公式，最后换成 llvm.store
  M3  memref.alloc  -> llvm.call @malloc + 7 次 insertvalue 填描述符
  A2  arith.addi/muli（index）-> llvm.add/mul（i64）
  A3  arith.addf/mulf        -> llvm.addf/fmul
  A4  arith.cmpf/select      -> llvm.fcmp/select（今天新增的清单第 10 行）
C1（scf.for 一族）留给 D117——所以今天的可执行主角是**不含循环**的
elementwise 算子：@add（2×2）与 @relu（2×2），外加标量 @step 单测 A2。

本机没有 mlir-opt（与 D57~D115 一致）：驱动器/模式注册表是 MLIR
DialectConversion 的教学仿真；但发射出的 LLVM IR 文本交给真 LLVM
（llvmlite 内嵌 LLVM 22.1.0）parse、verify、MCJIT 编译执行，结果与
numpy 参考逐点 bitwise 对照；汇编证据来自同一台真机。

用法：
  python3 op_lowering.py                    # 主运行：TP1~TP8，写 outputs/
  python3 op_lowering.py --shape 2 3 --tag s23   # 形状对照（TP9）
  python3 op_lowering.py --emit-src add|relu|step|gemm   # 打印源 IR 文本
"""

from __future__ import annotations

import argparse
import ctypes
import re
import subprocess
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from llvmlite import binding as lv
    lv.initialize_all_targets()
    lv.initialize_native_target()
    lv.initialize_native_asmprinter()
    HAVE_LLVMLITE = True
except ImportError:  # pragma: no cover
    HAVE_LLVMLITE = False

CODE = Path(__file__).resolve().parent
OUT = CODE / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

REPORT: list[str] = []
FROZEN_TAG = ""


def log(s: str = "") -> None:
    print(s)
    REPORT.append(s)


# ---------------------------------------------------------------------------
# 1. 源 IR 生成器：@add / @relu（展开形态）与 @step（标量）、GEMM（账本回归）
# ---------------------------------------------------------------------------

def _elem_body(lines: list[str], R: int, C: int, per_elem) -> None:
    """公共骨架：每个 (i, j) 展开一组 op；每个用到的下标值一个常量。"""
    for v in sorted(set(range(R)) | set(range(C))):
        lines.append(f"  %c{v} = arith.constant {v} : index" if v else
                     "  %c0 = arith.constant 0 : index")
    for i in range(R):
        for j in range(C):
            per_elem(i, j)


def make_add_ir(R: int, C: int) -> str:
    """elementwise Add 的展开形态（D96 unroll 应用在小形状上）。

    没有 scf.for：C1 是 D117 的模式，先别让它进今天的调试现场。
    """
    mty = f"memref<{R}x{C}xf32, strided<[{C}, 1]>>"
    lines = [f"// 第 {R}×{C} elementwise Add（第 116 天输入①，展开形态：无 scf.for）",
             f"func @add(%a: {mty},",
             f"         %b: {mty}) -> {mty} {{",
             f"  %c = memref.alloc() : {mty}"]

    def per_elem(i, j):
        lines.append(f"  %a{i}{j} = memref.load %a[%c{i}, %c{j}] : {mty}")
        lines.append(f"  %b{i}{j} = memref.load %b[%c{i}, %c{j}] : {mty}")
        lines.append(f"  %s{i}{j} = arith.addf %a{i}{j}, %b{i}{j} : f32")
        lines.append(f"  memref.store %s{i}{j}, %c[%c{i}, %c{j}] : {mty}")

    _elem_body(lines, R, C, per_elem)
    lines.append(f"  return %c : {mty}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def make_relu_ir(R: int, C: int) -> str:
    mty = f"memref<{R}x{C}xf32, strided<[{C}, 1]>>"
    lines = [f"// 第 {R}×{C} elementwise Relu（第 116 天输入②，展开形态）",
             f"func @relu(%x: {mty}) -> {mty} {{",
             "  %zero = arith.constant 0.0 : f32",
             f"  %r = memref.alloc() : {mty}"]

    def per_elem(i, j):
        lines.append(f"  %x{i}{j} = memref.load %x[%c{i}, %c{j}] : {mty}")
        lines.append(f"  %g{i}{j} = arith.cmpf ogt %x{i}{j}, %zero : f32")
        lines.append(f"  %m{i}{j} = arith.select %g{i}{j}, %x{i}{j}, %zero : f32")
        lines.append(f"  memref.store %m{i}{j}, %r[%c{i}, %c{j}] : {mty}")

    _elem_body(lines, R, C, per_elem)
    lines.append(f"  return %r : {mty}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def make_step_ir() -> str:
    return """// 标量 step（第 116 天输入③）：只审 A2（index 整数运算 -> i64）
func @step(%i: index, %k: index) -> index {
  %c2 = arith.constant 2 : index
  %s = arith.addi %i, %k : index
  %p = arith.muli %s, %c2 : index
  return %p : index
}
"""


def make_gemm_ir(M: int = 4, K: int = 6, N: int = 3) -> str:
    """D115 的同款 GEMM 循环 IR：今天只做账本回归（C1 在 D117，不执行）。"""
    return f"""// 第 {M}×{K}×{N} GEMM 的循环形态（第 115 天输入、第 116 天账本回归对象）
func @gemm(%a: memref<{M}x{K}xf32, strided<[{K}, 1]>>,
           %b: memref<{K}x{N}xf32, strided<[{N}, 1]>>) -> memref<{M}x{N}xf32, strided<[{N}, 1]>> {{
  %c = memref.alloc() : memref<{M}x{N}xf32, strided<[{N}, 1]>>
  %zero = arith.constant 0.0 : f32
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %cM = arith.constant {M} : index
  %cN = arith.constant {N} : index
  %cK = arith.constant {K} : index
  scf.for %i = %c0 to %cM step %c1 {{
    scf.for %j = %c0 to %cN step %c1 {{
      %acc = scf.for %k = %c0 to %cK step %c1
                  iter_args(%acc = %zero) -> (f32) {{
        %xa = memref.load %a[%i, %k] : memref<{M}x{K}xf32, strided<[{K}, 1]>>
        %xb = memref.load %b[%k, %j] : memref<{K}x{N}xf32, strided<[{N}, 1]>>
        %p = arith.mulf %xa, %xb : f32
        %s = arith.addf %acc, %p : f32
        scf.yield %s : f32
      }}
      memref.store %acc, %c[%i, %j] : memref<{M}x{N}xf32, strided<[{N}, 1]>>
    }}
  }}
  return %c : memref<{M}x{N}xf32, strided<[{N}, 1]>>
}}
"""


# ---------------------------------------------------------------------------
# 2. 类型兑换表（D115 的执行版原样复用；两道闸不变）
# ---------------------------------------------------------------------------

MEMREF_RE = re.compile(
    r"^memref<(?P<shape>[0-9x?]+)x(?P<elem>f32|f64|f16|i32|i64)"
    r"(?:,\s*strided<\[(?P<strides>[0-9,\s?]+)\]>)?>$")
TENSOR_RE = re.compile(r"^tensor<")


class TypeConversionError(Exception):
    pass


def parse_memref(ty: str) -> dict:
    m = MEMREF_RE.match(ty.strip())
    if not m:
        raise TypeConversionError(f"{ty}：无法解析的 memref 类型")
    if "?" in ty:
        raise TypeConversionError(f"{ty}：动态 shape 暂不支持（D114 清单'暂不支持'第 1 条）")
    shape = [int(x) for x in m.group("shape").split("x")]
    strides = [int(s) for s in m.group("strides").split(",") if s.strip()]
    if not strides:
        strides, acc = [], 1
        for d in reversed(shape):
            strides.insert(0, acc)
            acc *= d
    return {"shape": shape, "strides": strides, "rank": len(shape)}


def desc_type_text(rank: int) -> str:
    return f"!llvm.struct<(ptr, ptr, i64, array<{rank} x i64>, array<{rank} x i64>)>"


def conv_type(ty: str) -> str:
    """成功返回 LLVM 类型文本，拒收抛异常（与 D115 conv_type 同一套规则）。"""
    ty = ty.strip()
    if ty == "index":
        return "i64"                       # 位宽随目标指针宽度（64 位目标）
    if ty in ("f32", "f64", "f16", "i1", "i8", "i16", "i32", "i64"):
        return ty
    if TENSOR_RE.match(ty):
        raise TypeConversionError(
            f"{ty}：tensor 是值语义类型，兑换表里没有目标——先过第一段 Lowering")
    if ty.startswith("memref<"):
        return desc_type_text(parse_memref(ty)["rank"])
    raise TypeConversionError(f"{ty}：未知类型，兑换表拒收")


# ---------------------------------------------------------------------------
# 3. 模式注册表（D114 的 9 行 + 今天新增 A4）＋ census ＋ 驱动器
# ---------------------------------------------------------------------------

PATTERNS = [
    {"id": "F1", "src": "func.func",        "plan": "D115", "done": True,
     "doc": "签名逐参数兑换、结果 0/1/≥2 三档打包"},
    {"id": "R1", "src": "func.return",      "plan": "D115", "done": True,
     "doc": "返回值类型兑换后原样返回"},
    {"id": "A1", "src": "arith.constant",  "plan": "D115", "done": True,
     "doc": "常量随类型兑换：index -> i64，f32 原样"},
    {"id": "A2", "src": "arith.addi/muli",  "plan": "D116", "done": True,
     "doc": "index 整数乘加 -> i64 的 llvm.add/llvm.mul"},
    {"id": "A3", "src": "arith.addf/mulf", "plan": "D116", "done": True,
     "doc": "f32 乘加 -> llvm.addf/llvm.mulf"},
    {"id": "A4", "src": "arith.cmpf/select", "plan": "D116", "done": True,
     "doc": "今天新增的清单第 10 行：cmpf -> llvm.fcmp，select -> llvm.select"},
    {"id": "C1", "src": "scf.for/scf.yield", "plan": "D117", "done": False,
     "doc": "循环拆块：br/icmp/cond_br/块参数（phi）——今天的输入刻意不含 scf"},
    {"id": "M1", "src": "memref.load",      "plan": "D116", "done": True,
     "doc": "extractvalue×4 + 2 乘 2 加 + getelementptr + llvm.load"},
    {"id": "M2", "src": "memref.store",     "plan": "D116", "done": True,
     "doc": "M1 的地址公式 + llvm.store"},
    {"id": "M3", "src": "memref.alloc",     "plan": "D116", "done": True,
     "doc": "llvm.call @malloc + llvm.mlir.undef + insertvalue×7"},
    {"id": (None), "src": "mini.*",         "plan": "不做", "done": False,
     "doc": "最终 Lowering 不负责 mini：残留说明第一段 Lowering 没跑完"},
]

OP_KINDS = [
    (re.compile(r"^func\s+@"),                    "func.func",       "F1"),
    (re.compile(r"memref\.alloc"),                "memref.alloc",    "M3"),
    (re.compile(r"arith\.constant.*:\s*index"),   "arith.constant(index)", "A1"),
    (re.compile(r"arith\.constant"),              "arith.constant(f32)",  "A1"),
    (re.compile(r"arith\.(addi|muli)"),           "arith.addi/muli", "A2"),
    (re.compile(r"arith\.(addf|mulf)"),           "arith.addf/mulf", "A3"),
    (re.compile(r"arith\.cmpf"),                  "arith.cmpf",      "A4"),
    (re.compile(r"arith\.select"),                "arith.select",   "A4"),
    (re.compile(r"scf\.for"),                     "scf.for",         "C1"),
    (re.compile(r"scf\.yield"),                   "scf.yield",       "C1"),
    (re.compile(r"memref\.load"),                 "memref.load",     "M1"),
    (re.compile(r"memref\.store"),                 "memref.store",    "M2"),
    (re.compile(r"^return"),                      "func.return",     "R1"),
    (re.compile(r"mini\."),                        "mini.*",          None),
]


def census(src: str) -> list[dict]:
    ops = []
    for line in src.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        for rx, kind, pat in OP_KINDS:
            if rx.search(s):
                ops.append({"kind": kind, "pattern": pat, "line": s})
                break
    return ops


TODAY = {"F1", "R1", "A1", "A2", "A3", "A4", "M1", "M2", "M3"}   # C1 留给 D117


def drive(ops: list[dict], mode: str, patterns: set[str] | None = None) -> dict:
    """D114/D115 同款语义：partial 残留记账、整体成功；full 残留即整批退回。"""
    patterns = patterns if patterns is not None else TODAY
    converted, residuals = [], []
    for op in ops:
        if op["pattern"] is None:
            residuals.append((op["kind"], "非法方言 mini.*：回第一段 Lowering（D85~D105）"))
            continue
        if op["pattern"] not in patterns:
            residuals.append((op["kind"], f"模式 {op['pattern']} 未实现（排期见清单）"))
            continue
        converted.append((op["kind"], op["pattern"]))
    ok = (mode == "partial") or not residuals
    return {"mode": mode, "total": len(ops), "converted": converted,
            "residuals": residuals, "ok": ok}


# ---------------------------------------------------------------------------
# 4. 发射器：逐行模式匹配，发射目标形态（op 字典序列）
# ---------------------------------------------------------------------------

FUNC_RE = re.compile(r"^func @(\w+)\((.*)\) -> (.+) \{$")
CONST_RE = re.compile(r"^(%\w+) = arith\.constant (-?[\d.]+) : (\w+)$")
ALLOC_RE = re.compile(r"^(%\w+) = memref\.alloc\(\) : (memref<.+>)$")
LOAD_RE = re.compile(r"^(%\w+) = memref\.load (%\w+)\[(%\w+), (%\w+)\] : (memref<.+>)$")
STORE_RE = re.compile(r"^memref\.store (%\w+), (%\w+)\[(%\w+), (%\w+)\] : (memref<.+>)$")
FBIN_RE = re.compile(r"^(%\w+) = arith\.(addf|mulf) (%\w+), (%\w+) : f32$")
IBIN_RE = re.compile(r"^(%\w+) = arith\.(addi|muli) (%\w+), (%\w+) : index$")
CMPF_RE = re.compile(r"^(%\w+) = arith\.cmpf (\w+) (%\w+), (%\w+) : f32$")
SEL_RE = re.compile(r"^(%\w+) = arith\.select (%\w+), (%\w+), (%\w+) : f32$")
RET_RE = re.compile(r"^return (%\w+) : (.+)$")


class EmitError(Exception):
    pass


class Emitter:
    """把无循环的源函数发射成目标形态 op 序列（LLVM 方言的机器可读形式）。

    probe：P1 = M3 填描述符时 strides 两个分量填反（D114/D115 的 P1 家族）；
           P2 = 边界包装漏写返回描述符（sret 责任被跳过）。
    """

    def __init__(self, probe: str | None = None):
        self.probe = probe
        self.ops: list[dict] = []
        self.consts: dict[str, tuple[str, str]] = {}   # 名 -> (ty, val)
        self.func: dict = {}
        self.src_name = ""

    # ---- 记录工具 ----
    def _op(self, k: str, **d) -> None:
        d["k"] = k
        self.ops.append(d)

    def _const(self, res: str, ty: str, val: str) -> None:
        self.consts[res] = (ty, val)
        self._op("const", res=res, ty=ty, val=val)

    def emit(self, src: str) -> "Emitter":
        lines = src.splitlines()
        i = 0
        while not lines[i].strip().startswith("func @"):   # 跳过头部注释
            i += 1
        # 函数头可能跨两行：先拼起来
        head = lines[i].strip()
        while not head.endswith("{"):
            i += 1
            head += " " + lines[i].strip()
        m = FUNC_RE.match(head)
        if not m:
            raise EmitError(f"函数头无法解析：{head[:60]}…")
        name, arg_txt, ret_ty = m.group(1), m.group(2), m.group(3).strip()
        self.src_name = name
        args = []
        depth, cur = 0, ""
        for ch in arg_txt:                       # 顶层逗号切分（类型里有 <>）
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            if ch == "," and depth == 0:
                args.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            args.append(cur.strip())
        arg_names = [a.split(":")[0].strip().lstrip("%") for a in args]
        arg_types = [conv_type(a.split(":")[1].strip()) for a in args]
        self.func = {"name": name, "arg_names": arg_names, "arg_types": arg_types,
                     "ret_ty": conv_type(ret_ty), "ret_is_desc": ret_ty.startswith("memref")}
        for ln in lines[i + 1:]:
            self._emit_line(ln.strip())
        return self

    def _emit_line(self, s: str) -> None:
        if s in ("}", ""):
            return
        for rx in (CONST_RE, ALLOC_RE, LOAD_RE, STORE_RE, FBIN_RE, IBIN_RE,
                   CMPF_RE, SEL_RE, RET_RE):
            m = rx.match(s)
            if m:
                break
        else:
            if re.search(r"scf\.|mini\.", s):
                raise EmitError(f"今天的发射器不处理该 op（C1/mini 属其他段）：{s[:60]}")
            raise EmitError(f"无法解析的源行：{s[:60]}")
        if rx is CONST_RE:
            res, val, ty = m.group(1), m.group(2), m.group(3)
            self._const(res, conv_type(ty), val)
        elif rx is ALLOC_RE:
            self._emit_alloc(m.group(1), m.group(2))
        elif rx is LOAD_RE:
            self._emit_mem(m.group(1), m.group(2), [m.group(3), m.group(4)],
                           m.group(5), is_store=False)
        elif rx is STORE_RE:
            self._emit_mem(None, m.group(2), [m.group(3), m.group(4)],
                           m.group(5), is_store=True, val=m.group(1))
        elif rx is FBIN_RE:
            opc = "addf" if m.group(2) == "addf" else "mulf"
            self._op("fbin", res=m.group(1), opc=opc, a=m.group(3), b=m.group(4))
        elif rx is IBIN_RE:
            opc = "add" if m.group(2) == "addi" else "mul"
            self._op("ibin", res=m.group(1), opc=opc, a=m.group(3), b=m.group(4))
        elif rx is CMPF_RE:
            self._op("fcmp", res=m.group(1), pred=m.group(2), a=m.group(3), b=m.group(4))
        elif rx is SEL_RE:
            self._op("select", res=m.group(1), c=m.group(2), a=m.group(3), b=m.group(4))
        elif rx is RET_RE:
            self._op("ret", val=m.group(1), ty=conv_type(m.group(2)))

    # ---- M3：malloc + 7 次 insertvalue ----
    def _emit_alloc(self, res: str, mty: str) -> None:
        mr = parse_memref(mty)
        rank = mr["rank"]
        dty = desc_type_text(rank)
        nbytes = int(np.prod(mr["shape"])) * 4
        stem = res[1:]
        self._const(f"%b_{stem}", "i64", str(nbytes))
        self._op("call", res=f"%mem_{stem}", callee="@malloc", arg=f"%b_{stem}")
        self._op("undef", res=f"%u_{stem}", ty=dty)
        fields: list[tuple[str, str, list[int]]] = [
            (f"%mem_{stem}", "ptr", [0]), (f"%mem_{stem}", "ptr", [1])]
        self._const(f"%off_{stem}", "i64", "0")
        fields.append((f"%off_{stem}", "i64", [2]))
        for d, v in enumerate(mr["shape"]):
            self._const(f"%s{d}_{stem}", "i64", str(v))
            fields.append((f"%s{d}_{stem}", "i64", [3, d]))
        strides = list(mr["strides"])
        if self.probe == "P1":                 # 探针 P1：strides 分量填反
            strides = strides[::-1]
        for d, v in enumerate(strides):
            self._const(f"%t{d}_{stem}", "i64", str(v))
            fields.append((f"%t{d}_{stem}", "i64", [4, d]))
        prev = f"%u_{stem}"
        for n, (v, vty, pos) in enumerate(fields):
            r = res if n == len(fields) - 1 else f"%i{n}_{stem}"
            self._op("insert", res=r, val=v, src=prev, pos=pos, sty=dty, vty=vty)
            prev = r

    # ---- M1/M2：描述符取字段 -> 元素偏移 -> 地址 -> load/store ----
    def _emit_mem(self, res, mem: str, idx: list[str], mty: str,
                  is_store: bool, val: str | None = None) -> None:
        rank = parse_memref(mty)["rank"]
        dty = desc_type_text(rank)
        stem = (res or f"{val}_dst")[1:]
        self._op("extract", res=f"%{stem}_al", src=mem, pos=[1], sty=dty, rty="ptr")
        self._op("extract", res=f"%{stem}_off", src=mem, pos=[2], sty=dty, rty="i64")
        for d in range(rank):
            self._op("extract", res=f"%{stem}_s{d}", src=mem, pos=[4, d],
                     sty=dty, rty="i64")
        acc = f"%{stem}_off"
        for d in range(rank):
            m = f"%{stem}_m{d}"
            self._op("ibin", opc="mul", res=m, a=idx[d], b=f"%{stem}_s{d}")
            a = f"%{stem}_a{d}"
            self._op("ibin", opc="add", res=a, a=acc, b=m)
            acc = a
        self._op("gep", res=f"%{stem}_p", base=f"%{stem}_al", idx=acc, elem="f32")
        if is_store:
            self._op("store", val=val, ptr=f"%{stem}_p", ty="f32")
        else:
            self._op("load", res=res, ptr=f"%{stem}_p", ty="f32")


# ---------------------------------------------------------------------------
# 5. 两个序列化器：LLVM 方言文本 / LLVM IR 文本（含边界包装 _mlir_ciface）
# ---------------------------------------------------------------------------

F32_ZERO_LL = "0.000000e+00"


def to_dialect_text(em: Emitter) -> str:
    """LLVM 方言文本（D113/D114 的印刷约定；R3 的块与 phi 今天用不到）。"""
    f = em.func
    args = ", ".join(f"%{n}: {t}" for n, t in zip(f["arg_names"], f["arg_types"]))
    ret = f" -> {f['ret_ty']}" if f["ret_ty"] != "void" else ""
    lines = [f"llvm.func @{f['name']}({args}){ret} {{"]
    for o in em.ops:
        k = o["k"]
        if k == "const":
            lines.append(f"  {o['res']} = llvm.mlir.constant({o['val']} : {o['ty']}) : {o['ty']}")
        elif k == "undef":
            lines.append(f"  {o['res']} = llvm.mlir.undef : {o['ty']}")
        elif k == "call":
            lines.append(f"  {o['res']} = llvm.call @malloc({o['arg']} : i64) : (i64) -> !llvm.ptr")
        elif k == "insert":
            pos = ", ".join(str(p) for p in o["pos"])
            lines.append(f"  {o['res']} = llvm.insertvalue {o['val']}, {o['src']}[{pos}] : {o['sty']} -> {o['vty']}")
        elif k == "extract":
            pos = ", ".join(str(p) for p in o["pos"])
            lines.append(f"  {o['res']} = llvm.extractvalue {o['src']}[{pos}] : {o['sty']} -> {o['rty']}")
        elif k == "ibin":
            lines.append(f"  {o['res']} = llvm.{o['opc']} {o['a']}, {o['b']} : i64")
        elif k == "fbin":
            lines.append(f"  {o['res']} = llvm.{o['opc']} {o['a']}, {o['b']} : f32")
        elif k == "fcmp":
            lines.append(f"  {o['res']} = llvm.fcmp \"{o['pred']}\" {o['a']}, {o['b']} : f32")
        elif k == "select":
            lines.append(f"  {o['res']} = llvm.select {o['c']}, {o['a']}, {o['b']} : i1, f32")
        elif k == "gep":
            lines.append(f"  {o['res']} = llvm.getelementptr {o['base']}[{o['idx']}] : (!llvm.ptr, i64) -> !llvm.ptr, {o['elem']}")
        elif k == "load":
            lines.append(f"  {o['res']} = llvm.load {o['ptr']} : !llvm.ptr -> {o['ty']}")
        elif k == "store":
            lines.append(f"  llvm.store {o['val']}, {o['ptr']} : {o['ty']}, !llvm.ptr")
        elif k == "ret":
            lines.append(f"  llvm.return {o['val']} : {o['ty']}")
        else:
            raise EmitError(k)
    lines.append("}")
    lines.append("")
    lines.append("// 运行库符号：真实 MLIR 由 MemRefToLLVM 自动声明 malloc")
    lines.append("llvm.func @malloc(i64) -> !llvm.ptr")
    return "\n".join(lines) + "\n"


def to_llvm_text(em: Emitter, triple: str) -> str:
    """LLVM IR 文本：应用 D113 的导出规则（R1 命名沿用目标形态便于对照、
    R2 常量内联；R3 块参数/phi 今天无用武之地——没有控制流）。

    布局两件事与真实 MLIR 对齐：
      * 函数本体保持 llvm.func 的按值描述符签名（LLVM 内部合同，两侧都由
        同一个 LLVM 编译，自洽——实测：入参走栈副本、返回拆 x0..x6）；
      * 对 JIT/C 边界另发 _mlir_ciface 包装：只说指针与标量
        （真实 MLIR 在 llvm.emit_c_interface 时同样生成 _mlir_ciface_*）。
    """
    f = em.func
    ranks = [len(parse_memref_from_desc(t)) for t in list(f["arg_types"]) + ([f["ret_ty"]] if f["ret_is_desc"] else []) if t.startswith("!")]
    rank = ranks[0] if ranks else 2
    DS = desc_ll_type(rank)
    consts = {k: v for k, v in em.consts.items()}

    def lit(v: str) -> str:
        if v in consts:
            ty, val = consts[v]
            if ty == "f32":
                return F32_ZERO_LL if val == "0.0" else val
            return val
        return v

    lines = [f"; 第 116 天：由 op_lowering.py 从源 IR 转换导出（函数 {f['name']}）",
             f"target triple = \"{triple}\""]
    if f["ret_is_desc"] or any(t.startswith("!") for t in f["arg_types"]):
        lines += [f"%desc = type {DS}"]
    lines += ["declare ptr @malloc(i64)", ""]
    args = ", ".join(f"{ty} %{n}" for n, ty in zip(f["arg_names"], f["arg_types"]))
    args = args.replace(desc_type_text(rank), "%desc")
    ret_ty = f["ret_ty"].replace(desc_type_text(rank), "%desc") if f["ret_is_desc"] else f["ret_ty"]
    linkage = "internal" if f["ret_is_desc"] else ""      # 有包装时本体做内部函数
    noinline = " noinline" if f["ret_is_desc"] else ""    # 教学选择：保留调用边界，
    # 让 56B 聚合的 ABI 形态在汇编里可观察（注意 noinline 是函数属性，放参数表之后）
    lines += [f"define {linkage} {ret_ty} @{f['name']}({args}){noinline} {{", "entry:"]
    undefs = {o["res"] for o in em.ops if o["k"] == "undef"}
    for o in em.ops:
        k = o["k"]
        if k == "const":
            continue                                    # R2：常量内联
        if k == "undef":
            continue                                    # undef 只能作操作数（内联）
        elif k == "call":
            lines.append(f"  {o['res']} = call ptr @malloc(i64 {lit(o['arg'])})")
        elif k == "insert":
            pos = ", ".join(str(p) for p in o["pos"])
            src = "undef" if o["src"] in undefs else o["src"]
            # 注意：LLVM 里命名结构体（%desc）与字面结构体（{ ... }）是两个
            # 不同类型——识别到这一点本身就是一次真实踩坑（见常见错误 4）
            lines.append(f"  {o['res']} = insertvalue %desc {src}, "
                         f"{o['vty']} {lit(o['val'])}, {pos}")
        elif k == "extract":
            pos = ", ".join(str(p) for p in o["pos"])
            lines.append(f"  {o['res']} = extractvalue %desc {o['src']}, {pos}")
        elif k == "ibin":
            lines.append(f"  {o['res']} = {o['opc']} i64 {lit(o['a'])}, {lit(o['b'])}")
        elif k == "fbin":
            opc = {"addf": "fadd", "mulf": "fmul"}[o["opc"]]   # 方言名 -> IR 指令名
            lines.append(f"  {o['res']} = {opc} float {lit(o['a'])}, {lit(o['b'])}")
        elif k == "fcmp":
            lines.append(f"  {o['res']} = fcmp {o['pred']} float {lit(o['a'])}, {lit(o['b'])}")
        elif k == "select":
            lines.append(f"  {o['res']} = select i1 {o['c']}, float {lit(o['a'])}, float {lit(o['b'])}")
        elif k == "gep":
            lines.append(f"  {o['res']} = getelementptr float, ptr {o['base']}, i64 {lit(o['idx'])}")
        elif k == "load":
            lines.append(f"  {o['res']} = load float, ptr {o['ptr']}")
        elif k == "store":
            lines.append(f"  store float {lit(o['val'])}, ptr {o['ptr']}")
        elif k == "ret":
            lines.append(f"  ret {ret_ty} {o['val']}")
    lines.append("}")
    if f["ret_is_desc"]:                                # 边界包装：指针合同
        aps = ", ".join(f"ptr %{n}_p" for n in f["arg_names"])
        lines += ["", f"define void @_mlir_ciface_{f['name']}({aps}, ptr %outp) {{", "entry:"]
        for n, t in zip(f["arg_names"], f["arg_types"]):
            if t.startswith("!"):
                lines.append(f"  %{n} = load %desc, ptr %{n}_p")
        call_args = ", ".join(
            f"%desc %{n}" if t.startswith("!") else f"{t} %{n}"
            for n, t in zip(f["arg_names"], f["arg_types"]))
        lines.append(f"  %r = call %desc @{f['name']}({call_args})")
        if em.probe != "P2":                            # 探针 P2：漏写返回描述符
            lines.append("  store %desc %r, ptr %outp")
        lines += ["  ret void", "}"]
    return "\n".join(lines) + "\n"


def parse_memref_from_desc(desc_ty: str) -> list[int]:
    """从描述符类型文本取 rank（array<N x i64> 出现两次）。"""
    m = re.search(r"array<(\d+) x i64>", desc_ty)
    return [0] * int(m.group(1)) if m else [0, 0]


def desc_ll_type(rank: int) -> str:
    return (f"{{ ptr, ptr, i64, [{rank} x i64], [{rank} x i64] }}")


# ---------------------------------------------------------------------------
# 6. 静态检查（TP2/TP3 用）：目标图合法性、胶水清零、计数
# ---------------------------------------------------------------------------

DIALECT_OP_RES = [
    (re.compile(r"^\s*%\w+ = llvm\.mlir\.constant\("), "const"),
    (re.compile(r"^\s*%\w+ = llvm\.mlir\.undef :"), "undef"),
    (re.compile(r"^\s*%\w+ = llvm\.call @malloc\("), "call"),
    (re.compile(r"^\s*%\w+ = llvm\.insertvalue "), "insert"),
    (re.compile(r"^\s*%\w+ = llvm\.extractvalue "), "extract"),
    (re.compile(r"^\s*%\w+ = llvm\.(add|mul) "), "ibin"),
    (re.compile(r"^\s*%\w+ = llvm\.(addf|mulf) "), "fbin"),
    (re.compile(r"^\s*%\w+ = llvm\.fcmp \""), "fcmp"),
    (re.compile(r"^\s*%\w+ = llvm\.select "), "select"),
    (re.compile(r"^\s*%\w+ = llvm\.getelementptr "), "gep"),
    (re.compile(r"^\s*%\w+ = llvm\.load "), "load"),
    (re.compile(r"^\s*llvm\.store "), "store"),
    (re.compile(r"^\s*llvm\.return "), "ret"),
    (re.compile(r"^\s*llvm\.func @"), "func"),
    (re.compile(r"^\s*//"), "comment"),
    (re.compile(r"^\s*$"), "blank"),
    (re.compile(r"^\s*\}$"), "rbrace"),
]


def check_dialect(text: str, n_alloc: int, rank: int) -> tuple[list[str], dict]:
    errs: list[str] = []
    counts: dict[str, int] = {}
    inserts: list[tuple[int, ...]] = []
    extracts: list[tuple[int, ...]] = []
    for ln in text.splitlines():
        s = ln.split("//")[0].strip()
        if not s:
            continue
        for bad in ("memref<", ": index", "arith.", "scf.", "unrealized_conversion_cast"):
            if bad in s:
                errs.append(f"目标图残留非法内容 {bad!r}：{s[:56]}")
        for rx, name in DIALECT_OP_RES:
            if rx.match(ln):
                counts[name] = counts.get(name, 0) + 1
                if name == "insert":
                    pos = tuple(int(p) for p in
                                re.search(r"\[([0-9, ]+)\]", ln).group(1).split(","))
                    inserts.append(pos)
                if name == "extract":
                    pos = tuple(int(p) for p in
                                re.search(r"\[([0-9, ]+)\]", ln).group(1).split(","))
                    extracts.append(pos)
                break
        else:
            errs.append(f"未知的行（不是 llvm.* op）：{s[:56]}")
    need = {(0,), (1,), (2,)} | {(3, d) for d in range(rank)} | {(4, d) for d in range(rank)}
    if n_alloc and set(inserts) != need:
        errs.append(f"M3 填表不完整：{sorted(set(inserts))} != {sorted(need)}")
    for pos in extracts:
        if pos[0] not in (1, 2, 3, 4):
            errs.append(f"extractvalue 位置非法：{pos}")
        elif pos[0] in (1, 2) and len(pos) != 1:
            errs.append(f"extractvalue 位置深度非法：{pos}")
        elif pos[0] in (3, 4) and len(pos) != 2:
            errs.append(f"extractvalue 位置深度非法：{pos}")
    if counts.get("gep", 0) != counts.get("load", 0) + counts.get("store", 0):
        errs.append("getelementptr 数量不等于 load+store")
    if counts.get("call", 0) != n_alloc:
        errs.append("malloc 调用数不等于 alloc 数")
    return errs, counts


# ---------------------------------------------------------------------------
# 7. 真机：JIT + ctypes + 三层验证
# ---------------------------------------------------------------------------

_ENGINES: list = []      # MCJIT 引擎保活（D115 常见错误 4 的教训）


class Desc(ctypes.Structure):
    _fields_ = [("allocated", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("offset", ctypes.c_int64), ("sizes", ctypes.c_int64 * 2),
                ("strides", ctypes.c_int64 * 2)]


def jit_module(ll_text: str):
    mod = lv.parse_assembly(ll_text)
    mod.verify()
    tm = lv.Target.from_triple(lv.get_default_triple()).create_target_machine()
    eng = lv.create_mcjit_compiler(mod, tm)
    eng.finalize_object()
    _ENGINES.append(eng)
    return eng, tm, mod


def mk_desc(a: np.ndarray, strides_elems: tuple | None = None) -> Desc:
    d = Desc()
    d.allocated = a.ctypes.data
    d.aligned = a.ctypes.data
    d.offset = 0
    d.sizes[0], d.sizes[1] = a.shape
    st = strides_elems if strides_elems is not None else (a.shape[1], 1)
    d.strides[0], d.strides[1] = st
    return d


def run_ciface(eng, name: str, descs: list[Desc]) -> Desc:
    f = ctypes.CFUNCTYPE(None, *[ctypes.POINTER(Desc)] * len(descs),
                         ctypes.POINTER(Desc))(eng.get_function_address(
                             f"_mlir_ciface_{name}"))
    out = Desc()
    f(*[ctypes.byref(d) for d in descs], ctypes.byref(out))
    return out


def desc_view(out: Desc) -> np.ndarray:
    """按描述符读回结果（第 1 层：语义——值跟着 strides 走）。"""
    arr = np.ctypeslib.as_array(
        ctypes.cast(out.allocated, ctypes.POINTER(ctypes.c_float)),
        shape=(int(out.sizes[0] * out.sizes[1]),))
    idx = [(i, j) for i in range(int(out.sizes[0])) for j in range(int(out.sizes[1]))]
    view = np.empty((int(out.sizes[0]), int(out.sizes[1])), dtype=np.float32)
    for i, j in idx:
        lin = i * int(out.strides[0]) + j * int(out.strides[1]) + int(out.offset)
        view[i, j] = arr[lin]
    return view


def flat_view(out: Desc) -> np.ndarray:
    """裸内存顺序读回（第 2 层：布局——返回缓冲区必须是行主序连续）。"""
    n = int(out.sizes[0]) * int(out.sizes[1])
    return np.ctypeslib.as_array(
        ctypes.cast(out.allocated, ctypes.POINTER(ctypes.c_float)), shape=(n,)).copy()


def check_contract(out: Desc, shape: tuple, strides_exp: tuple) -> list[str]:
    bad = []
    if not out.allocated:
        bad.append("allocated 为空（包装没把描述符写回来？）")
    if out.aligned != out.allocated:
        bad.append(f"aligned({out.aligned}) != allocated({out.allocated})")
    if int(out.offset) != 0:
        bad.append(f"offset = {out.offset}，期望 0")
    if tuple(int(x) for x in out.sizes) != shape:
        bad.append(f"sizes = {list(out.sizes)}，期望 {list(shape)}")
    if tuple(int(x) for x in out.strides) != strides_exp:
        bad.append(f"strides = {list(out.strides)}，期望 {list(strides_exp)}")
    return bad


def bitwise(a: np.ndarray, b: np.ndarray) -> bool:
    return a.tobytes() == b.tobytes()


# ---------------------------------------------------------------------------
# 8. 测试：账本、静态检查、翻译、真机执行、转置、探针、形状对照
# ---------------------------------------------------------------------------

TRIPLE = lv.get_default_triple() if HAVE_LLVMLITE else "unknown"


def tp1_accounts(srcs: dict[str, str]) -> bool:
    log("[TP1] 账本四联：三个新输入 full 必须清零；GEMM 只做回归（C1 在 D117）")
    ok = True
    expect_full = {"add": True, "relu": True, "step": True, "gemm": False}
    for name, src in srcs.items():
        ops = census(src)
        par = drive(ops, "partial")
        ful = drive(ops, "full")
        res_kinds = sorted({k for k, _ in par["residuals"]})
        good = (par["ok"] and ful["ok"] == expect_full[name]
                and (len(par["residuals"]) == 0 if expect_full[name]
                     else len(par["residuals"]) == 4))
        ok &= good
        log(f"      @{name}: {len(par['converted'])}/{par['total']} 转换，"
            f"残账 {len(par['residuals'])} 条"
            + (f"（{', '.join(res_kinds)} -> C1，D117）" if par["residuals"] else "")
            + f"；full {'SUCCESS' if ful['ok'] else 'FAIL'}"
            + ("" if ful["ok"] else "（导出前的门，非今天的失败）"))
    return ok


def tp2_static(name: str, src: str) -> dict:
    em = Emitter().emit(src)
    text = to_dialect_text(em)
    out_name = name if not FROZEN_TAG else f"{name}-{FROZEN_TAG}"
    (OUT / f"{out_name}-target.mlir").write_text(text, encoding="utf-8")
    n_alloc = sum(1 for o in em.ops if o["k"] == "call")
    rank = 2
    errs, counts = check_dialect(text, n_alloc, rank)
    n_src = len(census(src))
    log(f"[TP2] @{name} 目标图静态检查（LLVM 方言文本）")
    log(f"      源 {n_src} op -> 目标 {len(em.ops)} op（膨胀 {len(em.ops) / n_src:.1f} 倍）；"
        f"胶水（unrealized_conversion_cast）0 条——full 转换后没有新旧类型交界")
    key = {"const": 0, "call": 0, "insert": 0, "extract": 0, "ibin": 0,
           "fbin": 0, "fcmp": 0, "select": 0, "gep": 0, "load": 0, "store": 0}
    for k in key:
        key[k] = counts.get(k, 0)
    log(f"      目标 op 分布：load {key['load']}，store {key['store']}，"
        f"extractvalue {key['extract']}，insertvalue {key['insert']}，"
        f"乘加 {key['ibin']}，浮点乘加 {key['fbin']}，fcmp {key['fcmp']}，"
        f"select {key['select']}，malloc {key['call']}，常量 {key['const']}")
    if errs:
        for e in errs:
            log(f"      问题：{e}")
    else:
        log("      全部 llvm.*、无 index/memref 残留、M3 填表 7 字段齐全、"
            "gep 数＝访存数：OK")
    return {"em": em, "text": text, "ok": not errs, "counts": key}


def tp3_translate(name: str, em: Emitter) -> dict:
    ll = to_llvm_text(em, TRIPLE)
    out_name = name if not FROZEN_TAG else f"{name}-{FROZEN_TAG}"
    (OUT / f"{out_name}.ll").write_text(ll, encoding="utf-8")
    mod = lv.parse_assembly(ll)
    mod.verify()
    n_const = sum(1 for o in em.ops if o["k"] == "const")
    n_body = len(em.ops) - n_const - sum(1 for o in em.ops if o["k"] == "undef")
    symbols = sorted(re.findall(r"^(?:define|declare)[^@]*@([\w.]+)", ll, re.M))
    has_wrap = f"_mlir_ciface_{name}" in ll
    log(f"[TP3] @{name} 导出与 verify：LLVM IR parse+verify 通过（真 LLVM "
        f"{'.'.join(map(str, lv.llvm_version_info))}）")
    log(f"      R2 常量内联：{n_const} 条 llvm.mlir.constant 全部消失，"
        f".ll 指令 {n_body} 条；R3（块参数/phi）今天用不到——没有控制流")
    log(f"      符号：{', '.join(symbols)}"
        + (f"；边界包装 _mlir_ciface_{name}（指针合同）已生成" if has_wrap else
           "；标量签名直接可调（无 memref，无需包装）"))
    return {"ll": ll, "ok": True, "has_wrap": has_wrap}


def _run_desc_fn(ll_text: str, name: str, arrays: list[np.ndarray],
                 strides: list[tuple | None]) -> dict:
    """JIT 一个 memref 签名函数并按三层验证读回（不比数值，数值交给调用方）。"""
    eng, _tm, mod = jit_module(ll_text)
    descs = [mk_desc(a, st) for a, st in zip(arrays, strides)]
    out = run_ciface(eng, name, descs)
    return {"eng": eng, "mod": mod, "out": out}


def _example_inputs(R: int, C: int):
    """2×2 用可手算的固定值；其他形状用固定种子随机值。"""
    if (R, C) == (2, 2):
        A = np.array([[1.5, -2.5], [0.0, -0.0]], dtype=np.float32)
        B = np.array([[10.25, -0.5], [3.0, 7.75]], dtype=np.float32)
        X = np.array([[1.5, -2.5], [0.0, -0.0]], dtype=np.float32)
        E = np.array([[np.inf, -np.inf], [np.nan, 3.25]], dtype=np.float32)
        return A, B, X, E
    rng = np.random.default_rng(116)
    A = rng.standard_normal((R, C)).astype(np.float32)
    B = rng.standard_normal((R, C)).astype(np.float32)
    X = rng.standard_normal((R, C)).astype(np.float32)
    pat = np.array([[np.inf, -np.inf], [np.nan, 3.25]], dtype=np.float32)
    E = np.resize(pat, (R, C)).astype(np.float32)
    return A, B, X, E


def tp4_add(ll: str, R: int, C: int) -> dict:
    A, B, X, E = _example_inputs(R, C)
    ref = (A + B).astype(np.float32)
    eng, _tm, mod = jit_module(ll)
    da, db = mk_desc(A), mk_desc(B)
    out = run_ciface(eng, "add", [da, db])

    log("[TP4] 真机执行 @add——第一个端到端可执行算子（源 IR -> 模式 -> 导出 -> JIT -> 参考对照）")
    bad = check_contract(out, (R, C), (C, 1))
    contract_ok = not bad
    for b in bad:
        log(f"      契约层问题：{b}")
    if contract_ok:
        log(f"      契约层：allocated!=0，aligned==allocated，offset 0，"
            f"sizes {[int(x) for x in out.sizes]}，strides {[int(x) for x in out.strides]} OK")
    view = desc_view(out)
    flat = flat_view(out)
    v_ok = bitwise(view, ref)
    f_ok = bitwise(flat, ref.flatten())
    n_v = int((view == ref).sum())
    n_f = int((flat == ref.flatten()).sum())
    log(f"      数值层（描述符读回）：{n_v}/{ref.size} 点 bitwise 一致")
    log(f"      布局层（裸内存行主序）：{n_f}/{ref.size} 点 bitwise 一致——"
        f"契约里的 strided<[{C},1]> 兑现")
    if (R, C) == (2, 2):
        log(f"      手算对照：1.5+10.25={ref[0,0]}，-2.5-0.5={ref[0,1]}，"
            f"0.0+3.0={ref[1,0]}，-0.0+7.75={ref[1,1]}")
    return {"ok": contract_ok and v_ok and f_ok, "eng": eng, "mod": mod,
            "view": view, "flat": flat, "ref": ref}


def disasm_evidence(mod, name: str) -> bool:
    """包装函数的汇编证据：按值聚合在 LLVM 内部合同下怎么上寄存器/栈。"""
    try:
        tm = lv.Target.from_triple(TRIPLE).create_target_machine()
        asm = tm.emit_assembly(mod)
    except Exception as e:  # pragma: no cover
        log(f"      汇编证据不可用：{e}")
        return False
    (OUT / ("ciface-disasm.s" if not FROZEN_TAG
            else f"ciface-disasm-{FROZEN_TAG}.s")).write_text(
        f"; 第 116 天：@{name} 与 _mlir_ciface_{name} 的真实汇编（llvmlite LLVM "
        f"{lv.llvm_version_info[0]} 输出，aarch64；noinline 保留调用边界）\n" + asm,
        encoding="utf-8")
    lines = asm.splitlines()
    body, on = [], False
    for ln in lines:
        t = ln.strip()
        if t.startswith(f"_mlir_ciface_{name}:"):
            on = True
            continue
        if on:
            if t == ".cfi_endproc" or t.startswith(".Lfunc_end"):
                break
            body.append(t)
    bl_i = next((i for i, t in enumerate(body)
                 if re.match(rf"bl\s+{name}\b", t)), None)
    if bl_i is None:
        log("      汇编证据：未见 bl（调用边界被内联），跳过形态分析")
        return False
    clean = lambda t: t.replace("\t", " ")
    before = [t for t in body[:bl_i] if t.startswith(("stp", "str"))]
    after = [t for t in body[bl_i + 1:] if re.match(r"(stp|str)\s+x\d", t)]
    log(f"      汇编证据（真机 aarch64，{len(body)} 条指令）：`{clean(body[bl_i])}` 前用 "
        f"{len(before)} 条 stp/str 把按值入参复制上栈/寄存器（2×56B＝14 个 8 字节，"
        "8 个可用寄存器装不下）")
    log(f"        调用后 {len(after)} 条把 56B 结果写进 outp：{clean(after[0])} … "
        f"{clean(after[-1])}——聚合返回拆在 x0..x6，不是 gcc C ABI 的 x8")
    log("        ——合同分层：C 合同（gcc，>16B 走间接/x8，D115 证据）与 LLVM 内部"
        "合同（两侧同编译，自洽）不是同一份；边界只说指针，所以必须包装")
    return bool(before) and len(after) >= 4


def tp5_relu(ll: str, R: int, C: int) -> bool:
    _A, _B, X, E = _example_inputs(R, C)
    eng, _tm, _mod = jit_module(ll)
    ok = True
    for tag, Xin in (("主输入", X), ("边界输入", E)):
        out = run_ciface(eng, "relu", [mk_desc(Xin)])
        bad = check_contract(out, (R, C), (C, 1))
        ok &= not bad
        ref_where = np.where(Xin > np.float32(0), Xin, np.float32(0)).astype(np.float32)
        ref_max = np.maximum(Xin, np.float32(0)).astype(np.float32)
        view, flat = desc_view(out), flat_view(out)
        w_ok = bitwise(view, ref_where)
        m_ok = bitwise(view, ref_max)
        n_w = int((view == ref_where).sum())
        n_m = int((view == ref_max).sum())
        log(f"      {tag} {Xin.tolist()}：")
        log(f"        结果 {view.tolist()}；与 np.where(x>0,x,0) "
            f"{n_w}/{Xin.size} 点 bitwise（{'OK' if w_ok else 'MISMATCH'}）；"
            f"与 np.maximum(x,0) {n_m}/{Xin.size} 点"
            + ("" if m_ok else "（不一致：NaN 语义，见常见错误 1）"))
        ok &= w_ok and bitwise(flat, ref_where.flatten())
    log("      语义注：cmpf ogt + select 下 relu(-0.0)=+0.0、relu(NaN)=0——"
        "参考必须与 IR 语义逐位对齐，np.maximum 在 NaN 上不适用")
    return ok


def tp6_step(ll: str) -> bool:
    eng, _tm, _mod = jit_module(ll)
    f = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64,
                         ctypes.c_int64)(eng.get_function_address("step"))
    log("[TP6] 真机执行 @step（A2：index 整数乘加 -> i64）")
    ok = True
    for i, k in [(0, 0), (2, 3), (-5, 7), (-1, -1), (2 ** 40, 2 ** 40)]:
        got = f(i, k)
        exp = (i + k) * 2
        ok &= got == exp
        log(f"      step({i}, {k}) = {got}（期望 {exp}）{'OK' if got == exp else 'MISMATCH'}")
    log("      标量签名 (index, index) -> index 兑换成 (i64, i64) -> i64——"
        "index 位宽就是目标指针宽度（D115 兑换表）")
    return ok


def tp7_transpose(add_res: dict, R: int, C: int) -> bool:
    base = np.arange(1, R * C + 1, dtype=np.float32).reshape(C, R)
    Av = base.T                      # (R, C) 视图，元素 strides (1, R)
    B = np.array([[10.25, -0.5], [3.0, 7.75]], dtype=np.float32)
    B = np.resize(B, (R, C)).astype(np.float32)
    ref = (Av + B).astype(np.float32)
    eng = add_res["eng"]
    out = run_ciface(eng, "add", [mk_desc(Av, (1, R)), mk_desc(B)])
    log("[TP7] 转置视图输入：@add 的 %a 换成转置视图（复用同一个 JIT 引擎）")
    log(f"      numpy .strides={Av.strides} 是字节，描述符要元素步长 (1, {R})"
        "（D115 常见错误 1 的正面应用）")
    bad = check_contract(out, (R, C), (C, 1))
    view, flat = desc_view(out), flat_view(out)
    v_ok = bitwise(view, ref)
    n_v = int((view == ref).sum())
    log(f"      描述符读回 {n_v}/{R * C} 点 bitwise（{'OK' if v_ok else 'MISMATCH'}）——"
        "M1 的地址公式对任意合法 strides 成立，描述符是通用读法")
    return not bad and v_ok and bitwise(flat, ref.flatten())


def tp8_probes(add_src: str, R: int, C: int) -> bool:
    log("[TP8] 探针三连：故意埋错，看哪一层咬得住（全部真实执行）")
    ok = True
    A, B, X, E = _example_inputs(R, C)
    ref = (A + B).astype(np.float32)

    # P1：M3 把输出描述符的 strides 填反。
    # 方形形状上反序是缓冲区上的双射（地址全部在界内、读回自洽）；
    # 非方形上 store 会线性越界写坏 malloc 堆——所以探针只在方形上跑。
    if R == C:
        em1 = Emitter(probe="P1").emit(add_src)
        ll1 = to_llvm_text(em1, TRIPLE)
        eng1, _tm, _m = jit_module(ll1)
        out1 = run_ciface(eng1, "add", [mk_desc(A), mk_desc(B)])
        bad = check_contract(out1, (R, C), (C, 1))
        view1, flat1 = desc_view(out1), flat_view(out1)
        p1_view = int((view1 == ref).sum())
        p1_flat = int((flat1 == ref.flatten()).sum())
        n_all = R * C
        log(f"      P1 M3 strides 填反：契约层咬住（{bad[0] if bad else '—'}）")
        log(f"        数值层（描述符读回）{p1_view}/{n_all} 点对——错误坐标系自洽，读回照样全对！")
        log(f"        布局层（裸内存）只有 {p1_flat}/{n_all} 点对、{n_all - p1_flat} 点错位——"
            "两层检查各抓各的，只做数值层就会放走这个 bug")
        ok &= bool(bad) and p1_view == n_all and p1_flat < n_all
    else:
        log(f"      P1 M3 strides 填反：{R}×{C} 非方形——反序不再在界内，"
            "store 会越界写坏堆，探针只在方形上跑（2×2 上它是双射，这就是它狡猾的地方）")

    # P2：包装漏写返回描述符（sret 责任被跳过）
    em2 = Emitter(probe="P2").emit(add_src)
    ll2 = to_llvm_text(em2, TRIPLE)
    eng2, _tm, _m = jit_module(ll2)
    out2 = run_ciface(eng2, "add", [mk_desc(A), mk_desc(B)])
    bad2 = check_contract(out2, (R, C), (C, 1))
    log(f"      P2 包装漏回写：契约层咬住（{'allocated 为空' if not out2.allocated else bad2}）"
        "——D115 的 sret 责任在包装里兑现，漏了就被字段检查抓")
    ok &= (not out2.allocated) and bool(bad2)

    # 参考探针：np.maximum 当 relu 参考（TP5 的数字对照）
    diff = int((np.where(E > np.float32(0), E, np.float32(0)).astype(np.float32)
                != np.maximum(E, np.float32(0)).astype(np.float32)).sum())
    log(f"      P3 参考写错（np.maximum 当 relu 参考）：边界输入下 {diff} 点不一致——"
        "参考也必须被验证语义，bitwise 对照的前提是参考与 IR 语义一致")
    ok &= diff == int(np.isnan(E).sum())
    return ok


def tp9_variant(R: int, C: int, srcs_gen) -> bool:
    log(f"[TP9] 形状对照：--shape {R} {C}（计数随形状变，字节账随形状变，正确性不变）")
    add_src = srcs_gen["add"](R, C)
    relu_src = srcs_gen["relu"](R, C)
    em = Emitter().emit(add_src)
    ll = to_llvm_text(em, TRIPLE)
    n_bytes = R * C * 4
    ops = census(add_src)
    par = drive(ops, "partial")
    log(f"      @add {R}×{C}：源 {par['total']} op（2×2 是 21）、full "
        f"{'SUCCESS' if not par['residuals'] else '有残账'}；malloc {n_bytes} B、"
        f"strides [{C},1]")
    eng, _tm, _m = jit_module(ll)
    rng = np.random.default_rng(116)
    A = rng.standard_normal((R, C)).astype(np.float32)
    B = rng.standard_normal((R, C)).astype(np.float32)
    ref = (A + B).astype(np.float32)
    out = run_ciface(eng, "add", [mk_desc(A), mk_desc(B)])
    bad = check_contract(out, (R, C), (C, 1))
    view, flat = desc_view(out), flat_view(out)
    ok1 = not bad and bitwise(view, ref) and bitwise(flat, ref.flatten())
    n1 = int((view == ref).sum())
    log(f"      真机 @add：{n1}/{R * C} 点 bitwise 一致（随机输入），"
        f"{'OK' if ok1 else 'MISMATCH'}")
    em2 = Emitter().emit(relu_src)
    ll2 = to_llvm_text(em2, TRIPLE)
    eng2, _tm, _m = jit_module(ll2)
    X = rng.standard_normal((R, C)).astype(np.float32)
    ref2 = np.where(X > np.float32(0), X, np.float32(0)).astype(np.float32)
    out2 = run_ciface(eng2, "relu", [mk_desc(X)])
    bad2 = check_contract(out2, (R, C), (C, 1))
    v2 = desc_view(out2)
    ok2 = not bad2 and bitwise(v2, ref2) and bitwise(flat_view(out2), ref2.flatten())
    n2 = int((v2 == ref2).sum())
    log(f"      真机 @relu：{n2}/{R * C} 点 bitwise 一致（随机输入），"
        f"{'OK' if ok2 else 'MISMATCH'}")
    gemm_ops = census(srcs_gen["gemm"]())
    gp = drive(gemm_ops, "partial")
    log(f"      GEMM 账本不变：{len(gp['converted'])}/{gp['total']}，残账 "
        f"{len(gp['residuals'])} 条（与形状无关的 C1 欠账）")
    return ok1 and ok2 and len(gp["residuals"]) == 4


# ---------------------------------------------------------------------------
# 9. 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    global FROZEN_TAG
    ap = argparse.ArgumentParser()
    ap.add_argument("--shape", type=int, nargs=2, default=[2, 2], metavar=("R", "C"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--emit-src", choices=["add", "relu", "step", "gemm"])
    args = ap.parse_args()
    R, C = args.shape
    FROZEN_TAG = args.tag
    if args.emit_src:
        sys.stdout.write({"add": make_add_ir(R, C), "relu": make_relu_ir(R, C),
                          "step": make_step_ir(),
                          "gemm": make_gemm_ir()}[args.emit_src])
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"第 116 天：转换简单 Elementwise 算子——真机报告（{stamp}）")
    import llvmlite
    env = (f"Python {sys.version.split()[0]} / numpy {np.__version__} / "
           f"llvmlite {llvmlite.__version__}（LLVM {'.'.join(map(str, lv.llvm_version_info))}）"
           f" / triple {TRIPLE}")
    log(f"环境：{env}")
    log(f"输入：@add {R}×{C}、@relu {R}×{C}（展开形态，无 scf.for）、"
        f"@step（标量）、GEMM 4×6×3（账本回归）")
    log("")

    srcs = {"add": make_add_ir(R, C), "relu": make_relu_ir(R, C),
            "step": make_step_ir(), "gemm": make_gemm_ir()}
    if (R, C) == (2, 2) and not FROZEN_TAG:
        for nm, key in (("add_ir.mlir", "add"), ("relu_ir.mlir", "relu"),
                        ("step_ir.mlir", "step"), ("gemm_ir.mlir", "gemm")):
            (CODE / nm).write_text(srcs[key], encoding="utf-8")

    results = {}
    results["TP1"] = tp1_accounts(srcs); log("")

    arts: dict[str, dict] = {}
    for nm in ("add", "relu", "step"):
        st = tp2_static(nm, srcs[nm])
        tr = tp3_translate(nm, st["em"])
        arts[nm] = {"em": st["em"], "ll": tr["ll"]}
        results["TP2"] = results.get("TP2", True) and st["ok"]
        results["TP3"] = results.get("TP3", True) and tr["ok"]
        log("")

    d4 = tp4_add(arts["add"]["ll"], R, C); log("")
    results["TP4"] = d4["ok"]
    results["DISASM"] = disasm_evidence(d4["mod"], "add"); log("")

    results["TP5"] = tp5_relu(arts["relu"]["ll"], R, C); log("")
    results["TP6"] = tp6_step(arts["step"]["ll"]); log("")
    results["TP7"] = tp7_transpose(d4, R, C); log("")
    results["TP8"] = tp8_probes(srcs["add"], R, C); log("")
    if FROZEN_TAG or (R, C) != (2, 2):
        gen = {"add": make_add_ir, "relu": make_relu_ir,
               "gemm": lambda: make_gemm_ir()}
        results["TP9"] = tp9_variant(R, C, gen); log("")

    log("汇总：")
    n_pass = 0
    n_all = 0
    for k in ("TP1", "TP2", "TP3", "TP4", "TP5", "TP6", "TP7", "TP8",
              "TP9", "DISASM"):
        if k not in results:
            continue
        n_all += 1
        ok = results[k]
        n_pass += 1 if ok else 0
        log(f"  {k}: {'PASS' if ok else 'FAIL'}")
    log(f"{n_pass}/{n_all} PASS")

    name = "op-report.txt" if not FROZEN_TAG else f"op-report-{FROZEN_TAG}.txt"
    (OUT / name).write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    log(f"报告已写入 outputs/{name}")
    return 0 if n_pass == n_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
