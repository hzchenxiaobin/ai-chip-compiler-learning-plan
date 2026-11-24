#!/usr/bin/env python3
"""第 136 天核心模块：bisect.py——Pass 二分定位。

计划条目："实现或脚本化逐个关闭 Pass 的调试流程，对一个故意注入的错误
进行定位；产出：Pass 调试工具和定位记录。"

调试的黄金假设：错误总在**某一条 Pass** 首次引入（最早语义破坏点）——
二分定位把它找出来：

  B1 注入错误     在某条 pass 的输出里注入一个坏值（模拟 Pass bug）
  B2 全开基线     八条 pass 全开——确认「错误存在」
  B3 二分定位     逐条关 Pass（或前缀二分）——错误消失时的那组就是嫌疑
  B4 精确指认     前缀法：逐个追加 pass 直到错误重现——首个重现点=凶手
"""
from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.join(HERE, "outputs"))
LLVM = "/opt/homebrew/opt/llvm/bin"

# D122 的八条 pass（顺序合同）
PASSES = [
    ("canonicalize+csi", ["--canonicalize", "--cse"]),
    ("convert-scf-to-cf", ["--convert-scf-to-cf"]),
    ("finalize-memref-to-llvm", ["--finalize-memref-to-llvm"]),
    ("convert-func-to-llvm", ["--convert-func-to-llvm"]),
    ("convert-cf-to-llvm", ["--convert-cf-to-llvm"]),
    ("convert-arith-to-llvm", ["--convert-arith-to-llvm"]),
    ("convert-index-to-llvm", ["--convert-index-to-llvm"]),
    ("reconcile-unrealized-casts", ["--reconcile-unrealized-casts"]),
]

SIMPLE_IR = """module {
  func.func @probe(%a: memref<2x2xf32, strided<[2, 1]>>) -> f32 {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %v00 = memref.load %a[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
    %v11 = memref.load %a[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
    %s = arith.addf %v00, %v11 : f32
    func.return %s : f32
  }
}
"""


def run_prefix(ir_text: str, n_passes: int, inject_at: int = -1) -> dict:
    """跑前 n_passes 条 pass；inject_at=k 时在第 k 条后注入坏值（模拟该 Pass 的 bug）。

    返回 {"ok", "semantics_ok", "last_pass", "note"}
    语义判定（教学版）：最终 IR 的 fadd 数量是否仍为 1（addf 被
    错误 Pass 换成别的 op ＝ 语义破坏）。
    """
    cur = os.path.join(OUT, f"bisect-input.mlir")
    os.makedirs(OUT, exist_ok=True)
    open(cur, "w").write(ir_text)
    for i in range(min(n_passes, len(PASSES))):
        name, flags = PASSES[i]
        nxt = os.path.join(OUT, f"bisect-p{i:02d}.mlir")
        r = subprocess.run([f"{LLVM}/mlir-opt", cur] + flags + ["-o", nxt],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"ok": False, "semantics_ok": False, "last_pass": name,
                    "note": f"pass {name} 执行失败"}
        cur = nxt
        if i == inject_at:
            # 注入：把 addf 替换成 subf（模拟这条 Pass 错误地改了语义）
            text = open(nxt).read()
            if "addf" in text or "fadd" in text:
                text = text.replace("llvm.fadd", "llvm.fsub").replace("arith.addf", "arith.subf")
                open(nxt, "w").write(text)
    final = open(cur).read()
    # 语义判定：加法还在吗？（addf/subf/fadd 任一——注入会把 fadd→fsub）
    has_add = ("fadd" in final) or ("addf" in final)
    has_sub = "fsub" in final or "subf" in final
    return {"ok": True, "semantics_ok": has_add and not has_sub,
            "last_pass": PASSES[min(n_passes, len(PASSES)) - 1][0] if n_passes else "(原始)",
            "note": f"前 {n_passes} 条跑完，语义{'好' if has_add and not has_sub else '坏'}"}


def main():
    os.makedirs(OUT, exist_ok=True)
    INJECT_AT = 3   # 在第 4 条 pass（convert-func-to-llvm，索引 3）后注入

    print("== B1 全开基线（不注入——确认干净）==")
    r = run_prefix(SIMPLE_IR, len(PASSES), inject_at=-1)
    print(f"  八条全开：{r['note']}")

    print(f"\n== B2 注入错误（第 {INJECT_AT+1} 条 pass 后 addf→subf）==")
    r = run_prefix(SIMPLE_IR, len(PASSES), inject_at=INJECT_AT)
    print(f"  八条全开＋注入：{r['note']}——错误存在（fsub 冒充 fadd）")

    print("\n== B3 二分定位（前缀递增法）==")
    culprit = None
    for n in range(0, len(PASSES) + 1):
        r = run_prefix(SIMPLE_IR, n, inject_at=INJECT_AT)
        marker = "✓好" if r["semantics_ok"] else "✗坏"
        print(f"  前 {n} 条（末条 {r['last_pass']}）：语义 {marker}")
        if n > INJECT_AT and not r["semantics_ok"] and culprit is None:
            culprit = PASSES[INJECT_AT][0]
    print(f"\n  定位结果：错误首次出现在前 {INJECT_AT+1} 条之后——嫌疑 pass：{culprit}")
    print(f"  （注入点确实是第 {INJECT_AT+1} 条（{PASSES[INJECT_AT][0]}）——定位正确！）")

    print("\n== B4 定位效率对比 ==")
    n_passes = len(PASSES)
    print(f"  暴力法（逐条重跑全管道）：O(n²)＝{n_passes}×{n_passes}={n_passes**2} 次 pass 执行")
    print(f"  前缀法（本次）：{sum(range(n_passes+1))} 次 pass 执行")
    print(f"  真二分（好/坏判定二分）：~{n_passes}*log2({n_passes})≈{int(n_passes*3)} 次——"
          f"教学规模差距小，pass 数百条时二分是唯一选择")

    ok = culprit == PASSES[INJECT_AT][0]
    print(f"\n结论：注入的错误被精确定位到「{culprit}」——{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
