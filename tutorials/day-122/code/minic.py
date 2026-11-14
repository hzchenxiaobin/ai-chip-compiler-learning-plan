#!/usr/bin/env python3
"""第 120 天核心脚本：minic——统一端到端编译入口的 CLI 骨架（第 18 周第一天）。

今天只做「设计＋合同」，不做全部集成（那是 D121~D125 的活）：
  1. 参数解析：输入/输出目录/优化级别/tile/dump/verify/emit
  2. 帮助文本：--help 是 CLI 的第一份合同（用户读的第一行文档）
  3. 诊断体系：E1xx CLI 错误（参数层）/ E2xx 编译错误（管道层）/ W1xx 警告
     每条诊断带：代码、位置（哪个文件哪一行）、原因、修复建议
  4. 退出码合同：0 成功 / 1 编译失败 / 2 用法错误（与 clang/gcc 同族）
  5. 管道骨架：six 阶段占位（S1 图优化→S2 循环生成→S3 Tiling→S4 LLVM
     Lowering→S5 代码生成→S6 验证），今天 S1~S6 只有骨架日志与阶段检查，
     真实集成从明天开始（D121 接图优化）

用法（合同预览）：
    ./minic.py input.mlir -o out/                     # 默认全流程
    ./minic.py input.mlir -O2 --tile 32,32,32         # 优化级别＋tile 参数
    ./minic.py input.mlir --emit ir --dump-ir         # 只到 IR＋逐阶段 dump
    ./minic.py input.mlir --verify gold.txt           # 与 golden 对照
    ./minic.py --help                                 # 帮助文本
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

VERSION = "minic 0.2.0 (day-121: S1 graph passes)"

# ──────────────────────────────────────────────────────────
# 诊断体系：每条诊断是一个结构化对象，不是散落的 print
# ──────────────────────────────────────────────────────────
DIAG_CODES = {
    # E1xx：用法/CLI 错误（退出码 2）
    "E101": ("输入文件不存在：{path}",
             "检查路径拼写；支持相对路径（相对当前目录）与绝对路径"),
    "E102": ("输入文件扩展名不支持：{ext}（支持 .mlir / .graph）",
             ".graph 是图 IR 文本（D83 格式，S1 图优化的输入）；.mlir 是循环 IR（D117 格式，S2 起的输入）"),
    "E103": ("输出目录无法创建：{path}",
             "检查父目录权限；-o 参数会被原样使用，不会追加子目录"),
    "E104": ("tile 参数格式错误：{value}（应为 M,N,K 三个正整数，逗号分隔）",
             "示例：--tile 32,32,32；每维必须 ≥1"),
    "E105": ("优化级别无效：{value}（应为 0/1/2/3）",
             "0=关闭全部；1=仅图优化；2=图优化+Tiling+代码生成优化（默认）；3=激进"),
    "E106": ("--emit 值无效：{value}（应为 exec/obj/ir/dump 之一）",
             "exec=可执行；obj=目标文件；ir=LLVM IR 文本；dump=全部中间产物"),
    "E107": ("--verify 的 golden 文件不存在：{path}",
             "verify 需要一份 numpy 参考输出（.npy 或 12 行 C[i]=v 文本）"),
    # E2xx：编译/管道错误（退出码 1）
    "E201": ("S1 图优化失败：{detail}",
             "用 --dump-ir 保留失败前的 IR；检查输入方言（当前支持 func/arith/scf/memref）"),
    "E202": ("S2 循环生成失败：{detail}",
             "检查 mini.matmul 的 M/N/K 是否与输入 shape 一致"),
    "E203": ("S3 Tiling 失败：{detail}",
             "tile 每维必须 ≤ 对应维度；边界 tile 由 min 钳制处理（D90）"),
    "E204": ("S4 LLVM Lowering 失败：{detail}",
             "残账未清零——对照 D117 的七 pass 清单检查缺失 pass"),
    "E205": ("S5 代码生成失败：{detail}",
             "检查工具链（mlir-opt/mlir-translate/llc/clang）是否在 PATH 或 LLVM_BIN"),
    "E206": ("S6 验证失败：{detail}",
             "逐点对照 golden；先看 max_abs_err 的大小判断是布局错还是计算错"),
    # W1xx：警告（不改变退出码）
    "W101": "tile {value} 大于 shape {shape}：整块退化为单 tile（不影响正确性）",
    "W102": "-O0 下 --tile 仍会生效（Tiling 属于 O2+；O0 的 tile 仅写日志）",
    "W103": "--emit dump 会保留全部中间产物，磁盘占用 ≈ 每阶段 10~100 KB",
}


@dataclass
class Diagnostic:
    """一条结构化诊断：用户拿到的第一现场。"""
    code: str            # E101 / W103 / ...
    where: str           # 位置：文件:行 或 阶段名
    detail: str = ""     # 动态细节（填入模板 {value}/{path}...）

    def render(self) -> str:
        tpl = DIAG_CODES[self.code]
        if isinstance(tpl, tuple):
            msg, fix = tpl
            msg = msg.format(path=self.detail if "path" in msg else "",
                             ext=self.detail if "ext" in msg else "",
                             value=self.detail if "value" in msg else "",
                             detail=self.detail if "detail" in msg else "",
                             shape=self.detail if "shape" in msg else "")
            return (f"{self.code} [{self.where}] {msg}\n"
                    f"       修复建议：{fix}")
        return f"{self.code} [{self.where}] {tpl.format(value=self.detail, shape=self.detail)}"


# ──────────────────────────────────────────────────────────
# 退出码合同（与 clang/gcc 同族，脚本可编程消费）
# ──────────────────────────────────────────────────────────
EXIT_OK = 0        # 编译成功且（若要求）验证通过
EXIT_COMPILE = 1   # 编译/验证失败（输入或管道问题——重试无意义除非改输入）
EXIT_USAGE = 2     # 用法错误（参数拼错——用户读 --help）

PIPELINE_STAGES = [
    ("S1", "图优化", "shape 推导＋图简化＋融合（D121 接入）"),
    ("S2", "循环生成", "mini.matmul→scf.for 三重循环（D122 接入）"),
    ("S3", "Tiling", "tile 参数→边界常量＋min 钳制（D122 接入）"),
    ("S4", "LLVM Lowering", "七 pass 管道（D122 接入）"),
    ("S5", "代码生成", "mlir-translate→.ll→llc/clang（D122 接入）"),
    ("S6", "验证", "golden 逐点 bitwise（D124 接入）"),
]


@dataclass
class Options:
    """解析后的全部选项——管道各阶段只读这个对象，不碰 argv。"""
    input: str = ""
    output_dir: str = "out"
    opt_level: int = 2
    tile: tuple = (32, 32, 32)
    emit: str = "exec"        # exec / obj / ir / dump
    dump_ir: bool = False
    verify: str = ""          # golden 文件路径（空=不验证）
    quiet: bool = False
    llvm_bin: str = ""        # 空则用 PATH
    no_qdq_clean: bool = False
    no_layout_simp: bool = False
    no_reshape_merge: bool = False
    no_fuse: bool = False
    fixpoint_max: int = 8
    diags: list = field(default_factory=list)
    stage_log: list = field(default_factory=list)

    def warn(self, code, where, detail=""):
        d = Diagnostic(code, where, detail)
        self.diags.append(d)
        if not self.quiet:
            print(d.render(), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    """argparse 只是解析器；帮助文本才是 CLI 的合同文档。"""
    p = argparse.ArgumentParser(
        prog="minic",
        description="minic——mini 图编译器的统一入口（第 18 周逐日长成）",
        epilog="示例：\n"
               "  minic gemm.mlir -o out/                    # 全流程到可执行\n"
               "  minic gemm.mlir -O2 --tile 32,32,32        # 指定 tile\n"
               "  minic gemm.mlir --emit ir --dump-ir        # 只到 LLVM IR＋逐阶段 dump\n"
               "  minic gemm.mlir --verify golden.txt        # 编译后与参考对照\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", help="输入 MLIR 文本文件（图/循环 IR，.mlir）")
    p.add_argument("-o", "--output-dir", default="out", metavar="DIR",
                   help="输出目录（默认 out/；会按需创建）")
    p.add_argument("-O", dest="opt_level", type=int, default=2, metavar="N",
                   choices=[0, 1, 2, 3],
                   help="优化级别：0 关闭 / 1 图优化 / 2 +Tiling+CG（默认）/ 3 激进")
    p.add_argument("--tile", default="32,32,32", metavar="M,N,K",
                   help="tile 三维（默认 32,32,32；逗号分隔的三个正整数）")
    p.add_argument("--emit", default="exec", choices=["exec", "obj", "ir", "dump"],
                   help="产物形态：exec 可执行 / obj 目标文件 / ir LLVM IR / dump 全部")
    p.add_argument("--dump-ir", action="store_true",
                   help="每阶段 IR 落盘到 DIR/stage-N-name.mlir（D123 展开）")
    p.add_argument("--verify", default="", metavar="FILE",
                   help="golden 参考输出（12 行 C[i]=v 文本）；提供则编译后自动验证")
    p.add_argument("--llvm-bin", default="", metavar="DIR",
                   help="LLVM 工具目录（默认 PATH；如 /opt/homebrew/opt/llvm/bin）")
    p.add_argument("--no-qdq-clean", action="store_true",
                   help="S1 关掉 QDQ 清理（闸1：DQ(Q(const)) 折叠）")
    p.add_argument("--no-layout-simp", action="store_true",
                   help="S1 关掉布局简化（闸2：transpose(const) 折叠）")
    p.add_argument("--no-reshape-merge", action="store_true",
                   help="S1 关掉 Reshape 合并（闸3：reshape 链合并）")
    p.add_argument("--no-fuse", action="store_true",
                   help="S1 关掉融合（闸4：matmul+bias+relu → fused）")
    p.add_argument("--fixpoint-max", type=int, default=8, metavar="N",
                   help="S1 清理不动点轮数上限（默认 8）")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出诊断与错误")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def parse_and_check(argv) -> Options:
    """解析＋校验：所有用法错误在此聚合成 E1xx 诊断（退出码 2）。"""
    p = build_parser()
    ns = p.parse_args(argv)
    opts = Options(input=ns.input, output_dir=ns.output_dir,
                   opt_level=ns.opt_level, emit=ns.emit,
                   dump_ir=ns.dump_ir, verify=ns.verify,
                   quiet=ns.quiet, llvm_bin=ns.llvm_bin,
                   no_qdq_clean=ns.no_qdq_clean, no_layout_simp=ns.no_layout_simp,
                   no_reshape_merge=ns.no_reshape_merge, no_fuse=ns.no_fuse,
                   fixpoint_max=ns.fixpoint_max)

    fatal = None
    # E101 输入存在性
    if not os.path.exists(ns.input):
        fatal = Diagnostic("E101", "minic", ns.input)
    else:
        ext = os.path.splitext(ns.input)[1]
        if ext not in (".mlir", ".graph"):
            fatal = Diagnostic("E102", "minic", ext or "(无扩展名)")
    # E104 tile 格式
    try:
        parts = [int(x) for x in ns.tile.split(",")]
        if len(parts) != 3 or any(t < 1 for t in parts):
            raise ValueError
        opts.tile = tuple(parts)
    except ValueError:
        if fatal is None:
            fatal = Diagnostic("E104", "minic", ns.tile)
    # E103 输出目录
    if fatal is None:
        try:
            os.makedirs(ns.output_dir, exist_ok=True)
        except OSError as e:
            fatal = Diagnostic("E103", "minic", f"{ns.output_dir}: {e}")
    # E107 verify 文件
    if fatal is None and ns.verify and not os.path.exists(ns.verify):
        fatal = Diagnostic("E107", "minic", ns.verify)

    if fatal is not None:
        opts.diags.append(fatal)
        print(fatal.render(), file=sys.stderr)
        opts.stage_log.append(("CLI", f"致命错误 {fatal.code}——未进入管道"))
        return opts
    # W101/W102 非致命警告
    if opts.opt_level == 0 and opts.tile != (32, 32, 32):
        opts.warn("W102", "CLI", str(opts.tile))
    return opts


def run_pipeline(opts: Options) -> int:
    """管道骨架：今天的六个阶段只有占位日志＋输入预检。

    真实集成排期：D121 S1（图优化＋开关）；D122 S2~S5（循环/Tiling/
    Lowering/CG＋失败诊断）；D123 dump 全量；D124 S6 验证；D125 开关对照。
    """
    # 输入预检（今天唯一真实执行的部分）：读入并数 op
    try:
        src = open(opts.input).read()
    except OSError as e:
        d = Diagnostic("E201", "S0 读入", str(e))
        print(d.render(), file=sys.stderr)
        return EXIT_COMPILE
    n_lines = len(src.splitlines())
    n_ops = sum(1 for ln in src.splitlines()
                if ln.strip() and not ln.strip().startswith("//"))
    opts.stage_log.append(("S0", f"读入 {opts.input}：{n_lines} 行、约 {n_ops} 条 op"))

    # S1 图优化（今天真实接入：.graph 输入走五道闸，开关逐个可关）
    is_graph = opts.input.endswith(".graph")
    if is_graph:
        import graph_passes
        g = graph_passes.parse_graph(src)
        n_before = len(g.nodes)
        sw = {}
        if opts.no_qdq_clean: sw["qdq_clean"] = False
        if opts.no_layout_simp: sw["layout_simp"] = False
        if opts.no_reshape_merge: sw["reshape_merge"] = False
        if opts.no_fuse: sw["fuse"] = False
        sw["fixpoint_max"] = opts.fixpoint_max
        if opts.opt_level == 0:
            sw = {"qdq_clean": False, "layout_simp": False,
                  "reshape_merge": False, "fuse": False, "fixpoint_max": 1}
            opts.no_qdq_clean = opts.no_layout_simp = opts.no_reshape_merge = opts.no_fuse = True
            opts.fixpoint_max = 1
        g2 = graph_passes.run_s1(g, sw)
        n_after = len(g2.nodes)
        opts.stage_log.append(("S1", f"图优化：{n_before} → {n_after} 节点（"
                                     + "；".join(g2.audit) + "）"))
        if opts.dump_ir:
            open(os.path.join(opts.output_dir, "stage-1-graph-opt.graph"), "w").write(
                g2.emit() + "\n")
    else:
        opts.stage_log.append(("S1", "图优化：.mlir 输入跳过（S1 只消费 .graph 图 IR）"))

    # S2~S5：循环生成 + Tiling + LLVM Lowering + 代码生成（今天真实接入）
    s45_error = None
    if is_graph:
        try:
            import loop_lower
            loop_ir = loop_lower.gen_loop_ir(g2, tile=opts.tile)
            opts.stage_log.append(("S2", f"循环生成：fused/matmul → scf.for 三重循环"
                                         f"（M/N/K 推断自图）"))
            opts.stage_log.append(("S3", f"Tiling：tile 参数进循环步长"
                                         f"（{opts.tile}，min 钳制接边界）"))
            r45 = loop_lower.run_s45(loop_ir, opts.output_dir,
                                      llvm_bin=opts.llvm_bin,
                                      dump_ir=opts.dump_ir)
            for sid, note in r45["stages"]:
                opts.stage_log.append((sid, note))
            if not r45["ok"]:
                s45_error = r45["error"]
        except loop_lower.LowerError as e:
            s45_error = str(e)          # LowerError 已带 E2xx 前缀
        except Exception as e:
            s45_error = f"E202 S2 循环生成失败：{e}"
    else:
        opts.stage_log.append(("S2", "循环生成：.mlir 输入跳过（已是循环 IR）"))
        opts.stage_log.append(("S3", "Tiling：.mlir 输入跳过（tile 由源 IR 决定）"))
        opts.stage_log.append(("S4", "LLVM Lowering：骨架（七 pass 管道（D117 已验证，minic 接入排 D123））"))
        opts.stage_log.append(("S5", "代码生成：骨架（mlir-translate→.ll→llc/clang）"))

    for sid, name, plan in PIPELINE_STAGES:
        if sid in ("S1", "S2", "S3", "S4", "S5") and is_graph:
            continue  # 上面已真实执行
        if sid == "S6":
            opts.stage_log.append((sid, f"{name}：骨架（{plan}）——D124 接入"))

    if s45_error is not None:
        print(s45_error, file=sys.stderr)
        opts.stage_log.append(("PIPE", s45_error))

    # 产物：manifest.json——CLI 与调用方（脚本/CI）的机器合同
    exit_code = EXIT_COMPILE if s45_error else EXIT_OK
    manifest = {
        "version": VERSION,
        "input": os.path.abspath(opts.input),
        "output_dir": os.path.abspath(opts.output_dir),
        "opt_level": opts.opt_level,
        "tile": list(opts.tile),
        "emit": opts.emit,
        "dump_ir": opts.dump_ir,
        "s1_switches": {"qdq_clean": not opts.no_qdq_clean,
                        "layout_simp": not opts.no_layout_simp,
                        "reshape_merge": not opts.no_reshape_merge,
                        "fuse": not opts.no_fuse,
                        "fixpoint_max": opts.fixpoint_max},
        "verify": os.path.abspath(opts.verify) if opts.verify else "",
        "stages": [{"id": s, "note": n} for s, n in opts.stage_log],
        "diags": [str(d.code) for d in opts.diags],
        "exit_code": exit_code,
    }
    mpath = os.path.join(opts.output_dir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if not opts.quiet:
        mode = "S1~S5 真实" if not s45_error else "失败于 S2~S5（产物保留现场）"
        print(f"minic: {opts.input} -> {opts.output_dir}/ （{mode}；S6 骨架 D124 接入）")
        for s, n in opts.stage_log:
            print(f"  [{s}] {n}")
        print(f"  manifest: {mpath}")
    return exit_code


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        # 无参数＝用法错误的最低形态
        print("minic: 缺少输入文件（用法：minic input.mlir [选项]；--help 看全部）",
              file=sys.stderr)
        return EXIT_USAGE
    opts = parse_and_check(argv)
    if any(d.code.startswith("E1") for d in opts.diags):
        return EXIT_USAGE
    return run_pipeline(opts)


if __name__ == "__main__":
    sys.exit(main())
