#!/usr/bin/env bash
# 第 47 天（常量折叠）一键重放：
#   1. 构建带 fold + materializeConstant 的 mini-opt
#   1b. 改动半径收据（相对 Day 46 的 mini 工程）
#   2. 正例 FileCheck：标量/张量/splat、级联、IEEE 边角、流水线接力、uniquing
#   3. 负例 FileCheck：入口参数/relu 结果/类型护栏/尺寸护栏（IR 一律不许变）
#   4. uniquing vs -cse 对照：fold 的去重一次到位，Pattern 路线要补跑 CSE
#   5. 上游 arith 探针：addf 的同款折叠与同款去重
#   6. 对照实验 A：删掉类型护栏 → 静默产出空常量 dense<>（rc=0，比报错更隐蔽）
#   7. 对照实验 B：忘开 hasFolder → 构建失败（无主函数）
#   8. 对照实验 C：不实现 materializeConstant → fold 静默失效
#   9. 编译期开销压测：1024 元素 vs 4096 元素，默认版 vs 放开版真实计时
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools）、
#       cmake 3.20.5 + Ninja、g++ 9.4、Python3 —— 与 Day 29/37~46 记录一致
# 用法：bash run_all.sh              # 在本目录执行
#   构建目录默认 /tmp/day047/build，可用环境变量 DAY047_BUILD 覆盖
#   变体与压测的临时目录默认 /tmp/day047，可用 DAY047_TMP 覆盖
#   （例如 DAY047_BUILD=/tmp/opencode/day047/build \
#          DAY047_TMP=/tmp/opencode/day047 bash run_all.sh）
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="${DAY047_BUILD:-/tmp/day047/build}"
TMP="${DAY047_TMP:-/tmp/day047}"
MINI_SRC="$HERE/mini"
MINI_OPT="$BUILD/bin/mini-opt"
FCK=$(command -v FileCheck-18 || command -v FileCheck)

mkdir -p "$TMP" "$(dirname "$BUILD")"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

run_check() {  # run_check <extra-args> <file>：mini-opt 跑文件，输出交 FileCheck
  local args=$1 f=$2
  if "$MINI_OPT" $args "$HERE/$f" 2>&1 | "$FCK" "$HERE/$f"; then
    echo "[$f] FileCheck 通过 (rc=0)"
  else
    echo "[$f] FileCheck 失败 (rc=$?)"
  fi
}

# 变体构建：copy 源码 → 打补丁 → 配置 + 构建，返回 rc
build_variant() {  # build_variant <name> <patch-script>
  local name=$1 patch=$2
  rm -rf "$TMP/mini-$name"
  cp -r "$MINI_SRC" "$TMP/mini-$name"
  if ! (cd "$TMP/mini-$name" && bash -c "$patch"); then
    echo "补丁应用失败：$name"
    return 1
  fi
  cmake -G Ninja -B "$TMP/build-$name" -S "$TMP/mini-$name" \
        -DCMAKE_BUILD_TYPE=Release \
        -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > "$TMP/configure-$name.log" 2>&1
  cmake --build "$TMP/build-$name" > "$TMP/build-$name.log" 2>&1
  return $?
}

# 计时器：同一命令跑 3 次取中位数（/usr/bin/time 不一定存在，用 python3）
timeit() {
  python3 - "$@" <<'PYEOF'
import subprocess, sys, time, statistics
cmd = sys.argv[1:]
times = []
for _ in range(3):
    t0 = time.perf_counter()
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    times.append(time.perf_counter() - t0)
    assert r.returncode == 0, f"rc={r.returncode}"
print(f"median={statistics.median(times):.3f}s  runs={[f'{t:.3f}' for t in times]}")
PYEOF
}

banner "0/9 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1
ninja --version
g++ --version | head -1
python3 --version

banner "1/9 构建：带 fold + materializeConstant 的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"

banner "1b/9 改动半径收据（相对 Day 46 的 mini 工程）"
if [ -d "$HERE/../../day-046/code/mini" ]; then
  diff -rq "$HERE/../../day-046/code/mini" "$MINI_SRC" || true
fi

banner "2/9 正例：常量碰常量折成新常量（FileCheck）"
run_check -canonicalize add_fold_basic.mlir
run_check -canonicalize add_fold_cascade.mlir
run_check -canonicalize add_fold_edges.mlir
run_check -canonicalize add_fold_pipeline.mlir
run_check -canonicalize add_fold_uniquing.mlir
echo "--- uniquing_pattern_style.mlir：手工摆出 Pattern 路线的结果（CHECK-COUNT-2 个常量）---"
run_check "" uniquing_pattern_style.mlir

banner "3/9 负例：护栏各拦一个，IR 一个字节不许变（FileCheck）"
run_check -canonicalize add_fold_safety.mlir

banner "4/9 uniquing vs -cse 对照：数 mini.constant 节点"
echo "--- (1) 手工 Pattern 风格结果（两个 dense<3.0>），不跑 Pass ---"
"$MINI_OPT" uniquing_pattern_style.mlir | grep -c mini.constant
echo "--- (2) 同文件 -cse：CSE 把两个相同常量合并 ---"
"$MINI_OPT" -cse uniquing_pattern_style.mlir | grep -c mini.constant
echo "--- (3) 同文件 -canonicalize：fold 的 uniquing 一次到位 ---"
"$MINI_OPT" -canonicalize uniquing_pattern_style.mlir | grep -c mini.constant
echo "--- (4) 原 uniquing 用例（两条 add 都折出 3.0）-canonicalize ---"
"$MINI_OPT" -canonicalize add_fold_uniquing.mlir | grep -c mini.constant

banner "5/9 上游 arith 探针：addf 的同款折叠与同款去重"
mlir-opt-18 -canonicalize arith_probe.mlir

banner "6/9 对照实验 A：删掉类型护栏 → 静默产出空常量（约 1 分钟构建）"
if build_variant noguard "python3 - <<'EOF'
s = open('lib/AddFold.cpp').read()
guard = '''  if (getRes().getType() != getLhs().getType() ||
      getRes().getType() != getRhs().getType())
    return {};
'''
assert guard in s
open('lib/AddFold.cpp', 'w').write(s.replace(guard, ''))
EOF"; then
  echo "--- 无护栏版 -canonicalize add_fold_safety.mlir（盯 @typeguard）---"
  "$TMP/build-noguard/bin/mini-opt" -canonicalize add_fold_safety.mlir; echo "rc=$?"
  echo "--- 对照：正确版同文件同命令，@typeguard 的 add 原样保留 ---"
  "$MINI_OPT" -canonicalize add_fold_safety.mlir | grep -A3 "@typeguard"
else
  echo "变体构建失败（见 $TMP/build-noguard.log）"
fi

banner "7/9 对照实验 B：忘开 hasFolder → 无主函数，构建失败（约 1 分钟）"
if build_variant nofolder "python3 - <<'EOF'
s = open('include/mini/MiniOps.td').read()
old = '''    let hasFolder = 1;

    let arguments = (ins
      Mini_F32Tensor:\$lhs,
      Mini_F32Tensor:\$rhs
    );'''
new = '''    let arguments = (ins
      Mini_F32Tensor:\$lhs,
      Mini_F32Tensor:\$rhs
    );'''
assert old in s
open('include/mini/MiniOps.td', 'w').write(s.replace(old, new))
EOF"; then
  echo "意外：无开关版本竟然构建成功"
else
  echo "构建以 rc=1 终止，报错原文："
  grep -m1 -A3 "error:" "$TMP/build-nofolder.log"
fi

banner "8/9 对照实验 C：不实现 materializeConstant → fold 静默失效（约 1 分钟）"
if build_variant nomat "python3 - <<'EOF'
s = open('lib/MiniDialect.cpp').read()
s = s[:s.index('//===----------------------------------------------------------------------===//\n// 第 47 天：常量物化')]
open('lib/MiniDialect.cpp', 'w').write(s)
t = open('include/mini/MiniDialect.td').read()
i = t.index('    // 第 47 天：常量物化钩子。')
j = t.index('}];', i) + len('}];')
open('include/mini/MiniDialect.td', 'w').write(t[:i] + t[j:])
EOF"; then
  echo "--- 无物化钩子版 -canonicalize add_fold_basic.mlir：数 mini.add 行数 ---"
  "$TMP/build-nomat/bin/mini-opt" -canonicalize add_fold_basic.mlir | grep -c mini.add
  echo "（正确版同命令应为 0：全部折掉）"
else
  echo "变体构建失败（见 $TMP/build-nomat.log）"
fi

banner "9/9 编译期开销压测：尺寸护栏值不值（各跑 3 次取中位数）"
python3 gen_stress.py --funcs 500 --dim 32 -o "$TMP/stress_small.mlir"
python3 gen_stress.py --funcs 500 --dim 64 -o "$TMP/stress_big.mlir"
echo "--- (1) 默认版（kMaxFoldElements=1024）x stress_small（500 个 32x32=1024 元素，允许折叠）---"
timeit "$MINI_OPT" -canonicalize "$TMP/stress_small.mlir" -o "$TMP/small_canon.mlir"
echo "    mini.add 剩余：$(grep -c mini.add "$TMP/small_canon.mlir" || true)"
echo "--- (2) 默认版 x stress_big（500 个 64x64=4096 元素，被尺寸护栏拒绝）---"
timeit "$MINI_OPT" -canonicalize "$TMP/stress_big.mlir" -o "$TMP/big_canon.mlir"
echo "    mini.add 剩余：$(grep -c mini.add "$TMP/big_canon.mlir" || true)"
if build_variant bigfold "sed -i 's/constexpr int64_t kMaxFoldElements = 1024;/constexpr int64_t kMaxFoldElements = 1000000;/' lib/AddFold.cpp"; then
  echo "--- (3) 放开版（kMaxFoldElements=1000000）x stress_small ---"
  timeit "$TMP/build-bigfold/bin/mini-opt" -canonicalize "$TMP/stress_small.mlir" -o "$TMP/small_bigfold.mlir"
  echo "    mini.add 剩余：$(grep -c mini.add "$TMP/small_bigfold.mlir" || true)"
  echo "--- (4) 放开版 x stress_big（这次真折：500 x 4096 个元素）---"
  timeit "$TMP/build-bigfold/bin/mini-opt" -canonicalize "$TMP/stress_big.mlir" -o "$TMP/big_bigfold.mlir"
  echo "    mini.add 剩余：$(grep -c mini.add "$TMP/big_bigfold.mlir" || true)"
fi
echo "读数口径：500 个函数各一条 add；(2) 与 (4) 的时间差就是折 500x4096 个元素的真实编译期代价。"
