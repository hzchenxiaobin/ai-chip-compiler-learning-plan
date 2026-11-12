#!/usr/bin/env python3
"""review_lab.py —— 第 63 天主实验（第 9 周复盘）：一个张量的六种身份 + 一条公式。

任务（来自学习计划）：
  串联 Shape、Stride、Layout、Broadcast 和动态维度；
  用同一个 Tensor 解释两个命题：
    命题一「Shape 相同但内存布局不同」
    命题二「动态维度不等于没有约束」

贯穿全文的数据（与第 61/62 天 MatMul 同一份，值肉眼可核对）：
  逻辑张量 A(2,3) = [[1, 2, 3],
                     [4, 5, 6]]
  周公式（第 57 天的偏移公式升格）：
  物理偏移(idx) = storage_offset + Σ idx[i] × strides[i]

六种身份（同 6 个数字的全部出场方式）：
  1  行主序 A      shape (2,3) strides (3,1)  —— Day 57 的「连续」基准
  2  列主序 A      shape (2,3) strides (1,2)  —— 命题一的 2D 现场-Day 58 的缩小版
  3  转置视图 A.T  shape (3,2) strides (1,3)  —— 零拷贝，与身份 1 共享存储
  4  转置副本 A.T  shape (3,2) strides (2,1)  —— 真重排，自己的存储
  5  reshape 家族  (6,) (2,3) (3,2) (1,6) (6,1) (1,2,3) —— 全是身份 1 的零拷贝视图
  6  广播视图 R    shape (2,3) strides (0,1)  —— stride-0 = 虚拟复制（Day 60）

段落安排：
  0  环境与主线
  1  命题一 A：同 Shape (2,3)，两种布局 —— 逐元素偏移账本对照
  2  命题一 B：同 Shape (3,2)，视图 vs 副本 —— 零拷贝权利的差异（Day 57/59）
  3  命题一 C：reshape 视图家族 + 非连续输入的代价（Day 59）
  4  命题一 D：4D 放大版 —— NCHW vs NHWC（Day 58 同款数据 (1,4,2,4)）
  5  命题一 E：Broadcast —— stride-0 的虚拟复制（Day 60）
  6  命题二：三房间 Verifier 裁决（真实 mlir-opt）+ 特化复验（Day 62 工具）
  7  知识时间线：A 的 dim0（M）的四档状态
  8  汇总

用法：python3 review_lab.py   （在 code/ 目录下；输出另存 outputs/review_lab.txt）
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def skip(name: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}（{why}）")


def elem_strides(a: np.ndarray) -> tuple[int, ...]:
    """numpy 字节 stride → 元素 stride，与 MLIR strided<[...]> 同口径。"""
    return tuple(s // a.itemsize for s in a.strides)


def storage_offset(view: np.ndarray, store: np.ndarray) -> int:
    """视图首元素相对底层存储首元素的偏移（元素个数）。对应 MLIR 的 offset: N。"""
    return (view.ctypes.data - store.ctypes.data) // view.itemsize


def phys_offset(view: np.ndarray, store: np.ndarray, idx: tuple[int, ...]) -> int:
    """逻辑下标 idx 的元素在底层存储中的物理偏移（元素个数）——按 ctypes 实测。"""
    addr = view.ctypes.data
    for i, s in zip(idx, view.strides):
        addr += i * s
    return (addr - store.ctypes.data) // view.itemsize


def formula_offset(offset0: int, strides: tuple[int, ...],
                   idx: tuple[int, ...]) -> int:
    """周公式：物理偏移 = storage_offset + Σ idx[i] × strides[i]。"""
    return offset0 + sum(i * s for i, s in zip(idx, strides))


def find_mlir_opt() -> str | None:
    exe = shutil.which("mlir-opt")
    if exe:
        return exe
    for c in ("/usr/lib/llvm-18/bin/mlir-opt", "/usr/bin/mlir-opt-18"):
        if Path(c).is_file() and Path(c).exists():
            return c
    return None


def mlir_opt_verdict(ir_text: str, tag: str) -> int | None:
    """把一段 IR 喂给 mlir-opt（parse + verify），返回退出码；不可用返回 None。"""
    exe = find_mlir_opt()
    if exe is None:
        skip(f"{tag}: mlir-opt 不可用", "跳过 IR 裁决")
        return None
    p = subprocess.run([exe, "-"], input=ir_text, capture_output=True, text=True)
    return p.returncode


def matmul_ir(a: str, b: str, o: str) -> str:
    """构造一个只有 matmul 的函数，类型串由调用方给定。"""
    return f"""module {{
  func.func @matmul(%a: {a}, %b: {b}, %o: {o}) {{
    linalg.matmul ins(%a, %b : {a}, {b}) outs(%o : {o})
    return
  }}
}}
"""


# ---------------------------------------------------------------------------
print("=" * 66)
print("第 63 天主实验：一个张量的六种身份 + 一条公式（第 9 周复盘）")
print("=" * 66)

print("\n== 0. 环境与主线 ==")
print(f"python  {platform.python_version()}")
print(f"numpy   {np.__version__}")
print(f"arch    {platform.machine()}")
mlir_opt = find_mlir_opt()
if mlir_opt:
    ver = subprocess.run([mlir_opt, "--version"], capture_output=True, text=True)
    print(f"mlir-opt {mlir_opt}（{ver.stdout.splitlines()[0] if ver.stdout else '?'}）")
else:
    print("mlir-opt 不可用（第 6 段将降级）")

A = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
print(f"\n主角登场：A = {A.astype(int).tolist()}，shape {A.shape}")
print("六种身份全部由这 6 个数字（和它的存储排列）扮演，公式只有一条：")
print("  物理偏移(idx) = storage_offset + Σ idx[i] × strides[i]")

# ---------------------------------------------------------------------------
print("\n== 1. 命题一 A：同 Shape (2,3)，两种布局 ==")

# 身份 1：行主序（row-major）——A 的自然摆放，物理读序 0,1,2,3,4,5
S_row = np.arange(1, 7, dtype=np.float32)          # [1,2,3,4,5,6]
id1 = S_row.reshape(2, 3)                          # strides (3,1) 偏移 0

# 身份 2：列主序（column-major）——同一个逻辑 A，但存储按列摆放
#   存储内容必须换成 [1,4,2,5,3,6]，strides 才能是 (1,2)
S_col = np.ascontiguousarray(A.T).ravel().astype(np.float32)   # [1,4,2,5,3,6]
id2 = S_col.reshape(3, 2).T                        # shape (2,3) strides (1,2)

print(f"身份 1（行主序）: shape={id1.shape} strides={elem_strides(id1)} "
      f"offset={storage_offset(id1, S_row)} 存储={S_row.astype(int).tolist()}")
print(f"身份 2（列主序）: shape={id2.shape} strides={elem_strides(id2)} "
      f"offset={storage_offset(id2, S_col)} 存储={S_col.astype(int).tolist()}")

print("\n逐元素账本（值 @ 物理偏移，括号里是周公式的手算过程）：")
for tag, view, store in (("身份1", id1, S_row), ("身份2", id2, S_col)):
    cells = []
    for i in range(2):
        for j in range(3):
            off = phys_offset(view, store, (i, j))
            fml = formula_offset(storage_offset(view, store),
                                 elem_strides(view), (i, j))
            assert off == fml
            cells.append(f"A[{i},{j}]={view[i, j]:.0f}@{off}"
                         f"({i}×{elem_strides(view)[0]}+{j}×{elem_strides(view)[1]})")
    print(f"  {tag}: " + "  ".join(cells))

row_order = [phys_offset(id1, S_row, (i, j)) for i in range(2) for j in range(3)]
col_order = [phys_offset(id2, S_col, (i, j)) for i in range(2) for j in range(3)]
print(f"\n按逻辑读序（行优先）走过的物理偏移序列：")
print(f"  身份 1（连续）: {row_order} ← 相邻逻辑元素在内存里也相邻")
print(f"  身份 2（跳跃）: {col_order} ← 同样的逻辑读序，物理上蹦着走")

check("1a 两身份 shape 相同且值逐位相等",
      id1.shape == id2.shape and np.array_equal(id1, id2))
check("1b 两身份底层字节不同（不是同一份内存）",
      not np.shares_memory(id1, id2) and S_row.tobytes() != S_col.tobytes(),
      f"S_row={S_row.astype(int).tolist()} vs S_col={S_col.astype(int).tolist()}")
check("1c 两身份 strides 不同（布局不同）",
      elem_strides(id1) == (3, 1) and elem_strides(id2) == (1, 2))
check("1d 周公式在两身份上逐元素成立（12/12 对账）",
      all(phys_offset(v, s, idx) == formula_offset(storage_offset(v, s),
          elem_strides(v), idx)
          for v, s in ((id1, S_row), (id2, S_col))
          for idx in np.ndindex(v.shape)))

# ---------------------------------------------------------------------------
print("\n== 2. 命题一 B：同 Shape (3,2)，视图 vs 副本 ==")

id3 = id1.T                                        # 转置视图 (3,2) strides (1,3)
id4 = np.ascontiguousarray(id1.T)                  # 转置副本 (3,2) strides (2,1)

print(f"身份 3（A.T 视图）: shape={id3.shape} strides={elem_strides(id3)} "
      f"offset={storage_offset(id3, S_row)} shares_memory(id1)="
      f"{np.shares_memory(id1, id3)}")
print(f"身份 4（A.T 副本）: shape={id4.shape} strides={elem_strides(id4)} "
      f"shares_memory(id1)={np.shares_memory(id1, id4)} "
      f"存储={id4.ravel().astype(int).tolist()}")

# 改一个字节看谁跟着动：身份 3 是同一条内存，身份 4 不是
S_row[0] = 99.0
check("2a 身份 3 与身份 1 共享存储（改 S_row[0]，A.T[0,0] 跟着变）",
      id3[0, 0] == 99.0 and np.shares_memory(id1, id3))
check("2b 身份 4 有自己的存储（改 S_row[0]，副本纹丝不动）",
      id4[0, 0] == 1.0 and not np.shares_memory(id1, id4))
S_row[0] = 1.0                                     # 恢复现场

# reshape 权利：连续者可零拷贝，非连续者必须拷贝（Day 59 的边界）
r3 = np.reshape(id3, (6,))                         # 非连续视图 reshape → 拷贝
r4 = np.reshape(id4, (6,))                         # 连续副本 reshape → 视图
check("2c 非连续的身份 3 reshape (6,) 被迫拷贝",
      not np.shares_memory(r3, S_row))
check("2d 连续的身份 4 reshape (6,) 仍是零拷贝视图",
      np.shares_memory(r4, id4))
print(f"  身份 3 →(6,) 是拷贝: shares_memory={np.shares_memory(r3, S_row)}"
      f"；身份 4 →(6,) 是视图: shares_memory={np.shares_memory(r4, id4)}")

# ---------------------------------------------------------------------------
print("\n== 3. 命题一 C：reshape 视图家族（Day 59：元素数量不变 ⇒ 只改元信息）==")

print(f"底层存储 S_row（连续）上的 reshape 家族——全部零拷贝：")
for target in [(6,), (2, 3), (3, 2), (1, 6), (6, 1), (1, 2, 3)]:
    v = S_row.reshape(target)
    print(f"  S.reshape{target}: shape={v.shape} strides={elem_strides(v)} "
          f"视图={np.shares_memory(v, S_row)}")
check("3a 六个 reshape 目标全部是同一存储的零拷贝视图",
      all(np.shares_memory(S_row.reshape(t), S_row)
          for t in [(6,), (2, 3), (3, 2), (1, 6), (6, 1), (1, 2, 3)]))

try:
    S_row.reshape((5,))
    n_5 = False
except ValueError:
    n_5 = True
check("3b 元素数量不变是前提：reshape(5,) 抛 ValueError", n_5)

# ---------------------------------------------------------------------------
print("\n== 4. 命题一 D：4D 放大版 —— NCHW vs NHWC（Day 58 同款数据）==")

# Day 58 的数据：N=1, C=4, H=2, W=4，v(n,c,h,w) = c*8 + h*4 + w
nchw = np.arange(32, dtype=np.float32).reshape(1, 4, 2, 4)    # 逻辑 (N,C,H,W)
nhwc_phys = np.ascontiguousarray(nchw.transpose(0, 2, 3, 1))  # 物理 NHWC 字节，(N,H,W,C)
nhwc = nhwc_phys.transpose(0, 3, 1, 2)  # 同一逻辑 (N,C,H,W) 张量，strides=NHWC 版

print(f"NCHW 布局: shape={nchw.shape} strides={elem_strides(nchw)}"
      f"（C 的步长 8，W 的步长 1）")
print(f"NHWC 布局: shape={nhwc.shape} strides={elem_strides(nhwc)}"
      f"（C 的步长 1，W 的步长 4=W 要跨过一整份 C）")
print(f"  逻辑值逐位相等：nchw[0,1,0,2]={nchw[0, 1, 0, 2]:.0f} == "
      f"nhwc[0,1,0,2]={nhwc[0, 1, 0, 2]:.0f}（= c*8+h*4+w）")
print(f"  两种布局的物理字节顺序不同：")
print(f"    NCHW ravel 前 8: {nchw.ravel()[:8].astype(int).tolist()}")
print(f"    NHWC ravel 前 8: {nhwc_phys.ravel()[:8].astype(int).tolist()}")
check("4a 同 Shape (1,4,2,4) 两种布局，逻辑值逐位相等",
      nchw.shape == nhwc.shape == (1, 4, 2, 4) and np.array_equal(nchw, nhwc))
check("4b NHWC 的 C 维 stride=1（最内层），NCHW 的 C 维 stride=8",
      elem_strides(nchw)[1] == 8 and elem_strides(nhwc)[1] == 1)
check("4c 重排后的物理字节顺序真的换了",
      nhwc_phys.ravel()[:8].astype(int).tolist() == [0, 8, 16, 24, 1, 9, 17, 25]
      and nchw.ravel()[:8].astype(int).tolist() == list(range(8)))
check("4d 两种布局不共享存储（真重排，非视图改名）",
      not np.shares_memory(nhwc, nchw))

# ---------------------------------------------------------------------------
print("\n== 5. 命题一 E：Broadcast —— stride-0 的虚拟复制（Day 60）==")

r = np.array([7.0, 8.0, 9.0])                      # (3,) —— Day 60 的 (2,3)+(3,)
R = np.broadcast_to(r, (2, 3))                     # (2,3) strides (0,1)
print(f"r = {r.astype(int).tolist()}，broadcast_to(r, (2,3))：")
print(f"  逻辑 shape={R.shape}，元素 strides={elem_strides(R)} —— dim0 的步长是 0")
print(f"  R[0,:] 与 R[1,:] 的物理偏移：")
off_row0 = [phys_offset(R, r, (0, j)) for j in range(3)]
off_row1 = [phys_offset(R, r, (1, j)) for j in range(3)]
print(f"    第 0 行 {off_row0}，第 1 行 {off_row1} —— 两行落在同一批字节上")
print(f"  A + r = {(A + r).astype(int).tolist()}（逻辑上像复制了两行再相加）")

check("5a 广播视图 stride=0：6 个逻辑元素只占 3 个物理位置",
      elem_strides(R) == (0, 1) and off_row0 == off_row1)
check("5b 广播是视图不是拷贝：与 r 共享存储",
      np.shares_memory(R, r))
check("5c 广播结果逻辑正确（与手算一致）",
      (A + r).astype(int).tolist() == [[8, 10, 12], [11, 13, 15]])
try:
    R[0, 0] = 99.0
    writable = True
except ValueError:
    writable = False
check("5d 广播视图只读（写它抛 ValueError）", not writable)

# ---------------------------------------------------------------------------
print("\n== 6. 命题二：动态维度不等于没有约束（三房间裁决 + 特化复验）==")

rooms = [
    ("房间 1：合法动态  ?x3 · 3x2 → ?x2",
     matmul_ir("memref<?x3xf32>", "memref<3x2xf32>", "memref<?x2xf32>"),
     0, "M 未知但 rank=2、K=3 静态可查——放行，约束退到运行期"),
    ("房间 2：全静态失配 2x4 · 3x2 → 2x2",
     matmul_ir("memref<2x4xf32>", "memref<3x2xf32>", "memref<2x2xf32>"),
     1, "K=4 vs 3 无处可藏——Verifier 当场拦截"),
    ("房间 3：失明现场  ?x4 · 3x2 → ?x2",
     matmul_ir("memref<?x4xf32>", "memref<3x2xf32>", "memref<?x2xf32>"),
     0, "K=4 vs 3 明明都是静态，但 M 的 ? 让推断整体失效——放行（缺口）"),
]

verdicts: dict[str, int | None] = {}
for tag, ir, expect, why in rooms:
    code = mlir_opt_verdict(ir, tag)
    verdicts[tag] = code
    if code is None:
        continue
    mark = "符合预期" if code == expect else "!! 与预期不符"
    print(f"  {tag}: mlir-opt exit={code}（预期 {expect}，{mark}）")
    print(f"    → {why}")

if verdicts.get(rooms[0][0]) is not None:
    check("6a 房间 1（合法动态）放行：约束仍在，只是编译期不查",
          verdicts[rooms[0][0]] == 0)
    check("6b 房间 2（全静态 K 失配）被拦：同样的失配，静态时逃不掉",
          verdicts[rooms[1][0]] == 1)
    check("6c 房间 3（失明现场）放行：一个 ? 拖瞎了一串静态检查",
          verdicts[rooms[2][0]] == 0)

    # 把房间 3 的 IR 落盘，走 Day 62 的特化链：约束被钉回来后重新生效
    blind_ir = OUT / "blind_k.mlir"
    blind_ir.write_text(
        "// 第 63 天复盘用：藏在 ? 后面的 K 失配（与 Day 62 k_blind 同款）\n"
        + rooms[2][1], encoding="utf-8")
    spec_tool = (HERE.parent.parent / "day-062" / "code" / "specialize.py")
    if spec_tool.is_file():
        spec_out = OUT / "blind_k_spec_rejected.mlir"
        print("\n  特化复验（Day 62 的 specialize.py，同一份 blind_k.mlir）：")
        # 第 1 步：不加 --force —— mini 层 K 对账直接拒绝（exit=3，不写出文件）
        p1 = subprocess.run(
            [sys.executable, str(spec_tool), str(blind_ir),
             "--specialize-shape", "a=2x4,b=3x2", "-o", str(spec_out)],
            capture_output=True, text=True)
        out1 = (p1.stdout + p1.stderr).strip().splitlines()
        print(f"    不加 --force: exit={p1.returncode} —— "
              f"{out1[-1] if out1 else '(无输出)'}")
        # 第 2 步：加 --force —— 写出文件，交给 mlir-opt，被拦（exit=4）
        p2 = subprocess.run(
            [sys.executable, str(spec_tool), str(blind_ir),
             "--specialize-shape", "a=2x4,b=3x2", "--force",
             "-o", str(spec_out)],
            capture_output=True, text=True)
        out2 = (p2.stdout + p2.stderr).strip().splitlines()
        err2 = next((ln for ln in out2 if "error" in ln or "to be" in ln),
                    out2[-1] if out2 else "(无输出)")
        print(f"    加 --force:   exit={p2.returncode} —— {err2.strip()}")
        check("6d 特化把约束钉回类型：mini 层 exit=3 拒绝（K 4 vs 3 点名）",
              p1.returncode == 3)
        check("6e --force 后外部 Verifier 拦截：exit=4（产物不可用）",
              p2.returncode == 4)
        print("    → 约束搬家链闭环：静态拦截(exit=1) → 动态放行(exit=0) "
              "→ 特化后拦截回归(exit=3/4)")
    else:
        skip("6d/6e 特化复验", f"找不到 Day 62 工具 {spec_tool}")
else:
    skip("6a–6e 三房间与特化复验", "mlir-opt 不可用")

# ---------------------------------------------------------------------------
print("\n== 7. 知识时间线：A 的 dim0（M）的四档状态 ==")

rows = [
    ("静态 static",      "memref<2x3xf32>（写死）", "写类型那一刻",
     "编译期 Verifier（房间 2 的 exit=1）"),
    ("符号 sym（mini）",  'Sym("M") + 约束表同名对账', "编译期只有名字",
     "推导时同名必须相等（Day 61）"),
    ("未知 runtime",     "memref<?x3xf32>（描述符 sizes[0]）", "运行期输入到达",
     "运行期检查 / 放行但欠账（房间 1、3）"),
    ("特化 specialized", "memref<2x3xf32>（观测值钉回）", "运行期观测之后",
     "重推 + 重验（6d/6e 的 exit=3/4）"),
]
print(f"  {'档位':<18}{'写法':<34}{'数值何时知道':<14}约束在哪查")
for a, b, c, d in rows:
    print(f"  {a:<18}{b:<34}{c:<14}{d}")
print("  一句话：? 只隐瞒「数值」，从不豁免「规矩」——rank、静态维、")
print("  运行期取值合法性一条没少，变的只是检查时机与检查者。")

check("7 知识四档齐备（static/sym/runtime/specialized）",
      len(rows) == 4 and "特化" in rows[3][0])

# ---------------------------------------------------------------------------
print("\n" + "=" * 66)
print(f"汇总：PASS {PASS} / FAIL {FAIL}" + (f" / SKIP {SKIP}" if SKIP else ""))
print("两个命题的验证状态：")
print("  命题一（Shape 相同但内存布局不同）——段 1–5：17 组现场（1a–5d）")
print("  命题二（动态维度不等于没有约束）——段 6–7：三房间 + 特化链 + 四档表")
print("=" * 66)
sys.exit(0 if FAIL == 0 else 1)
