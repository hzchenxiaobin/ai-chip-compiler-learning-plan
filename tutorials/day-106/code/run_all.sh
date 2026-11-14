#!/usr/bin/env bash
# 第 106 天一键复现：搜索空间主表 + shape 对照 + 预算扫描 + 自检 + 环境
set -e
cd "$(dirname "$0")"
mkdir -p outputs

echo "==> 1/4 主交付物：512³ fp32 搜索空间（轴表 + naive 反面教材 + 漏斗 + 幸存者统计 + 全表）"
python3 search_space.py --exp table --outdir outputs | tee outputs/space-table.txt

echo ""
echo "==> 2/4 shape 对照：512 走整除模式，516 逼出尾部模式"
python3 search_space.py --exp shape | tee outputs/shape-516.txt

echo ""
echo "==> 3/4 预算扫描：预算收紧时幸存者怎么变"
python3 search_space.py --exp sweep | tee outputs/budget-sweep.txt

echo ""
echo "==> 4/4 断言自检（53 项）"
python3 search_space.py --exp self-test | tee outputs/test-all.txt

{
  echo "环境：$(python3 -c 'import search_space; print(search_space.env_line())')"
  echo "硬件参数为示例值：SRAM 预算 256 KiB、DMA 对齐 32 B；记账规则与 D101/D104 逐数字一致"
  echo "输出均为确定性生成器在本次运行中的真实计算结果，不是实测性能数据"
} > outputs/env.txt

echo ""
echo "全部完成。记录见 outputs/：space-table / shape-516 / budget-sweep / test-all / env / candidates"
