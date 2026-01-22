"""
示例 4: 沙箱执行

演示如何使用沙箱执行服务将 Claude Agent SDK 的工具执行隔离到安全环境中。

需要安装:
    pip install e2b

需要配置:
    设置环境变量 E2B_API_KEY 或在 .env 文件中配置
"""

import asyncio
import os

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 导入沙箱模块
from claude_agent_test.sandbox import (
    SandboxConfig,
    SandboxType,
    SandboxExecutor,
    E2BSandbox,
)
from claude_agent_test.sandbox.config import ResourceLimits, SecurityConfig


async def demo_basic_sandbox():
    """演示基本沙箱使用"""
    print("=" * 60)
    print("演示 1: 基本沙箱使用")
    print("=" * 60)
    
    # 创建配置
    config = SandboxConfig(
        sandbox_type=SandboxType.E2B,
        e2b_api_key=os.environ.get("E2B_API_KEY"),
        resource_limits=ResourceLimits(
            timeout_seconds=30,
            memory_mb=512,
        ),
    )
    
    # 使用沙箱执行器
    async with SandboxExecutor(config) as executor:
        # 执行 Bash 命令
        print("\n1. 执行 Bash 命令:")
        result = await executor.execute_bash("echo 'Hello from sandbox!' && pwd && whoami")
        print(f"   成功: {result.success}")
        print(f"   输出: {result.output}")
        print(f"   耗时: {result.execution_time_ms}ms")
        
        # 写入文件
        print("\n2. 写入文件:")
        result = await executor.write_file(
            "test.txt",
            "这是一个测试文件\n在沙箱中创建"
        )
        print(f"   成功: {result.success}")
        print(f"   输出: {result.output}")
        
        # 读取文件
        print("\n3. 读取文件:")
        result = await executor.read_file("test.txt")
        print(f"   成功: {result.success}")
        print(f"   内容: {result.output}")
        
        # 列出文件
        print("\n4. 列出文件:")
        result = await executor.list_files(".")
        print(f"   成功: {result.success}")
        print(f"   文件列表:\n{result.output}")
        
        # 搜索文件
        print("\n5. 搜索文件内容:")
        result = await executor.search_files("测试", ".")
        print(f"   成功: {result.success}")
        print(f"   搜索结果: {result.output}")
        
        # 获取审计日志
        print("\n6. 审计日志:")
        logs = executor.get_audit_logs()
        for log in logs:
            print(f"   [{log['timestamp']}] {log['tool_name']}: "
                  f"{'成功' if log['success'] else '失败'}")


async def demo_security_validation():
    """演示安全验证"""
    print("\n" + "=" * 60)
    print("演示 2: 安全验证")
    print("=" * 60)
    
    # 创建带安全限制的配置
    config = SandboxConfig(
        sandbox_type=SandboxType.E2B,
        e2b_api_key=os.environ.get("E2B_API_KEY"),
        security=SecurityConfig(
            # 命令黑名单
            command_blacklist=[
                r"rm\s+-rf",
                r"sudo",
            ],
            enable_audit_log=True,
        ),
    )
    
    async with SandboxExecutor(config) as executor:
        # 尝试执行危险命令
        print("\n1. 尝试执行危险命令 (rm -rf /):")
        result = await executor.execute_bash("rm -rf /")
        print(f"   成功: {result.success}")
        print(f"   错误: {result.error}")
        
        # 尝试执行 sudo 命令
        print("\n2. 尝试执行 sudo 命令:")
        result = await executor.execute_bash("sudo apt update")
        print(f"   成功: {result.success}")
        print(f"   错误: {result.error}")
        
        # 执行安全命令
        print("\n3. 执行安全命令:")
        result = await executor.execute_bash("ls -la")
        print(f"   成功: {result.success}")
        print(f"   输出 (前 200 字符): {result.output[:200]}...")


async def demo_direct_sandbox_usage():
    """演示直接使用 E2B 沙箱"""
    print("\n" + "=" * 60)
    print("演示 3: 直接使用 E2B 沙箱")
    print("=" * 60)
    
    config = SandboxConfig(
        sandbox_type=SandboxType.E2B,
        e2b_api_key=os.environ.get("E2B_API_KEY"),
        working_directory="/home/user/project",
    )
    
    # 使用上下文管理器
    async with E2BSandbox(config) as sandbox:
        print(f"\n沙箱 ID: {sandbox.sandbox_id}")
        
        # 执行多个命令
        commands = [
            "python --version",
            "pip --version",
            "node --version 2>/dev/null || echo 'Node not installed'",
            "echo $PATH",
        ]
        
        for cmd in commands:
            result = await sandbox.execute_bash(cmd)
            print(f"\n$ {cmd}")
            print(f"  {result.output.strip()}")


async def demo_with_claude_agent_sdk():
    """
    演示与 Claude Agent SDK 集成
    
    注意：此示例需要安装 claude-agent-sdk 并配置 ANTHROPIC_API_KEY
    """
    print("\n" + "=" * 60)
    print("演示 4: 与 Claude Agent SDK 集成")
    print("=" * 60)
    
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query, AssistantMessage, TextBlock
    except ImportError:
        print("  跳过：未安装 claude-agent-sdk")
        return
    
    # 检查 API Key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  跳过：未配置 ANTHROPIC_API_KEY")
        return
    
    # 创建沙箱配置
    sandbox_config = SandboxConfig(
        sandbox_type=SandboxType.E2B,
        e2b_api_key=os.environ.get("E2B_API_KEY"),
        security=SecurityConfig(
            enable_audit_log=True,
        ),
    )
    
    # 创建沙箱执行器
    async with SandboxExecutor(sandbox_config) as executor:
        # 获取工具回调
        tool_callback = executor.get_tool_callback()
        
        # 创建 Claude Agent SDK 选项
        options = ClaudeAgentOptions(
            system_prompt="你是一个代码助手。所有代码执行都在安全沙箱中进行。",
            can_use_tool=tool_callback,  # 使用沙箱工具回调
        )
        
        print("\n正在与 Claude 交互...")
        
        # 发送查询
        async for message in query(
            prompt="请执行一个简单的 Python 命令来打印 'Hello from Sandbox!'",
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"\nClaude: {block.text}")
        
        # 显示审计日志
        print("\n审计日志:")
        for log in executor.get_audit_logs():
            print(f"  [{log['tool_name']}] 成功={log['success']}, 耗时={log['execution_time_ms']}ms")


async def main():
    """主函数"""
    print("沙箱执行示例")
    print("=" * 60)
    
    # 检查 E2B API Key
    if not os.environ.get("E2B_API_KEY"):
        print("\n警告: 未设置 E2B_API_KEY 环境变量")
        print("请在 .env 文件中添加:")
        print("  E2B_API_KEY=your-api-key")
        print("\n或者设置环境变量:")
        print("  export E2B_API_KEY=your-api-key")
        print("\n可以在 https://e2b.dev 获取 API Key")
        return
    
    try:
        # 运行演示
        await demo_basic_sandbox()
        await demo_security_validation()
        await demo_direct_sandbox_usage()
        await demo_with_claude_agent_sdk()
        
    except Exception as e:
        print(f"\n错误: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
