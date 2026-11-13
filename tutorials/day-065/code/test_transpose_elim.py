#!/usr/bin/env python3
"""test_transpose_elim.py —— 第 65 天验收测试：两个 RewritePattern + PassManager。

分节：
  A  组合排列代数（compose_perm / is_identity / inverse_perm / perm_order / 结合律）
  B  Pattern 1 互逆消除（2D/3D/4D + 使用替换的传播）
  C  Pattern 2 一般合并（单转置 / 恒等特例 / Verifier 自检 / 单独跑的覆盖）
  D  多使用者与返回值边界（反例图不动）
  E  PassManager 不动点（链长 1..8、迭代轮数、幂等性）
  F  判定表与随机压力对拍（12 场景 + 300 组）
  G  MLIR 对照（linalg 链 --canonicalize 原样 + loops 降级证据；不可用则跳过）

用法：python3 test_transpose_elim.py   （在 code/ 目录下）
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path

import numpy as np

from transpose_elim_lab import (
    MiniGraph, MiniTransposeOp, cancel_inverse_transpose, compose_perm,
    find_mlir_opt, infer_transposed_shape, inverse_perm, is_identity,
    linalg_chain_ir, merge_consecutive_transpose, perm_order, run_passes,
    run_mlir_opt, verify_transpose,
)

PASS = 0
FAIL = 0
SKIP = 0

TWO_PATTERNS = [
    ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
    ("P2 merge_consecutive_transpose", merge_consecutive_transpose),
]


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))
    return cond


def skip(name: str, why: str = "") -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}（{why}）")


def make_chain(shape, perms, extra_users=(), return_tail=True):
    """构造链图：T_{perms[0]} → T_{perms[1]} → …。

    extra_users 是 (ids 索引 k, 该消费方的 perm) 元组——给 ids[k]
    （k≥1 时是第 k 个转置的结果）加第二个使用者（多使用者反例）。
    """
    x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
    ids = ["%in"] + [f"%t{i}" for i in range(len(perms))]
    ops_, cur = [], tuple(shape)
    for i, pm in enumerate(perms):
        ops_.append(MiniTransposeOp(ids[i + 1], ids[i], cur, "f32", pm))
        cur = infer_transposed_shape(cur, pm)
    returns = [ids[-1]] if return_tail else []
    for k, pm in extra_users:
        u_shape = infer_transposed_shape(ops_[k - 1].result_shape, pm)
        uid = f"%u{k}_{len(returns)}"
        ops_.append(MiniTransposeOp(uid, ids[k], u_shape, "f32", pm))
        returns.append(uid)
    return MiniGraph(ops=ops_, returns=returns, inputs={"%in": x})


rng = random.Random(65)
B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)

print("== A. 组合排列代数 ==")
ok = True
for p_ in itertools.permutations(range(3)):
    for q_ in itertools.permutations(range(3)):
        ok &= np.array_equal(np.transpose(np.transpose(B, p_), q_),
                             np.transpose(B, compose_perm(p_, q_)))
check("A1 compose 全量对拍：36 对 3 元排列 T_q∘T_p == T_{compose(p,q)}", ok)

ok = True
for p_ in itertools.permutations(range(3)):
    for q_ in itertools.permutations(range(3)):
        back = np.array_equal(np.transpose(np.transpose(B, p_), q_), B)
        ok &= (back == is_identity(compose_perm(p_, q_))
               == (q_ == inverse_perm(p_)))
check("A2 回到原样 ⟺ compose==恒等 ⟺ q==inv(p)，三重判定 36 对一致", ok)

check("A3 3-循环 p² = inv(p)：compose((1,2,0),(1,2,0)) == (2,0,1)",
      compose_perm((1, 2, 0), (1, 2, 0)) == (2, 0, 1)
      == inverse_perm((1, 2, 0)))

ok = True
for p_ in itertools.permutations(range(4)):
    cur = tuple(range(4))
    for _ in range(perm_order(p_)):
        cur = compose_perm(cur, p_)
    ok &= cur == tuple(range(4))
check("A4 阶：24 个 4 元排列连做『阶』次同款转置回到恒等", ok)

ok = True
for p_ in itertools.permutations(range(3)):
    for q_ in itertools.permutations(range(3)):
        for s_ in itertools.permutations(range(3)):
            if compose_perm(compose_perm(p_, q_), s_) != \
                    compose_perm(p_, compose_perm(q_, s_)):
                ok = False
check("A5 结合律 (p∘q)∘s == p∘(q∘s)（729 组 3 元三元组）——"
      "长链先合并哪一对都不影响终点", ok)
check("A6 is_identity 只认真恒等：(0,1) 是、(1,0) 不是、(1,0,2) 不是",
      is_identity((0, 1)) and not is_identity((1, 0))
      and not is_identity((1, 0, 2)))
check("A7 verify_transpose 四关入口仍在：perm [2,0] 对 2 维被 E2 拒绝",
      verify_transpose((2, 3), (2, 0), (3, 2))[0].startswith("[E2]"))

print("\n== B. Pattern 1 互逆消除 ==")
g = make_chain((2, 3), [(1, 0), (1, 0)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("B1 2D 互逆对：2 op → 0，returns 换成 %in",
      len(g.ops) == 0 and g.returns == ["%in"]
      and np.array_equal(g.eval()[0], before[0]))

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("B2 3D 互逆对（非对合）：2 op → 0 且数值不变",
      len(g.ops) == 0 and np.array_equal(g.eval()[0], before[0]))

g = make_chain((2, 3, 4, 5), [(3, 2, 1, 0), (3, 2, 1, 0)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("B3 4D 互逆对（rev 排列是对合）：2 op → 0", len(g.ops) == 0)

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1), (0, 2, 1)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("B4 使用替换传播：链尾 %t2 直接改接 %in（op 数 3→1，perm 不变）",
      len(g.ops) == 1 and g.ops[0].input_id == "%in"
      and g.ops[0].perm == (0, 2, 1)
      and np.array_equal(g.eval()[0], before[0]))

g = make_chain((2, 3), [(1, 0), (0, 1)])
run_passes(g, [("P1 only", cancel_inverse_transpose)])
check("B5 非互逆对 P1 不动手（T_(1,0)∘T_(0,1) 原样 2 op，留给 P2 合并）",
      len(g.ops) == 2)

print("\n== C. Pattern 2 一般合并 ==")
g = make_chain((2, 3, 4), [(1, 2, 0), (1, 2, 0)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("C1 3D 一般对 p=q：合并为单转置 T_{p²}=T_(2,0,1)，op 2→1",
      len(g.ops) == 1 and g.ops[0].perm == (2, 0, 1)
      and g.ops[0].input_id == "%in"
      and np.array_equal(g.eval()[0], before[0]))
check("C2 合并产物过四关 Verifier（结果类型 = 推导结果）", g.verify() == [])

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)])
before = g.eval()
run_passes(g, [("P2 only", merge_consecutive_transpose)])
check("C3 P2 单独也能消除互逆对（P1 在数学上是 P2 的特例）：2 op → 0",
      len(g.ops) == 0 and np.array_equal(g.eval()[0], before[0]))

ok = True
for shape, perms, want_ops in [((2, 3), [(1, 0), (1, 0)], 0),
                              ((2, 3, 4), [(1, 2, 0), (2, 0, 1)], 0),
                              ((2, 3, 4), [(1, 2, 0), (1, 2, 0)], 1),
                              ((2, 3, 4), [(1, 2, 0)] * 3, 0),
                              ((2, 3, 4), [(1, 2, 0)] * 4, 1)]:
    g1 = make_chain(shape, perms)
    before = g1.eval()
    run_passes(g1, TWO_PATTERNS)
    g2 = make_chain(shape, perms)
    run_passes(g2, [("P2 only", merge_consecutive_transpose)])
    ok &= (len(g1.ops) == want_ops and len(g2.ops) == want_ops
           and np.array_equal(g1.eval()[0], g2.eval()[0])
           and np.array_equal(g1.eval()[0], before[0]))
check("C4 五个代表场景：P2 单独跑与双 Pattern 的结果完全一致", ok)

g = make_chain((2, 3, 4), [(1, 2, 0), (0, 2, 1)])
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("C5 一般对 p≠q：合并为 T_(1,0,2)，值与两步链一致",
      len(g.ops) == 1 and g.ops[0].perm == (1, 0, 2)
      and np.array_equal(g.eval()[0], before[0]))

print("\n== D. 多使用者与返回值边界 ==")
g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)],
               extra_users=[(1, (0, 2, 1))])
before = g.eval()
rounds, applied = run_passes(g, TWO_PATTERNS)
check("D1 中间值多一个消费方：图不动（3 op）且数值不变",
      len(g.ops) == 3 and rounds >= 1 and applied == 0
      and all(np.array_equal(a, b) for a, b in zip(g.eval(), before)))
check("D2 use_count('%t0') == 2（%t1 一个 + %u 一个）", g.use_count("%t0") == 2)

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)], return_tail=True)
g.returns = ["%t1", "%t0"]          # 中间值 %t0 也要导出
before = g.eval()
run_passes(g, TWO_PATTERNS)
check("D3 中间值被 func.return：拒绝（2 op 原样），两个返回值都完好",
      len(g.ops) == 2
      and all(np.array_equal(a, b) for a, b in zip(g.eval(), before)))

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)])
tail_val = g.eval()[0]
run_passes(g, TWO_PATTERNS)
check("D4 消除后返回值个数不变且值不变",
      len(g.returns) == 1 and np.array_equal(g.eval()[0], tail_val))

print("\n== E. PassManager 不动点 ==")
expect = {1: 1, 2: 1, 3: 0, 4: 1, 5: 1, 6: 0, 7: 1, 8: 1}
ok_cnt = 0
for L in range(1, 9):
    g = make_chain((2, 3, 4), [(1, 2, 0)] * L)
    before = g.eval()
    _, applied = run_passes(g, TWO_PATTERNS)
    if (len(g.ops) == expect[L]
            and np.array_equal(g.eval()[0], before[0])
            and (applied >= 1) == (L >= 2)):
        ok_cnt += 1
check(f"E1 3-循环链长 1..8：op 数按 p^L 消长（L mod 3==0 → 0，否则 1），"
      f"数值不变 {ok_cnt}/8", ok_cnt == 8)

g = make_chain((2, 3, 4), [(1, 2, 0)] * 8)
rounds, _ = run_passes(g, TWO_PATTERNS)
check(f"E2 八连链在 max_rounds 内收敛（实际 {rounds} 轮 < 10）", rounds < 10)

g = make_chain((2, 3), [(1, 0)])
ir_before = g.print_ir()
_, applied = run_passes(g, TWO_PATTERNS)
check("E3 无链可配时 0 次应用且 IR 不变", applied == 0
      and g.print_ir() == ir_before)

g = make_chain((2, 3, 4), [(1, 2, 0), (2, 0, 1)])
run_passes(g, TWO_PATTERNS)
ir_once = g.print_ir()
_, applied2 = run_passes(g, TWO_PATTERNS)
check("E4 已优化的图再跑一遍不动（幂等）",
      applied2 == 0 and g.print_ir() == ir_once)

print("\n== F. 判定表与随机压力对拍 ==")
scenes = [
    ("S1  2D TT（对合）",     (2, 3),   [(1, 0), (1, 0)], 0),
    ("S2  2D 恒等对",         (2, 3),   [(0, 1), (1, 0)], 1),
    ("S3  3D 互逆对",         (2, 3, 4), [(1, 2, 0), (2, 0, 1)], 0),
    ("S4  3D 一般对 p=q",     (2, 3, 4), [(1, 2, 0), (1, 2, 0)], 1),
    ("S5  3D 一般对 p≠q",     (2, 3, 4), [(1, 2, 0), (0, 2, 1)], 1),
    ("S6  3D 三连链（阶 3）", (2, 3, 4), [(1, 2, 0)] * 3, 0),
    ("S7  3D 四连链",         (2, 3, 4), [(1, 2, 0)] * 4, 1),
    ("S8  4D 互逆对",         (2, 3, 4, 5), [(3, 2, 1, 0)] * 2, 0),
    ("S9  4D 长链 5 个",      (2, 3, 4, 5), [(1, 2, 3, 0)] * 5, 1),
    ("S10 单转置",            (2, 3),   [(1, 0)], 1),
    ("S11 恒等单转置",        (2, 3),   [(0, 1)], 1),
    ("S12 交错链 4 个",       (2, 3, 4, 5), [(1, 0, 2, 3), (0, 2, 1, 3),
                                             (2, 1, 0, 3), (3, 0, 1, 2)], 1),
]
ok = True
for name, shape, perms, want in scenes:
    g = make_chain(shape, perms)
    before = g.eval()
    run_passes(g, TWO_PATTERNS)
    good = (len(g.ops) == want and np.array_equal(g.eval()[0], before[0])
            and g.verify() == [])
    if not good:
        print(f"  MISMATCH: {name}: got {len(g.ops)} ops, want {want}")
    ok &= good
check(f"F1 判定表 {len(scenes)}/{len(scenes)}：op 数 + 数值 + Verifier", ok)

rand_ok, single_cnt, single_ok = 0, 0, 0
for t in range(300):
    rank = rng.randint(1, 5)
    shape = tuple(rng.randint(1, 5) for _ in range(rank))
    L = rng.randint(1, 5)
    perms = []
    pm0 = list(range(rank))
    for _ in range(L):
        rng.shuffle(pm0)
        perms.append(tuple(pm0))
    g = make_chain(shape, perms)
    before = g.eval()
    run_passes(g, TWO_PATTERNS)
    if (np.array_equal(g.eval()[0], before[0]) and g.verify() == []
            and len(g.ops) <= L):
        rand_ok += 1
    if len(g.ops) == 1:
        single_cnt += 1
        x = g.inputs["%in"]
        cur = x
        for pm in perms:
            cur = np.transpose(cur, pm)
        if np.array_equal(np.transpose(x, g.ops[0].perm), cur):
            single_ok += 1
check(f"F2 随机对拍 {rand_ok}/300：数值不变、Verifier 通过、op 数不增",
      rand_ok == 300)
check(f"F3 合并后剩单转置的 {single_cnt} 组：排列恰好等价整条链",
      single_cnt > 0 and single_ok == single_cnt)

print("\n== G. MLIR 对照（本机 LLVM 18.1.8）==")
mlir_opt = find_mlir_opt()
if mlir_opt is None:
    skip("G1–G5", "mlir-opt 不可用")
else:
    code, canon = run_mlir_opt(linalg_chain_ir(), ["--canonicalize"])
    check("G1 互逆转置对经 --canonicalize 原样保留（2 个 linalg.transpose）",
          code == 0 and canon.count("linalg.transpose") == 2)
    check("G2 canonicalize 输出结构不变（2 个 alloc + return）",
          canon.count("memref.alloc") == 2 and "return" in canon)

    code_l, loops = run_mlir_opt(linalg_chain_ir(),
                                 ["--convert-linalg-to-loops"])
    check("G3 链降级：6 层 scf.for + 2 行 load + 2 行 store（numel×2 访存）",
          code_l == 0 and loops.count("scf.for") == 6
          and loops.count("memref.load") == 2
          and loops.count("memref.store") == 2)

    single = """module {
  func.func @one(%in: memref<2x3x4xf32>) -> memref<3x4x2xf32> {
    %0 = memref.alloc() : memref<3x4x2xf32>
    linalg.transpose ins(%in: memref<2x3x4xf32>) outs(%0: memref<3x4x2xf32>) permutation = [1, 2, 0]
    return %0 : memref<3x4x2xf32>
  }
}
"""
    _, loops1 = run_mlir_opt(single, ["--convert-linalg-to-loops"])
    check("G4 单转置降级：3 层 scf.for + 1 行 load（链白付一整次搬运的对照）",
          loops1.count("scf.for") == 3 and loops1.count("memref.load") == 1)

    here = Path(__file__).resolve().parent
    chain_file = here / "transpose_chain.mlir"
    check("G5 静态 IR 文件 transpose_chain.mlir 存在且非空",
          chain_file.exists() and chain_file.stat().st_size > 0)

print()
print("=" * 60)
print(f"汇总：PASS {PASS} / FAIL {FAIL} / SKIP {SKIP}")
print("=" * 60)
raise SystemExit(0 if FAIL == 0 else 1)
