#!/usr/bin/env python3
"""第 115 天：转换函数与类型——函数级 Conversion 骨架（F1/R1/A1＋类型测试＋真机 ABI 验证）。

真实工具链里，今天对应的是最终 Lowering 管道的第一段实现：
  convert-func-to-llvm 中的"函数签名转换"（含 memref 参数 → 描述符结构体、
  多结果打包、入口块参数换类型），以及 arith.constant → llvm.mlir.constant。
本环境没有 mlir-opt（与 D57~D114 一致），所以用 Python 复刻 DialectConversion 的
角色分工（TypeConverter / ConversionTarget / ConversionPattern / 驱动器），
类型与 DataLayout 的每个数字都交给真 LLVM（llvmlite 内嵌 LLVM 22.1.0）核对，
C ABI 的证据链交给本机 gcc（9.4.0）产出的汇编核对。

三条真实执行路径：
  ① 驱动器：18 个源 op 逐一过海关，partial 模式记账（今天 8/18，残账排期 D116/D117），
     full 模式同一账本整体 FAIL（D117 导出前的门）；
  ② 类型测试：签名兑换表 10 组样例＋两道闸（tensor / 动态 memref 拒收）＋
     DataLayout 数字逐项与真机 TargetData 对账（56B / align 8 / 偏移 0,8,16,24,40）；
  ③ 真机：JIT 出 peek / mul2_out / echo，用 ctypes 按 C ABI 调用，逐点 bitwise 比对；
     gcc 编译 getoff_c(按值) 与 getoff_p(指针)——汇编一字不差，是大聚合"间接传"的证据。

用法：
  python3 func_lowering.py                       # 主运行：TP1~TP9＋探针，写 outputs/
  python3 func_lowering.py --shape 2 3 2 --tag s232  # 对照：换形状重跑（类型文本变化，计数不变）
"""

from __future__ import annotations

import argparse
import ctypes
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from llvmlite import ir as lv_ir
    from llvmlite import binding as lv
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
# 1. DataLayout：教学版布局计算器（与真机 TargetData 对账）
# ---------------------------------------------------------------------------

class TeachingDataLayout:
    """极简数据布局：只回答今天需要的三个问题——标量多大、结构体怎么排、index 多宽。

    真实 LLVM 的 data layout 字符串（如 aarch64 的
    e-m:e-...-i64:64-...）记录端序、指针宽度、各类型大小/对齐；
    真实 MLIR 也有对应的 DataLayout 系统（ModuleOp 可携带 datalayout，
    index 的位宽由目标指针宽度决定）。这里用一张小表＋顺序布局算法复刻。
    """

    SCALAR = {  # 类型: (ABI 大小 B, ABI 对齐 B)
        "f32": (4, 4), "f64": (8, 8), "f16": (2, 2),
        "i1": (1, 1), "i8": (1, 1), "i16": (2, 2), "i32": (4, 4), "i64": (8, 8),
    }

    def __init__(self, pointer_bits: int = 64):
        self.pointer_bits = pointer_bits
        self.SCALAR["ptr"] = (pointer_bits // 8, pointer_bits // 8)
        # index 位宽随目标指针宽度（64 位目标 -> i64）——D114 类型表的同一条规则
        self.index_bits = pointer_bits

    def index_llvm(self) -> str:
        return f"i{self.index_bits}"

    def struct_layout(self, fields: list[tuple[str, int, int]]) -> dict:
        """顺序布局：每个成员对齐到自己的 ABI 对齐值，总大小补齐到最大对齐。

        fields: [(成员名, 成员字节大小, 成员 ABI 对齐)]；
        注意 array<N x i64> 的对齐是元素对齐（8），不是整块大小——初版把整块
        大小当对齐，rank2 算出 64B/align16，被真机 TargetData 咬住（见 TP1 修订记录）。
        返回 {"size", "align", "offsets"}。
        """
        offsets, cur, align = [], 0, 1
        for _, size, f_align in fields:
            align = max(align, f_align)
            cur = (cur + f_align - 1) // f_align * f_align
            offsets.append(cur)
            cur += size
        size = (cur + align - 1) // align * align
        return {"size": size, "align": align, "offsets": offsets}


DL = TeachingDataLayout(pointer_bits=64)


# ---------------------------------------------------------------------------
# 2. 类型兑换表：memref 解析、描述符类型、兑换（含拒收）
# ---------------------------------------------------------------------------

class TypeConversionError(Exception):
    pass


MEMREF_RE = re.compile(
    r"^memref<(?P<shape>[0-9x?]+)x(?P<elem>f32|f64|f16|i32|i64)"
    r"(?:,\s*strided<\[(?P<strides>[0-9,\s?]+)\]>)?>$")
TENSOR_RE = re.compile(r"^tensor<")


def parse_memref(ty: str) -> dict:
    m = MEMREF_RE.match(ty.strip())
    if not m:
        raise TypeConversionError(f"{ty}：无法解析的 memref 类型")
    if "?" in ty:
        raise TypeConversionError(f"{ty}：动态 shape 暂不支持（'暂不支持'第 1 条，D114 清单第四节）")
    shape = [int(x) for x in m.group("shape").split("x")]
    elem = m.group("elem")
    strides_raw = (m.group("strides") or "").split(",")
    strides = [int(s) for s in strides_raw if s.strip() != ""]
    if not strides:  # 未写 strided 的连续 memref：按行主序推导
        strides, acc = [], 1
        for d in reversed(shape):
            strides.insert(0, acc)
            acc *= d
    return {"shape": shape, "elem": elem, "strides": strides, "rank": len(shape)}


def desc_type_text(rank: int) -> str:
    return (f"!llvm.struct<(ptr, ptr, i64, array<{rank} x i64>, array<{rank} x i64>)>")


def desc_layout(rank: int) -> dict:
    """描述符的布局：按成员逐个算（对账用），字段顺序 D114 已定。

    allocated/aligned/offset 各 8B 对齐 8；sizes/strides 是 array<rank x i64>，
    大小 8·rank，对齐仍是元素对齐 8。
    """
    return DL.struct_layout(
        [("allocated", 8, 8), ("aligned", 8, 8), ("offset", 8, 8),
         (f"sizes[{rank}]", 8 * rank, 8), (f"strides[{rank}]", 8 * rank, 8)])


def conv_type(ty: str) -> dict:
    """D114 类型兑换表的执行版：成功返回 {"llvm", "size", "align"}，拒收抛异常。

    与 D114 相比多了一件事：每个兑换结果都带上 DataLayout 算出的字节账。
    """
    ty = ty.strip()
    if ty == "index":
        return {"llvm": DL.index_llvm(), "size": 8, "align": 8}
    if ty in DL.SCALAR and ty != "ptr":
        s, a = DL.SCALAR[ty]
        return {"llvm": ty, "size": s, "align": a}
    if TENSOR_RE.match(ty):
        raise TypeConversionError(
            f"{ty}：tensor 是值语义类型，兑换表里没有目标类型——"
            "必须先经过第一段 Lowering（bufferize，D85~D105）")
    if ty.startswith("memref<"):
        mr = parse_memref(ty)
        lay = desc_layout(mr["rank"])
        return {"llvm": desc_type_text(mr["rank"]), "size": lay["size"],
                "align": lay["align"], "memref": mr, "layout": lay}
    raise TypeConversionError(f"{ty}：未知类型，兑换表拒收")


def pack_results(result_types: list[str]) -> dict:
    """结果打包规则：0 个 -> void；1 个 -> 兑换类型；≥2 个 -> 打包成 LLVM 结构体。

    真实 MLIR 的 FuncToLLVM 对多结果函数同样把结果打包进一个字面结构体
    （packFunctionResults 的行为）；返回大结构体在 C ABI 上走隐式结果指针（见 TP7）。
    """
    convs = [conv_type(t) for t in result_types]
    if not convs:
        return {"llvm": "void", "size": 0, "align": 0, "packed": False}
    if len(convs) == 1:
        c = convs[0]
        return {"llvm": c["llvm"], "size": c["size"], "align": c["align"], "packed": False}
    lay = DL.struct_layout([(c["llvm"], c["size"], c["align"]) for c in convs])
    inner = ", ".join(c["llvm"] for c in convs)
    return {"llvm": f"!llvm.struct<({inner})>", "size": lay["size"],
            "align": lay["align"], "packed": True, "layout": lay}


def convert_signature(args: list[str], results: list[str]) -> dict:
    """F1 的核心：函数签名逐参数兑换＋结果打包；任何一关失败即整条签名失败。"""
    conv_args = [conv_type(a) for a in args]
    ret = pack_results(results)
    return {"args": conv_args, "ret": ret,
            "arg_bytes": sum(c["size"] for c in conv_args)}


def llvm_func_line(name: str, arg_names: list[str], sig: dict) -> str:
    arg_txt = ", ".join(f"%{n}: {c['llvm']}" for n, c in zip(arg_names, sig["args"]))
    ret_txt = "" if sig["ret"]["llvm"] == "void" else f" -> {sig['ret']['llvm']}"
    return f"llvm.func @{name}({arg_txt}){ret_txt}"


# ---------------------------------------------------------------------------
# 3. 源 IR：生成与解析（与 D114 同构，作为 partial 驱动的输入）
# ---------------------------------------------------------------------------

def make_source_ir(M: int, K: int, N: int) -> str:
    return f"""// 第 {M}×{K}×{N} GEMM 的循环形态（第 115 天输入，由本脚本生成）
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

OP_KINDS = [
    (re.compile(r"^func\s+@"), "func.func", "F1", "D115"),
    (re.compile(r"memref\.alloc"), "memref.alloc", "M3", "D116"),
    (re.compile(r"arith\.constant.*:\s*index"), "arith.constant(index)", "A1", "D115"),
    (re.compile(r"arith\.constant"), "arith.constant(f32)", "A1", "D115"),
    (re.compile(r"scf\.for"), "scf.for", "C1", "D117"),
    (re.compile(r"scf\.yield"), "scf.yield", "C1", "D117"),
    (re.compile(r"memref\.load"), "memref.load", "M1", "D116"),
    (re.compile(r"memref\.store"), "memref.store", "M2", "D116"),
    (re.compile(r"arith\.(mulf|addf)"), "arith.mulf/addf", "A3", "D116"),
    (re.compile(r"^return"), "func.return", "R1", "D115"),
    (re.compile(r"mini\."), "mini.*", None, "不做"),
]

IMPLAINED_TODAY = {"F1", "R1", "A1"}  # 今天实现的模式；其余只记账


def census(src: str) -> list[dict]:
    """逐行判定 op 类别、负责模式与排期（驱动器的输入）。"""
    ops = []
    for line in src.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        for rx, kind, pat, sched in OP_KINDS:
            if rx.search(s):
                ops.append({"kind": kind, "pattern": pat, "sched": sched,
                            "line": s, "raw": line})
                break
    return ops


def drive(ops: list[dict], mode: str) -> dict:
    """D114 驱动器的今天版：partial 记账 SUCCESS；full 残留即 FAIL。"""
    converted, residuals = [], []
    for op in ops:
        if op["pattern"] is None:
            residuals.append((op["kind"], "非法方言 mini.*：必须在第一段 Lowering 处理（D85~D105）"))
            continue
        if op["pattern"] not in IMPLAINED_TODAY:
            residuals.append((op["kind"], f"模式 {op['pattern']} 未实现（排期 {op['sched']}）"))
            continue
        converted.append((op["kind"], op["pattern"]))
    ok = (mode == "partial") or not residuals
    return {"mode": mode, "total": len(ops), "converted": converted,
            "residuals": residuals, "ok": ok}


def residual_summary(residuals: list[tuple]) -> list[tuple]:
    agg: dict = {}
    for kind, reason in residuals:
        agg.setdefault((kind, reason), 0)
        agg[(kind, reason)] += 1
    return sorted(agg.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------------------
# 4. 半转换 IR：F1/R1/A1 的发射（含 unrealized_conversion_cast 胶水）
# ---------------------------------------------------------------------------

def split_top(s: str, sep: str = ",") -> list[str]:
    """在括号深度 0 处切分（strided<[6, 1]> 里的逗号不能切）。"""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def emit_partial_ir(src: str) -> tuple[str, int]:
    """把源 IR 变成"签名与常量已转、循环与访存仍是旧方言"的半转换文本。

    三类胶水（真实 MLIR 的 materialization，reconcile-unrealized-casts 在 D117 清理）：
      源物化：新类型入口参数 -> 旧类型（desc -> memref，i64 -> index）
      目标物化：旧类型返回值 -> 新类型（memref -> desc）
    """
    out = ["// 半转换产物（partial 模式）：F1/R1/A1 已转换，其余记入残账（排期 D116/D117）"]
    rename = {}  # 旧值名 -> 胶水产物名（供残留 op 引用）
    casts = 0
    lines = src.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        s = line.strip()
        indent = line[:len(line) - len(line.lstrip())]
        if s.startswith("func @") and not s.endswith("{"):
            while not s.endswith("{"):  # 函数头可能跨两行：先拼成一行
                idx += 1
                s = s + " " + lines[idx].strip()
        idx += 1
        if s.startswith("func @"):
            m = re.match(r"func @(\w+)\((.*)\) -> (.+) \{", s)
            name = m.group(1)
            args = split_top(m.group(2))
            ret = m.group(3).strip()
            arg_names = [a.split(":")[0].strip().lstrip("%") for a in args]
            sig = convert_signature([a.split(":")[1].strip() for a in args], [ret])
            head = llvm_func_line(name, arg_names, sig)
            out.append(f"{head} {{")
            for a, n in zip(args, arg_names):
                old = a.split(":")[1].strip()
                new = conv_type(old)["llvm"]
                out.append(f"{indent}  %{n}_m = builtin.unrealized_conversion_cast %{n} : "
                           f"{new} -> {old}   // 胶水：入口参数已换新类型，残留 op 还要旧值")
                rename[f"%{n}"] = f"%{n}_m"
                casts += 1
            continue
        m = re.match(r"%(?P<res>\w+) = arith\.constant (?P<val>-?[\d.]+) : (?P<ty>\w+)", s)
        if m:
            new_ty = conv_type(m.group("ty"))["llvm"]
            out.append(f"{indent}%{m.group('res')} = llvm.mlir.constant {m.group('val')} : {new_ty}")
            if m.group("ty") != new_ty:  # index -> i64：旧使用者需要胶水
                out.append(f"{indent}%{m.group('res')}_i = builtin.unrealized_conversion_cast "
                           f"%{m.group('res')} : {new_ty} -> {m.group('ty')}   // 胶水：scf.for 还要 index")
                rename[f"%{m.group('res')}"] = f"%{m.group('res')}_i"
                casts += 1
            continue
        if s.startswith("return "):
            m2 = re.match(r"return (%\w+) : (.+)", s)
            val, old_ty = m2.group(1), m2.group(2).strip()
            new_ty = conv_type(old_ty)["llvm"]
            out.append(f"{indent}{val}_d = builtin.unrealized_conversion_cast {val} : "
                       f"{old_ty} -> {new_ty}   // 胶水：llvm.return 要新类型")
            out.append(f"{indent}llvm.return {val}_d : {new_ty}")
            casts += 1
            continue
        s2 = s
        for old, new in rename.items():  # 残留 op 改用胶水产物（%c0 不得误伤 %c0/%acc）
            s2 = re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, s2)
        tag = ""
        for rx, kind, pat, sched in OP_KINDS:
            if rx.search(s2) and pat not in IMPLAINED_TODAY and pat is not None:
                tag = f"   // 残留：{pat} 排期 {sched}"
                break
        out.append(indent + s2 + tag)
    return "\n".join(out) + "\n", casts


# ---------------------------------------------------------------------------
# 5. 真机验证：llvmlite JIT ＋ TargetData ＋ gcc 汇编证据
# ---------------------------------------------------------------------------

_ENGINES: list = []  # MCJIT 引擎必须保活，否则代码内存被回收（实测踩坑，见常见错误 4）


def real_target_data():
    lv.initialize_all_targets()
    lv.initialize_native_target()
    lv.initialize_native_asmprinter()
    triple = lv.get_default_triple()
    tm = lv.Target.from_triple(triple).create_target_machine()
    return triple, tm, tm.target_data


def ll_type_of(llvm_ty: str):
    f = {"f32": lv_ir.FloatType, "f64": lv_ir.DoubleType, "f16": lv_ir.HalfType}
    if llvm_ty in f:
        return f[llvm_ty]()
    if llvm_ty.startswith("i"):
        return lv_ir.IntType(int(llvm_ty[1:]))
    if llvm_ty == "ptr":
        return lv_ir.PointerType(lv_ir.FloatType())
    if llvm_ty.startswith("!llvm.struct<("):
        inner = llvm_ty[len("!llvm.struct<("):-2]
        parts, depth, cur = [], 0, ""
        for ch in inner:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur.strip())
        fields = []
        for p in parts:
            m = re.match(r"array<(\d+) x (.+)>", p)
            if m:
                fields.append(lv_ir.ArrayType(ll_type_of(m.group(2)), int(m.group(1))))
            else:
                fields.append(ll_type_of(p))
        return lv_ir.LiteralStructType(fields)
    raise ValueError(f"ll_type_of: 不认识 {llvm_ty}")


PEEK_LL = """; 第 115 天真机 ABI 验证（LLVM 22.1.0，aarch64）
; 描述符经 ptr 传递：aarch64 C ABI 上 >16B 聚合按"间接"传（x0 = 调用方副本地址，
; gcc 实测 getoff_c(按值) 与 getoff_p(指针) 汇编一字不差，见 abi-ground-truth.s）。
target triple = "{triple}"
%desc = type {{ ptr, ptr, i64, [2 x i64], [2 x i64] }}

define float @peek(ptr %d, i64 %i, i64 %j) {{
entry:
  %alp = getelementptr %desc, ptr %d, i32 0, i32 1
  %al  = load ptr, ptr %alp
  %ofp = getelementptr %desc, ptr %d, i32 0, i32 2
  %of  = load i64, ptr %ofp
  %s0p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 0
  %s0  = load i64, ptr %s0p
  %s1p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 1
  %s1  = load i64, ptr %s1p
  %t0  = mul i64 %i, %s0
  %t1  = mul i64 %j, %s1
  %tt  = add i64 %t0, %t1
  %ix  = add i64 %tt, %of
  %p   = getelementptr float, ptr %al, i64 %ix
  %v   = load float, ptr %p
  ret float %v
}}

define float @mul2_out(ptr %d, i64 %i, i64 %j, ptr %out) {{
entry:
  %alp = getelementptr %desc, ptr %d, i32 0, i32 1
  %al  = load ptr, ptr %alp
  %ofp = getelementptr %desc, ptr %d, i32 0, i32 2
  %of  = load i64, ptr %ofp
  %s0p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 0
  %s0  = load i64, ptr %s0p
  %s1p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 1
  %s1  = load i64, ptr %s1p
  %t0  = mul i64 %i, %s0
  %t1  = mul i64 %j, %s1
  %tt  = add i64 %t0, %t1
  %ix  = add i64 %tt, %of
  %p   = getelementptr float, ptr %al, i64 %ix
  %v   = load float, ptr %p
  %w   = fmul float %v, 2.0
  store float %w, ptr %out
  ret float %v
}}

define i64 @echo(ptr %p) {{
entry:
  %r = ptrtoint ptr %p to i64
  ret i64 %r
}}

; --- ABI 误用对照（TP8）：三种签名形态，同一个字段读取 ---
define i64 @getoff(ptr %d) {{
entry:
  %fp = getelementptr %desc, ptr %d, i32 0, i32 2
  %o  = load i64, ptr %fp
  ret i64 %o
}}

define i64 @getoff_byval(ptr byval(%desc) %d) {{
entry:
  %s = load %desc, ptr %d
  %o = extractvalue %desc %s, 2
  ret i64 %o
}}

define i64 @getoff_agg({{ ptr, ptr, i64, [2 x i64], [2 x i64] }} %d) {{
entry:
  %o = extractvalue {{ ptr, ptr, i64, [2 x i64], [2 x i64] }} %d, 2
  ret i64 %o
}}
"""


class Desc(ctypes.Structure):
    _fields_ = [("allocated", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                ("offset", ctypes.c_int64), ("sizes", ctypes.c_int64 * 2),
                ("strides", ctypes.c_int64 * 2)]


def jit_module(ll_text: str):
    mod = lv.parse_assembly(ll_text)
    mod.verify()
    triple = lv.get_default_triple()
    tm = lv.Target.from_triple(triple).create_target_machine()
    eng = lv.create_mcjit_compiler(mod, tm)
    eng.finalize_object()
    _ENGINES.append(eng)
    return eng


GCC_SRC = """/* 第 115 天：C ABI 证据链（gcc -O2 -S 的输入） */
struct desc { void *allocated; void *aligned; long offset; long sizes[2]; long strides[2]; };
long getoff_c(struct desc d) { return d.offset; }      /* 56B 按值传 */
long getoff_p(struct desc *d) { return d->offset; }    /* 指针传 */
struct desc make_desc(void) { struct desc d = {0,0,7,{1,2},{3,4}}; return d; }
int main(void) { return sizeof(struct desc); }         /* 退出码 = 56 */
"""


def gcc_ground_truth() -> dict | None:
    """用本机 gcc 产出三个 ABI 证据：汇编体一致性、x8 返回、sizeof。"""
    gcc = shutil.which("gcc")
    if gcc is None:
        return None
    with tempfile.TemporaryDirectory() as td:
        c_path = Path(td) / "abi.c"
        s_path = Path(td) / "abi.s"
        c_path.write_text(GCC_SRC, encoding="utf-8")
        subprocess.run([gcc, "-O2", "-S", str(c_path), "-o", str(s_path)],
                       check=True, capture_output=True)
        asm = s_path.read_text(encoding="utf-8")

        def body(fn: str) -> list[str]:
            lines, on = [], False
            for ln in asm.splitlines():
                t = ln.strip()
                if t.startswith(f"{fn}:"):
                    on = True
                    continue
                if on:
                    if t.startswith(".") or t == "":
                        if t.startswith(".size"):
                            break
                        continue
                    lines.append(t)
            return lines

        same = body("getoff_c") == body("getoff_p")
        make = body("make_desc")
        x8 = any("[x8]" in t for t in make)
        bin_path = Path(td) / "abi.bin"
        subprocess.run([gcc, "-O2", str(c_path), "-o", str(bin_path)],
                       check=True, capture_output=True)
        r = subprocess.run([str(bin_path)], capture_output=True)
        sizeof = r.returncode
    (OUT / "abi-ground-truth.s").write_text(
        f"; gcc -O2 -S 编译产物（第 115 天，真实输出）\n; 输入源码见 func_lowering.py 的 GCC_SRC\n\n" + asm,
        encoding="utf-8")
    return {"asm_equal": same, "getoff_c": body("getoff_c"),
            "make_desc": make, "x8_return": x8, "sizeof": sizeof}


# ---------------------------------------------------------------------------
# 6. 测试
# ---------------------------------------------------------------------------

def tp1_layout_vs_real(td) -> bool:
    log("[TP1] DataLayout 对账：教学计算 vs 真机 LLVM TargetData")
    ok = True
    for ty, (sz, al) in [("f32", (4, 4)), ("f64", (8, 8)), ("i32", (4, 4)),
                         ("i64", (8, 8)), ("i1", (1, 1))]:
        t = ll_type_of(ty)
        rsz, ral = t.get_abi_size(td), t.get_abi_alignment(td)
        good = (sz, al) == (int(rsz), int(ral))
        ok &= good
        log(f"      {ty:>4}: 教学 {sz}/{al} B  真机 {int(rsz)}/{int(ral)} B  {'OK' if good else 'MISMATCH'}")
    log(f"      index -> {DL.index_llvm()}（位宽随目标指针宽度 {DL.pointer_bits} 位）")
    ptr = lv_ir.PointerType(lv_ir.FloatType())
    log(f"      ptr  : 教学 {8}/{8} B  真机 {int(ptr.get_abi_size(td))}/{int(ptr.get_abi_alignment(td))} B")
    for rank, exp in [(1, 40), (2, 56), (3, 72)]:
        lay = desc_layout(rank)
        t = ll_type_of(desc_type_text(rank))
        rsz = int(t.get_abi_size(td))
        offs = [int(t.get_element_offset(td, i)) for i in range(5)]
        good = lay["size"] == rsz == exp and offs == lay["offsets"]
        ok &= good
        log(f"      rank{rank} 描述符: 教学 {lay['size']}B/align{lay['align']} "
            f"offsets{lay['offsets']}  真机 {rsz}B offsets{offs}  {'OK' if good else 'MISMATCH'}")
    log(f"      结论：{'全部一致' if ok else '存在不一致'}——56B/align8/偏移 0,8,16,24,40 不是背出来的，是 LLVM 算出来的")
    return ok


SIG_CASES = [
    ("S1 GEMM", ["memref<4x6xf32, strided<[6, 1]>>", "memref<6x3xf32, strided<[3, 1]>>"],
     ["memref<4x3xf32, strided<[3, 1]>>"]),
    ("S2 Relu", ["f32"], ["f32"]),
    ("S3 Add", ["f32", "f32"], ["f32"]),
    ("S4 init", [], []),
    ("S5 scale", ["index", "index"], ["f32"]),
    ("S6 rank1 点积", ["memref<5xf32, strided<[1]>>"], ["f32"]),
    ("S7 rank3 求和", ["memref<2x3x4xf32, strided<[12, 4, 1]>>"], ["f32"]),
    ("S8 双结果", ["memref<4x3xf32, strided<[3, 1]>>", "f32"], ["f32", "f32"]),
    ("S9 双 memref 结果", ["memref<2x2xf32, strided<[2, 1]>>"],
     ["memref<2x2xf32, strided<[2, 1]>>", "memref<2x2xf32, strided<[2, 1]>>"]),
    ("S10 混合标量", ["f64", "i32", "f32"], ["i32"]),
]


def tp2_signature_table(td) -> bool:
    log("[TP2] 签名转换表（类型测试主体）：10 组样例")
    ok = True
    lines = ["# 第 115 天：签名转换表（机器生成）", "",
             "| # | 源签名 | 目标 llvm.func 签名 | 参数字节 | 结果字节 |",
             "|---|---|---|---|---|"]
    for i, (name, args, results) in enumerate(SIG_CASES, 1):
        sig = convert_signature(args, results)
        src_sig = "(" + ", ".join(args) + ") -> (" + ", ".join(results) + ")"
        tgt = llvm_func_line(name.split()[0].lower() + "_fn",
                             [f"a{k}" for k in range(len(args))], sig)
        lines.append(f"| {name} | `{src_sig}` | `{tgt}` | {sig['arg_bytes']} | {sig['ret']['size']} |")
        log(f"      {name}: 参数 {sig['arg_bytes']}B，结果 {sig['ret']['size']}B"
            f"{'（打包 struct）' if sig['ret']['packed'] else ''}")
    # 真机抽查三个：S1 参数各 56B；S8 struct<(f32,f32)>=8B/align4；S9 struct<(desc,desc)>=112B
    s8 = pack_results(["f32", "f32"])
    t8 = ll_type_of(s8["llvm"])
    s9 = pack_results(["memref<2x2xf32, strided<[2, 1]>>", "memref<2x2xf32, strided<[2, 1]>>"])
    t9 = ll_type_of(s9["llvm"])
    checks = [
        ("S8 struct<(f32,f32)>", s8["size"], int(t8.get_abi_size(td)), int(t8.get_abi_alignment(td)), s8["align"]),
        ("S9 struct<(desc,desc)>", s9["size"], int(t9.get_abi_size(td)), int(t9.get_abi_alignment(td)), s9["align"]),
    ]
    for name, mine, rsize, ralign, malign in checks:
        good = mine == rsize and malign == ralign
        ok &= good
        log(f"      {name}: 教学 {mine}B/align{malign}  真机 {rsize}B/align{ralign}  {'OK' if good else 'MISMATCH'}")
    lines += ["", "打包规则：0 结果 -> void；1 结果 -> 兑换类型；≥2 结果 -> !llvm.struct<(...)>（真实 MLIR FuncToLLVM 同样打包多结果）。",
              "字节账来自 DataLayout（TP1 与真机 LLVM 对账）。"]
    (OUT / "signature-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok


def tp3_gates() -> bool:
    log("[TP3] 两道闸（D114 对照实验 B 的执行版）")
    ok = True
    cases = [
        ("tensor 参数", ["tensor<4x6xf32>"], ["f32"], "tensor"),
        ("动态 memref 参数", ["memref<?x?xf32>"], ["f32"], "动态 shape"),
        ("未知标量 bf16", ["bf16"], ["f32"], "未知类型"),
    ]
    for name, args, results, needle in cases:
        try:
            convert_signature(args, results)
            log(f"      {name}: 未拒收（FAIL）")
            ok = False
        except TypeConversionError as e:
            good = needle in str(e)
            ok &= good
            log(f"      {name}: 拒收 OK —— {e}"[:110])
    # 方言闸：mini op 在残账里必须出现且不带排期
    src = make_source_ir(4, 6, 3).replace("  %zero = arith.constant 0.0 : f32\n",
                                           "  %zero = mini.relu(%x) : f32\n")
    ops = census(src)
    res = drive(ops, "partial")["residuals"]
    mini_hits = [r for r in res if "mini" in r[1]]
    log(f"      mini.* 方言闸：残账命中 {len(mini_hits)} 条非法方言（无排期、'不做'）")
    ok &= len(mini_hits) >= 1
    return ok


def tp4_partial_drive(src: str) -> dict:
    ops = census(src)
    par = drive(ops, "partial")
    ful = drive(ops, "full")
    log(f"[TP4] partial 驱动：{len(par['converted'])}/{par['total']} 转换，"
        f"残账 {len(par['residuals'])} 条，结论 {'SUCCESS' if par['ok'] else 'FAIL'}")
    for (kind, reason), n in residual_summary(par["residuals"]):
        log(f"      残账：{kind} ×{n} —— {reason}")
    log(f"      full 驱动：同配置残账 {len(ful['residuals'])} 条 -> "
        f"{'FAIL（整批退回，D117 导出前的门）' if not ful['ok'] else 'SUCCESS'}")
    return {"partial": par, "full": ful, "ops": ops}


def tp5_glue(src: str) -> bool:
    ir, casts = emit_partial_ir(src)
    name = "partial-ir.mlir" if not FROZEN_TAG else f"partial-ir-{FROZEN_TAG}.mlir"
    (OUT / name).write_text(ir, encoding="utf-8")
    desc2 = desc_type_text(2)
    c_ty = re.search(r"return %\w+ : (memref<.+>)", src).group(1)  # C 的类型随 --shape 变
    expect = {"desc->memref": ir.count(f"{desc2} -> memref"),
              "i64->index": ir.count(": i64 -> index"),
              "memref->desc": ir.count(f"{c_ty} -> {desc2}")}
    total = sum(expect.values())
    log(f"[TP5] 胶水账：partial-ir.mlir 共 {casts} 条 unrealized_conversion_cast")
    for k, v in expect.items():
        log(f"      {k}: {v} 条")
    op_lines = [ln for ln in ir.splitlines()
                if re.search(r"llvm\.func @| = llvm\.mlir\.constant |llvm\.return ",
                             ln.split("//")[0])]
    log(f"      产出中 llvm.* op：{len(op_lines)} 行（llvm.func 1 + llvm.mlir.constant 6 + llvm.return 1）")
    return total == casts == 8 and len(op_lines) == 8


def tp6_real_abi(triple: str) -> dict:
    log("[TP6] 真机 ABI（正确路径：描述符经 ptr 传递，C ABI 间接传副本的等价形式）")
    ll_text = PEEK_LL.format(triple=triple)
    (OUT / "abi-verify.ll").write_text(ll_text, encoding="utf-8")
    eng = jit_module(ll_text)
    peek = ctypes.CFUNCTYPE(ctypes.c_float, ctypes.POINTER(Desc),
                            ctypes.c_int64, ctypes.c_int64)(eng.get_function_address("peek"))
    mul2 = ctypes.CFUNCTYPE(ctypes.c_float, ctypes.POINTER(Desc), ctypes.c_int64,
                            ctypes.c_int64, ctypes.POINTER(ctypes.c_float))(eng.get_function_address("mul2_out"))
    echo = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_void_p)(eng.get_function_address("echo"))

    A = np.arange(24, dtype=np.float32).reshape(4, 6)
    da = Desc(A.ctypes.data_as(ctypes.c_void_p).value, A.ctypes.data_as(ctypes.c_void_p).value,
              0, (ctypes.c_int64 * 2)(4, 6), (ctypes.c_int64 * 2)(6, 1))
    n_ok = sum(peek(ctypes.byref(da), i, j) == A[i, j] for i in range(4) for j in range(6))
    log(f"      peek 连续布局 4×6（strides [6,1]）：{n_ok}/24 点 bitwise 一致")

    Bv = np.arange(12, dtype=np.float32).reshape(3, 4).T  # 4×3 视图，strides (1,4) 元素
    est = tuple(s // Bv.itemsize for s in Bv.strides)  # numpy .strides 是字节，要换算成元素步长
    db = Desc(Bv.ctypes.data_as(ctypes.c_void_p).value, Bv.ctypes.data_as(ctypes.c_void_p).value,
              0, (ctypes.c_int64 * 2)(4, 3), (ctypes.c_int64 * 2)(*est))
    n_ok2 = sum(peek(ctypes.byref(db), i, j) == Bv[i, j] for i in range(4) for j in range(3))
    log(f"      peek 转置视图 4×3（元素 strides {est}；numpy .strides={Bv.strides} 是字节）："
        f"{n_ok2}/12 点 bitwise 一致")

    out = np.zeros(1, dtype=np.float32)
    r = mul2(ctypes.byref(da), 3, 5, out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
    mul_ok = r == A[3, 5] and out[0] == A[3, 5] * 2
    log(f"      mul2_out（sret 式双出口）：ret={r}（{A[3, 5]}） out={out[0]}（{A[3, 5] * 2.0:.1f}） "
        f"{'bitwise OK' if mul_ok else 'MISMATCH'}")

    addr = A.ctypes.data_as(ctypes.c_void_p).value
    echo_ok = echo(addr) == addr
    log(f"      echo：x0 直通指针（回传 {hex(echo(addr))} == 传入 {hex(addr)}）{'OK' if echo_ok else 'MISMATCH'}")
    return {"peek_contig": n_ok, "peek_transposed": n_ok2, "mul2": mul_ok,
            "echo": echo_ok, "ok": n_ok == 24 and n_ok2 == 12 and mul_ok and echo_ok}


def tp7_gcc() -> bool:
    log("[TP7] C ABI 证据链（本机 gcc -O2 -S）")
    gt = gcc_ground_truth()
    if gt is None:
        log("      gcc 不可用，跳过（非本机情况）")
        return False
    log(f"      getoff_c（56B 按值）汇编体：{' ; '.join(gt['getoff_c'])}")
    log(f"      getoff_p（指针）与按值版{'一致' if gt['asm_equal'] else '不一致'}"
        f"——>16B 聚合在 C ABI 上按'间接'传（x0=调用方副本地址）")
    log(f"      make_desc（返回 56B struct）：{' ; '.join(gt['make_desc'])}")
    log(f"      返回值经 x8 隐式结果指针（sret）：{'OK' if gt['x8_return'] else '未观察到'}")
    log(f"      sizeof(struct desc)：程序退出码 {gt['sizeof']}（期望 56）"
        f"{'OK' if gt['sizeof'] == 56 else 'MISMATCH'}")
    return gt["asm_equal"] and gt["x8_return"] and gt["sizeof"] == 56


def tp8_probes(triple: str) -> dict:
    log("[TP8] ABI 误用探针：三种签名形态＋两个填表 bug（真机实测）")
    eng = jit_module(PEEK_LL.format(triple=triple))
    getoff = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.POINTER(Desc))(eng.get_function_address("getoff"))
    getoff_byval = ctypes.CFUNCTYPE(ctypes.c_int64, Desc)(eng.get_function_address("getoff_byval"))
    getoff_agg = ctypes.CFUNCTYPE(ctypes.c_int64, Desc)(eng.get_function_address("getoff_agg"))
    peek = ctypes.CFUNCTYPE(ctypes.c_float, ctypes.POINTER(Desc), ctypes.c_int64,
                            ctypes.c_int64)(eng.get_function_address("peek"))

    d = Desc(None, None, 42, (ctypes.c_int64 * 2)(1, 2), (ctypes.c_int64 * 2)(3, 4))
    v_ptr = getoff(ctypes.byref(d))
    v_byval = getoff_byval(d)
    v_agg = getoff_agg(d)
    log(f"      同一个 offset=42：ptr 形态读到 {v_ptr}；byval 形态读到 {v_byval}；"
        f"直接聚合形态读到 {v_agg}")
    log(f"      ——byval（LLVM 22/aarch64 上 callee 从参数栈区读）与直接聚合（LLVM 自行拆传）"
        f"都不等于 C ABI 的'间接传'；错位值随环境变化，但'错'是确定的")

    # P1：strides 填反（strided<[6,1]>写成[1,6]）——D114 探针 P1 的 ABI 版，确定性错值
    A_big = np.arange(48, dtype=np.float32).reshape(8, 6)
    A = A_big[:4]
    dp1 = Desc(A_big.ctypes.data_as(ctypes.c_void_p).value,
               A_big.ctypes.data_as(ctypes.c_void_p).value,
               0, (ctypes.c_int64 * 2)(4, 6), (ctypes.c_int64 * 2)(1, 6))  # 反了！
    diffs = [abs(peek(ctypes.byref(dp1), i, j) - A[i, j]) for i in range(4) for j in range(6)]
    p1 = max(diffs)
    n1 = sum(1 for d in diffs if d > 0)  # i==j 的 3 个对角点恰好读对，是巧合不是正确
    # P2：offset 填错（8 而不是 0）——整体错位 8 个元素
    dp2 = Desc(A_big.ctypes.data_as(ctypes.c_void_p).value,
               A_big.ctypes.data_as(ctypes.c_void_p).value,
               8, (ctypes.c_int64 * 2)(4, 6), (ctypes.c_int64 * 2)(6, 1))
    diffs2 = [abs(peek(ctypes.byref(dp2), i, j) - A[i, j]) for i in range(4) for j in range(6)]
    p2 = max(diffs2)
    n2 = sum(1 for d in diffs2 if d > 0)
    log(f"      P1 strides 填反（[6,1]写成[1,6]）：{n1}/24 点错，max|diff| = {p1:g}"
        f"（对角线 3 点碰巧读对——巧合不等于正确）")
    log(f"      P2 offset 错填 8：{n2}/24 点错，max|diff| = {p2:g}（确定性）")
    return {"ptr": v_ptr, "byval": v_byval, "agg": v_agg, "p1": p1, "p2": p2}


def tp9_variant(M: int, K: int, N: int, td) -> bool:
    log(f"[TP9] 对照：换形状 {M}×{K}×{N}（--shape {M} {K} {N}）")
    src = make_source_ir(M, K, N)
    ops = census(src)
    par = drive(ops, "partial")
    conv = convert_signature(
        [f"memref<{M}x{K}xf32, strided<[{K}, 1]>>", f"memref<{K}x{N}xf32, strided<[{N}, 1]>>"],
        [f"memref<{M}x{N}xf32, strided<[{N}, 1]>>"])
    log(f"      计数不变：{len(par['converted'])}/{par['total']} 转换、"
        f"残账 {len(par['residuals'])} 条（与形状无关）")
    log(f"      类型文本随形状变化：A strides [{K},1]，C 是 {M}×{N}，"
        f"参数 {conv['arg_bytes']}B（两个 rank2 描述符仍是 2×{desc_layout(2)['size']}B）")
    return len(par["converted"]) == 8 and conv["arg_bytes"] == 112


# ---------------------------------------------------------------------------
# 7. 主流程
# ---------------------------------------------------------------------------

def main() -> int:
    global FROZEN_TAG
    ap = argparse.ArgumentParser()
    ap.add_argument("--shape", type=int, nargs=3, default=[4, 6, 3], metavar=("M", "K", "N"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--emit-src", action="store_true",
                    help="仅打印源 IR 文本后退出（用于生成/校验 loop_ir.mlir）")
    args = ap.parse_args()
    M, K, N = args.shape
    FROZEN_TAG = args.tag
    if args.emit_src:
        sys.stdout.write(make_source_ir(M, K, N))
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"第 115 天：转换函数与类型——真机报告（{stamp}）")
    import llvmlite
    env = (f"Python {sys.version.split()[0]} / numpy {np.__version__} / "
           f"llvmlite {llvmlite.__version__}（LLVM {'.'.join(map(str, lv.llvm_version_info))}）")
    if HAVE_LLVMLITE:
        env += f" / triple {lv.get_default_triple()}"
    gcc_v = shutil.which("gcc")
    if gcc_v:
        r = subprocess.run([gcc_v, "--version"], capture_output=True, text=True)
        env += f" / gcc {r.stdout.splitlines()[0].split()[-1]}"
    log(f"环境：{env}")
    src = make_source_ir(M, K, N)
    log(f"输入：GEMM {M}×{K}×{N} 的循环 IR（{len(census(src))} op）")
    log("")

    triple, _tm, td = real_target_data()
    results = {}
    results["TP1"] = tp1_layout_vs_real(td); log("")
    results["TP2"] = tp2_signature_table(td); log("")
    results["TP3"] = tp3_gates(); log("")
    d4 = tp4_partial_drive(src); log("")
    results["TP4"] = d4["partial"]["ok"] and not d4["full"]["ok"]
    results["TP5"] = tp5_glue(src); log("")
    d6 = tp6_real_abi(triple); log("")
    results["TP6"] = d6["ok"]
    results["TP7"] = tp7_gcc(); log("")
    d8 = tp8_probes(triple); log("")
    results["TP8"] = d8["ptr"] == 42 and d8["byval"] != 42 and d8["agg"] != 42 \
        and d8["p1"] > 0 and d8["p2"] > 0
    if FROZEN_TAG:
        results["TP9"] = tp9_variant(M, K, N, td); log("")

    log("汇总：")
    for k, v in results.items():
        log(f"  {k}: {'PASS' if v else 'FAIL'}")
    n_pass = sum(1 for v in results.values() if v)
    log(f"{n_pass}/{len(results)} PASS")

    report_name = "func-report.txt" if not FROZEN_TAG else f"func-report-{FROZEN_TAG}.txt"
    (OUT / report_name).write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    log(f"报告已写入 outputs/{report_name}")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
