"""改进的基础示例：带进度提示和性能监控"""

import asyncio
import time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)


async def main() -> None:
    """运行带进度提示的示例"""
    start_time = time.time()

    # 配置选项
    options = ClaudeAgentOptions(
        model="deepseek-chat",
        # model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个有帮助的助手，专注于准确性。",
    )

    print("=" * 60)
    print("Claude Agent SDK - 基础示例（带进度提示）")
    print("=" * 60)
    print(f"[{time.time() - start_time:.2f}s] 开始初始化...")

    # 使用 query() 函数进行简单查询
    message_count = 0
    init_done = False

    async for message in query(prompt="什么是 2 + 2？", options=options):
        elapsed = time.time() - start_time
        message_type = type(message).__name__

        if not init_done:
            print(f"[{elapsed:.2f}s] ✓ 初始化完成，开始处理请求")
            init_done = True

        message_count += 1
        # 调试：打印收到的每条消息类型
        print(f"[{elapsed:.2f}s] 收到消息 #{message_count}: {message_type}")

        # 打印助手的文本回复
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"\n{'─' * 60}")
                    print("Agent 回复：")
                    print(f"{'─' * 60}")
                    print(block.text)
                    print(f"{'─' * 60}")

        # 打印结果消息
        elif isinstance(message, ResultMessage):
            print("\n[统计信息]")
            print(f"  • 总耗时: {message.duration_ms}ms ({message.duration_ms/1000:.2f}s)")
            print(f"  • API 耗时: {message.duration_api_ms}ms ({message.duration_api_ms/1000:.2f}s)")
            print(f"  • 对话轮次: {message.num_turns}")
            if message.total_cost_usd:
                print(f"  • API 成本: ${message.total_cost_usd:.6f}")
            if message.usage:
                print(f"  • Token 使用: {message.usage}")

        # 对于其他类型的消息，也打印基本信息（调试用）
        else:
            print(f"  [调试] 收到其他类型消息: {message_type}")

    total_time = time.time() - start_time
    print(f"\n[{total_time:.2f}s] 完成！共处理 {message_count} 条消息")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
