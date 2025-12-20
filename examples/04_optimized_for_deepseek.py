"""优化配置示例：适配 DeepSeek API"""

import asyncio
import os

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from dotenv import load_dotenv

load_dotenv()

# 增加超时设置
os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] = "180000"  # 3 分钟


async def main():
    """使用优化配置"""
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个助手。用一句话回答。",  # 简短的 prompt
        max_turns=3,  # 限制最大轮次
        max_budget_usd=0.05,  # 限制预算
    )

    print("正在询问 Claude（DeepSeek API）...")
    print("提示：首次查询可能需要 30-60 秒，请耐心等待...\n")

    try:
        async for message in query(prompt="2+2等于几？", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"回复: {block.text}")
        print("\n✓ 查询成功完成")
    except Exception as e:
        print(f"\n✗ 查询失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
