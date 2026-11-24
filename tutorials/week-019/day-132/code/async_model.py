#!/usr/bin/env python3
"""第 132 天核心模块：async_model.py——异步与同步模型的教学仿真。

计划条目："画出当前 CPU 实现映射到异步设备执行时的依赖和同步位置；
产出：异步执行示意图和 Compiler/Runtime 分工说明。"——不实现真实驱动。

三个实验（用 Python 线程＋队列仿真 GPU 的 stream/event 语义）：
  E1 同步基线    现状：调用→算→返回（CPU 语义——调用方被阻塞）
  E2 异步仿真    Stream 队列＋异步 launch＋event 同步点
  E3 依赖分析    多 kernel 链的依赖图＋同步点标注

关键概念映射（CPU → 异步设备）：
  函数调用          → Launch（提交到队列，不执行）
  返回值            → Event（完成通知——需要主动等）
  内存池            → 设备内存（生命周期跨 launch——不能提前 release）
  Python 的 GIL     → 无对应（GPU 真并行——数据竞争风险真实存在）
"""
from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass, field

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


# ──────────────────────────────────────────────────────────
# E1：同步基线（CPU 语义——D118~D131 的世界）
# ──────────────────────────────────────────────────────────

def sync_call(kernel, *args):
    """同步调用：提交＝执行＝返回——调用方全程阻塞。"""
    result = kernel(*args)          # 执行在这里发生
    return result                    # 返回时结果已就绪


# ──────────────────────────────────────────────────────────
# E2：异步仿真（Stream/Event 的教学版）
# ──────────────────────────────────────────────────────────

@dataclass
class Event:
    """完成通知：kernel 完成时置位；调用方可以 wait。"""
    name: str
    _set: bool = False
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def set(self):
        with self._cond:
            self._set = True
            self._cond.notify_all()

    def wait(self):
        with self._cond:
            while not self._set:
                self._cond.wait()

    @property
    def is_set(self):
        return self._set


class Stream:
    """命令队列仿真：launch 把 (kernel, args, event) 入队；
    工作线程按序执行——与 GPU stream 的顺序执行语义一致。"""

    def __init__(self, name: str = "stream0"):
        self.name = name
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.launched = 0
        self.completed = 0

    def launch(self, kernel, args, event: Event = None):
        """异步 Launch：立即返回（只入队）；执行在工作线程。"""
        self._q.put((kernel, args, event))
        self.launched += 1
        # 注意：调用方此刻拿不到结果——结果就绪要等 event

    def _worker(self):
        while True:
            kernel, args, event = self._q.get()
            if kernel is None:      # 毒丸退出
                break
            kernel(*args)           # 真实执行（异步于调用方）
            self.completed += 1
            if event:
                event.set()

    def synchronize(self):
        """流同步：等队列清空（cuStreamSynchronize 语义）。"""
        done = Event("sync")
        self._q.put((lambda: None, (), done))
        done.wait()

    def shutdown(self):
        self._q.put((None, (), None))
        self._thread.join(timeout=1)


# ──────────────────────────────────────────────────────────
# 实验
# ──────────────────────────────────────────────────────────

def busy_kernel(ms: float, name: str = ""):
    """模拟耗时 kernel。"""
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) * 1000 < ms:
        pass


def main():
    os.makedirs(OUT, exist_ok=True)

    # ── E1 同步基线 ──
    print("== E1 同步基线：调用＝执行＝返回（CPU 语义）==")
    t0 = time.perf_counter()
    sync_call(lambda: busy_kernel(30, "k1"))
    t1 = time.perf_counter()
    sync_call(lambda: busy_kernel(30, "k2"))
    t2 = time.perf_counter()
    total_sync = (t2 - t0) * 1000
    print(f"  k1: {30}ms ＋ k2: {30}ms ＝ 总 {total_sync:.0f}ms（调用方全程阻塞）")

    # ── E2 异步仿真 ──
    print("\n== E2 异步仿真：launch 立即返回＋event 同步 ==")
    s = Stream("stream0")
    ev1, ev2 = Event("k1_done"), Event("k2_done")

    t0 = time.perf_counter()
    s.launch(busy_kernel, (30, "k1"), ev1)
    t_launch1 = time.perf_counter()
    print(f"  launch k1：耗时 {(t_launch1-t0)*1000:.2f}ms（入队即返回——不等执行）")
    # 调用方此刻可以干别的（仿真：什么都不干，直接等）
    s.launch(busy_kernel, (30, "k2"), ev2)
    t_launch2 = time.perf_counter()
    print(f"  launch k2：又 {(t_launch2-t_launch1)*1000:.2f}ms（同 stream 排队）")
    ev2.wait()                        # 同步点：等最后一个完成
    t_done = time.perf_counter()
    total_async = (t_done - t0) * 1000
    print(f"  两个 30ms kernel 总耗时 {total_async:.0f}ms（stream 内串行——同 GPU 语义）")
    print(f"  launch 开销：{(t_launch2-t0)*1000:.2f}ms vs 执行 {total_async:.0f}ms")
    print(f"  → 调用方从「等 60ms」变「等 0.1ms＋自由 60ms」——异步的全部收益")

    # 双 stream 并行
    s2 = Stream("stream1")
    ev3 = Event("k3_done")
    t0 = time.perf_counter()
    s.launch(busy_kernel, (30, "p1"), ev1)
    s2.launch(busy_kernel, (30, "p2"), ev3)
    ev1.wait(); ev3.wait()
    total_par = (time.perf_counter() - t0) * 1000
    print(f"\n  双 stream 并行：两个 30ms kernel 总 {total_par:.0f}ms（<60ms——真并行）")
    print(f"  → 单 stream 串行、多 stream 并行——GPU 的执行模型")

    # ── E3 依赖与同步点分析 ──
    print("\n== E3 依赖分析：MatMul→Bias→Relu 链的同步点标注 ==")
    # minic 的图（D124）：fused 已融合成一个 kernel——单 stream 无需中间同步
    print("  场景 A（minic 现状·融合后）：")
    print("    fused_kernel [launch] → event → 调用方读结果")
    print("    同步点：1 个（融合把三个算子打进一个 kernel——无中间依赖）")
    print("  场景 B（假想·未融合）：")
    print("    matmul [launch] → event? → bias [launch] → event? → relu [launch] → event")
    print("    依赖：bias 读 matmul 输出、relu 读 bias 输出")
    print("    同一 stream：自动按序——无需显式 event（顺序执行语义保证）")
    print("    跨 stream：必须 event——bias_stream.wait_event(matmul_event)")
    print("  场景 C（池化内存的交互——D131 的伏笔）：")
    print("    release(buf) 必须等读 buf 的最后一个 kernel 完成！")
    print("    → 池的归还语义在异步世界要加 event 依赖——否则数据竞争")
    print()
    print("  Compiler/Runtime 分工（异步版）：")
    print("    Compiler：算子依赖图（静态已知）→ launch 顺序（拓扑序）")
    print("    Runtime ：stream 分配、event 创建/等待、内存生命周期（event 触发 release）")
    print("    调用方 ：最终同步（wait 最后一个 event）＋读结果")

    s.shutdown(); s2.shutdown()
    print("\n  E2 数据汇总：")
    print(f"    同步串行 60ms ｜ 异步单 stream ~60ms（串行）｜ 异步双 stream ~{total_par:.0f}ms（并行）")
    assert total_par < 55, "双 stream 应接近 30ms"
    print("    双 stream 加速比：%.1fx" % (60.0 / total_par))


if __name__ == "__main__":
    main()
