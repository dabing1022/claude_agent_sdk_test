"""
示例 4: 沙箱执行

演示如何使用沙箱执行服务将 Claude Agent SDK 的工具执行隔离到安全环境中。

需要安装:
    pip install e2b

需要配置:
    设置环境变量 E2B_API_KEY 或在 .env 文件中配置
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

# 配置 logging 以便查看沙箱操作日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 加载环境变量
load_dotenv(override=True)

# 导入沙箱模块
from claude_agent_test.sandbox import (  # noqa: E402
    E2BSandbox,
    SandboxConfig,
    SandboxExecutor,
    SandboxType,
)
from claude_agent_test.sandbox.config import ResourceLimits, SecurityConfig  # noqa: E402


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
            "python3 --version",
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
    演示与 Claude Agent SDK 集成 - 使用 MCP Server 实现沙箱工具
    
    关键点：
    - Claude Agent SDK 内置的工具（Bash, Write 等）总是在本地执行
    - 要实现沙箱执行，需要使用自定义 MCP 工具，禁用内置工具
    - 在自定义工具中调用 E2B 沙箱
    """
    print("\n" + "=" * 60)
    print("演示 4: 与 Claude Agent SDK 集成（MCP 沙箱工具）")
    print("=" * 60)
    
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            PermissionMode,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
            create_sdk_mcp_server,
            query,
            tool,
        )
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
    )
    
    # 使用沙箱执行器
    async with SandboxExecutor(sandbox_config) as executor:
        print(f"\n沙箱已启动: {executor.stats}")
        
        # 定义在沙箱中执行的工具
        @tool(
            name="sandbox_bash",
            description="在安全沙箱中执行 Bash 命令。所有命令都在隔离的 E2B 云环境中运行。",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 Bash 命令"
                    }
                },
                "required": ["command"]
            }
        )
        async def sandbox_bash(args: dict) -> dict:
            """在沙箱中执行 Bash 命令"""
            command = args.get("command", "")
            print(f"\n[沙箱执行] Bash: {command}", flush=True)
            
            result = await executor.execute_bash(command)
            
            output = result.output if result.success else f"错误: {result.error}"
            print(f"[沙箱结果] {output[:200]}...", flush=True)
            
            return {
                "content": [{"type": "text", "text": output}],
                "isError": not result.success
            }
        
        @tool(
            name="sandbox_write_file",
            description="在安全沙箱中写入文件。文件保存在隔离的 E2B 云环境中。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容"
                    }
                },
                "required": ["path", "content"]
            }
        )
        async def sandbox_write_file(args: dict) -> dict:
            """在沙箱中写入文件"""
            path = args.get("path", "")
            content = args.get("content", "")
            print(f"\n[沙箱执行] 写入文件: {path}", flush=True)
            
            result = await executor.write_file(path, content)
            
            output = result.output if result.success else f"错误: {result.error}"
            print(f"[沙箱结果] {output}", flush=True)
            
            return {
                "content": [{"type": "text", "text": output}],
                "isError": not result.success
            }
        
        @tool(
            name="sandbox_read_file",
            description="从安全沙箱中读取文件。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径"
                    }
                },
                "required": ["path"]
            }
        )
        async def sandbox_read_file(args: dict) -> dict:
            """从沙箱中读取文件"""
            path = args.get("path", "")
            print(f"\n[沙箱执行] 读取文件: {path}", flush=True)
            
            result = await executor.read_file(path)
            
            output = result.output if result.success else f"错误: {result.error}"
            print(f"[沙箱结果] {output[:200]}...", flush=True)
            
            return {
                "content": [{"type": "text", "text": output}],
                "isError": not result.success
            }
        
        # 创建 SDK MCP 服务器（进程内）
        sandbox_mcp_server = create_sdk_mcp_server(
            name="sandbox_tools",
            version="1.0.0",
            tools=[sandbox_bash, sandbox_write_file, sandbox_read_file]
        )
        
        # 创建 Claude Agent SDK 选项
        # 关键：禁用内置的 Bash/Write/Read 工具，只使用我们的沙箱工具
        options = ClaudeAgentOptions(
            system_prompt="""你是一个代码助手。所有代码执行都在安全的 E2B 云沙箱中进行。

可用的沙箱工具：
- sandbox_bash: 在沙箱中执行 Bash 命令
- sandbox_write_file: 在沙箱中写入文件  
- sandbox_read_file: 从沙箱中读取文件

重要：你只能使用上述沙箱工具，不要使用其他工具。""",
            # 禁用可能在本地执行的危险工具
            disallowed_tools=["Bash", "Write", "Edit", "Read", "Glob", "Grep", "NotebookEdit"],
            permission_mode="bypassPermissions",
            mcp_servers={"sandbox": sandbox_mcp_server},
        )
        
        print("\n正在与 Claude 交互（使用沙箱工具）...")
        
        async def stream_prompt():
            yield {"type": "user", "message": {"role": "user", "content": "请在沙箱中执行 'echo Hello from E2B Sandbox!' 命令，然后创建一个文件 test.txt 内容为 'Hello World'，最后读取这个文件。"}}
        
        # 发送查询
        async for message in query(
            prompt=stream_prompt(),
            options=options,
        ):
            print(f"\n[DEBUG] Message type: {type(message).__name__}")
            
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"\n[Text] Claude: {block.text}")
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[ToolUse] 工具调用: {block.name}")
                        print(f"  ID: {block.id}")
                        print(f"  输入: {block.input}")
                    elif isinstance(block, ToolResultBlock):
                        print("\n[ToolResult] 工具结果:")
                        print(f"  工具ID: {block.tool_use_id}")
                        print(f"  内容: {block.content}")
                        print(f"  是否错误: {block.is_error}")
                    else:
                        print(f"\n[Other Block] {type(block).__name__}: {block}")
            else:
                print(f"[DEBUG] Message: {message}")
        
        # 显示审计日志
        print("\n" + "=" * 60)
        print("沙箱审计日志:")
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
        # await demo_basic_sandbox()
        # await demo_security_validation()
        # await demo_direct_sandbox_usage()
        await demo_with_claude_agent_sdk()
        
    except Exception as e:
        print(f"\n错误: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
