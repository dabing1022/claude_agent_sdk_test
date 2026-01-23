# 沙箱执行服务使用指南

本文档介绍如何使用沙箱执行服务将 Claude Agent SDK 的工具执行隔离到安全环境中。

## 目录

1. [快速开始](#快速开始)
2. [配置说明](#配置说明)
3. [基本使用](#基本使用)
4. [与 Claude Agent SDK 集成](#与-claude-agent-sdk-集成)
5. [安全策略](#安全策略)
6. [API 服务器部署](#api-服务器部署)
7. [最佳实践](#最佳实践)

## 快速开始

### 安装依赖

```bash
# 安装基础依赖
pip install -e .

# 安装沙箱依赖
pip install -e ".[sandbox]"

# 如果需要 API 服务器功能
pip install -e ".[api]"
```

### 配置 E2B API Key

1. 在 [E2B](https://e2b.dev) 注册并获取 API Key
2. 设置环境变量：

```bash
export E2B_API_KEY=your-api-key
```

或在 `.env` 文件中添加：

```
E2B_API_KEY=your-api-key
```

### 运行示例

```bash
# 基本沙箱示例
python examples/04_sandbox_execution.py

# API 服务器示例
python examples/05_sandbox_api_server.py
```

## 配置说明

### SandboxConfig

```python
from claude_agent_test.sandbox import (
    SandboxConfig,
    SandboxType,
    ResourceLimits,
    NetworkConfig,
    SecurityConfig,
)

config = SandboxConfig(
    # 沙箱类型
    sandbox_type=SandboxType.E2B,
    
    # E2B 配置
    e2b_api_key="your-api-key",  # 或使用环境变量
    e2b_template="base",  # 使用的模板
    
    # 资源限制
    resource_limits=ResourceLimits(
        cpu_cores=2,
        memory_mb=512,
        disk_mb=1024,
        timeout_seconds=60,
        max_processes=50,
    ),
    
    # 网络配置
    network=NetworkConfig(
        enabled=False,  # 禁用网络访问
        allowed_domains=[],  # 允许的域名
    ),
    
    # 安全配置
    security=SecurityConfig(
        allowed_tools=[],  # 允许的工具（空表示全部允许）
        blocked_tools=[],  # 禁止的工具
        command_blacklist=[  # 命令黑名单
            r"rm\s+-rf\s+/",
            r"sudo",
        ],
        enable_audit_log=True,
        allow_root=False,
    ),
    
    # 会话配置
    session_timeout_minutes=60,
    auto_cleanup=True,
    working_directory="/workspace",
)
```

### 预设配置

```python
from claude_agent_test.sandbox import SANDBOX_PRESETS

# 使用预设配置
minimal_config = SANDBOX_PRESETS["minimal"]  # 最小资源配置
standard_config = SANDBOX_PRESETS["standard"]  # 标准配置
dev_config = SANDBOX_PRESETS["development"]  # 开发配置（允许网络）
```

## 基本使用

### 使用 SandboxExecutor

```python
import asyncio
from claude_agent_test.sandbox import SandboxConfig, SandboxExecutor

async def main():
    config = SandboxConfig()
    
    async with SandboxExecutor(config) as executor:
        # 执行 Bash 命令
        result = await executor.execute_bash("echo 'Hello!'")
        print(result.output)
        
        # 写入文件
        await executor.write_file("test.txt", "Hello, World!")
        
        # 读取文件
        result = await executor.read_file("test.txt")
        print(result.output)
        
        # 搜索文件
        result = await executor.search_files("Hello", ".")
        print(result.output)

asyncio.run(main())
```

### 直接使用 E2BSandbox

```python
import asyncio
from claude_agent_test.sandbox import E2BSandbox, SandboxConfig

async def main():
    config = SandboxConfig(working_directory="/home/user")
    
    async with E2BSandbox(config) as sandbox:
        # 执行命令
        result = await sandbox.execute_bash("python --version")
        print(result.output)
        
        # 文件操作
        await sandbox.write_file("script.py", "print('Hello!')")
        result = await sandbox.execute_bash("python script.py")
        print(result.output)

asyncio.run(main())
```

## 与 Claude Agent SDK 集成

### 方式一：工具权限回调

```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, query, AssistantMessage, TextBlock
from claude_agent_test.sandbox import SandboxConfig, SandboxExecutor

async def main():
    # 创建沙箱执行器
    sandbox_config = SandboxConfig()
    
    async with SandboxExecutor(sandbox_config) as executor:
        # 获取工具回调
        tool_callback = executor.get_tool_callback()
        
        # 创建 Claude Agent SDK 选项
        options = ClaudeAgentOptions(
            system_prompt="你是一个代码助手。",
            can_use_tool=tool_callback,  # 使用沙箱工具回调
        )
        
        # 发送查询
        async for message in query(prompt="执行 ls 命令", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(main())
```

### 方式二：自定义工具代理

```python
from claude_agent_test.sandbox import (
    ToolProxy,
    SandboxConfig,
    create_sandbox_tool_callback,
    E2BSandbox,
)

async def create_sandbox():
    config = SandboxConfig()
    sandbox = E2BSandbox(config)
    await sandbox.connect()
    return sandbox

# 创建工具代理
config = SandboxConfig()
tool_proxy = ToolProxy(config, create_sandbox)

# 创建回调
callback = create_sandbox_tool_callback(tool_proxy)

# 使用回调
options = ClaudeAgentOptions(can_use_tool=callback)
```

## 安全策略

### 命令分析器

```python
from claude_agent_test.sandbox import CommandAnalyzer, SecurityConfig

config = SecurityConfig(
    command_blacklist=[
        r"rm\s+-rf",
        r"sudo",
    ]
)

analyzer = CommandAnalyzer(config)

# 分析命令
violations = analyzer.analyze("rm -rf /")
for v in violations:
    print(f"违规: {v.description} (风险: {v.risk_level})")

# 检查是否安全
is_safe, reason = analyzer.is_safe("ls -la")
print(f"安全: {is_safe}, 原因: {reason}")
```

### 安全管理器

```python
from claude_agent_test.sandbox import (
    SecurityManager,
    SecurityConfig,
    ToolInput,
)

config = SecurityConfig(
    blocked_tools=["WebFetch"],
    command_blacklist=[r"rm\s+-rf"],
    enable_audit_log=True,
)

manager = SecurityManager(config)

# 验证工具调用
tool_input = ToolInput(
    tool_name="Bash",
    arguments={"command": "ls -la"},
)

is_valid, reason = manager.validate_tool_call(tool_input)
print(f"有效: {is_valid}, 原因: {reason}")

# 获取违规记录
violations = manager.get_violations()
stats = manager.get_stats()
print(f"统计: {stats}")
```

### 速率限制

```python
from claude_agent_test.sandbox import RateLimiter

limiter = RateLimiter(
    max_requests=100,  # 最大请求数
    window_seconds=60,  # 时间窗口
)

# 检查速率
is_allowed, reason = limiter.check("user_123")
if not is_allowed:
    print(f"限流: {reason}")
```

## API 服务器部署

### 启动服务器

```bash
# 直接运行
python examples/05_sandbox_api_server.py

# 使用 uvicorn
uvicorn examples.05_sandbox_api_server:app --host 0.0.0.0 --port 8000

# 生产环境
uvicorn examples.05_sandbox_api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

### API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务状态 |
| `/health` | GET | 健康检查 |
| `/execute` | POST | 执行任意工具 |
| `/bash` | POST | 执行 Bash 命令 |
| `/file/read` | POST | 读取文件 |
| `/file/write` | POST | 写入文件 |
| `/search` | POST | 搜索文件 |
| `/audit-logs` | GET | 获取审计日志 |
| `/stats` | GET | 获取统计信息 |

### 使用示例

```bash
# 执行 Bash 命令
curl -X POST http://localhost:8000/bash \
  -H "Content-Type: application/json" \
  -d '{"command": "echo Hello"}'

# 写入文件
curl -X POST http://localhost:8000/file/write \
  -H "Content-Type: application/json" \
  -d '{"path": "test.txt", "content": "Hello, World!"}'

# 读取文件
curl -X POST http://localhost:8000/file/read \
  -H "Content-Type: application/json" \
  -d '{"path": "test.txt"}'
```

## 最佳实践

### 1. 始终使用沙箱

在生产环境中，所有工具执行都应该在沙箱中进行：

```python
# 推荐
async with SandboxExecutor(config) as executor:
    result = await executor.execute_bash(command)

# 不推荐
import subprocess
subprocess.run(command, shell=True)
```

### 2. 配置适当的资源限制

```python
config = SandboxConfig(
    resource_limits=ResourceLimits(
        timeout_seconds=30,  # 防止无限执行
        memory_mb=512,  # 限制内存使用
        max_processes=50,  # 限制进程数
    ),
)
```

### 3. 启用审计日志

```python
config = SandboxConfig(
    security=SecurityConfig(
        enable_audit_log=True,
    ),
)

# 定期检查审计日志
logs = executor.get_audit_logs()
for log in logs:
    if not log["success"]:
        alert(f"执行失败: {log}")
```

### 4. 禁用网络访问

除非必要，否则禁用沙箱的网络访问：

```python
config = SandboxConfig(
    network=NetworkConfig(
        enabled=False,
    ),
)
```

### 5. 使用命令白名单

对于高安全要求的场景，使用命令白名单：

```python
config = SandboxConfig(
    security=SecurityConfig(
        command_whitelist=[
            "ls",
            "cat",
            "echo",
            "python",
        ],
    ),
)
```

### 6. 定期清理沙箱

```python
config = SandboxConfig(
    auto_cleanup=True,  # 执行完成后自动清理
    session_timeout_minutes=30,  # 设置会话超时
)
```

### 7. 监控和告警

```python
from claude_agent_test.sandbox import SecurityManager, RiskLevel

manager = SecurityManager(config)

# 定期检查高风险违规
violations = manager.get_violations(risk_level=RiskLevel.HIGH)
if violations:
    send_alert(f"检测到 {len(violations)} 个高风险违规")
```

## 故障排除

### E2B 连接失败

1. 检查 API Key 是否正确
2. 检查网络连接
3. 检查 E2B 服务状态

### 命令执行超时

1. 增加 `timeout_seconds`
2. 检查命令是否有无限循环
3. 检查资源限制是否过于严格

### 安全验证失败

1. 检查命令是否在黑名单中
2. 检查文件路径是否在禁止列表中
3. 查看审计日志了解详细原因

## Daytona 官方示例

Daytona 官方提供了三个与 Claude Agent SDK 集成的示例，展示了不同的使用场景。

### 示例 1：交互式终端沙箱

> 文档链接：https://www.daytona.io/docs/en/claude-agent-sdk-interactive-terminal-sandbox/

**功能概述**

在 Daytona 沙箱中运行自主编码代理，支持：
- 开发全栈 Web 应用
- 用任何编程语言编写代码
- 安装依赖并运行脚本
- 启动和管理开发服务器
- 生成实时应用预览链接

**环境变量配置**

```bash
DAYTONA_API_KEY=your-daytona-api-key      # 从 Daytona 仪表板获取
SANDBOX_ANTHROPIC_API_KEY=your-api-key    # 从 Anthropic 控制台获取
```

**代理工具配置**

允许的工具包括：`Read`、`Edit`、`Glob`、`Grep`、`Bash`，权限模式设为 `acceptEdits`。

**核心代码示例**

```typescript
// 向代理发送提示
const result = await sandbox.codeInterpreter.runCode(
  `coding_agent.run_query_sync(os.environ.get('PROMPT', ''))`,
  { context: ctx, envs: { PROMPT: prompt } }
)
```

**使用步骤**

1. 克隆仓库并进入示例目录
2. 配置 `.env` 文件添加 API 密钥
3. 运行 `npm install` 安装依赖
4. 执行 `npm run start` 启动代理
5. 在命令行界面输入提示词与代理交互
6. 退出时自动清理沙箱资源

---

### 示例 2：两代理编码系统（服务连接沙箱）

> 文档链接：https://www.daytona.io/docs/en/claude-agent-sdk-connect-service-sandbox/

**功能概述**

基于 Claude Agent SDK 和 Daytona 沙箱的自主编码框架，由两个协作代理组成：

| 代理 | 运行位置 | 职责 | 模型 |
|------|----------|------|------|
| **项目经理代理** | 本地 | 高层规划和任务委派 | `claude-sonnet-4-20250514` |
| **开发者代理** | 沙箱 | 执行编码任务 | Claude Code |

这种架构将高层规划与低层代码执行分离，实现更强大的自动化。

**环境变量配置**

```bash
DAYTONA_API_KEY=your-daytona-api-key           # 从 Daytona 仪表板获取
ANTHROPIC_API_KEY=your-api-key                 # 项目经理代理所需
SANDBOX_ANTHROPIC_API_KEY=your-api-key         # 可选，用于开发者代理
```

**系统要求**

- Node.js 18 或更新版本

**核心代码示例**

```typescript
// 开发者代理执行任务
const result = await sandbox.codeInterpreter.runCode(
  `coding_agent.run_query_sync(os.environ.get('PROMPT', ''))`,
  { context: ctx, envs: { PROMPT: task } }
);
```

项目经理代理使用 `<developer_task>` 标签进行任务委派，系统解析这些标签并调用开发者代理。

**使用步骤**

1. 克隆仓库：`git clone https://github.com/daytonaio/daytona.git`
2. 配置环境：复制 `.env.example` 到 `.env` 并填入 API 密钥
3. 安装依赖：`npm install`
4. 启动系统：`npm run start`
5. 通过终端提示与项目经理代理交互，系统自动处理委派和执行
6. 退出程序时，沙箱自动清理

---

### 示例 3：运行任务并流式输出日志

> 文档链接：https://www.daytona.io/docs/en/claude-code-run-tasks-stream-logs-sandbox/

**功能概述**

在 Daytona 隔离沙箱中运行 Claude Code，核心目的是"自动化和编排任务，使用自然语言和代码"，同时在安全的隔离环境中执行这些操作。

**环境变量配置**

```bash
ANTHROPIC_API_KEY=your-api-key
```

**命令标志**

- `--dangerously-skip-permissions`：跳过权限检查
- `--output-format stream-json`：流式 JSON 输出
- `--verbose`：详细输出

**Python 示例**

```python
from daytona import AsyncDaytona

async def main():
    async with AsyncDaytona() as daytona:
        # 创建沙箱
        sandbox = await daytona.create()

        # 安装 Claude Code
        await sandbox.process.exec("npm install -g @anthropic-ai/claude-code")

        # 创建 PTY 会话并执行命令
        pty = await sandbox.process.create_pty()
        await pty.send(f"ANTHROPIC_API_KEY={api_key} claude --dangerously-skip-permissions --output-format stream-json --verbose 'your prompt here'\n")

        # 处理流式输出
        async for data in pty.on_data():
            print(data, end="")

        # 清理
        await daytona.delete(sandbox)
```

**TypeScript 示例**

```typescript
import { Daytona } from '@daytona/sdk';

async function main() {
    const daytona = new Daytona();
    const sandbox = await daytona.create();

    // 安装 Claude Code
    await sandbox.process.exec("npm install -g @anthropic-ai/claude-code");

    // 创建 PTY 并配置回调
    const pty = await sandbox.process.createPty({
        onData: (data) => process.stdout.write(data)
    });

    // 发送命令
    await pty.send(`ANTHROPIC_API_KEY=${apiKey} claude --dangerously-skip-permissions "your prompt"\n`);

    // 等待完成后清理
    await daytona.delete(sandbox);
}
```

**使用步骤**

1. 创建沙箱实例
2. 安装 Claude Code 工具
3. 建立 PTY 会话连接
4. 执行 Claude 命令
5. 处理流式输出
6. 清理资源（删除沙箱）

---

### Daytona + Claude Code 集成总结

| 特性 | 说明 |
|------|------|
| **自定义镜像** | 支持通过 `CreateSandboxParams.image` 指定自定义 Docker 镜像 |
| **环境变量** | 支持通过 `env_vars` 传递 API 密钥等配置 |
| **PTY 支持** | 支持伪终端，可运行交互式 CLI 工具 |
| **流式输出** | 支持实时流式输出日志 |
| **自动清理** | 退出时自动清理沙箱资源 |

**关键发现：Daytona 可以内置 Claude Code CLI**

通过以下方式实现：

1. **运行时安装**：在沙箱创建后通过 `npm install -g @anthropic-ai/claude-code` 安装
2. **自定义镜像**：构建预装 Claude Code 的 Docker 镜像
3. **PTY 会话**：使用 PTY 运行交互式 Claude Code CLI
4. **环境变量**：通过 `ANTHROPIC_API_KEY` 传递认证信息

## 参考资料

- [E2B 官方文档](https://e2b.dev/docs)
- [Claude Agent SDK 文档](https://platform.claude.com/docs/agent-sdk)
- [沙箱方案对比](./SANDBOX_COMPARISON.md)
- [Daytona 官方文档](https://www.daytona.io/docs)
- [Daytona + Claude Agent SDK 交互式终端](https://www.daytona.io/docs/en/claude-agent-sdk-interactive-terminal-sandbox/)
- [Daytona + Claude Agent SDK 服务连接](https://www.daytona.io/docs/en/claude-agent-sdk-connect-service-sandbox/)
- [Daytona + Claude Code 流式日志](https://www.daytona.io/docs/en/claude-code-run-tasks-stream-logs-sandbox/)
