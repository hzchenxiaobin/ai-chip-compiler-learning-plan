#!/usr/bin/env bash
# 第 105 天一键复现：旅程故事 + 对照实验 + 本周测试 + 自检 + 环境
set -e
cd "$(dirname "$0")"
mkdir -p outputs

echo "==> 1/5 主交付物：一个 Tile 的一生（默认配置 64³ fp32 double）"
python3 tile_story.py                 | tee outputs/story.txt

echo ""
echo "==> 2/5 对照实验一：tile 128 ——旅程在闸门被拦下"
python3 tile_story.py --tile 128      | tee outputs/gate-128.txt

echo ""
echo "==> 3/5 对照实验二：退单缓冲——S2 距离回到 1，轮流值班"
python3 tile_story.py --buffering single | tee outputs/buffering-single.txt

echo ""
echo "==> 4/5 本周测试：样例答卷判分 + 参考答案"
python3 weekly_test.py --demo        | tee outputs/weekly-test.txt
python3 weekly_test.py --explain     >> outputs/weekly-test.txt

echo ""
echo "==> 5/5 断言自检（35 项）"
python3 tile_story.py --self-test    | tee outputs/test-all.txt

{
  echo "环境：$(python3 -c 'import tile_story; print(tile_story.env_line())')"
  echo "硬件参数为示例值：DMA 32,768 B/µs、计算 262,144 MAC/µs、SRAM 预算 256 KiB、对齐 32 B"
  echo "输出均为确定性模型在本次运行中的真实计算结果，不是实测性能数据。"
} > outputs/env.txt

echo ""
echo "全部完成。记录见 outputs/：story / gate-128 / buffering-single / weekly-test / test-all / env"
