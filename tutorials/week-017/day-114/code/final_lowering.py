#!/usr/bin/env python3
"""第 114 天：设计最终 Lowering 路径——类型表、合法性清单与两种驱动（教学仿真）。

真实工具链里，最终 Lowering 是一串 Pass（真实名称与顺序）：
  mlir-opt --convert-scf-to-cf --convert-arith-to-llvm --convert-memref-to-llvm \
           --convert-cf-to-llvm --convert-func-to-llvm --reconcile-unrealized-casts
本环境没有 mlir-opt（与 D57~D113 一致），所以用 Python 复刻 DialectConversion 的
角色分工：TypeConverter（类型兑换表）、ConversionTarget（终态合法性）、
ConversionPattern（翻译手册）、驱动器（full / partial 两种执法模式）。

但"设计"必须可执行、可验证，所以今天有三条真实执行路径：
  ① 驱动器：18 个源 op 逐一过海关，full/partial 两种模式各跑一遍（含对照实验）；
  ② 解释器：把设计出的目标形态（TIR）用 numpy 逐 op 解释，与逐项参考比对；
  ③ 真机：把同一份设计翻译成 LLVM IR 文本，交给 llvmlite（LLVM 22.1.0）
     parse → verify → MCJIT 编译 → ctypes 调用，与参考逐位（bitwise）比对。

用法：
  python3 final_lowering.py                     # 主运行：全部检查＋探针＋对照实验 A/B
  python3 final_lowering.py --shape 2 3 2 --tag s233   # 对照实验 C：换形状
  python3 final_lowering.py --emit-src           # 仅生成 loop_ir.mlir 后退出
"""

from __future__ import annotations

import argparse
import ctypes
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parent
OUT = CODE / "outputs"

# ---------------------------------------------------------------------------
# 1. 源 IR：生成与解析（教学版解析器，只认本日需要的语法）
# ---------------------------------------------------------------------------

def make_source_ir(M: int, K: int, N: int) -> str:
    """按 (M,K,N) 生成 GEMM 的循环 IR 文本（与 D85 ir-loop.txt 同构）。"""
    return f"""// 第 {M}×{K}×{N} GEMM 的循环形态（第 114 天输入，由本脚本生成）
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


FUNC_RE = re.compile(
    r"^func\s+@([\w.$-]+)\s*\((?P<args>[^)]*)\)\s*->\s*(?P<ret>.+?)\s*\{\s*$")
ARG_RE = re.compile(r"^\s*(%\S+)\s*:\s*(.+?)\s*$")
CONST_RE = re.compile(
    r"^%(?P<res>\S+)\s*=\s*arith\.constant\s+(?P<val>-?[\d.]+)\s*:\s*(?P<ty>\w+)\s*$")
ALLOC_RE = re.compile(
    r"^%(?P<res>\S+)\s*=\s*memref\.alloc\(\)\s*:\s*(?P<ty>memref<.+>)\s*$")
FOR_RE = re.compile(
    r"^(?:%(?P<res>\S+)\s*=\s*)?scf\.for\s+%(?P<iv>\S+)\s*=\s*%(?P<lb>\S+)\s+to\s+%(?P<ub>\S+)"
    r"\s+step\s+%(?P<st>\S+)(?P<iter>.*)$")
ITER_RE = re.compile(
    r"iter_args\((?P<name>\S+)\s*=\s*(?P<init>\S+)\)\s*->\s*\((?P<ty>\w+)\)")
LOAD_RE = re.compile(
    r"^%(?P<res>\S+)\s*=\s*memref\.load\s+%(?P<mem>\S+)\[(?P<idx>[^\]]*)\]"
    r"\s*:\s*(?P<ty>memref<.+>)\s*$")
STORE_RE = re.compile(
    r"^memref\.store\s+%(?P<val>\S+)\s*,\s*%(?P<mem>\S+)\[(?P<idx>[^\]]*)\]"
    r"\s*:\s*(?P<ty>memref<.+>)\s*$")
BINOP_RE = re.compile(
    r"^%(?P<res>\S+)\s*=\s*arith\.(?P<op>mulf|addf|muli|addi)\s+"
    r"%(?P<a>\S+)\s*,\s*%(?P<b>\S+)\s*:\s*(?P<ty>\w+)\s*$")
YIELD_RE = re.compile(r"^scf\.yield(?:\s+%(?P<v>\S+)\s*:\s*(?P<ty>\w+))?\s*$")
RETURN_RE = re.compile(
    r"^return(?:\s+%(?P<v>\S+)\s*:\s*(?P<ty>.+?))?\s*$")
GENERIC_RE = re.compile(
    r"^%(?P<res>\S+)\s*=\s*(?P<op>[\w.]+)\((?P<args>[^)]*)\)\s*"
    r":\s*\((?P<aty>[^)]*)\)\s*->\s*(?P<rty>.+?)\s*$")
CLOSE_RE = re.compile(r"^\}\s*$")


class Op:
    def __init__(self, kind: str, **kw):
        self.kind = kind          # func/alloc/const/for/yield/load/store/binop/return/generic
        self.__dict__.update(kw)

    @property
    def name(self) -> str:
        """操作名（方言.操作），用于合法性判定与清单行。"""
        base = {"func": "func.func", "alloc": "memref.alloc", "const": "arith.constant",
                "for": "scf.for", "yield": "scf.yield", "load": "memref.load",
                "store": "memref.store", "return": "func.return"}
        if self.kind in base:
            return base[self.kind]
        if self.kind == "binop":
            return "arith.op"
        if self.kind == "generic":
            return self.op
        return self.kind

    def brief(self) -> str:
        if self.kind == "func":
            return f"func.func @{self.func_name}（{len(self.args)} 参数）"
        if self.kind == "for":
            it = f"，iter_args({self.iter_name} = {self.iter_init})" if self.iter_name else ""
            return f"scf.for {self.iv}（体内 {len(self.body)} op{it}）"
        if self.kind == "load":
            return f"memref.load {self.mem}[{', '.join(self.idx)}]"
        if self.kind == "store":
            return f"memref.store {self.val}, {self.mem}[{', '.join(self.idx)}]"
        if self.kind == "const":
            return f"arith.constant {self.val} : {self.ty}"
        if self.kind == "binop":
            return f"arith.{self.op} : {self.ty}"
        if self.kind == "yield":
            return f"scf.yield {self.val}" if self.val else "scf.yield"
        if self.kind == "return":
            return f"func.return {self.val}" if self.val else "func.return"
        if self.kind == "alloc":
            return "memref.alloc()"
        return getattr(self, "op", "?")

    def types(self) -> list[str]:
        """这个 op 牵涉的全部类型（驱动器用它做类型转换试探）。"""
        if self.kind == "func":
            return [t for _, t in self.args] + [self.ret]
        if self.kind in ("alloc",):
            return [self.ty]
        if self.kind == "const":
            return [self.ty]
        if self.kind == "binop":
            return [self.ty]
        if self.kind in ("load", "store"):
            return [self.ty]
        if self.kind == "return":
            return [self.ty] if self.ty else []
        if self.kind == "for":
            return [self.iter_ty] if self.iter_ty else []
        if self.kind == "yield":
            return [self.ty] if self.ty else []
        if self.kind == "generic":
            return [t.strip() for t in self.aty.split(",")] + [self.rty]
        return []


def split_top(s: str, sep: str = ",") -> list[str]:
    """按顶层分隔符切分（忽略 <> / () 内部的分隔符）。"""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return [x for x in out if x.strip()]


def parse_source(text: str) -> Op:
    """把源 IR 文本解析成一棵 op 树（根是 func）。只认本日语法。"""
    lines = [ln for ln in text.splitlines()
             if ln.strip() and not ln.strip().startswith("//")]
    # 函数签名可能跨多行：把直到首个以 "{" 结尾的行合并
    if not lines[0].rstrip().endswith("{"):
        for i in range(1, len(lines)):
            if lines[i].rstrip().endswith("{"):
                lines[0] = " ".join(ln.strip() for ln in lines[:i + 1])
                lines = [lines[0]] + lines[i + 1:]
                break
    pos = 0

    def parse_block(lines, pos):
        body, m_close = [], None
        while pos < len(lines):
            ln = lines[pos].strip()
            if ln.endswith("{"):
                ln = ln[:-1].rstrip()
            if CLOSE_RE.match(ln):
                m_close = True
                pos += 1
                break
            m = FOR_RE.match(ln)
            if m:
                iter_part = m.group("iter")
                if not iter_part.strip() and pos + 1 < len(lines) \
                        and lines[pos + 1].strip().startswith("iter_args"):
                    iter_part = lines[pos + 1].strip().rstrip("{").rstrip()
                    pos += 1
                it = ITER_RE.search(iter_part)
                if iter_part.strip() and not it:
                    raise ValueError(f"无法解析的 scf.for 附加段：{ln}")
                body.append(Op("for",
                               res="%"+m.group("res") if m.group("res") else None,
                               iv="%"+m.group("iv"), lb="%"+m.group("lb"),
                               ub="%"+m.group("ub"), st="%"+m.group("st"),
                               iter_name=it.group("name") if it else None,
                               iter_init=it.group("init") if it else None,
                               iter_ty=it.group("ty") if it else None, body=[]))
                pos += 1
                inner, pos, ok = parse_block(lines, pos)
                if not ok:
                    raise ValueError("scf.for 未闭合")
                body[-1].body = inner
                continue
            m = CONST_RE.match(ln)
            if m:
                body.append(Op("const", res="%"+m.group("res"), val=m.group("val"),
                               ty=m.group("ty")))
                pos += 1
                continue
            m = ALLOC_RE.match(ln)
            if m:
                body.append(Op("alloc", res="%"+m.group("res"), ty=m.group("ty")))
                pos += 1
                continue
            m = LOAD_RE.match(ln)
            if m:
                idx = [x.strip() for x in m.group("idx").split(",")]
                body.append(Op("load", res="%"+m.group("res"), mem="%"+m.group("mem"),
                               idx=idx, ty=m.group("ty")))
                pos += 1
                continue
            m = STORE_RE.match(ln)
            if m:
                idx = [x.strip() for x in m.group("idx").split(",")]
                body.append(Op("store", val="%"+m.group("val"), mem="%"+m.group("mem"),
                               idx=idx, ty=m.group("ty")))
                pos += 1
                continue
            m = BINOP_RE.match(ln)
            if m:
                body.append(Op("binop", res="%"+m.group("res"), op=m.group("op"),
                                a="%"+m.group("a"), b="%"+m.group("b"), ty=m.group("ty")))
                pos += 1
                continue
            m = YIELD_RE.match(ln)
            if m:
                body.append(Op("yield", val="%"+m.group("v") if m.group("v") else None,
                               ty=m.group("ty")))
                pos += 1
                continue
            m = RETURN_RE.match(ln)
            if m:
                body.append(Op("return", val="%"+m.group("v") if m.group("v") else None,
                               ty=m.group("ty")))
                pos += 1
                continue
            m = GENERIC_RE.match(ln)
            if m:
                body.append(Op("generic", res="%"+m.group("res"), op=m.group("op"),
                               args=[x.strip() for x in m.group("args").split(",")],
                               aty=m.group("aty"), rty=m.group("rty")))
                pos += 1
                continue
            raise ValueError(f"无法解析的行：{ln}")
        return body, pos, m_close

    m = FUNC_RE.match(lines[0].strip())
    if not m:
        raise ValueError(f"首行不是函数头：{lines[0]}")
    args = []
    for a in split_top(m.group("args")):
        am = ARG_RE.match(a)
        if am:
            args.append((am.group(1), am.group(2)))
    body, pos, closed = parse_block(lines, 1)
    if not closed or pos != len(lines):
        raise ValueError("函数体未正确闭合或有多余内容")
    return Op("func", func_name=m.group(1), args=args, ret=m.group("ret"), body=body)


def flat_ops(func: Op) -> list[Op]:
    out = [func]

    def walk(ops):
        for o in ops:
            out.append(o)
            if o.kind == "for":
                walk(o.body)
    walk(func.body)
    return out


# ---------------------------------------------------------------------------
# 2. TypeConverter：类型兑换表（含"拒收清单"）
# ---------------------------------------------------------------------------

class TypeConversionError(Exception):
    pass


MEMREF_RE = re.compile(
    r"memref<(?P<dims>[\d x?]+)x(?P<elem>f32|f64|f16)\s*,\s*strided<\[(?P<strides>[\d, ?]+)\]\>")


def parse_memref(ty: str) -> dict:
    m = MEMREF_RE.match(ty)
    if not m:
        raise TypeConversionError(f"无法解析的 memref 类型：{ty}")
    dims = m.group("dims").strip()
    sizes = [int(x) for x in re.split(r"[x ]+", dims) if x] if dims != "?" else ["?"]
    if "?" in dims:
        raise TypeConversionError(
            f"{ty}：动态 shape——运行时才知道 sizes/strides，必须把描述符"
            "的填充搬到运行期（本周明确暂不支持，见清单'暂不支持'第 1 条）")
    strides = [int(x) for x in m.group("strides").split(",") if x.strip()]
    return {"kind": "memref", "sizes": sizes, "strides": strides,
            "elem": m.group("elem"), "offset": 0, "raw": ty}


class TypeConverter:
    """类型兑换表。index -> i64（位宽随目标指针宽度，64 位目标即 64），
    f32/i32 原样，memref -> 五字段描述符结构体；tensor／动态 memref 拒收。"""

    def __init__(self, index_bitwidth: int = 64):
        self.index_bitwidth = index_bitwidth

    def desc_ty(self, rank: int) -> str:
        """memref 的目标结构体：allocated ptr, aligned ptr, offset, sizes[], strides[]。
        字段与顺序来自真实 MLIR 的 MemRefDescriptor（MemRefBuilder.h pack 的注释）。"""
        return (f"!llvm.struct<(ptr, ptr, i64, array<{rank} x i64>, "
                f"array<{rank} x i64>)>")

    def desc_bytes(self, rank: int) -> int:
        """描述符在 64 位目标上的体积：2 指针 + 1 偏移 + rank sizes + rank strides。"""
        return 2 * 8 + 8 + 16 * rank

    def conv_type(self, ty: str) -> dict:
        if ty == "index":
            return {"kind": "int", "llvm": f"i{self.index_bitwidth}"}
        if ty in ("f32", "f64", "f16", "i32", "i64"):
            return {"kind": "scalar", "llvm": ty}
        if ty.startswith("tensor<"):
            raise TypeConversionError(
                f"{ty}：tensor 是值语义类型，最终 Lowering 的兑换表里没有目标类型——"
                "必须先经过第一段 Lowering（bufferize，D85~D105）")
        if ty.startswith("memref<"):
            return parse_memref(ty)
        raise TypeConversionError(f"{ty}：未知类型，兑换表拒收")

    def conv_signature(self, args: list[tuple[str, str]], ret: str):
        conv_args, errors = [], []
        for name, ty in args:
            try:
                t = self.conv_type(ty)
                conv_args.append((name, self._llvm_ty(t)))
            except TypeConversionError as e:
                errors.append(str(e))
        try:
            r = self.conv_type(ret)
            conv_ret = self._llvm_ty(r)
        except TypeConversionError as e:
            errors.append(str(e))
        return conv_args, conv_ret, errors

    @staticmethod
    def _llvm_ty(t: dict) -> str:
        if t["kind"] == "memref":
            return TypeConverter().desc_ty(len(t["sizes"]))
        return t["llvm"]


# ---------------------------------------------------------------------------
# 3. ConversionTarget：终态合法性
# ---------------------------------------------------------------------------

ILLEGAL_DIALECTS = ("mini", "scf", "memref", "arith", "func", "cf", "vector")
TARGET_DOC = ("终态（D117 导出 LLVM IR 前）：终图只允许 llvm.* 一族；"
              "mini／scf／memref／arith／func／cf／vector 全部非法。"
              "真实 MLIR 中每个 Pass 有自己的合法集（如 convert-scf-to-cf 允许 memref "
              "原地不动），终态合法集只有一份——今天的清单把两层分开记录。")


def is_legal(opname: str) -> bool:
    return opname.split(".")[0] == "llvm"


# ---------------------------------------------------------------------------
# 4. Pattern 注册表：翻译手册（今天的核心产出，机器生成清单）
# ---------------------------------------------------------------------------

PATTERNS = [
    {"id": "F1", "src": "func.func", "plan": "D115",
     "doc": "签名经 TypeConverter 兑换（memref 参数 -> 描述符结构体按值），产出 llvm.func",
     "seq": "llvm.func"},
    {"id": "R1", "src": "func.return", "plan": "D115",
     "doc": "返回值类型兑换后原样返回", "seq": "llvm.return"},
    {"id": "A1", "src": "arith.constant", "plan": "D115",
     "doc": "常量随类型兑换：index 的 0/1/4/3/6 -> i64 字面量，f32 的 0.0 原样",
     "seq": "llvm.mlir.constant"},
    {"id": "A2", "src": "arith.muli / arith.addi", "plan": "D116",
     "doc": "整数乘／加，index 兑换成 i64 后按 llvm.mul／llvm.add 计算",
     "seq": "llvm.mul / llvm.add"},
    {"id": "A3", "src": "arith.mulf / arith.addf", "plan": "D116",
     "doc": "f32 乘／加（LLVM 方言里有同名浮点指令）", "seq": "llvm.fmul / llvm.fadd"},
    {"id": "C1", "src": "scf.for（含体内 scf.yield）", "plan": "D117",
     "doc": "循环拆成块：前置 br 传入初值，头块参数即归纳变量与 iter_args（导出后是 phi），"
            "icmp+cond_br 判退出，尾块自增并跳回；scf.yield 的值沿回边回传",
     "seq": "llvm.br + llvm.icmp + llvm.cond_br + llvm.add（含块参数）"},
    {"id": "M1", "src": "memref.load", "plan": "D116",
     "doc": "从描述符取 aligned 指针/offset/strides（4 次 extractvalue），"
            "线性地址 = offset + Σ idx_d × stride_d（2 乘 2 加），getelementptr 换算元素地址",
     "seq": "llvm.extractvalue×4 + llvm.mul×2 + llvm.add×2 + llvm.getelementptr + llvm.load"},
    {"id": "M2", "src": "memref.store", "plan": "D116",
     "doc": "与 M1 同一条地址公式，最后换成 store", 
     "seq": "llvm.extractvalue×4 + llvm.mul×2 + llvm.add×2 + llvm.getelementptr + llvm.store"},
    {"id": "M3", "src": "memref.alloc", "plan": "D116",
     "doc": "静态大小 × 4 字节 -> llvm.call @malloc（真实 MLIR 的 MemRefToLLVM 默认走"
            "运行库分配），再用 7 次 insertvalue 把指针/0/sizes/strides 填进描述符",
     "seq": "llvm.call @malloc + llvm.mlir.undef + llvm.insertvalue×7"},
    {"id": "（无）", "src": "mini.*", "plan": "不做",
     "doc": "最终 Lowering 不负责 mini：残留即说明第一段 Lowering（D85~D105）没跑或没跑完",
     "seq": "无模式——残留并报错"},
    {"id": "（无）", "src": "vector.*", "plan": "不做",
     "doc": "本周不涉及 vector 方言；出现即为出界输入",
     "seq": "无模式——明确暂不支持"},
]

PATTERN_FOR_KIND = {"func": "F1", "return": "R1", "const": "A1", "binop": None,
                    "for": "C1", "yield": "C1", "load": "M1", "store": "M2",
                    "alloc": "M3", "generic": None}

BINOP_PATTERN = {"muli": ("A2", "mul"), "addi": ("A2", "add"),
                 "mulf": ("A3", "fmul"), "addf": ("A3", "fadd")}


# ---------------------------------------------------------------------------
# 5. 驱动器：full / partial 两种执法模式
# ---------------------------------------------------------------------------

def drive(root: Op, patterns: set[str], conv: TypeConverter, mode: str) -> dict:
    """对 op 树做转换记账。
    full：残留任何一个非法 op -> 整体失败（原子执法）。
    partial：翻得动就翻，翻不动的逐项记账，整体成功（渐进施工的账本）。"""
    converted, residuals = [], []
    all_ops = flat_ops(root)
    for op in all_ops:
        name = op.name if op.kind != "binop" else f"arith.{op.op}"
        if op.kind == "binop":
            pid = BINOP_PATTERN[op.op][0] if op.ty != "index" else "A2"
        else:
            pid = PATTERN_FOR_KIND.get(op.kind)
        if op.kind == "generic":
            pid = None if "." in op.op else None
        if is_legal(name):
            converted.append((op.brief(), "（已是 llvm.*，无需转换）"))
            continue
        if pid is None or pid not in patterns:
            dialect = name.split(".")[0]
            if dialect == "mini":
                reason = ("非法方言 mini.* 且未注册任何模式——最终 Lowering 不负责 mini，"
                          "请先完成第一段 Lowering（D85~D105）")
            elif dialect == "vector":
                reason = "非法方言 vector.*：本周明确暂不支持（见清单'暂不支持'第 6 条）"
            else:
                reason = f"模式未注册（排期见清单：{pid or '—'} 尚未实现）"
            residuals.append((op.brief(), reason))
            continue
        try:
            for ty in op.types():
                conv.conv_type(ty)
            converted.append((op.brief(), pid))
        except TypeConversionError as e:
            residuals.append((op.brief(), f"类型转换失败：{e}"))
    report = {"mode": mode, "total": len(all_ops), "converted": converted,
              "residuals": residuals,
              "ok": (mode == "partial") or len(residuals) == 0}
    return report


def fmt_drive_report(rep: dict, indent="") -> list[str]:
    lines = [f"{indent}驱动模式：{'full（全量：残留即整体失败）' if rep['mode']=='full' else 'partial（部分：残留记账、整体成功）'}",
             f"{indent}op 总数 {rep['total']}，转换 {len(rep['converted'])}，残留 {len(rep['residuals'])}",
             f"{indent}结论：{'SUCCESS' if rep['ok'] else 'FAIL'}"]
    if rep["residuals"]:
        lines.append(f"{indent}残留清单：")
        for b, r in rep["residuals"]:
            lines.append(f"{indent}  - {b}")
            lines.append(f"{indent}      原因：{r}")
    return lines


# ---------------------------------------------------------------------------
# 6. Emitter：把设计走到底——源 IR -> 目标形态（TIR）
# ---------------------------------------------------------------------------

class Emitter:
    """模式驱动的目标形态发射器。probe 可注入三类设计错误：
    P1：M3 填 C 描述符时把 strides 两个分量填反（镜像 D85 的 P1"strides 算反"）；
    P2：index 不兑换，直接以 index 类型出现在目标形态（LLVM 方言没有 index）；
    P3：k 循环 iter_args 接线断开——body 里用的还是初值 %zero（镜像 D85 的 P3）。"""

    def __init__(self, conv: TypeConverter, probe: str | None = None):
        self.conv = conv
        self.probe = probe
        self.func = None
        self.blocks: list[dict] = []
        self.cur: dict | None = None
        self.consts: dict[str, dict] = {}
        self.edges: list[tuple[str, str, list[str]]] = []

    # ---- TIR 构造小工具 ----
    def new_block(self, name: str, params: list[tuple[str, str]] | None = None) -> dict:
        b = {"name": name, "params": params or [], "ops": []}
        self.blocks.append(b)
        self.cur = b
        return b

    def op(self, **d):
        self.cur["ops"].append(d)
        k = d.get("op")
        if k == "br":
            self.edges.append((self.cur["name"], d["dst"], [v for v, _ in d["args"]]))
        elif k == "condbr":
            if d["fargs"]:
                self.edges.append((self.cur["name"], d["tf"], [v for v, _ in d["fargs"]]))
            else:
                self.edges.append((self.cur["name"], d["tf"], []))
        return d

    def register_const(self, res: str, ty: str, val: str):
        self.consts[res] = {"ty": ty, "val": val}

    # ---- 入口 ----
    def emit(self, func: Op) -> dict:
        conv_args, conv_ret, errors = self.conv.conv_signature(func.args, func.ret)
        if errors:
            raise TypeConversionError("；".join(errors))
        self.func = {"name": func.func_name, "args": conv_args, "ret": conv_ret}
        self.new_block("entry")
        for op in func.body:
            self.emit_op(op)
        return {"func": self.func, "blocks": self.blocks, "consts": self.consts,
                "edges": self.edges}

    def emit_op(self, op: Op, alias: dict | None = None):
        alias = alias or {}
        k = op.kind
        if k == "alloc":
            self.emit_alloc(op)
        elif k == "const":
            self.emit_const(op)
        elif k == "for":
            self.emit_for(op)
        elif k == "load":
            self.emit_mem_access(op, alias, is_store=False)
        elif k == "store":
            self.emit_mem_access(op, alias, is_store=True)
        elif k == "binop":
            a = alias.get(op.a, op.a)
            b = alias.get(op.b, op.b)
            _, llop = BINOP_PATTERN[op.op]
            cty = op.ty if self.probe == "P2" and op.ty == "index" else \
                self.conv.conv_type(op.ty)["llvm"]
            self.op(op="ibin", opc=llop, res=op.res, ty=cty, a=a, b=b)
        elif k == "return":
            t = self.conv.conv_type(op.ty)
            llvm_t = t["llvm"] if t["kind"] != "memref" else self.conv.desc_ty(len(t["sizes"]))
            vals = [(alias.get(op.val, op.val), llvm_t)]
            # return 由外层 for/func 结束时处理：这里记到当前块并返回
            self.op(op="ret", vals=vals)
        elif k == "yield":
            pass  # 已折叠进 for 的回边
        else:
            raise ValueError(f"emit_op 不支持 {k}")

    def resolve(self, name: str, alias: dict) -> str:
        return alias.get(name, name)

    # ---- 各模式 ----
    def emit_const(self, op: Op):
        t = op.ty
        cty = t if (self.probe == "P2" and t == "index") else \
            self.conv.conv_type(t)["llvm"]
        self.op(op="const", res=op.res, ty=cty, val=op.val)
        self.register_const(op.res, cty, op.val)

    def emit_alloc(self, op: Op):
        mt = self.conv.conv_type(op.ty)
        rank = len(mt["sizes"])
        dty = self.conv.desc_ty(rank)
        nbytes = int(np.prod(mt["sizes"])) * 4
        # 常量按需生成（真实 MLIR 会经 CSE 与循环边界常量合并）
        b = f"%b_{op.res[1:]}"
        self.op(op="const", res=b, ty="i64", val=str(nbytes))
        self.register_const(b, "i64", str(nbytes))
        mem = f"%mem_{op.res[1:]}"
        self.op(op="call", res=mem, callee="@malloc", args=[(b, "i64")],
                rty="!llvm.ptr")
        u = f"%{op.res[1:]}_u"
        self.op(op="undef", res=u, ty=dty)
        # 七次 insertvalue：allocated、aligned、offset、sizes×rank、strides×rank
        strides = list(mt["strides"])
        if self.probe == "P1":        # 探针 P1：strides 分量填反
            strides = strides[::-1]
        fields: list[tuple[str, str, list[int]]] = [
            (mem, "!llvm.ptr", [0]), (mem, "!llvm.ptr", [1])]
        off = f"%{op.res[1:]}_off"
        self.op(op="const", res=off, ty="i64", val=str(mt["offset"]))
        self.register_const(off, "i64", str(mt["offset"]))
        fields.append((off, "i64", [2]))
        for d, s in enumerate(mt["sizes"]):
            n = f"%{op.res[1:]}_s{d}"
            self.op(op="const", res=n, ty="i64", val=str(s))
            self.register_const(n, "i64", str(s))
            fields.append((n, "i64", [3, d]))
        for d, s in enumerate(strides):
            n = f"%{op.res[1:]}_t{d}"
            self.op(op="const", res=n, ty="i64", val=str(s))
            self.register_const(n, "i64", str(s))
            fields.append((n, "i64", [4, d]))
        prev, final = u, u
        for i, (v, vty, pos) in enumerate(fields):
            r = op.res if i == len(fields) - 1 else f"%{op.res[1:]}_{i+1}"
            self.op(op="insert", res=r, val=v, src=prev, pos=pos, sty=dty, vty=vty)
            prev, final = r, r

    def emit_for(self, f: Op):
        # for 的结果名（k 循环是 %acc）在出口块重新定义，body 内对 iter 变量的
        # 引用改指向头块参数 %<name>_h
        iv, lb, ub, st = f.iv, f.lb, f.ub, f.st
        hdr = f"^{iv[1:]}_hdr"
        body_name = f"^{iv[1:]}_body"
        done = f"^{iv[1:]}_done"
        iv_ty = "index" if (self.probe == "P2") else "i64"
        it_name = f.iter_name
        it_init = f.iter_init
        it_h = f"{it_name}_h" if it_name else None    # %acc -> %acc_h
        # 前置块：无条件跳进头块，带上初值（归纳变量下界 + iter_args 初值）
        args = [(lb, iv_ty)]
        if it_name:
            args.append((it_init, "f32"))
        self.op(op="br", dst=hdr, args=args)
        # 头块：块参数即"活着的"归纳变量与 iter_args（导出后是 phi）
        params = [(iv, iv_ty)] + ([(it_h, "f32")] if it_name else [])
        self.new_block(hdr, params)
        cmp = f"%cmp_{iv[1:]}"
        self.op(op="icmp", res=cmp, ty=iv_ty, a=iv, b=ub)
        fargs = [(it_h, "f32")] if it_name else []
        self.op(op="condbr", c=cmp, tt=body_name, tf=done, fargs=fargs)
        # 体块
        self.new_block(body_name)
        alias = {it_name: it_h} if it_name else {}
        if it_name and self.probe == "P3":
            # 探针 P3：iter_args 接线断开——body 用初值 %zero 而不是头块参数
            alias[it_name] = it_init
        for op in f.body:
            self.emit_op(op, alias)
        # 循环尾（latch）不另开新块：自增 + 回边直接接在体内最后一个块后面
        nxt = f"%{iv[1:]}n"
        self.op(op="ibin", opc="add", res=nxt, ty=iv_ty, a=iv, b=st)
        yv = None
        for op in f.body:
            if op.kind == "yield":
                yv = op.val
        back = [(nxt, iv_ty)]
        if it_name:
            back.append((self.resolve(yv, alias), "f32"))
        self.op(op="br", dst=hdr, args=back)
        # 出口块：循环结果（iter_args 终值）在这里以块参数形式出现
        self.new_block(done, [(f.res, "f32")] if it_name else [])

    def emit_mem_access(self, op: Op, alias: dict, is_store: bool):
        mt = self.conv.conv_type(op.ty)
        rank = len(mt["sizes"])
        dty = self.conv.desc_ty(rank)
        stem = op.mem[1:] if not is_store else f"{op.mem[1:]}_st"
        idx = [self.resolve(x, alias) for x in op.idx]
        ity = "index" if self.probe == "P2" else "i64"
        al, off, s0, s1 = (f"%{stem}_al", f"%{stem}_off", f"%{stem}_s0", f"%{stem}_s1")
        self.op(op="extract", res=al, src=op.mem, pos=[1], sty=dty, rty="!llvm.ptr")
        self.op(op="extract", res=off, src=op.mem, pos=[2], sty=dty, rty="i64")
        self.op(op="extract", res=s0, src=op.mem, pos=[4, 0], sty=dty, rty="i64")
        self.op(op="extract", res=s1, src=op.mem, pos=[4, 1], sty=dty, rty="i64")
        m0, m1, lin, ix = (f"%{stem}_m0", f"%{stem}_m1", f"%{stem}_lin", f"%{stem}_ix")
        self.op(op="ibin", opc="mul", res=m0, ty=ity, a=idx[0], b=s0)
        self.op(op="ibin", opc="mul", res=m1, ty=ity, a=idx[1], b=s1)
        self.op(op="ibin", opc="add", res=lin, ty=ity, a=m0, b=m1)
        self.op(op="ibin", opc="add", res=ix, ty=ity, a=lin, b=off)
        ptr = f"%{stem}_ptr"
        self.op(op="gep", res=ptr, base=al, idx=ix, elem="f32")
        if is_store:
            self.op(op="store", val=self.resolve(op.val, alias), ptr=ptr, ty="f32")
        else:
            self.op(op="load", res=op.res, ptr=ptr, ty="f32")


# ---------------------------------------------------------------------------
# 7. 两个序列化器：LLVM 方言文本 ／ LLVM IR 文本（后者喂真 LLVM）
# ---------------------------------------------------------------------------

F32_ZERO = "0.000000e+00"


def emit_mlir_text(tir: dict) -> str:
    f = tir["func"]
    dty = f["ret"]
    arglist = ", ".join(f"{n}: {t}" for n, t in f["args"])
    lines = [f"llvm.func @{f['name']}({arglist}) -> {dty} {{"]
    for b in tir["blocks"]:
        if b["name"] == "entry":
            lines.append(f"  {b['name']}:   // 入口块：分配 + 描述符 + 常量")
        else:
            ps = ", ".join(f"{n}: {t}" for n, t in b["params"])
            lines.append(f"  {b['name']}({ps}):" if ps else f"  {b['name']}:")
        for o in b["ops"]:
            lines.append("    " + op_to_mlir(o, tir))
    lines.append("}")
    lines.append("")
    lines.append("// 运行库依赖：真实 MLIR 由 MemRefToLLVM 自动声明 malloc")
    lines.append("llvm.func @malloc(i64) -> !llvm.ptr")
    return "\n".join(lines) + "\n"


def op_to_mlir(o: dict, tir: dict) -> str:
    k = o["op"]
    if k == "const":
        if o["ty"] == "f32":
            return f"%{o['res'][1:]} = llvm.mlir.constant({o['val']} : f32) : f32"
        return f"%{o['res'][1:]} = llvm.mlir.constant({o['val']} : {o['ty']}) : {o['ty']}"
    if k == "undef":
        return f"%{o['res'][1:]} = llvm.mlir.undef : {o['ty']}"
    if k == "ibin":
        return f"%{o['res'][1:]} = llvm.{o['opc']} {o['a']}, {o['b']} : {o['ty']}"
    if k == "icmp":
        return f"%{o['res'][1:]} = llvm.icmp \"slt\" {o['a']}, {o['b']} : {o['ty']}"
    if k == "br":
        if o["args"]:
            asig = ", ".join(f"{v} : {t}" for v, t in o["args"])
            return f"llvm.br {o['dst']}({asig})"
        return f"llvm.br {o['dst']}"
    if k == "condbr":
        s = f"llvm.cond_br {o['c']}, {o['tt']}, {o['tf']}"
        if o["fargs"]:
            s += "(" + ", ".join(f"{v} : {t}" for v, t in o["fargs"]) + ")"
        return s
    if k == "extract":
        pos = ", ".join(str(p) for p in o["pos"])
        return f"%{o['res'][1:]} = llvm.extractvalue {o['src']}[{pos}] : {o['sty']} -> {o['rty']}"
    if k == "gep":
        return (f"%{o['res'][1:]} = llvm.getelementptr {o['base']}[{o['idx']}] "
                f": (!llvm.ptr, i64) -> !llvm.ptr, {o['elem']}")
    if k == "load":
        return f"%{o['res'][1:]} = llvm.load {o['ptr']} : !llvm.ptr -> {o['ty']}"
    if k == "store":
        return f"llvm.store {o['val']}, {o['ptr']} : {o['ty']}, !llvm.ptr"
    if k == "call":
        asig = ", ".join(f"{v} : {t}" for v, t in o["args"])
        return f"%{o['res'][1:]} = llvm.call {o['callee']}({asig}) : (i64) -> !llvm.ptr"
    if k == "insert":
        pos = ", ".join(str(p) for p in o["pos"])
        return f"%{o['res'][1:]} = llvm.insertvalue {o['val']}, {o['src']}[{pos}] : {o['sty']} -> {o['vty']}"
    if k == "ret":
        if o["vals"]:
            v, t = o["vals"][0]
            return f"llvm.return {v} : {t}"
        return "llvm.return"
    if k == "return":
        return "// 函数收尾"
    raise ValueError(k)


def emit_llvm_text(tir: dict) -> str:
    """TIR -> LLVM IR 文本。应用 D113 的三条导出规则：
    R1 命名：值名沿用目标形态（便于对照），块名去 ^；
    R2 常量内联：llvm.mlir.constant 的结果直接写成字面量，不再产生名字；
    R3 块参数变 phi：头块的 (iv, iter_args) 变成 phi，cond_br 的出口传值也是 phi。
    教学真机 ABI：描述符按指针传（entry 聚合 load 进来），结果经 sret 指针写回
    ——真实 MLIR 默认按值传描述符，字段运算完全一致，D115 对齐真实 ABI。"""
    f = tir["func"]
    DS = "{ ptr, ptr, i64, [2 x i64], [2 x i64] }"
    consts = tir["consts"]

    undefs = {o["res"] for b in tir["blocks"] for o in b["ops"]
              if o["op"] == "undef"}

    def lit(v: str) -> str:
        if v in consts:
            c = consts[v]
            if c["ty"] == "f32":
                return c["val"] if c["val"] != "0.0" else F32_ZERO
            return c["val"]
        if v in undefs:
            return "undef"
        return v

    def ty_llvmlir(t: str) -> str:
        return {"i64": "i64", "f32": "float", "index": "i64", "!llvm.ptr": "ptr",
                "i32": "i32"}.get(t, DS)

    def bname(n: str) -> str:
        return n[1:] if n.startswith("^") else n

    incoming: dict[str, list] = {}
    for src, dst, vals in tir["edges"]:
        incoming.setdefault(dst, []).append((src, vals))
    lines = ["; 第 114 天真机验证：由 final_lowering.py 从目标形态导出（教学 ABI：描述符按指针）",
             f"target triple = \"{llvm_triple()}\"",
             "declare ptr @malloc(i64)", "",
             f"define void @{f['name']}(ptr %ap, ptr %bp, ptr %outp) {{",
             "entry:",
             f"  %a = load {DS}, ptr %ap",
             f"  %b = load {DS}, ptr %bp"]
    # entry 块的真实 op（malloc、描述符构造、常量）——常量仍按 R2 内联
    for o in tir["blocks"][0]["ops"]:
        k = o["op"]
        if k == "const":
            continue
        if k == "call":
            args = ", ".join(f"i64 {lit(v)}" for v, _ in o["args"])
            lines.append(f"  {o['res']} = call ptr @malloc({args})")
        elif k == "undef":
            pass                        # undef 只能作操作数（内联），不是指令
        elif k == "insert":
            pos = ", ".join(str(p) for p in o["pos"])
            lines.append(f"  {o['res']} = insertvalue {DS} {lit(o['src'])}, "
                         f"{ty_llvmlir(o['vty'])} {lit(o['val'])}, {pos}")
        elif k == "br":
            lines.append(f"  br label %{bname(o['dst'])}")
        else:
            raise ValueError(f"entry 块出现未预期的 op：{k}")
    for b in tir["blocks"]:
        if b["name"] == "entry":
            continue
        lines.append(f"{bname(b['name'])}:")
        # phi（R3）：块参数 -> phi；每个参数按位置取各入边传来的值（常量按 R2 内联）
        for i, (pn, pt) in enumerate(b["params"]):
            inc = [f"[ {lit(vals[i])}, %{bname(src)} ]"
                   for src, vals in incoming[b["name"]]]
            lines.append(f"  {pn} = phi {ty_llvmlir(pt)} " + ", ".join(inc))
        for o in b["ops"]:
            k = o["op"]
            if k == "br":
                lines.append(f"  br label %{bname(o['dst'])}")
            elif k == "condbr":
                lines.append(f"  br i1 {o['c']}, label %{bname(o['tt'])}, "
                             f"label %{bname(o['tf'])}")
            elif k == "ibin":
                lines.append(f"  {o['res']} = {o['opc']} {ty_llvmlir(o['ty'])} "
                             f"{lit(o['a'])}, {lit(o['b'])}")
            elif k == "icmp":
                lines.append(f"  {o['res']} = icmp slt {ty_llvmlir(o['ty'])} "
                             f"{lit(o['a'])}, {lit(o['b'])}")
            elif k == "const":
                pass                    # R2：常量内联，不再产生名字、不占槽位
            elif k == "extract":
                pos = ", ".join(str(p) for p in o["pos"])
                lines.append(f"  {o['res']} = extractvalue {DS} {o['src']}, {pos}")
            elif k == "gep":
                lines.append(f"  {o['res']} = getelementptr float, ptr {o['base']}, "
                             f"i64 {o['idx']}")
            elif k == "load":
                lines.append(f"  {o['res']} = load float, ptr {o['ptr']}")
            elif k == "store":
                lines.append(f"  store float {lit(o['val'])}, ptr {o['ptr']}")
            elif k == "call":
                args = ", ".join(f"i64 {lit(v)}" for v, _ in o["args"])
                lines.append(f"  {o['res']} = call ptr @malloc({args})")
            elif k == "undef":
                pass                    # undef 只能作操作数（内联），不是指令
            elif k == "insert":
                pos = ", ".join(str(p) for p in o["pos"])
                lines.append(f"  {o['res']} = insertvalue {DS} {lit(o['src'])}, "
                             f"{ty_llvmlir(o['vty'])} {lit(o['val'])}, {pos}")
            elif k == "ret":
                lines.append(f"  store {DS} {o['vals'][0][0]}, ptr %outp")
                lines.append("  ret void")
            else:
                raise ValueError(k)
    lines.append("}")
    return "\n".join(lines) + "\n"


def llvm_triple() -> str:
    return LLVM_TRIPLE


LLVM_TRIPLE = ""


# ---------------------------------------------------------------------------
# 8. 解释器：对 TIR 逐 op 仿真（numpy），验证模式语义
# ---------------------------------------------------------------------------

class Ptr:
    def __init__(self, arr: np.ndarray, base: int):
        self.arr, self.base = arr, base


def run_tir(tir: dict, A: np.ndarray, B: np.ndarray) -> np.ndarray:
    env: dict[str, object] = {}
    heap = []

    def desc_of(a: np.ndarray, sizes, strides):
        return {"allocated": Ptr(a, 0), "aligned": Ptr(a, 0), "offset": 0,
                "sizes": list(sizes), "strides": list(strides), "elem": "f32"}

    env["%a"] = desc_of(A, A.shape, [A.shape[1], 1])
    env["%b"] = desc_of(B, B.shape, [B.shape[1], 1])
    blocks = {b["name"]: b for b in tir["blocks"]}
    cur = "entry"
    result = None
    steps = 0
    while True:
        steps += 1
        if steps > 2_000_000:
            raise RuntimeError("解释器步数超限——疑似控制流接线错误")
        b = blocks[cur]
        for o in b["ops"]:
            k = o["op"]
            if k == "const":
                env[o["res"]] = (np.float32(o["val"]) if o["ty"] == "f32" else int(o["val"]))
            elif k == "undef":
                env[o["res"]] = {"allocated": None, "aligned": None, "offset": None,
                                 "sizes": [None] * 2, "strides": [None] * 2, "elem": "f32"}
            elif k == "ibin":
                a, bb = env[o["a"]], env[o["b"]]
                if o["opc"] in ("mul", "fmul"):
                    env[o["res"]] = np.float32(a * bb) if o["ty"] == "f32" else a * bb
                else:
                    env[o["res"]] = np.float32(a + bb) if o["ty"] == "f32" else a + bb
            elif k == "icmp":
                env[o["res"]] = int(env[o["a"]] < env[o["b"]])
            elif k == "br":
                for (pn, _), (vn, _) in zip(b2 := blocks[o["dst"]]["params"], o["args"]):
                    env[pn] = env[vn]
                cur = o["dst"]
                break
            elif k == "condbr":
                tgt, targs = (o["tt"], o.get("targs", [])) if env[o["c"]] else (o["tf"], o["fargs"])
                for (pn, _), (vn, _) in zip(blocks[tgt]["params"], targs):
                    env[pn] = env[vn]
                cur = tgt
                break
            elif k == "extract":
                d = env[o["src"]]
                pos = o["pos"]
                if pos == [1]:
                    env[o["res"]] = d["aligned"]
                elif pos == [2]:
                    env[o["res"]] = d["offset"]
                else:
                    env[o["res"]] = d["strides"][pos[1]] if pos[0] == 4 else d["sizes"][pos[1]]
            elif k == "gep":
                env[o["res"]] = Ptr(env[o["base"]].arr, env[o["base"]].base + env[o["idx"]])
            elif k == "load":
                p = env[o["ptr"]]
                env[o["res"]] = np.float32(p.arr.ravel()[p.base])
            elif k == "store":
                p = env[o["ptr"]]
                p.arr.ravel()[p.base] = np.float32(env[o["val"]])
            elif k == "call":
                nbytes = env[o["args"][0][0]]
                buf = np.full(int(nbytes) // 4, np.nan, dtype=np.float32)
                heap.append(buf)
                env[o["res"]] = Ptr(buf, 0)
            elif k == "insert":
                d = {kk: (list(vv) if isinstance(vv, list) else vv)
                     for kk, vv in env[o["src"]].items()}
                pos = o["pos"]
                if pos[0] in (0, 1):
                    d[["allocated", "aligned"][pos[0]]] = env[o["val"]]
                elif pos[0] == 2:
                    d["offset"] = env[o["val"]]
                elif pos[0] == 3:
                    d["sizes"][pos[1]] = env[o["val"]]
                else:
                    d["strides"][pos[1]] = env[o["val"]]
                env[o["res"]] = d
            elif k == "ret":
                result = env[o["vals"][0][0]]
                cur = None
                break
            elif k == "return":
                cur = None
                break
        else:
            raise RuntimeError(f"块 {cur} 没有终结符——设计错误")
        if cur is None:
            break
    # 出来的描述符必须已填满（TP4 之外的动态复核）
    for key in ("allocated", "aligned", "offset"):
        if result[key] is None:
            raise RuntimeError("返回的描述符有未填字段")
    return result["allocated"].arr.reshape(result["sizes"]).copy(), steps


# ---------------------------------------------------------------------------
# 9. 真机验证：llvmlite parse -> verify -> MCJIT -> ctypes 调用
# ---------------------------------------------------------------------------

def jit_run(ll_text: str, A: np.ndarray, B: np.ndarray, shape: tuple):
    import llvmlite.binding as lv
    lv.initialize_all_targets()
    lv.initialize_all_asmprinters()
    mod = lv.parse_assembly(ll_text)
    mod.verify()
    tm = lv.Target.from_triple(lv.get_default_triple()).create_target_machine()
    engine = lv.create_mcjit_compiler(mod, tm)
    engine.finalize_object()
    addr = engine.get_function_address("gemm")

    class Desc(ctypes.Structure):
        _fields_ = [("allocated", ctypes.c_void_p), ("aligned", ctypes.c_void_p),
                    ("offset", ctypes.c_int64), ("sizes", ctypes.c_int64 * 2),
                    ("strides", ctypes.c_int64 * 2)]

    def mk(a: np.ndarray) -> Desc:
        d = Desc()
        d.allocated = ctypes.c_void_p(a.ctypes.data)
        d.aligned = ctypes.c_void_p(a.ctypes.data)
        d.offset = 0
        d.sizes[0], d.sizes[1] = a.shape
        d.strides[0], d.strides[1] = a.shape[1], 1
        return d

    out = Desc()
    f = ctypes.CFUNCTYPE(None, ctypes.POINTER(Desc), ctypes.POINTER(Desc),
                         ctypes.POINTER(Desc))(addr)
    f(ctypes.byref(mk(A)), ctypes.byref(mk(B)), ctypes.byref(out))
    arr = np.ctypeslib.as_array(
        ctypes.cast(out.allocated, ctypes.POINTER(ctypes.c_float)),
        shape=(int(out.sizes[0] * out.sizes[1]),)).reshape(tuple(int(x) for x in out.sizes))
    return arr.copy(), lv.get_default_triple()


# ---------------------------------------------------------------------------
# 10. 参考实现与检查
# ---------------------------------------------------------------------------

def make_inputs(M, K, N):
    A = (np.arange(1, M * K + 1, dtype=np.float32).reshape(M, K) * 0.37)
    B = (np.arange(1, K * N + 1, dtype=np.float32).reshape(K, N) * -0.53)
    return A, B


def ref_seq(A, B):
    """逐项参考：与源 IR 语义严格一致（每步 f32 舍入、k 从 0 到 K-1 顺序累加）。"""
    M, K, N = A.shape[0], A.shape[1], B.shape[1]
    C = np.zeros((M, N), dtype=np.float32)
    for i in range(M):
        for j in range(N):
            acc = np.float32(0.0)
            for k in range(K):
                acc = np.float32(acc + np.float32(A[i, k] * B[k, j]))
            C[i, j] = acc
    return C


def main():
    global LLVM_TRIPLE
    ap = argparse.ArgumentParser()
    ap.add_argument("--shape", nargs=3, type=int, default=[4, 6, 3], metavar=("M", "K", "N"))
    ap.add_argument("--tag", default=None)
    ap.add_argument("--emit-src", action="store_true")
    args = ap.parse_args()
    M, K, N = args.shape
    tag = args.tag or f"s{M}{K}{N}"
    OUT.mkdir(exist_ok=True)

    if args.emit_src:
        (CODE / "loop_ir.mlir").write_text(make_source_ir(M, K, N), encoding="utf-8")
        print(f"已生成 loop_ir.mlir（{M}×{K}×{N}）")
        return

    try:
        import llvmlite
        import llvmlite.binding as lv
        LLVM_TRIPLE = lv.get_default_triple()
        have_llvmlite = True
    except ImportError:
        have_llvmlite = False
        LLVM_TRIPLE = "unknown"

    src = make_source_ir(M, K, N)
    if (M, K, N) == (4, 6, 3) and not (CODE / "loop_ir.mlir").exists():
        (CODE / "loop_ir.mlir").write_text(src, encoding="utf-8")
    root = parse_source(src)
    ops = flat_ops(root)
    conv = TypeConverter()

    R: list[str] = []
    add = R.append
    add(f"第 114 天 最终 Lowering 设计——检查报告")
    add(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"环境：Python {platform.python_version()} {platform.machine()}; "
        f"numpy {np.__version__}; "
        + (f"llvmlite {llvmlite.__version__}（LLVM {'.'.join(map(str, lv.llvm_version_info))}），"
           f"triple {LLVM_TRIPLE}" if have_llvmlite else "llvmlite 不可用"))
    add(f"输入：GEMM A({M}×{K}) @ B({K}×{N}) 的循环 IR，"
        f"{len(ops)} 个 op，方言 {sorted({o.name.split('.')[0] for o in ops})}")
    add("")

    tps: list[tuple[str, bool, str]] = []

    # ---- TP1 类型表 ----
    ok1, msg1 = True, []
    a_desc = conv.conv_type(f"memref<{M}x{K}xf32, strided<[{K}, 1]>")
    rows = []
    ok = (conv.conv_type("index")["llvm"] == "i64")
    rows.append(("index", "i64", "位宽随目标指针宽度（64 位目标）", ok))
    ok = (conv.conv_type("f32")["llvm"] == "f32")
    rows.append(("f32", "f32", "原样（LLVM 方言兼容类型）", ok))
    ok = (conv.conv_type("i32")["llvm"] == "i32")
    rows.append(("i32", "i32", "原样（D113 step 函数同款）", ok))
    exp = conv.desc_ty(2)
    got = conv._llvm_ty(a_desc)
    ok = got == exp and a_desc["sizes"] == [M, K] and a_desc["strides"] == [K, 1] and \
        a_desc["offset"] == 0
    rows.append((f"memref<{M}x{K}xf32, strided<[{K},1]>>", exp,
                 f"sizes={a_desc['sizes']}, strides={a_desc['strides']}, offset=0", ok))
    db = conv.desc_bytes(2)
    ok1 = all(r[3] for r in rows)
    for r in rows:
        msg1.append(f"{r[0]:<42} -> {r[1]:<28} {r[2]}")
    msg1.append(f"描述符体积（64 位目标，rank 2）：{db} 字节")
    # 拒收
    try:
        conv.conv_type("tensor<4x6xf32>")
        ok1, msg1 = False, msg1 + ["tensor 应被拒收"]
    except TypeConversionError as e:
        msg1.append(f"tensor<4x6xf32> -> 拒收（{str(e)[:22]}…）")
    try:
        conv.conv_type("memref<?x?xf32>")
        ok1 = False
        msg1.append("动态 memref 应被拒收")
    except TypeConversionError as e:
        msg1.append(f"memref<?x?xf32> -> 拒收（动态 shape 暂不支持）")
    tps.append(("TP1 类型兑换表", ok1, "\n".join(msg1)))

    # ---- TP2 清单完整性 ----
    kinds = {}
    for o in ops:
        nm = o.name if o.kind != "binop" else f"arith.{o.op}"
        kinds[nm] = kinds.get(nm, 0) + 1
    covered = {"func.func": "F1", "func.return": "R1", "arith.constant": "A1",
               "arith.muli": "A2", "arith.addi": "A2", "arith.mulf": "A3",
               "arith.addf": "A3", "scf.for": "C1", "scf.yield": "C1（折叠进 C1）",
               "memref.load": "M1", "memref.store": "M2", "memref.alloc": "M3"}
    missing = [nm for nm in sorted(kinds) if not nm.startswith("llvm")
               and nm not in covered]
    ok2 = (not missing) and set(kinds) == {
        "func.func", "memref.alloc", "arith.constant", "scf.for", "scf.yield",
        "memref.load", "memref.store", "arith.mulf", "arith.addf", "func.return"}
    tps.append(("TP2 合法性清单覆盖", ok2,
                f"源 IR 出现 {len(kinds)} 类 op，全部在清单中有归属；"
                f"非法方言 {sorted({n.split('.')[0] for n in kinds})}；"
                + ("无漏项" if not missing else f"漏项 {missing}")))

    # ---- TP3 全量驱动 ----
    full = drive(root, {"F1", "R1", "A1", "A2", "A3", "C1", "M1", "M2", "M3"},
                conv, "full")
    ok3 = full["ok"] and len(full["converted"]) == len(ops) and not full["residuals"]
    tps.append(("TP3 全量驱动（full）", ok3,
                f"{len(full['converted'])}/{full['total']} 转换，残留 0，"
                f"结论 {'SUCCESS' if full['ok'] else 'FAIL'}"))

    # ---- 发射目标形态 ----
    em = Emitter(conv)
    tir = em.emit(root)
    n_tir = sum(len(b["ops"]) for b in tir["blocks"])
    # 目标 op 计数（不含收尾哨兵）
    n_target = sum(1 for b in tir["blocks"] for o in b["ops"] if o["op"] != "return")
    n_mlir_const = sum(1 for b in tir["blocks"] for o in b["ops"] if o["op"] == "const")

    # ---- TP4 目标形态静态合法性 ----
    errs4 = []
    used_ops = set()
    for b in tir["blocks"]:
        for o in b["ops"]:
            used_ops.add(o["op"])
            ty_fields = [o.get("ty")] + list(o.get("args", []) and
                          [t for _, t in o["args"]] or [])
            for t in [o.get("ty")]:
                if t == "index":
                    errs4.append(f"{o['op']} 仍使用 index 类型")
            for key in ("rty", "vty"):
                if o.get(key) == "index":
                    errs4.append(f"{o['op']} 含 index 结果类型")
        terms = [o for o in b["ops"] if o["op"] in ("br", "condbr", "ret")]
        if len(terms) != 1 or b["ops"][-1] not in terms:
            errs4.append(f"块 {b['name']} 终结符数量 {len(terms)}")
    names = {b["name"] for b in tir["blocks"]}
    for b in tir["blocks"]:
        for o in b["ops"]:
            if o["op"] == "br" and o["dst"] not in names:
                errs4.append(f"br 目标 {o['dst']} 不存在")
            if o["op"] == "condbr" and (o["tt"] not in names or o["tf"] not in names):
                errs4.append("cond_br 目标不存在")
    # 描述符完整性：C 的 7 个 insertvalue 覆盖全部字段
    inserts = [tuple(o["pos"]) for b in tir["blocks"] for o in b["ops"]
               if o["op"] == "insert"]
    need = {(0,), (1,), (2,), (3, 0), (3, 1), (4, 0), (4, 1)}
    if set(inserts) != need:
        errs4.append(f"描述符 insertvalue 覆盖 {set(inserts)} != {need}")
    # extractvalue 位置合法
    for b in tir["blocks"]:
        for o in b["ops"]:
            if o["op"] == "extract":
                p = o["pos"]
                if not (p[0] in range(5) and (len(p) == 1 if p[0] < 3 else len(p) == 2)):
                    errs4.append(f"extractvalue 位置非法 {p}")
    ok4 = not errs4
    tps.append(("TP4 目标形态静态合法性", ok4,
                "终图 op 全部 llvm.*；每块恰一个终结符；分支目标齐全；"
                f"描述符 7 字段全覆盖；extractvalue 位置合法"
                + ("" if ok4 else f"；问题：{errs4}")))

    # ---- TP5 语义仿真 ----
    A, B = make_inputs(M, K, N)
    C_ref = ref_seq(A, B)
    C_sim, steps = run_tir(tir, A, B)
    bit_sim = bool((C_sim == C_ref).all())
    d_blas = float(np.abs(C_sim.astype(np.float64) -
                          (A @ B).astype(np.float64)).max())
    ok5 = bit_sim
    tps.append(("TP5 目标形态语义仿真", ok5,
                f"解释器执行 {steps} 步，C_sim 与逐项参考 bitwise 相等：{bit_sim}；"
                f"与 numpy f32 matmul 的最大差 {d_blas:.3e}（BLAS 累加序不同，只作参考）"))

    # ---- TP6 真机（llvmlite） ----
    if have_llvmlite:
        ll_text = emit_llvm_text(tir)
        C_jit, triple = jit_run(ll_text, A, B, (M, N))
        bit_jit = bool((C_jit == C_ref).all())
        ok6 = bit_jit and triple == LLVM_TRIPLE
        tps.append(("TP6 真机 JIT（LLVM parse→verify→MCJIT→ctypes）", ok6,
                    f"LLVM IR parse+verify 通过，MCJIT 编译执行；"
                    f"C_jit 与逐项参考 bitwise 相等：{bit_jit}"))
    else:
        ll_text = emit_llvm_text(tir)
        ok6 = False
        tps.append(("TP6 真机 JIT", False, "llvmlite 不可用，跳过（环境缺失）"))

    # ---- TP7 部分转换对照（含对照实验 A）----
    exp_a_partial = drive(root, {"F1", "R1", "A1", "A2", "A3", "M1", "M2", "M3"},
                          conv, "partial")
    exp_a_full = drive(root, {"F1", "R1", "A1", "A2", "A3", "M1", "M2", "M3"},
                      conv, "full")
    ok7 = (exp_a_partial["ok"] and not exp_a_full["ok"]
           and len(exp_a_partial["residuals"]) == 4
           and all("模式未注册" in r for _, r in exp_a_partial["residuals"]))
    tps.append(("TP7 partial/full 对照（扣掉 C1 一族）", ok7,
                f"partial：{len(exp_a_partial['converted'])}/{exp_a_partial['total']} 转换、"
                f"残留 {len(exp_a_partial['residuals'])}（3×scf.for + 1×scf.yield），SUCCESS；"
                f"full：同配置 FAIL——残留清单一致，语义相反"))

    # ---- 探针 ----
    probes = []
    em_p1 = Emitter(conv, probe="P1")
    tir_p1 = em_p1.emit(root)
    C_p1, _ = run_tir(tir_p1, A, B)
    nan_ct = int(np.isnan(C_p1).sum())
    diff1 = np.abs(C_p1.astype(np.float64) - C_ref.astype(np.float64))
    fin1 = diff1[~np.isnan(diff1)]
    d1 = float(fin1.max()) if fin1.size else 0.0
    probes.append(("P1 描述符 strides 分量填反",
                   f"有限部分 max|diff|={d1:.4f}，未写元素 {nan_ct} 个（NaN）",
                   "探针被 TP5 咬住：地址错位导致写入位置全错"
                   + (f"；{nan_ct} 个元素永远写不到，malloc 的未初始化内存（仿真里是 NaN）暴露"
                      if nan_ct > 0 else "") if (d1 > 0 or nan_ct > 0)
                   else "探针未生效！"))
    em_p3 = Emitter(conv, probe="P3")
    tir_p3 = em_p3.emit(root)
    C_p3, _ = run_tir(tir_p3, A, B)
    d3 = float(np.abs(C_p3.astype(np.float64) - C_ref.astype(np.float64)).max())
    probes.append(("P3 iter_args 接线断开（body 用初值）", f"max|diff|={d3:.4f}",
                   "探针被 TP5 咬住：每个 (i,j) 只剩最后一项乘积" if d3 > 0
                   else "探针未生效！"))
    em_p2 = Emitter(conv, probe="P2")
    tir_p2 = em_p2.emit(root)
    idx_uses = sum(1 for b in tir_p2["blocks"] for o in b["ops"]
                   if o.get("ty") == "index" or o.get("rty") == "index"
                   or o.get("vty") == "index")
    probes.append(("P2 index 不兑换（LLVM 方言没有 index）",
                   f"目标形态出现 index 类型 {idx_uses} 处",
                   "探针被 TP4 的类型检查咬住：LLVM 方言兼容类型清单里没有 index"
                   if idx_uses > 0 else "探针未生效！"))

    # ---- 对照实验 B：mini + tensor 残留输入 ----
    res_path = CODE / "variants" / "residual.mlir"
    exp_b_lines = []
    if res_path.exists():
        res_root = parse_source(res_path.read_text(encoding="utf-8"))
        res_ops = flat_ops(res_root)
        exp_b_partial = drive(res_root, {"F1", "R1", "A1", "A2", "A3", "C1",
                                         "M1", "M2", "M3"}, conv, "partial")
        exp_b_full = drive(res_root, {"F1", "R1", "A1", "A2", "A3", "C1",
                                      "M1", "M2", "M3"}, conv, "full")
        exp_b_lines = [
            f"输入 variants/residual.mlir：{len(res_ops)} op（func + mini.matmul + return）",
            f"partial：{len(exp_b_partial['converted'])}/{len(res_ops)} 转换，"
            f"残留 {len(exp_b_partial['residuals'])}，"
            f"结论 {'SUCCESS（账本入账）' if exp_b_partial['ok'] else 'FAIL'}"]
        for b, r in exp_b_partial["residuals"]:
            exp_b_lines.append(f"  - {b}")
            exp_b_lines.append(f"      原因：{r}")
        exp_b_lines.append(
            f"full：同输入 FAIL——两道闸（TypeConverter 拒收 tensor、"
            f"ConversionTarget 拒收 mini）把管道顺序错误拦在门外")
        ok_b = (exp_b_partial["ok"] and not exp_b_full["ok"]
                and len(exp_b_partial["residuals"]) == 3)
    else:
        ok_b = False
        exp_b_lines = ["variants/residual.mlir 缺失"]

    # ---- 汇总输出 ----
    add("=" * 72)
    for name, ok, detail in tps:
        add(f"[{'PASS' if ok else 'FAIL'}] {name}")
        for ln in detail.splitlines():
            add(f"       {ln}")
        add("")
    add("探针（故意埋的三个设计错误，应全部被检查咬住）")
    for name, val, note in probes:
        add(f"  - {name}：观测值 {val}。{note}")
    add("")
    add("对照实验 A：扣掉 C1（scf 一族）后，partial 与 full 的执法对照")
    add("\n".join(fmt_drive_report(exp_a_partial, indent="  ")))
    add("")
    add("\n".join(fmt_drive_report(exp_a_full, indent="  ")))
    add("")
    add("对照实验 B：把第一段 Lowering 之前的 tensor 图直接喂给最终 Lowering")
    add("\n".join("  " + ln for ln in exp_b_lines))
    add("")
    add(f"汇总：{sum(1 for _, ok, _ in tps if ok)}/{len(tps)} 项 PASS；"
        f"对照实验 B {'符合预期' if ok_b else '异常'}")
    add("")
    add("统计")
    add(f"  源 IR：{len(ops)} op")
    add(f"  目标形态：{n_target} op（{len(tir['blocks'])} 块），膨胀 {n_target/len(ops):.1f} 倍；"
        f"其中常量 {n_mlir_const} 个（LLVM IR 文本中按 R2 内联，不占槽位）")

    report = "\n".join(R)
    suffix = "" if tag == "s463" else f"-{tag}"
    (OUT / f"conversion-report{suffix}.txt").write_text(report, encoding="utf-8")
    if tag == "s463":
        mlir_text = emit_mlir_text(tir)
        (OUT / "llvm-dialect-target.mlir").write_text(mlir_text, encoding="utf-8")
        (OUT / "gemm.ll").write_text(ll_text if have_llvmlite else
                                     emit_llvm_text(tir), encoding="utf-8")
        (OUT / "legality-checklist.md").write_text(
            make_checklist(kinds, tir, conv, M, K, N), encoding="utf-8")
        (OUT / "design-doc.md").write_text(
            make_design_doc(ops, tir, conv, M, K, N, n_target), encoding="utf-8")
    print(report)
    if tag != "s463":
        print(f"\n（--tag {tag}：仅报告文件 conversion-report{suffix}.txt；"
              f"样板文件保持 4×6×3 版本）")
    return 0 if all(ok for _, ok, _ in tps) else 1


# ---------------------------------------------------------------------------
# 11. 机器生成的两份文档：合法性清单 + 设计文档
# ---------------------------------------------------------------------------

def make_checklist(kinds, tir, conv, M, K, N):
    target_counts = {}
    for b in tir["blocks"]:
        for o in b["ops"]:
            target_counts[o["op"]] = target_counts.get(o["op"], 0) + 1
    seq_ops = {"const": "llvm.mlir.constant", "undef": "llvm.mlir.undef",
               "ibin": "llvm.mul / llvm.add / llvm.fmul / llvm.fadd", "icmp": "llvm.icmp",
               "br": "llvm.br", "condbr": "llvm.cond_br", "extract": "llvm.extractvalue",
               "gep": "llvm.getelementptr", "load": "llvm.load", "store": "llvm.store",
               "call": "llvm.call @malloc", "insert": "llvm.insertvalue",
               "ret": "llvm.return"}
    lines = ["# 第 114 天：最终 Lowering 合法性清单（机器生成）", "",
             f"输入：GEMM A({M}×{K})@B({K}×{N}) 的循环 IR（`loop_ir.mlir`）。"
             "每个源 op 一行：终态判定、负责的模式、目标 op 序列、实现排期。", "",
             "## 一、源 op → 目标（对照实验 A/B 之外，全部由驱动器逐 op 记账）", "",
             "| 源 op（本例出现次数） | 源方言 | 终态判定 | 模式 | 目标 op 序列 | 排期 |",
             "|---|---|---|---|---|---|"]
    plan_by_id = {p["id"]: p for p in PATTERNS}
    for p in PATTERNS:
        toks = re.findall(r"\b[\w]+\.[\w\*]+", p["src"])
        cnt = sum(kinds.get(t, 0) for t in toks)
        lines.append(f"| `{p['src']}`（{cnt}） | {p['src'].split('.')[0]} | 非法，必须转换 | "
                     f"{p['id']} | {p['seq']} | {p['plan']} |")
    lines += ["", "## 二、终态合法集（目标形态里实际出现的 llvm.* op，机器统计）", ""]
    for k in sorted(target_counts):
        if k == "return":
            continue
        lines.append(f"- `{seq_ops.get(k, k)}` × {target_counts[k]}")
    lines += ["", "## 三、类型兑换表（TypeConverter）", "",
              "| 源类型 | 目标类型 | 说明 |", "|---|---|---|",
              "| `index` | `i64` | 位宽随目标指针宽度（64 位目标），LLVM 方言没有 index |",
              "| `f32` | `f32` | 原样（LLVM 方言兼容类型） |",
              "| `i32` | `i32` | 原样 |",
              f"| `memref<{M}x{K}xf32, strided<[{K},1]>>` | `{conv.desc_ty(2)}` | "
              "五字段描述符：allocated/aligned/offset/sizes/strides，按值传递，"
              f"64 位目标上 {conv.desc_bytes(2)} 字节 |",
              "| `tensor<...>` | 拒收 | 管道纪律：必须先 bufferize（D85~D105） |",
              "| `memref<?x?xf32>` | 拒收 | 动态 shape 暂不支持（'暂不支持'第 1 条） |"]
    lines += ["", "## 四、暂不支持清单（残留报告里它们的理由）", "",
              "1. **动态 shape／动态 strides／动态 offset**：运行时才知道 sizes/strides，"
              "描述符填充必须搬到运行期；本周所有 shape 静态已知。",
              "2. **tensor 残留**：兑换表拒收（管道纪律），报'类型转换失败'。",
              "3. **`mini.*` 残留**：终态非法且无模式——必须在第一段 Lowering 处理。",
              "4. **`vector.*`**：本周 IR 不会出现，出现即出界输入，残留报告'明确暂不支持'。",
              "5. **`memref.dealloc`**：源 IR 不生成（D105 的计划式内存不做逐点释放）；"
              "模式 M4（llvm.call @free）列入清单但排期'本周不做'。",
              "6. **f64／f16／混合精度**：类型表只收 f32 与整型；扩展=加一行兑换+核对目标支持。",
              "7. **对齐处理**：描述符保留 aligned_ptr 字段（与真实 MLIR 一致），"
              "本周 allocated == aligned；真实 MemRefToLLVM 会做对齐偏移。"]
    return "\n".join(lines) + "\n"


def make_design_doc(ops, tir, conv, M, K, N, n_target):
    f = tir["func"]
    lines = ["# 第 114 天：最终 Lowering 设计文档", "",
             f"## 1. 任务与输入", "",
             f"把 `loop_ir.mlir`（GEMM A({M}×{K})@B({K}×{N}) 的循环 IR）降成只含 `llvm.*` 的"
             f"目标形态。源 IR {len(ops)} op；目标形态 {n_target} op、{len(tir['blocks'])} 个基本块。"
             "信息显式化的代价在这里量化：每条 memref.load 展开 10 条目标 op，"
             "每个描述符要 7 次 insertvalue 填充。", "",
             "## 2. 角色分工（与 D85 同一套框架）", "",
             "- **ConversionTarget（终态）**：只允许 `llvm.*`；mini/scf/memref/arith/func 全非法。"
             "真实管道分 Pass：convert-scf-to-cf → convert-arith-to-llvm → "
             "convert-memref-to-llvm → convert-cf-to-llvm → convert-func-to-llvm → "
             "reconcile-unrealized-casts；每个 Pass 有自己的合法集，终态只有一份。",
             "- **TypeConverter（兑换表）**：index→i64；f32/i32 原样；memref→五字段描述符"
             "（与真实 MLIR MemRefDescriptor 字段与顺序一致）；tensor／动态 memref 拒收。",
             "- **ConversionPattern（翻译手册）**：F1/R1/A1~A3/C1/M1~M3 共 9 条模式，"
             "外加 mini.*/vector.* 两行\"无模式\"的拒绝行，见 `legality-checklist.md` 第一节。",
             "- **驱动器**：full＝残留即整体失败（D117 导出前的门）；partial＝残留记账"
             "（D115~D116 渐进施工的账本）。两种模式共用同一份残留报告格式。", "",
             "## 3. 关键设计决策", "",
             "1. **alloc → malloc 运行库调用**（模式 M3）：真实 MLIR 的 MemRefToLLVM 默认把 "
             "memref.alloc 降成对 malloc 的调用；描述符字段随后用 insertvalue 填满。",
             "2. **iter_args → 块参数 → phi**（模式 C1）：scf.yield 的值沿回边传回头块，"
             "导出后是 phi（D113 规则 R3）；出口块的块参数接住循环终值。",
             "3. **load/store 的地址公式**（M1/M2）：addr_elems = offset + Σ idx_d×stride_d，"
             "getelementptr 负责元素→字节。字段编号 [1]=aligned、[2]=offset、[4,d]=strides——"
             "这是 P1 探针盯防的位置。",
             "4. **描述符按值传参**：默认 ABI 下每个 memref 参数是 "
             f"{conv.desc_bytes(2)} 字节的聚合值；教学真机验证用'指针+聚合 load/sret'等价形式，"
             "字段运算一致，D115 实现时对齐真实 ABI。",
             "5. **常量内联发生在导出**：目标形态里常量是 op（llvm.mlir.constant）；"
             "LLVM IR 文本里按 D113 规则 R2 内联成字面量、不占槽位。", "",
             "## 4. 实现排期（本周）", "",
             "- D115：F1/R1/A1（函数签名与类型）——对照实验 B 的两道闸就是它的验收。",
             "- D116：M1/M2/M3/A2/A3（内存与算术）——Relu/Add 先行，参考结果验证。",
             "- D117：C1（循环）+ 完整管道 → 导出 LLVM IR；full 驱动必须全绿。",
             "- D118：执行（JIT/AOT）——真机验证脚本今天是它的预演。", "",
             "## 5. 残留报告格式（partial 模式的账本）", "",
             "每条残留两行：`op 简述` + `原因`，原因取值：'模式未注册（排期见清单）'、"
             "'类型转换失败：…'、'非法方言 mini.*…'、'明确暂不支持：…'。"
             "D117 导出前，账本必须清零或逐项写明归属。"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
