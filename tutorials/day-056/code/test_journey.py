#!/usr/bin/env python3
"""test_journey.py —— 第 56 天四站旅程的 Python 层验收测试。

subprocess 调真实 MLIR 工具 build/mini-journey，对四个用例断言：
  main       8 -> 3，终点形态、类型静态、时间轴数字
  skip-infer 大融合被 ? 护栏拦（信息不齐的重写不做）
  shared     半融合不动点（use 表不答应）
  bad        验证站拦截（f64），旅程短路
另含 2 个单元级断言（不依赖工具输出）。

运行: python3 test_journey.py   （在 code/ 目录下，需先构建 mlir-mini）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "mlir-mini" / "build" / "mini-journey"
INPUTS = HERE / "mlir-mini" / "inputs"

_failures: list[str] = []
_passed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failures.append(name)
        print(f"  FAIL  {name}  {detail}")


def run(input_name: str, *extra: str) -> tuple[int, str, str]:
    p = subprocess.run(
        [str(TOOL), str(INPUTS / input_name), *extra],
        capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def stage(out: str, n: int) -> str:
    """提取「===== 阶段 n =====」到下一个 ===== 之间的 IR 段。"""
    m = re.search(rf"===== 阶段 {n}:.*?=====\n(.*?)(?=\n=====|\n\[J)", out, re.S)
    return m.group(1) if m else ""


def main() -> int:
    print("== T1 主线 journey.mlir（默认顺序）==")
    rc, out, err = run("journey.mlir", "--expect=fused")
    check("rc=0 且 accept=PASS", rc == 0 and "accept=PASS" in out)
    s4 = stage(out, 4)
    check("阶段 4 恰含 3 个 mini.* 算子",
          len(re.findall(r"^\s*%.* = mini\.", s4, re.M)) == 3, s4)
    check("终点形态 = constant + fused_matmul_bias_relu + fused_add_relu",
          "mini.fused_matmul_bias_relu" in s4 and "mini.fused_add_relu" in s4
          and "mini.constant" in s4 and "mini.matmul" not in s4)
    check("阶段 4 类型全静态（无 ?x2）", "?x2" not in s4)
    check("阶段 2 只改类型不改结构（仍 8 个）",
          "阶段 2: Shape 推导后 IR（8 个 mini.*" in out)
    check("阶段 3 折掉 1 个 add（6 个）",
          "阶段 3: 折叠后 IR（6 个 mini.*" in out)
    check("签名也被细化（返回类型 ?x2 -> 2x2）",
          "-> (tensor<2x2xf32>, tensor<2x2xf32>)" in s4)
    check("折叠日志：add(0.5,0.5) 折成 1.0",
          "[J3] 折叠: 1 个 add 折成常量" in out)
    check("时间轴：开场引用真实计数 8 -> 3",
          "输入图 8 个 mini.*" in out and "剩 3 个" in out)

    print("== T2 对照 skip-infer（信息不齐，融合站卡住）==")
    rc2, out2, err2 = run("journey.mlir", "--skip-infer", "--expect=fused")
    s4b = stage(out2, 4)
    check("rc=0（小融合照常，verdict 仍 fused）", rc2 == 0)
    check("终点 5 个 mini.*", "阶段 4: 融合后 IR（5 个 mini.*" in out2)
    check("大融合缺席（无 fused_matmul_bias_relu）",
          "mini.fused_matmul_bias_relu" not in s4b)
    check("类型 ?x2 残留（没人细化）", "?x2" in s4b)
    check("? 护栏在决策日志里拒绝过大融合",
          "乘积类型含动态维（?）-> 拒绝" in err2)

    print("== T3 对照 journey_shared（半融合不动点）==")
    rc3, out3, err3 = run("journey_shared.mlir", "--expect=fused")
    s4c = stage(out3, 4)
    check("rc=0", rc3 == 0)
    check("形态 = fused_matmul_bias + relu（半融合不动点）",
          "mini.fused_matmul_bias " in s4c and "mini.relu" in s4c
          and "mini.fused_matmul_bias_relu" not in s4c)
    check("P2 拒绝日志（融合结果有 2 个使用者）",
          "融合结果有 2 个使用者 -> 不能吸收 Relu" in err3)

    print("== T4 对照 journey_bad（验证站拦截）==")
    rc4, out4, err4 = run("journey_bad.mlir", "--expect=verifier_reject")
    check("rc=0 且 verdict=verifier_reject",
          rc4 == 0 and "verdict=verifier_reject" in out4)
    check("验证站在最前面拦下 f64", "元素类型必须是 f32" in err4)
    check("后续三站短路（无阶段 2 dump）", "阶段 2" not in out4)

    print("== T5 单元级：四站职责口径 ==")
    check("验证只裁决不改图（阶段 0 == 阶段 1 的 IR 段）",
          stage(out, 0) == stage(out, 1))
    check("推导只补信息不删算子（阶段 1 与 2 算子数相同）",
          len(re.findall(r"^\s*%.* = mini\.", stage(out, 1), re.M)) ==
          len(re.findall(r"^\s*%.* = mini\.", stage(out, 2), re.M)))

    print(f"\n== 汇总: {_passed} 通过 / {len(_failures)} 失败 ==")
    if _failures:
        for f in _failures:
            print(f"  失败: {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
