#!/usr/bin/env python3
"""specialize.py —— 第 62 天：最小静态 Shape 特化工具（specialize-shape 入口）。

用法：
  python3 specialize.py matmul_dyn.mlir --list-dims
  python3 specialize.py matmul_dyn.mlir --specialize-shape "a=2x3,b=3x2" \
          -o matmul_spec.mlir
  python3 specialize.py k_blind.mlir --specialize-shape "a=2x4,b=3x2" \
          --force -o /tmp/bad_spec.mlir      # 演示：外部 Verifier 拦下

做了什么（三步，对应「将给定动态维度替换为具体值并重新验证」）：
  1. 替换：把 --specialize-shape 给出的具体维填进参数类型里的 ?。
     MLIR 的 ? 没有名字（第 61 天：分不出 Sym 和 None），所以按
     「参数名 = 第几维」对号——这是第 61 天 bindings 表的 MLIR 版。
  2. 重推：用 matmul 规则（M=%a.dim0，N=%b.dim1，K 对账 dim(A,1)==dim(B,0)）
     重推 outs 参数的类型；K 静态失配当场拒绝（--force 跳过，交给外部）。
  3. 重验：写出的 IR 再过一遍 mlir-opt（解析 + verify），确认产物合法。

已知边界（最小工具，够今天用）：
  - 只认 memref/tensor 的「纯维度」类型，不带 layout/offset；
  - 按「类型字符串」全局替换：不同参数共用同一类型串时无法区分（会报错）；
  - 只内置 matmul 一条推导规则；其它算子的 outs 类型不会被重推。

退出码：0 成功；2 spec 非法/冲突；3 mini K 对账失败（未写出）；4 外部验证失败。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


class SpecError(ValueError):
    """spec 非法或与 IR 冲突（rank 不符、改静态维、输出无根据、类型串歧义……）。"""


class KAccountError(ValueError):
    """特化后 K 对不上账——mini 推导器拒绝写出（对应第 61 天的静态对账）。"""


FUNC_RE = re.compile(r"func\.func\s+(?:private\s+)?(@[\w.$-]+)\s*\(([^)]*)\)")
MATMUL_RE = re.compile(r"linalg\.matmul\s+ins\(\s*([^)]*?)\s*\)\s*outs\(\s*([^)]*?)\s*\)")


# ------------------------------------------------------------
# 类型解析：memref<?x3xf32> → ("memref", [None, 3], "f32")
# ------------------------------------------------------------

def parse_shaped_type(t: str):
    t = t.strip()
    m = re.fullmatch(r"(memref|tensor)<(.+)>", t)
    if not m:
        return None
    container, inner = m.group(1), m.group(2)
    if "," in inner or "<" in inner:
        raise SpecError(f"暂不支持带 layout/offset 的类型：{t}")
    if "x" not in inner:                       # 0 维（没有维度可特化）
        return container, [], inner
    dims_s, elem = inner.rsplit("x", 1)
    dims = []
    for d in dims_s.split("x"):
        if d == "?":
            dims.append(None)
        elif d.isdigit():
            dims.append(int(d))
        else:
            raise SpecError(f"维度既不是数字也不是 ?：{d}（类型 {t}）")
    return container, dims, elem


def fmt_type(container: str, dims: list, elem: str) -> str:
    if not dims:
        return f"{container}<{elem}>"
    body = "x".join("?" if d is None else str(d) for d in dims)
    return f"{container}<{body}x{elem}>"


def parse_spec(spec: str) -> dict:
    """"a=2x3,b=3x2" → {"a": [2, 3], "b": [3, 2]}；? 表示该维保持动态。"""
    out: dict[str, list] = {}
    if not spec.strip():
        raise SpecError("--specialize-shape 不能为空")
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SpecError(f"spec 项应为 名字=维x维…，收到 {part!r}")
        name, vals = part.split("=", 1)
        name = name.strip().lstrip("%")
        vals = vals.strip()
        if name in out:
            raise SpecError(f"参数 {name} 在 spec 里出现了两次")
        if not re.fullmatch(r"(\?|\d+)(x(\?|\d+))*", vals):
            raise SpecError(f"{name} 的维度串 {vals!r} 不合法（数字或 ?，用 x 分隔）")
        out[name] = [None if v == "?" else int(v) for v in vals.split("x")]
    return out


def parse_args_str(args_str: str):
    """函数参数表 → [(名字, 类型串), ...]；不是 %名: 类型 的参数返回 None。"""
    args = []
    for chunk in args_str.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.fullmatch(r"%([\w.$-]+)\s*:\s*(.+)", chunk)
        if not m:
            return None
        args.append((m.group(1), m.group(2).strip()))
    return args


def find_func_spans(text: str):
    """[(函数名, 参数表, 体起点, 体终点)]。用花括号配对找函数体。"""
    spans = []
    for m in FUNC_RE.finditer(text):
        open_ = text.find("{", m.end())
        if open_ < 0:
            raise SpecError(f"函数 {m.group(1)} 没有函数体")
        depth, close = 0, None
        for j in range(open_, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    close = j
                    break
        if close is None:
            raise SpecError(f"函数 {m.group(1)} 的函数体没有闭合")
        spans.append((m.group(1), m.group(2), open_, close))
    return spans


# ------------------------------------------------------------
# 核心：特化（可当库用，products_lab.py 会 import 这一层）
# ------------------------------------------------------------

def specialize_ir(text: str, spec: dict, func_name: str | None = None,
                  force: bool = False):
    """把 spec 里的具体维填进 text 的 ?，重推 matmul 的 outs 类型。

    返回 (new_text, report_lines, replacements, n_subs)。
    非法抛 SpecError / KAccountError（不修改原文本）。
    """
    spans = find_func_spans(text)
    if not spans:
        raise SpecError("文件里没有带函数体的 func.func")

    # ---- 选目标函数：--func 指定，否则取唯一含 linalg.matmul 的 ----
    targets = []
    for name, args_s, open_, close in spans:
        if func_name and name.lstrip("@") != func_name.lstrip("@"):
            continue
        if MATMUL_RE.search(text[open_:close]):
            targets.append((name, args_s, open_, close))
    if func_name:
        if not targets:
            cand = ", ".join(s[0] for s in spans)
            raise SpecError(f"找不到函数 @{func_name.lstrip('@')}（候选：{cand}）")
        target = targets[0]
    else:
        if len(targets) == 0:
            raise SpecError("没有找到含 linalg.matmul 的函数（--func 可指定）")
        if len(targets) > 1:
            cand = ", ".join(t[0] for t in targets)
            raise SpecError(f"多个函数含 linalg.matmul（{cand}），请用 --func 选择")
        target = targets[0]
    fname, args_s, open_, close = target

    args = parse_args_str(args_s)
    if args is None:
        raise SpecError(f"函数 {fname} 的参数表解析不了（只支持 %名: shaped类型）")

    # ---- 解析 spec 的目标参数（支持参数名或 argN 位置）----
    by_name = {n: i for i, (n, _) in enumerate(args)}
    resolved: dict[int, list] = {}
    for key, vals in spec.items():
        if key in by_name:
            idx = by_name[key]
        elif re.fullmatch(r"arg\d+", key):
            idx = int(key[3:])
            if idx >= len(args):
                raise SpecError(f"{key} 越界（{fname} 共 {len(args)} 个参数）")
        else:
            cands = ", ".join(n for n, _ in args)
            raise SpecError(f"spec 里的名字 {key!r} 不是 {fname} 的参数（可用：{cands}）")
        if idx in resolved:
            raise SpecError(f"参数 %{args[idx][0]} 在 spec 里出现了两次")
        resolved[idx] = vals

    # ---- 把 spec 应用到 ins 参数上 ----
    new_dims: dict[int, tuple[str, list, str]] = {}
    for idx, vals in resolved.items():
        name, t = args[idx]
        parsed = parse_shaped_type(t)
        if parsed is None:
            raise SpecError(f"参数 %{name} 的类型 {t} 不是受支持的 shaped 类型")
        container, dims, elem = parsed
        if len(vals) != len(dims):
            raise SpecError(
                f"%{name} 是 {len(dims)} 维，spec 给了 {len(vals)} 个数")
        nd = []
        for i, (d, v) in enumerate(zip(dims, vals)):
            if d is not None and v is not None and d != v:
                raise SpecError(
                    f"%{name} 的第 {i} 维已是静态 {d}，不能改成 {v}")
            nd.append(v if v is not None else d)
        new_dims[idx] = (container, nd, elem)

    replacements: dict[str, str] = {}
    repl_info: list[tuple[str, str, str, str]] = []

    def add_repl(old: str, new: str):
        if old in replacements and replacements[old] != new:
            raise SpecError(
                f"类型 {old} 要替换成两个不同的新类型，按类型串全局替换无法区分")
        replacements[old] = new

    def dims_of(idx: int):
        """spec 应用后该参数的维度（没被 spec 的用原类型）。"""
        if idx in new_dims:
            return new_dims[idx][1]
        parsed = parse_shaped_type(args[idx][1])
        return parsed[1] if parsed else None

    # ---- 逐个 matmul：K 对账 + outs 重推 ----
    body = text[open_:close]
    name_to_idx = {n: i for i, (n, _) in enumerate(args)}
    outs_indices: set[int] = set()
    for mm in MATMUL_RE.finditer(body):
        ins_s, outs_s = mm.group(1), mm.group(2)
        if " : " not in ins_s or " : " not in outs_s:
            continue
        names_part, types_part = ins_s.split(":", 1)
        ins_names = [n.strip().lstrip("%") for n in names_part.split(",")]
        oname_s, otype_s = outs_s.split(":", 1)
        out_name = oname_s.split(",")[0].strip().lstrip("%")
        out_type = otype_s.split(",")[0].strip()
        if len(ins_names) != 2:
            continue                      # 只支持二元 matmul
        if not all(n in name_to_idx for n in ins_names + [out_name]):
            continue                      # 操作数不是本函数参数 → 跳过
        ia, ib = name_to_idx[ins_names[0]], name_to_idx[ins_names[1]]
        io = name_to_idx[out_name]
        outs_indices.add(io)
        da, db, do = dims_of(ia), dims_of(ib), dims_of(io)
        if not da or not db or not do or len(da) != 2 or len(db) != 2:
            continue                      # matmul 操作数不是二维 shaped → 跳过

        # K 对账（重新验证第 1 层：mini 推导器）
        ka, kb = da[1], db[0]
        if ka is not None and kb is not None and ka != kb:
            msg = (f"K 对不上账：%{args[ia][0]} 的 dim1={ka}，"
                   f"%{args[ib][0]} 的 dim0={kb}")
            if not force:
                raise KAccountError(msg + "（--force 可跳过本检查，交给 mlir-opt）")

        # outs 重推：M=%a.dim0，N=%b.dim1
        derived = [da[0], db[1]]
        if io in resolved:
            v = resolved[io]
            for i, (dv, sv) in enumerate(zip(derived, v)):
                src = (f"%{args[ia][0]}.dim0" if i == 0
                       else f"%{args[ib][0]}.dim1")
                if dv is None and sv is not None:
                    raise SpecError(
                        f"%{args[io][0]} 的第 {i} 维特化没有根据：它跟随 {src}，"
                        f"而后者仍是 ?——请先特化来源参数")
                if dv is not None and sv is not None and dv != sv:
                    raise SpecError(
                        f"%{args[io][0]} 的第 {i} 维由推导得出 {dv}，"
                        f"与 spec 的 {sv} 冲突")
            # 全一致（或同为 ?）→ outs 仍由推导重推，spec 只是冗余确认
        po = parse_shaped_type(args[io][1])
        new_o_type = fmt_type(po[0], derived, po[2])
        if new_o_type != args[io][1]:
            add_repl(args[io][1], new_o_type)
            repl_info.append((args[io][0], args[io][1], new_o_type, "输出重推"))

    # ---- ins 参数的类型替换（outs 已由推导负责）----
    for idx, (container, nd, elem) in new_dims.items():
        if idx in outs_indices:
            continue
        name, t = args[idx]
        nt = fmt_type(container, nd, elem)
        if nt != t:
            add_repl(t, nt)
            repl_info.append((name, t, nt, "spec"))

    # ---- 单遍替换（避免 A 的新类型串再被 B 的替换波及）----
    if replacements:
        keys = sorted(replacements, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(k) for k in keys))
        n_subs = len(pattern.findall(text))
        new_text = pattern.sub(lambda m: replacements[m.group(0)], text)
    else:
        new_text, n_subs = text, 0

    # ---- 报告 ----
    lines = [f"函数 {fname}（{len(args)} 个参数）"]
    lines.append("替换清单（MLIR 的 ? 没有名字，按「参数.维」对号——"
                 "第 61 天 bindings 表的 MLIR 版）：")
    changed = {name for name, *_ in repl_info}
    for name, t in args:
        parsed = parse_shaped_type(t)
        tag = "  ← outs（输出，由推导重推）" if by_name[name] in outs_indices else ""
        if name in changed:
            for cname, old, new, why in repl_info:
                if cname == name:
                    lines.append(f"  %{name} : {old} → {new}   （{why}）")
        else:
            dims_txt = "x".join("?" if d is None else str(d)
                                for d in (parsed[1] if parsed else []))
            note = "全静态，未改动" if parsed and all(
                d is not None for d in parsed[1]) else "保持原样"
            lines.append(f"  %{name} : {t}   [{dims_txt}] {note}{tag}")
    return new_text, lines, replacements, n_subs


# ------------------------------------------------------------
# 外部重新验证：mlir-opt parse + verify
# ------------------------------------------------------------

def find_mlir_opt() -> str | None:
    from shutil import which
    if which("mlir-opt"):
        return "mlir-opt"
    for c in ("/usr/lib/llvm-18/bin/mlir-opt", "/usr/bin/mlir-opt-18",
              "/usr/lib/llvm-17/bin/mlir-opt", "/usr/bin/mlir-opt-17"):
        if Path(c).is_file() and Path(c).stat().st_mode & 0o111:
            return c
    return None


def verify_with_mlir_opt(text: str, mlir_opt: str):
    """返回 (exit_code, 首条 error 行)。"""
    with tempfile.NamedTemporaryFile("w", suffix=".mlir", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        r = subprocess.run([mlir_opt, path], capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    first = ""
    for line in (r.stderr or "").splitlines():
        if "error:" in line:
            first = line.strip()
            break
    return r.returncode, first


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def list_dims(text: str) -> int:
    spans = find_func_spans(text)
    if not spans:
        print("文件里没有带函数体的 func.func")
        return 2
    for name, args_s, open_, close in spans:
        if not MATMUL_RE.search(text[open_:close]):
            continue
        args = parse_args_str(args_s)
        if args is None:
            continue
        outs_names = set()
        for mm in MATMUL_RE.finditer(text[open_:close]):
            oname = mm.group(2).split(":")[0].split(",")[0].strip().lstrip("%")
            outs_names.add(oname)
        print(f"函数 {name}（{len(args)} 个参数）：")
        for n, t in args:
            parsed = parse_shaped_type(t)
            dims = parsed[1] if parsed else []
            dims_txt = "x".join("?" if d is None else str(d) for d in dims)
            tag = "   ← outs（输出，由推导重推）" if n in outs_names else ""
            print(f"  %{n} : {t:<24} 维度 [{dims_txt}]{tag}")
        print('  spec 写法示例：--specialize-shape "'
              + ",".join(f"{n}=" + "x".join("?" if d is None else str(d)
                                            for d in (parse_shaped_type(t)[1]
                                                      if parse_shaped_type(t) else []))
                         for n, t in args if parse_shaped_type(t)) + '"')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="最小静态 Shape 特化工具：把 ? 替换成具体值并重新验证")
    ap.add_argument("input", help="输入 MLIR 文件")
    ap.add_argument("--specialize-shape", default=None,
                    help='替换清单，如 "a=2x3,b=3x2"；? 表示该维保持动态')
    ap.add_argument("-o", "--output", default=None, help="输出文件（缺省打印到屏幕）")
    ap.add_argument("--func", default=None,
                    help="要特化的函数（缺省：唯一含 linalg.matmul 的函数）")
    ap.add_argument("--force", action="store_true",
                    help="跳过 mini K 对账，把检查交给 mlir-opt（演示重新验证用）")
    ap.add_argument("--no-verify", action="store_true",
                    help="不调用 mlir-opt（无环境时）")
    ap.add_argument("--list-dims", action="store_true",
                    help="列出参数与维度后退出")
    ap.add_argument("--mlir-opt", default=None, help="mlir-opt 路径")
    args = ap.parse_args(argv)

    src = Path(args.input)
    if not src.is_file():
        print(f"错误：找不到输入文件 {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8")

    if args.list_dims:
        return list_dims(text)
    if not args.specialize_shape:
        print("错误：请给 --specialize-shape（或 --list-dims 查看参数）",
              file=sys.stderr)
        return 2

    try:
        spec = parse_spec(args.specialize_shape)
        new_text, report, repls, n_subs = specialize_ir(
            text, spec, args.func, args.force)
    except (SpecError, KAccountError) as e:
        kind = "K 对账失败" if isinstance(e, KAccountError) else "spec 非法"
        print(f"错误（{kind}）：{e}", file=sys.stderr)
        return 3 if isinstance(e, KAccountError) else 2

    print(f"== specialize-shape：{src.name} → "
          f"{args.output or '(stdout)'} ==")
    for line in report:
        print(line)
    print(f"共替换 {n_subs} 处类型串（{len(repls)} 种类型）")

    # 重新验证（第 2 层：外部 Verifier）
    mlir_opt = args.mlir_opt or find_mlir_opt()
    if args.no_verify:
        print("重新验证：已跳过（--no-verify）")
    elif mlir_opt is None:
        print("重新验证：找不到 mlir-opt，已跳过（以下为未验证产物）")
    else:
        rc, err = verify_with_mlir_opt(new_text, mlir_opt)
        if rc == 0:
            print(f"重新验证（{mlir_opt} parse+verify）：exit=0 通过")
        else:
            print(f"重新验证（{mlir_opt} parse+verify）：exit={rc} 被拒")
            if err:
                print(f"  {err}")
            if args.output:
                Path(args.output).write_text(new_text, encoding="utf-8")
                print(f"  （产物仍按 --force 语义写出：{args.output}）")
            return 4

    if args.output:
        Path(args.output).write_text(new_text, encoding="utf-8")
        print(f"写出 {args.output}")
    else:
        print(new_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
