"""基础示例：Claude Agent SDK 的基本使用"""

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

async def main() -> None:
    """运行基础示例"""
    # 配置选项
    options = ClaudeAgentOptions(
        # model="deepseek-chat",
        # model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个有帮助的助手，专注于准确性。",
    )

    print("正在询问 Claude...")

    # 使用 query() 函数进行简单查询
    async for message in query(prompt="什么是 2 + 2？", options=options):
        # 打印 AssistantMessage 的所有细节
        if isinstance(message, AssistantMessage):
            print("\nAgent AssistantMessage 回复详情：")
            print("完整对象:", message)
            print("角色:", getattr(message, 'role', None))
            print("内容 blocks 列表:")
            for i, block in enumerate(message.content):
                print(f"  Block {i}: {block}")
                if isinstance(block, TextBlock):
                    print("    类型: TextBlock")
                    print("    文本内容:", block.text)
        else:
            # 打印其它类型消息
            print("\n收到非 AssistantMessage 类型：", type(message))
            print("内容：", message)


if __name__ == "__main__":
    asyncio.run(main())
