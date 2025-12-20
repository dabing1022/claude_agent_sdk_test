"""异步示例：使用 ClaudeSDKClient 进行双向交互和流式响应"""

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def main() -> None:
    """运行异步流式示例"""
    # 配置选项
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个有帮助的助手。请用简洁的方式回答问题。",
    )

    print("正在连接到 Claude...")
    print("-" * 50)

    # 使用 ClaudeSDKClient 进行双向交互
    async with ClaudeSDKClient(options) as client:
        # 第一个问题
        print("\n【问题 1】Python 的主要特点是什么？\n")
        await client.query("请用三句话介绍 Python 编程语言的主要特点。")

        # 接收响应
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print(f"\n[完成] 耗时: {message.duration_ms}ms")
                if message.total_cost_usd:
                    print(f"[成本] ${message.total_cost_usd:.6f}")

        # 第二个问题（展示双向交互能力）
        print("\n" + "-" * 50)
        print("\n【问题 2】什么是异步编程？\n")
        await client.query("请用两句话解释什么是异步编程。")

        # 接收第二个响应
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print(f"\n[完成] 耗时: {message.duration_ms}ms")
                if message.total_cost_usd:
                    print(f"[成本] ${message.total_cost_usd:.6f}")

    print("\n" + "-" * 50)
    print("会话结束")


if __name__ == "__main__":
    asyncio.run(main())
