#!/usr/bin/env python3
"""
Daytona PTY 沙箱运行 Claude Code 演示

在 Daytona 隔离沙箱中运行 Claude Code CLI，支持流式输出和 JSONL 解析。

基于官方文档示例：
https://www.daytona.io/docs/en/claude-code-run-tasks-stream-logs-sandbox/

运行前准备:
1. 安装 daytona-sdk: pip install daytona-sdk
2. 设置环境变量:
   - DAYTONA_API_KEY: Daytona API 密钥
   - ANTHROPIC_API_KEY: Anthropic API 密钥
   - ANTHROPIC_BASE_URL: (可选) 自定义 API Base URL

运行方式:
    python examples/07_daytona_pty_claude_code.py
"""

import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)


class MessageType(Enum):
    """Claude Code 消息类型"""
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    RESULT = "result"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ParsedMessage:
    """解析后的消息"""
    type: MessageType
    subtype: Optional[str] = None
    text: Optional[str] = None
    model: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    is_error: bool = False
    duration_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    usage: Optional[dict] = None
    raw: dict = field(default_factory=dict)


class ClaudeCodeOutputParser:
    """Claude Code stream-json 输出解析器"""

    def __init__(self, on_message: Optional[Callable[[ParsedMessage], None]] = None):
        self.buffer = ""
        self.messages: list[ParsedMessage] = []
        self.on_message = on_message or self._default_printer

    def _default_printer(self, msg: ParsedMessage):
        """默认的消息打印器"""
        if msg.type == MessageType.SYSTEM:
            if msg.subtype == "init":
                print(f"\n🔧 [初始化] 模型: {msg.model}")
                tools = msg.raw.get("tools", [])
                if tools:
                    print(f"   可用工具: {', '.join(tools[:5])}{'...' if len(tools) > 5 else ''}")

        elif msg.type == MessageType.ASSISTANT:
            if msg.text:
                print(f"\n💬 [助手] {msg.text}")

        elif msg.type == MessageType.TOOL_USE:
            print(f"\n🔨 [工具调用] {msg.tool_name}")
            if msg.tool_input:
                # 简化显示工具输入
                input_str = json.dumps(msg.tool_input, ensure_ascii=False)
                if len(input_str) > 100:
                    input_str = input_str[:100] + "..."
                print(f"   输入: {input_str}")

        elif msg.type == MessageType.TOOL_RESULT:
            print("\n📋 [工具结果]")
            if msg.text:
                text = msg.text[:200] + "..." if len(msg.text) > 200 else msg.text
                print(f"   {text}")

        elif msg.type == MessageType.RESULT:
            print(f"\n{'❌' if msg.is_error else '✅'} [完成]")
            if msg.text:
                print(f"   结果: {msg.text}")
            if msg.duration_ms:
                print(f"   耗时: {msg.duration_ms}ms")
            if msg.cost_usd:
                print(f"   费用: ${msg.cost_usd:.6f}")
            if msg.usage:
                input_tokens = msg.usage.get("input_tokens", 0)
                output_tokens = msg.usage.get("output_tokens", 0)
                print(f"   Token: 输入 {input_tokens}, 输出 {output_tokens}")

        elif msg.type == MessageType.ERROR:
            print(f"\n❌ [错误] {msg.text}")

    def parse_line(self, line: str) -> Optional[ParsedMessage]:
        """解析单行 JSON"""
        line = line.strip()
        if not line or not line.startswith("{"):
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        msg_type = data.get("type", "unknown")
        valid_types = [e.value for e in MessageType]
        msg = ParsedMessage(
            type=MessageType(msg_type) if msg_type in valid_types else MessageType.UNKNOWN,
            raw=data
        )

        if msg_type == "system":
            msg.subtype = data.get("subtype")
            msg.model = data.get("model")

        elif msg_type == "assistant":
            message = data.get("message", {})
            msg.model = message.get("model")
            content = message.get("content", [])

            # 提取文本内容
            texts = []
            for block in content:
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    # 工具调用作为单独消息处理
                    tool_msg = ParsedMessage(
                        type=MessageType.TOOL_USE,
                        tool_name=block.get("name"),
                        tool_input=block.get("input"),
                        raw=block
                    )
                    self.messages.append(tool_msg)
                    if self.on_message:
                        self.on_message(tool_msg)

            msg.text = "\n".join(texts) if texts else None

        elif msg_type == "user":
            content = data.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    tool_msg = ParsedMessage(
                        type=MessageType.TOOL_RESULT,
                        text=str(block.get("content", ""))[:500],
                        is_error=block.get("is_error", False),
                        raw=block
                    )
                    self.messages.append(tool_msg)
                    if self.on_message:
                        self.on_message(tool_msg)
            return None  # user 消息主要是工具结果，已单独处理

        elif msg_type == "result":
            msg.subtype = data.get("subtype")
            msg.text = data.get("result")
            msg.is_error = data.get("is_error", False)
            msg.duration_ms = data.get("duration_ms")
            msg.cost_usd = data.get("total_cost_usd")
            msg.usage = data.get("usage")

        return msg

    def feed(self, data: str) -> list[ParsedMessage]:
        """喂入数据，返回解析出的消息列表"""
        self.buffer += data
        new_messages = []

        # 按行分割处理
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            msg = self.parse_line(line)
            if msg:
                self.messages.append(msg)
                new_messages.append(msg)
                if self.on_message:
                    self.on_message(msg)

        return new_messages

    def is_complete(self) -> bool:
        """检查是否收到完成消息"""
        return any(m.type == MessageType.RESULT for m in self.messages)

    def get_result(self) -> Optional[ParsedMessage]:
        """获取最终结果"""
        for msg in reversed(self.messages):
            if msg.type == MessageType.RESULT:
                return msg
        return None


async def run_claude_code_in_sandbox():
    """在 Daytona 沙箱中运行 Claude Code"""

    # 检查环境变量
    daytona_api_key = os.environ.get("DAYTONA_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    anthropic_base_url = os.environ.get("ANTHROPIC_BASE_URL")

    if not daytona_api_key:
        print("❌ 错误: DAYTONA_API_KEY 环境变量未设置")
        return

    if not anthropic_api_key:
        print("❌ 错误: ANTHROPIC_API_KEY 环境变量未设置")
        return

    print("=" * 60)
    print("🚀 Daytona PTY 沙箱运行 Claude Code 演示")
    print("=" * 60)
    print(f"✅ DAYTONA_API_KEY: {daytona_api_key[:12]}...")
    print(f"✅ ANTHROPIC_API_KEY: {anthropic_api_key[:12]}...")
    if anthropic_base_url:
        print(f"✅ ANTHROPIC_BASE_URL: {anthropic_base_url}")

    try:
        from daytona import AsyncDaytona
    except ImportError:
        print("\n❌ Daytona SDK 未安装")
        print("   请运行: pip install daytona-sdk")
        return

    # 定义要执行的提示词
    prompt = "write a dad joke about penguins"

    # Claude Code 命令
    claude_command = f"claude --dangerously-skip-permissions -p '{prompt}' --output-format stream-json --verbose"

    print(f"\n📝 提示词: {prompt}")
    print(f"📌 命令: {claude_command}")

    async with AsyncDaytona() as daytona:
        print("\n🔄 正在创建沙箱...")
        sandbox = await daytona.create()
        print(f"✅ 沙箱已创建: {sandbox.id}")

        try:
            # 安装 Claude Code
            print("\n📦 正在安装 Claude Code CLI...")
            install_result = await sandbox.process.exec(
                "npm install -g @anthropic-ai/claude-code"
            )
            print(f"   安装结果: {install_result.result[:200] if install_result.result else '完成'}...")

            # 创建 PTY 会话
            print("\n🖥️ 创建 PTY 会话...")

            # 创建解析器和完成事件
            result_received = asyncio.Event()
            parser = ClaudeCodeOutputParser()

            # 用于跳过命令回显
            skip_echo = True

            def on_data(data: bytes):
                """处理 PTY 输出数据"""
                nonlocal skip_echo
                decoded = data.decode('utf-8', errors='replace')

                # 跳过命令回显（PTY 会回显输入的命令）
                if skip_echo:
                    # 检测到 JSON 输出开始
                    if '{"type":' in decoded:
                        skip_echo = False
                        # 只处理 JSON 部分
                        idx = decoded.find('{"type":')
                        decoded = decoded[idx:]
                    else:
                        return

                # 解析 JSONL 输出
                parser.feed(decoded)

                # 检查是否完成
                if parser.is_complete():
                    result_received.set()

            pty_handle = await sandbox.process.create_pty_session(
                id="claude-code-session",
                on_data=on_data
            )

            # 等待连接建立
            await pty_handle.wait_for_connection()
            print("✅ PTY 会话已连接")

            print("\n" + "=" * 60)
            print("📤 Claude Code 输出:")
            print("=" * 60)

            # 构建环境变量字符串
            env_vars = f"ANTHROPIC_API_KEY={anthropic_api_key}"
            if anthropic_base_url:
                env_vars += f" ANTHROPIC_BASE_URL={anthropic_base_url}"

            # 发送命令（包含环境变量）
            await pty_handle.send_input(
                f"{env_vars} {claude_command}\n"
            )

            # 等待 result 消息或超时
            timeout = 120
            try:
                await asyncio.wait_for(result_received.wait(), timeout=timeout)
                # 给一点时间让剩余输出处理完
                await asyncio.sleep(0.5)
            except TimeoutError:
                print(f"\n\n⚠️ 命令执行超时 ({timeout}秒)")

            print("\n" + "=" * 60)
            print("✅ Claude Code 执行完成")

            # 显示最终结果摘要
            result = parser.get_result()
            if result:
                print("\n📊 执行摘要:")
                print(f"   状态: {'失败' if result.is_error else '成功'}")
                if result.duration_ms:
                    print(f"   总耗时: {result.duration_ms}ms")
                if result.cost_usd:
                    print(f"   总费用: ${result.cost_usd:.6f}")
                print(f"   消息数: {len(parser.messages)}")

            print("=" * 60)

        except Exception as e:
            print(f"\n❌ 执行过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 清理沙箱
            print("\n🗑️ 正在删除沙箱...")
            await daytona.delete(sandbox)
            print("✅ 沙箱已删除")


async def run_simple_demo():
    """简单演示：在沙箱中执行基本命令"""

    daytona_api_key = os.environ.get("DAYTONA_API_KEY")

    if not daytona_api_key:
        print("❌ 错误: DAYTONA_API_KEY 环境变量未设置")
        return

    print("=" * 60)
    print("📦 Daytona 沙箱基础演示")
    print("=" * 60)

    try:
        from daytona import AsyncDaytona
    except ImportError:
        print("\n❌ Daytona SDK 未安装")
        return

    async with AsyncDaytona() as daytona:
        print("\n🔄 正在创建沙箱...")
        sandbox = await daytona.create()
        print(f"✅ 沙箱已创建: {sandbox.id}")

        try:
            # 执行一些基本命令
            print("\n📌 执行基本命令:")

            # 系统信息
            result = await sandbox.process.exec("uname -a")
            print(f"   系统: {result.result.strip()}")

            # Node.js 版本
            result = await sandbox.process.exec("node --version")
            print(f"   Node.js: {result.result.strip()}")

            # npm 版本
            result = await sandbox.process.exec("npm --version")
            print(f"   npm: {result.result.strip()}")

            # Python 版本
            result = await sandbox.process.exec("python3 --version")
            print(f"   Python: {result.result.strip()}")

            print("\n✅ 基础演示完成")

        finally:
            print("\n🗑️ 正在删除沙箱...")
            await daytona.delete(sandbox)
            print("✅ 沙箱已删除")


async def run_debug_demo():
    """调试演示：显示 Daytona API HTTP 请求详情"""

    daytona_api_key = os.environ.get("DAYTONA_API_KEY")

    if not daytona_api_key:
        print("❌ 错误: DAYTONA_API_KEY 环境变量未设置")
        return

    print("=" * 60)
    print("🔍 Daytona API HTTP 调试演示")
    print("=" * 60)

    try:
        import aiohttp
        from daytona import AsyncDaytona, DaytonaConfig
    except ImportError:
        print("\n❌ Daytona SDK 未安装")
        return

    # 保存原始的请求方法
    original_request = aiohttp.ClientSession._request

    # 请求计数器
    request_count = [0]

    async def patched_request(self, method, url, **kwargs):
        """拦截并打印 HTTP 请求详情"""
        request_count[0] += 1
        req_num = request_count[0]

        print(f"\n{'─' * 60}")
        print(f"📡 HTTP 请求 #{req_num}")
        print(f"{'─' * 60}")
        print(f"   方法: {method}")
        print(f"   URL: {url}")

        # 打印请求头（隐藏敏感信息）
        headers = kwargs.get('headers', {})
        if headers:
            print("   请求头:")
            for key, value in headers.items():
                if key.lower() in ('authorization', 'x-api-key'):
                    # 隐藏敏感信息
                    value = value[:20] + '...' if len(value) > 20 else value
                print(f"      {key}: {value}")

        # 打印请求体（如果有）
        data = kwargs.get('data') or kwargs.get('json')
        if data:
            print("   请求体:")
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, ensure_ascii=False, indent=6)
            else:
                data_str = str(data)
            # 限制长度
            if len(data_str) > 500:
                data_str = data_str[:500] + "..."
            print(f"      {data_str}")

        # 执行原始请求
        response = await original_request(self, method, url, **kwargs)

        # 打印响应信息
        print("\n   📥 响应:")
        print(f"      状态码: {response.status}")
        print(f"      状态: {response.reason}")

        # 尝试读取响应体（需要小心，因为响应体只能读取一次）
        # 这里我们不读取响应体，因为会影响后续处理

        return response

    # 应用 monkey patch
    aiohttp.ClientSession._request = patched_request
    print("\n✅ HTTP 请求拦截器已启用")

    try:
        # 创建配置
        config = DaytonaConfig(
            api_key=daytona_api_key,
            api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
        )

        async with AsyncDaytona(config) as daytona:
            print("\n🔄 正在创建沙箱...")
            sandbox = await daytona.create()
            print(f"\n✅ 沙箱已创建: {sandbox.id}")

            # 显示沙箱详细信息
            print("\n📋 沙箱详细信息:")
            print(f"   ID: {sandbox.id}")
            print(f"   状态: {sandbox.state}")
            if hasattr(sandbox, '_sandbox'):
                sb = sandbox._sandbox
                if hasattr(sb, 'target'):
                    print(f"   目标区域: {sb.target}")
                if hasattr(sb, 'created_at'):
                    print(f"   创建时间: {sb.created_at}")

            try:
                # 执行简单命令
                print("\n📌 执行命令...")
                result = await sandbox.process.exec("echo 'Hello from debug mode!'")
                print(f"\n   输出: {result.result.strip()}")

            finally:
                print("\n🗑️ 正在删除沙箱...")
                await daytona.delete(sandbox)
                print("\n✅ 沙箱已删除")

    finally:
        # 恢复原始方法
        aiohttp.ClientSession._request = original_request
        print("\n✅ HTTP 请求拦截器已移除")

    print(f"\n📊 总计 HTTP 请求数: {request_count[0]}")
    print("✅ 调试演示完成")


async def main():
    """主函数"""
    print("\n选择要运行的演示:")
    print("1. 基础沙箱演示（测试连接）")
    print("2. Claude Code PTY 演示（完整功能 + JSONL 解析）")
    print("3. HTTP 调试演示（查看 Daytona API 请求详情）")
    print("-" * 40)

    choice = input("请输入选项 (1-3，默认 1): ").strip() or "1"

    if choice == "1":
        await run_simple_demo()
    elif choice == "2":
        await run_claude_code_in_sandbox()
    elif choice == "3":
        await run_debug_demo()
    else:
        print("无效选项，运行基础演示...")
        await run_simple_demo()


if __name__ == "__main__":
    asyncio.run(main())
