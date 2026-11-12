#!/usr/bin/env bash
# 第 34 天一键重放：构建 Standalone 示例并重放全部实验
# 环境：Ubuntu 20.04 (arm64)、LLVM/MLIR 18.1.8（mlir-18-tools + libmlir-18-dev + llvm-18-dev）
# 用法：bash run_all.sh          # 完整重放（构建 + 8 组实验 + 修改验证闭环）
#       DAY034_BUILD=... 指定构建目录（默认 /tmp/day034-build）
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/standalone"
BUILD="${DAY034_BUILD:-/tmp/day034-build}"
OPT="$BUILD/bin/standalone-opt"
MLIR_DIR="/usr/lib/llvm-18/lib/cmake/mlir"
LIT_BIN="$(command -v lit || true)"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

# ── 实验⑧的改动手印：结束（或中途出错）时一律还原，交付的源码树保持上游原状 ──
M_CPP="$SRC/lib/Standalone/StandalonePasses.cpp"
M_TD="$SRC/include/Standalone/StandalonePasses.td"
M_T1="$SRC/test/Standalone/standalone-plugin.mlir"
M_T2="$SRC/test/Standalone/standalone-pass-plugin.mlir"
restore_mods() {
  for f in "$M_CPP" "$M_TD" "$M_T1" "$M_T2"; do [ -f "$f.orig" ] && mv "$f.orig" "$f"; done
}
trap restore_mods EXIT

banner "0/8 环境检查"
test -f "$MLIR_DIR/MLIRConfig.cmake" || { echo "缺少 $MLIR_DIR（先安装 libmlir-18-dev llvm-18-dev）"; exit 1; }
echo "MLIR_DIR=$MLIR_DIR"
echo "lit=$LIT_BIN"

banner "1/8 配置并构建 Standalone 示例工程"
test -f "$BUILD/build.ninja" || cmake -G Ninja -S "$SRC" -B "$BUILD" \
  -DMLIR_DIR="$MLIR_DIR" \
  -DLLVM_EXTERNAL_LIT="$LIT_BIN"
ninja -C "$BUILD" || exit 1
echo "构建产物：$(ls "$BUILD/bin")"

banner "2/8 工具的方言注册表：--show-dialects"
"$OPT" --show-dialects | grep -o 'standalone' && echo "(standalone 已注册：解析器认识 standalone.*)"

banner "3/8 算子 round-trip：standalone.foo"
"$OPT" "$HERE/foo_demo.mlir"

banner "4/8 报错探针：解析器拦截 vs op 自己的 Verifier"
err=$("$OPT" "$HERE/foo_bad_type.mlir" 2>&1 || true)
echo "(4a) foo_bad_type.mlir：块参数声明 i32 却按 i64 用 —— 解析器当场拦下："
first=$(printf '%s\n' "$err" | grep "error:" | head -n1)
[ -n "$first" ] && printf '%s\n' "$first" || echo "(预期 error 未出现)"
err=$("$OPT" "$HERE/foo_bad_verifier.mlir" 2>&1 || true)
echo "(4b) foo_bad_verifier.mlir：参数本来就是 i64，语法自洽 —— 这次由 op 的 Verifier 报错："
first=$(printf '%s\n' "$err" | grep "error:" | head -n1)
[ -n "$first" ] && printf '%s\n' "$first" || echo "(预期 error 未出现)"

banner "5/8 运行示例自带 Pass：standalone-switch-bar-foo"
"$OPT" "$HERE/bar_to_foo.mlir" --pass-pipeline="builtin.module(standalone-switch-bar-foo)"

banner "6/8 官方 lit 测试：check-standalone"
if [ -n "$LIT_BIN" ]; then
  ninja -C "$BUILD" check-standalone 2>&1 | grep -E "Passed|Failed|Unsupported|Total"
else
  echo "未安装 lit（pip install lit==18.1.8），退回手工 FileCheck："
  "$OPT" --show-dialects | FileCheck-18 --check-prefix=NONE /dev/null 2>/dev/null || true
  "$OPT" "$SRC/test/Standalone/standalone-plugin.mlir" >/dev/null && echo "standalone-plugin.mlir round-trip OK"
fi

banner "7/8 插件机制：系统 mlir-opt-18 动态加载 StandalonePlugin.so"
if [ -f "$BUILD/lib/StandalonePlugin.so" ]; then
  mlir-opt-18 "$HERE/bar_to_foo.mlir" \
    --load-dialect-plugin="$BUILD/lib/StandalonePlugin.so" \
    --pass-pipeline="builtin.module(standalone-switch-bar-foo)"
else
  echo "StandalonePlugin.so 未构建（跳过）"
fi

banner "8/8 修改输出文本并重新验证（foo→qux 闭环）"
cp "$M_CPP" "$M_CPP.orig"; cp "$M_TD" "$M_TD.orig"; cp "$M_T1" "$M_T1.orig"; cp "$M_T2" "$M_T2.orig"
echo "(8a) 修改 Pass：setSymName(\"foo\")→\"qux\"，.td summary 同步"
sed -i 's/op.setSymName("foo")/op.setSymName("qux")/' "$M_CPP"
sed -i 's/named `bar` to `foo`/named `bar` to `qux`/g' "$M_TD"
ninja -C "$BUILD" >/dev/null
echo "(8b) 重编译后重跑："
"$OPT" "$HERE/bar_to_foo.mlir" --pass-pipeline="builtin.module(standalone-switch-bar-foo)" | grep "func.func @"
echo "(8c) --help 里的 pass 说明也变了："
"$OPT" --help 2>&1 | grep "standalone-switch"
echo "(8d) 但旧测试开始失败（CHECK 还在等 @foo）："
ninja -C "$BUILD" check-standalone 2>&1 | grep -E "FAIL:|Failed Tests|Failed     :|Passed" || true
echo "(8e) 把 CHECK 里的 @foo 更新为 @qux，测试恢复绿："
sed -i 's/CHECK-LABEL: func @foo()/CHECK-LABEL: func @qux()/' "$M_T1" "$M_T2"
ninja -C "$BUILD" check-standalone 2>&1 | grep -E "Passed|Failed|Unsupported"
echo "(8f) 还原上游原状并确认基线："
restore_mods
ninja -C "$BUILD" >/dev/null
"$OPT" "$HERE/bar_to_foo.mlir" --pass-pipeline="builtin.module(standalone-switch-bar-foo)" | grep "func.func @"
ninja -C "$BUILD" check-standalone 2>&1 | grep -E "Passed|Failed|Unsupported"

banner "重放完成"
