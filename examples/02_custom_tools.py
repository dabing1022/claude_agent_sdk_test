"""工具示例：如何在 Agent 中使用自定义工具（MCP SDK 工具）"""

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLIConnectionError,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from dotenv import load_dotenv

# 加载环境变量(override=True 确保 .env 文件覆盖系统环境变量)
load_dotenv(override=True)


# 使用 @tool 装饰器定义计算器工具
@tool(
    "add",
    "将两个数字相加",
    {"a": float, "b": float}
)
async def add_numbers(args: dict) -> dict:
    """加法工具"""
    result = args["a"] + args["b"]
    return {
        "content": [
            {"type": "text", "text": f"计算结果: {args['a']} + {args['b']} = {result}"}
        ]
    }


@tool(
    "multiply",
    "将两个数字相乘",
    {"a": float, "b": float}
)
async def multiply_numbers(args: dict) -> dict:
    """乘法工具"""
    result = args["a"] * args["b"]
    return {
        "content": [
            {"type": "text", "text": f"计算结果: {args['a']} × {args['b']} = {result}"}
        ]
    }


@tool(
    "subtract",
    "将两个数字相减",
    {"a": float, "b": float}
)
async def subtract_numbers(args: dict) -> dict:
    """减法工具"""
    result = args["a"] - args["b"]
    return {
        "content": [
            {"type": "text", "text": f"计算结果: {args['a']} - {args['b']} = {result}"}
        ]
    }


@tool(
    "divide",
    "将两个数字相除",
    {"a": float, "b": float}
)
async def divide_numbers(args: dict) -> dict:
    """除法工具"""
    if args["b"] == 0:
        return {
            "content": [
                {"type": "text", "text": "错误：除数不能为零"}
            ],
            "is_error": True
        }
    result = args["a"] / args["b"]
    return {
        "content": [
            {"type": "text", "text": f"计算结果: {args['a']} ÷ {args['b']} = {result}"}
        ]
    }


def _is_transport_race_condition(exc: Exception) -> bool:
    """检查是否是传输层关闭时的竞态条件错误（可以安全忽略）"""
    if isinstance(exc, CLIConnectionError):
        return "ProcessTransport is not ready for writing" in str(exc)
    return False


async def main() -> None:
    """运行工具示例"""
    # 创建 SDK MCP 服务器
    calculator_server = create_sdk_mcp_server(
        name="calculator",
        version="1.0.0",
        tools=[add_numbers, multiply_numbers, subtract_numbers, divide_numbers]
    )

    # 配置选项
    options = ClaudeAgentOptions(
        # model 参数留空,使用环境变量 ANTHROPIC_MODEL
        system_prompt="你是一个数学助手。使用提供的计算器工具来进行计算。",
        mcp_servers={"calculator": calculator_server},
        # 允许使用这些工具
        allowed_tools=[
            "mcp__calculator__add",
            "mcp__calculator__multiply",
            "mcp__calculator__subtract",
            "mcp__calculator__divide"
        ]
    )

    print("正在询问 Claude 进行计算...")

    async def wrap_prompt(text):
        yield {"type": "user", "message": {"role": "user", "content": text}}  # noqa: E501
    # 使用 query() 函数查询
    try:
        async for message in query(
            prompt=wrap_prompt("请计算 15.5 乘以 3.2 的结果是多少？"),
            options=options
        ):
            # 打印助手的回复
            print(message)
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print("\nAgent 回复：")
                        print(block.text)

            # 处理结果消息（确保消息流完整处理）
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    print(f"\n[错误] {message.result}")
                else:
                    print(f"\n[完成] 耗时: {message.duration_ms}ms")
                    if message.total_cost_usd:
                        print(f"[成本] ${message.total_cost_usd:.6f}")
    except* Exception as eg:
        # 捕获所有 ExceptionGroup（包括 CLIConnectionError 等）
        # 检查是否只包含预期的传输层竞态条件错误
        transport_errors = [exc for exc in eg.exceptions if _is_transport_race_condition(exc)]

        if len(transport_errors) == len(eg.exceptions):
            print(transport_errors)
            pass
        else:
            # 有其他类型的错误，需要重新抛出
            # 但先尝试提取非传输错误
            other_errors = [exc for exc in eg.exceptions if not _is_transport_race_condition(exc)]
            if other_errors:
                # 如果有其他错误，重新抛出它们
                if len(other_errors) == 1:
                    raise other_errors[0]
                else:
                    # 创建新的 ExceptionGroup 只包含非传输错误
                    raise ExceptionGroup("查询错误", other_errors) from eg
            else:
                raise


if __name__ == "__main__":
    asyncio.run(main())
