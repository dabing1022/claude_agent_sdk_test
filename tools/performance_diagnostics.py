"""性能诊断工具：分析 SDK 各阶段耗时"""

import asyncio
import os
import time
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    query,
)
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self.start_time = time.time()
        self.checkpoints = []

    def checkpoint(self, name: str):
        """记录检查点"""
        elapsed = time.time() - self.start_time
        self.checkpoints.append((name, elapsed))
        print(f"[{elapsed:7.2f}s] {name}")

    def summary(self):
        """打印总结"""
        print("\n" + "=" * 70)
        print("性能分析总结")
        print("=" * 70)

        if len(self.checkpoints) < 2:
            print("检查点不足，无法生成总结")
            return

        for i in range(len(self.checkpoints) - 1):
            name1, time1 = self.checkpoints[i]
            name2, time2 = self.checkpoints[i + 1]
            duration = time2 - time1
            print(f"{name1} → {name2}: {duration:.2f}s")

        total = self.checkpoints[-1][1] - self.checkpoints[0][1]
        print(f"\n总耗时: {total:.2f}s")
        print("=" * 70)


async def diagnose_sdk():
    """诊断 SDK 性能"""
    profiler = PerformanceProfiler()

    print("=" * 70)
    print("Claude Agent SDK 性能诊断工具")
    print("=" * 70)
    print()

    profiler.checkpoint("开始")

    # 检查环境
    profiler.checkpoint("检查环境变量")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    print(f"  • API Key: {'已设置 (' + api_key[:10] + '...)' if api_key else '未设置'}")
    print(f"  • Base URL: {base_url or '使用默认'}")
    print(f"  • 工作目录: {os.getcwd()}")
    print()

    # 检查 CLI 二进制
    profiler.checkpoint("检查 CLI 二进制")
    venv_path = Path(".venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude")
    if venv_path.exists():
        size_mb = venv_path.stat().st_size / (1024 * 1024)
        print(f"  • CLI 路径: {venv_path}")
        print(f"  • CLI 大小: {size_mb:.1f} MB")
    else:
        print(f"  ✗ CLI 未找到: {venv_path}")
    print()

    # 创建配置
    profiler.checkpoint("创建配置")
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个助手。",
    )

    # 开始查询
    profiler.checkpoint("开始查询（启动 CLI 子进程）")

    message_types = []
    first_message_time = None

    async for message in query(prompt="说'Hi'", options=options):
        msg_type = type(message).__name__

        if first_message_time is None:
            first_message_time = time.time()
            profiler.checkpoint(f"收到第一条消息 ({msg_type})")

        message_types.append(msg_type)

        # 详细记录不同类型的消息
        if isinstance(message, SystemMessage):
            profiler.checkpoint(f"系统消息: {message.subtype}")

        elif isinstance(message, AssistantMessage):
            text_blocks = sum(1 for b in message.content if isinstance(b, TextBlock))
            profiler.checkpoint(f"助手回复 (包含 {text_blocks} 个文本块)")

            # 打印回复内容
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"\n  回复内容: {block.text[:100]}...")

        elif isinstance(message, ResultMessage):
            profiler.checkpoint("收到结果消息")
            print(f"\n  • API 耗时: {message.duration_api_ms}ms")
            print(f"  • 总耗时: {message.duration_ms}ms")
            print(f"  • 对话轮次: {message.num_turns}")

    profiler.checkpoint("查询完成")

    # 打印消息类型统计
    print(f"\n消息类型统计:")
    from collections import Counter

    for msg_type, count in Counter(message_types).items():
        print(f"  • {msg_type}: {count}")

    # 打印总结
    profiler.summary()

    # 分析瓶颈
    print("\n" + "=" * 70)
    print("瓶颈分析")
    print("=" * 70)

    if len(profiler.checkpoints) >= 4:
        _, start_time = profiler.checkpoints[2]  # "开始查询"
        _, first_msg_time = profiler.checkpoints[3]  # "收到第一条消息"

        cli_startup_time = first_msg_time - start_time

        print(f"CLI 启动耗时: {cli_startup_time:.2f}s")

        if cli_startup_time > 5:
            print("  ⚠️  CLI 启动较慢（>5秒），这是主要瓶颈")
            print("     原因: 闭源 CLI 二进制较大（174MB），加载需要时间")
            print("     建议: 这是正常现象，无法优化")
        elif cli_startup_time > 2:
            print("  ℹ️  CLI 启动时间适中（2-5秒）")
        else:
            print("  ✓ CLI 启动快速（<2秒）")

    print("=" * 70)


async def main():
    """主函数"""
    try:
        await diagnose_sdk()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
