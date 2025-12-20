"""简单测试：验证 SDK 基本功能"""

import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=== 环境变量检查 ===")
print(f"ANTHROPIC_API_KEY: {'已设置' if os.getenv('ANTHROPIC_API_KEY') else '未设置'}")
print(f"ANTHROPIC_BASE_URL: {os.getenv('ANTHROPIC_BASE_URL', '未设置')}")
print(f"ANTHROPIC_MODEL: {os.getenv('ANTHROPIC_MODEL', '未设置')}")

async def test_import():
    """测试导入"""
    print("\n=== 测试导入 ===")
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
        print("✓ 导入成功")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False

async def test_simple_query():
    """测试简单查询"""
    print("\n=== 测试简单查询 ===")
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        options = ClaudeAgentOptions(
            model="claude-sonnet-4-5-20250929",
            system_prompt="你是一个助手。",
        )

        print("开始查询...")
        count = 0
        async for message in query(prompt="说'你好'", options=options):
            count += 1
            print(f"收到消息 #{count}: {type(message).__name__}")

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"回复: {block.text}")

            # 限制只处理前5条消息，避免无限等待
            if count >= 10:
                print("达到消息限制，停止")
                break

        print("✓ 查询完成")
        return True
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("Claude Agent SDK 测试\n")

    if not await test_import():
        return

    await test_simple_query()

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())
