#!/usr/bin/env python3
"""Day 43 测试清单——先写测试样例，再写推导代码（本文件先于 matmul_infer.py 完成）。

用法:
    python3 test_matmul_infer.py

每一行测试样例 = (编号, lhs shape, rhs shape, 期望结果, 检查点说明)。
shape 用元组表示，None 代表 IR 里的动态维 "?"；
期望结果是输出 shape 元组，或字符串 "FAIL"（防御性失败，见教程 5.2 失败语义）。
"""

from matmul_infer import infer_matmul_result

D = None  # 动态维 "?" 的简写

CASES = [
    # ---- 全静态：输出每一维都算得出 ----
    ("T01", (2, 3), (3, 2), (2, 2), "全静态教科书案例（贯穿全文的 2x3 · 3x2）"),
    ("T02", (2, 2, 3), (2, 3, 2), (2, 2, 2), "rank 3：batch 维静态对齐"),
    ("T03", (2, 2, 2, 3), (2, 2, 3, 2), (2, 2, 2, 2), "rank 4：规则不随秩变多"),
    ("T04", (3, 1), (1, 3), (3, 3), "K=1：内维收缩到 1 也是合法 MatMul"),
    ("T05", (1, 3), (3, 1), (1, 1), "M=1、N=1：退化成向量内积"),
    # ---- 单侧动态：? 沿 M / N 传播 ----
    ("T06", (D, 3), (3, 2), (D, 2), "M 动态：lhs 的 ? 原样传到输出 M"),
    ("T07", (2, 3), (3, D), (2, D), "N 动态：rhs 的 ? 原样传到输出 N"),
    ("T08", (2, D), (D, 2), (2, 2), "K 双侧动态：K 被消费，输出反而全静态"),
    ("T09", (D, 3), (3, D), (D, D), "M、N 都未知：输出 ?x?，推导成功而非失败"),
    ("T10", (D, D), (D, D), (D, D), "全动态：一个数字都不发明"),
    # ---- batch 维：取“已知一侧” ----
    ("T11", (D, 2, 3), (2, 3, 2), (2, 2, 2), "lhs batch 是 ?：取 rhs 的静态值 2"),
    ("T12", (3, D, 3), (D, 3, 2), (3, D, 2), "rhs batch 是 ?：取 lhs 的 3；M 仍 ?"),
    # ---- 防御性失败：正常管线里 Verifier 先拦，推导只是兜底 ----
    ("T13", (2, 3), (2, 2), "FAIL", "K 双侧静态不等：Verifier 规则 3 的职责"),
    ("T14", (2, 3), (2, 3, 2), "FAIL", "秩不一致：Verifier 规则 1 的职责"),
    ("T15", (3,), (3,), "FAIL", "rank<2：ODS 的 Mini_F32Tensor2DPlus 已挡"),
]


def compact(shape):
    """(2, None, 3) -> '2x?x3'，与 IR 文本同形，方便和 C++ 版对答案。"""
    return "x".join("?" if d is None else str(d) for d in shape)


def main():
    print(f"{'编号':<5}{'lhs · rhs':<18}{'期望':<10}{'实测':<28}{'判定':<6}检查点")
    passed = failed = 0
    for tid, lhs, rhs, expected, note in CASES:
        want = "FAIL" if expected == "FAIL" else compact(expected)
        try:
            got, err = infer_matmul_result(lhs, rhs)
            have = compact(got) if err is None else "FAIL(" + err.split(":")[0] + ")"
            crashed = False
        except Exception as exc:  # 实现抛异常 = 该行报 ERROR，不算 FAIL 也不算 PASS
            have, err, crashed = "EXC:" + type(exc).__name__, None, True
        if expected == "FAIL":
            ok = (not crashed) and err is not None
        else:
            ok = (not crashed) and err is None and got == expected
        verdict = "PASS" if ok else "FAIL"
        passed, failed = passed + ok, failed + (not ok)
        print(f"{tid:<5}{compact(lhs) + ' · ' + compact(rhs):<18}{want:<10}{have:<28}{verdict:<6}{note}")
    total = len(CASES)
    print(f"\n== {total} 行: {passed} PASS / {failed} FAIL (含异常行) ==")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
