#!/usr/bin/env python3
"""Day 43 TDD 第 0 步：stub 版——测试先行，实现缺席。

用途：`test_matmul_infer.py` 先写完 15 行样例后，第一件事不是写推导逻辑，
而是放一个"只会举手"的 stub，把整张测试表跑红，确认测试真的在测东西。

预期：15 行全部 EXC（NotImplementedError），0/15。
重放（在 code/ 目录下）：bash tdd_replay.sh
"""


def infer_matmul_result(lhs_shape, rhs_shape):
    raise NotImplementedError("Day 43: 规则表还没写")
