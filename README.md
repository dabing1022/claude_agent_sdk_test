# Claude Agent SDK 测试项目

官方SDK：https://github.com/anthropics/claude-agent-sdk-python

这是一个用于学习和测试 Claude Agent SDK 的 Python 项目。

## 项目简介

Claude Agent SDK 是 Anthropic 官方提供的 Python 框架，用于构建生产级的 AI agents。它提供了高级抽象，自动处理：
- Agent 循环逻辑
- 工具编排
- 上下文管理
- 扩展思考模式

## 环境要求

- Python 3.12.11
- Claude API Key

## 项目结构

```
claude-agent-sdk-test/
├── pyproject.toml          # 项目配置和依赖管理
├── README.md               # 项目文档
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略文件
├── src/                    # 源代码目录
│   └── claude_agent_test/  # 主模块
│       └── __init__.py
├── examples/               # 示例代码
│   ├── 01_basic_usage.py             # 基础使用示例
│   ├── 01_basic_usage_verbose.py     # 带进度提示的基础示例
│   ├── 02_custom_tools.py            # 自定义 MCP 工具示例
│   ├── 03_async_streaming.py         # 双向交互示例
│   ├── 04_sandbox_execution.py       # 沙箱执行示例
│   └── 05_sandbox_api_server.py      # 沙箱 API 服务器示例
├── tools/                  # 工具目录
│   └── performance_diagnostics.py    # 性能诊断工具
├── docs/                   # 文档目录
│   ├── SDK_SOURCE_CODE_ANALYSIS.md   # SDK 源码分析
│   ├── PERFORMANCE_OPTIMIZATION.md   # 性能优化指南
│   ├── SANDBOX_COMPARISON.md         # 沙箱方案对比
│   └── SANDBOX_USAGE.md              # 沙箱使用指南
└── tests/                  # 测试目录
```

## 安装步骤

### 1. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 安装开发依赖（可选）

```bash
pip install -e ".[dev]"
```

### 4. 安装沙箱功能依赖（可选）

```bash
# 仅沙箱功能
pip install -e ".[sandbox]"

# 包含 API 服务器
pip install -e ".[api]"
```

### 4. 配置环境变量

复制 `.env.example` 到 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
ANTHROPIC_API_KEY=your_api_key_here
```

## 使用示例

### 示例 1：基础使用

```bash
python examples/01_basic_usage.py
```

创建一个简单的 agent 并运行基本任务。

### 示例 2：自定义工具

```bash
python examples/02_custom_tools.py
```

演示如何为 agent 添加自定义工具（如计算器）。

### 示例 3：异步流式响应

```bash
python examples/03_async_streaming.py
```

展示如何使用异步 API 获取流式响应。

### 示例 4：沙箱执行

```bash
python examples/04_sandbox_execution.py
```

演示如何在安全沙箱中执行工具，需要配置 `E2B_API_KEY`。

### 示例 5：沙箱 API 服务器

```bash
python examples/05_sandbox_api_server.py
```

启动一个安全的 API 服务器，将工具执行隔离到沙箱中。

## 代码示例

### 基本使用（query 函数）

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

async def main():
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929",
        system_prompt="你是一个有帮助的助手。"
    )

    async for message in query(prompt="什么是 Python？", options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)

asyncio.run(main())
```

### 双向交互（ClaudeSDKClient）

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def main():
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5-20250929"
    )

    async with ClaudeSDKClient(options) as client:
        # 第一个问题
        await client.query("什么是 Python？")
        async for msg in client.receive_response():
            # 处理响应
            pass

        # 第二个问题（复用连接，更快）
        await client.query("什么是异步编程？")
        async for msg in client.receive_response():
            # 处理响应
            pass

asyncio.run(main())
```

### 使用自定义 MCP 工具

```python
import asyncio
from claude_agent_sdk import tool, create_sdk_mcp_server, query, ClaudeAgentOptions

@tool("greet", "向用户问好", {"name": str})
async def greet(args: dict) -> dict:
    return {
        "content": [
            {"type": "text", "text": f"你好，{args['name']}！"}
        ]
    }

async def main():
    server = create_sdk_mcp_server("my_server", tools=[greet])

    options = ClaudeAgentOptions(
        mcp_servers={"my_server": server},
        allowed_tools=["greet"]
    )

    async for msg in query(prompt="向 Alice 问好", options=options):
        # 处理响应
        pass

asyncio.run(main())
```

## 性能优化

### ⚠️ 首次运行慢是正常的

Claude Agent SDK 首次运行时会卡 5-10 秒，这是因为：
1. 闭源 CLI 二进制（174MB）需要加载
2. 需要建立双向通信协议

**这是正常现象！** 后续查询会快很多。

### 🚀 优化建议

#### 1. 使用带进度提示的版本

```bash
# 让用户知道程序在运行，不是卡住
python examples/01_basic_usage_verbose.py
```

#### 2. 复用连接避免重复启动

❌ **慢**：每次都重新启动 CLI
```python
async for msg in query(prompt="问题1", options=options): pass
async for msg in query(prompt="问题2", options=options): pass
```

✅ **快**：复用连接
```python
async with ClaudeSDKClient(options) as client:
    await client.query("问题1")
    await client.query("问题2")  # 快！
```

#### 3. 运行性能诊断

```bash
# 分析你的系统具体瓶颈在哪里
python tools/performance_diagnostics.py
```

### 📖 详细优化指南

查看完整的性能优化文档：
- [性能优化指南](docs/PERFORMANCE_OPTIMIZATION.md) - 详细的优化建议和诊断方法

## 文档

- [SDK 源码分析](docs/SDK_SOURCE_CODE_ANALYSIS.md) - 详细的架构和源码分析
- [性能优化指南](docs/PERFORMANCE_OPTIMIZATION.md) - 性能优化和使用建议
- [沙箱方案对比](docs/SANDBOX_COMPARISON.md) - 不同沙箱方案的对比分析
- [沙箱使用指南](docs/SANDBOX_USAGE.md) - 沙箱执行服务的使用文档

## 沙箱执行服务

本项目提供了一套完整的沙箱执行服务，用于将 Claude Agent SDK 的工具执行隔离到安全环境中。

### 为什么需要沙箱？

Claude Agent SDK 内置了许多强大的工具（Bash、Read、Write、Edit 等），在 API 服务器上直接执行存在安全风险：
- **命令执行风险**: Bash 工具可以执行任意系统命令
- **文件系统风险**: 文件操作可能访问敏感数据
- **资源耗尽风险**: 恶意代码可能耗尽系统资源

### 沙箱解决方案

本项目支持多种沙箱后端，推荐使用 E2B：

```python
from claude_agent_test.sandbox import SandboxConfig, SandboxExecutor

config = SandboxConfig(
    e2b_api_key="your-api-key",
)

async with SandboxExecutor(config) as executor:
    # 所有工具执行都在安全沙箱中进行
    result = await executor.execute_bash("echo 'Hello from sandbox!'")
    print(result.output)
```

### 与 Claude Agent SDK 集成

```python
from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_test.sandbox import SandboxConfig, SandboxExecutor

async with SandboxExecutor(SandboxConfig()) as executor:
    options = ClaudeAgentOptions(
        can_use_tool=executor.get_tool_callback(),  # 使用沙箱工具回调
    )
    
    async for message in query(prompt="执行 ls 命令", options=options):
        # 工具执行在沙箱中完成
        pass
```

详细文档请参阅 [沙箱使用指南](docs/SANDBOX_USAGE.md)。

## 开发工具

项目配置了以下开发工具：

- **Black**: 代码格式化
- **Ruff**: 代码检查
- **MyPy**: 类型检查
- **Pytest**: 测试框架

运行代码检查：

```bash
# 格式化代码
black src/ examples/

# 代码检查
ruff check src/ examples/

# 类型检查
mypy src/
```

## 学习资源

- [Claude Agent SDK 官方文档](https://platform.claude.com/docs/zh-CN/agent-sdk/python)
- [GitHub 仓库](https://github.com/anthropics/claude-agent-sdk-python)
- [DataCamp 教程](https://www.datacamp.com/tutorial/how-to-use-claude-agent-sdk)
- [KDnuggets 入门指南](https://www.kdnuggets.com/getting-started-with-the-claude-agent-sdk)

## 注意事项

1. 确保你的 `ANTHROPIC_API_KEY` 已正确设置
2. Claude Agent SDK 需要 Python 3.10 或更高版本
3. 使用 API 会产生费用，请注意使用量

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
