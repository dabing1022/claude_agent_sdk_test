# Claude Agent SDK 源码分析

## 概览

Claude Agent SDK 的核心二进制是**闭源的**，位于 `_bundled/claude`（约 174MB 的 Mach-O 可执行文件）。Python SDK 代码是开源的，主要作为**封装层**和**协议桥接层**，负责与闭源 CLI 进程通信。

## 架构设计

### 1. 整体架构

```
┌─────────────────────────────────────────────────────┐
│           Python SDK (开源部分)                        │
│  ┌──────────────────────────────────────────────┐   │
│  │  query() / ClaudeSDKClient                   │   │
│  │  (用户 API 层)                                │   │
│  └──────────────┬───────────────────────────────┘   │
│                 │                                     │
│  ┌──────────────▼───────────────────────────────┐   │
│  │  Query (控制协议层)                            │   │
│  │  - 处理双向通信                                │   │
│  │  - 管理 hooks 和权限回调                       │   │
│  │  - 路由 MCP 消息                               │   │
│  └──────────────┬───────────────────────────────┘   │
│                 │                                     │
│  ┌──────────────▼───────────────────────────────┐   │
│  │  Transport (传输层抽象)                        │   │
│  │  - SubprocessCLITransport                     │   │
│  │  - 标准输入/输出通信                           │   │
│  └──────────────┬───────────────────────────────┘   │
└─────────────────┼───────────────────────────────────┘
                  │ JSON-RPC over stdin/stdout
                  │
┌─────────────────▼───────────────────────────────────┐
│        闭源 CLI (_bundled/claude)                    │
│  - Agent 循环逻辑                                     │
│  - 实际的 Claude API 调用                             │
│  - 工具执行引擎                                       │
│  - 上下文管理和压缩                                   │
└─────────────────────────────────────────────────────┘
```

## 开源代码模块分析

### 1. 类型定义 (`types.py` - 755行)

#### 核心类型

**消息类型**:
- `UserMessage`: 用户消息
- `AssistantMessage`: Claude 的回复
- `SystemMessage`: 系统消息
- `ResultMessage`: 结果消息（包含成本、使用统计）
- `StreamEvent`: 流式响应事件

**内容块类型**:
- `TextBlock`: 文本内容
- `ThinkingBlock`: 思考内容（扩展思考模式）
- `ToolUseBlock`: 工具调用
- `ToolResultBlock`: 工具执行结果

**配置类型**:
- `ClaudeAgentOptions`: 主配置类，包含约30个配置选项
- `AgentDefinition`: Agent 定义
- `PermissionMode`: 权限模式（default, acceptEdits, plan, bypassPermissions）

#### 权限系统

```python
# 权限结果类型
PermissionResultAllow    # 允许执行，可修改输入
PermissionResultDeny     # 拒绝执行，可中断会话
PermissionUpdate         # 权限更新配置

# 权限回调
CanUseTool = Callable[[str, dict, ToolPermissionContext],
                      Awaitable[PermissionResult]]
```

#### Hook 系统

支持的 Hook 事件：
- `PreToolUse`: 工具调用前
- `PostToolUse`: 工具调用后
- `UserPromptSubmit`: 用户提交提示后
- `Stop`: 停止时
- `SubagentStop`: 子 Agent 停止时
- `PreCompact`: 上下文压缩前

Hook 输出配置：
```python
# 异步 Hook
AsyncHookJSONOutput: {"async_": True, "asyncTimeout": int}

# 同步 Hook
SyncHookJSONOutput: {
    "continue_": bool,          # 是否继续执行
    "suppressOutput": bool,     # 隐藏输出
    "stopReason": str,          # 停止原因
    "decision": "block",        # 决策
    "hookSpecificOutput": {...} # Hook 特定输出
}
```

#### MCP 服务器配置

```python
# 支持 4 种 MCP 服务器类型
McpStdioServerConfig   # 标准 I/O（外部进程）
McpSSEServerConfig     # Server-Sent Events
McpHttpServerConfig    # HTTP
McpSdkServerConfig     # SDK 内置（in-process）
```

#### 沙箱配置

```python
SandboxSettings: {
    "enabled": bool,                      # 启用沙箱
    "autoAllowBashIfSandboxed": bool,     # 自动允许沙箱命令
    "excludedCommands": list[str],        # 排除的命令
    "allowUnsandboxedCommands": bool,     # 允许非沙箱命令
    "network": SandboxNetworkConfig,      # 网络配置
    "ignoreViolations": {...}             # 忽略的违规
}
```

### 2. 客户端 (`client.py` - 378行)

#### ClaudeSDKClient 类

**核心功能**：
- 双向、有状态的对话管理
- 支持流式响应
- 支持中断操作
- 动态权限模式切换
- 模型切换

**关键方法**：

```python
async def connect(prompt)           # 连接到 Claude
async def query(prompt, session_id) # 发送新请求
async def interrupt()               # 中断执行
async def set_permission_mode(mode) # 修改权限模式
async def set_model(model)          # 切换模型
async def rewind_files(msg_id)      # 文件回滚
async def receive_messages()        # 接收所有消息
async def receive_response()        # 接收单次响应
async def disconnect()              # 断开连接
```

**限制**：
- 不能跨异步运行时上下文使用（v0.0.20 的已知限制）
- 必须在相同的 async context 中完成所有操作

### 3. 查询函数 (`query.py` - 127行)

#### query() 函数

**用途**: 一次性、无状态的查询

```python
async def query(
    *,
    prompt: str | AsyncIterable[dict],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None,
) -> AsyncIterator[Message]
```

**适用场景**:
- 简单的一次性问题
- 批处理
- 已知所有输入的自动化脚本
- CI/CD 管道

**不适用场景**:
- 需要交互式对话
- 需要根据响应发送后续消息
- 需要中断能力

### 4. 内部查询层 (`_internal/query.py` - 622行)

#### Query 类（控制协议核心）

**职责**：
- 控制请求/响应路由
- Hook 回调管理
- 工具权限回调管理
- 消息流管理
- 初始化握手
- SDK MCP 服务器桥接

**控制协议消息**：

```python
# 请求类型
SDKControlInterruptRequest         # 中断请求
SDKControlPermissionRequest        # 权限请求
SDKControlInitializeRequest        # 初始化请求
SDKControlSetPermissionModeRequest # 设置权限模式
SDKHookCallbackRequest            # Hook 回调请求
SDKControlMcpMessageRequest       # MCP 消息请求
SDKControlRewindFilesRequest      # 文件回滚请求

# 响应类型
ControlResponse                    # 成功响应
ControlErrorResponse              # 错误响应
```

**关键实现细节**：

1. **初始化流程**：
   ```python
   async def initialize():
       # 构建 hooks 配置
       # 注册 hook 回调 ID
       # 发送 initialize 控制请求
       # 等待响应（可配置超时）
   ```

2. **消息读取循环**：
   ```python
   async def _read_messages():
       # 从 transport 读取消息
       # 路由控制消息（control_response, control_request）
       # 转发普通消息到消息流
       # 处理错误和结束信号
   ```

3. **控制请求处理**：
   ```python
   async def _handle_control_request(request):
       # 根据 subtype 分发
       # can_use_tool: 调用权限回调
       # hook_callback: 调用注册的 hook
       # mcp_message: 桥接到 SDK MCP 服务器
       # 发送响应
   ```

4. **SDK MCP 桥接**：
   ```python
   async def _handle_sdk_mcp_request(server_name, message):
       # 手动路由 JSONRPC 消息
       # 处理 initialize, tools/list, tools/call
       # 转换 MCP 结果为 JSONRPC 响应
   ```

**注意事项**：
- Python MCP SDK 缺少 Transport 抽象，需要手动路由方法
- TypeScript SDK 有 `server.connect(transport)` 支持自定义 transport
- Python SDK 需要 `server.run(read_stream, write_stream)` 实际流

### 5. 传输层 (`_internal/transport/`)

#### Transport 抽象类

**接口定义**：

```python
class Transport(ABC):
    @abstractmethod
    async def connect() -> None

    @abstractmethod
    async def write(data: str) -> None

    @abstractmethod
    def read_messages() -> AsyncIterator[dict]

    @abstractmethod
    async def close() -> None

    @abstractmethod
    def is_ready() -> bool

    @abstractmethod
    async def end_input() -> None
```

**SubprocessCLITransport 实现**：
- 启动 `_bundled/claude` 子进程
- 通过 stdin/stdout 进行 JSON-RPC 通信
- 管理进程生命周期
- 处理错误和超时

**特点**：
- 这是一个内部 API，可能在未来版本中改变
- 支持自定义 Transport 实现（如远程连接）

### 6. MCP 支持 (`__init__.py`)

#### SDK MCP 工具

**核心功能**：
```python
# 装饰器定义工具
@tool(name, description, input_schema)
async def my_tool(args: dict) -> dict:
    return {"content": [{"type": "text", "text": "..."}]}

# 创建 in-process MCP 服务器
server = create_sdk_mcp_server(
    name="my_server",
    version="1.0.0",
    tools=[my_tool, ...]
)
```

**优势**：
- 进程内运行（无 IPC 开销）
- 更好的性能
- 更简单的部署（单进程）
- 更容易调试
- 直接访问应用状态

**实现细节**：
```python
def create_sdk_mcp_server(name, version, tools):
    # 创建 MCP Server 实例
    server = Server(name, version=version)

    # 注册 list_tools 处理器
    @server.list_tools()
    async def list_tools():
        # 转换 input_schema 为 JSON Schema
        # 返回 Tool 列表

    # 注册 call_tool 处理器
    @server.call_tool()
    async def call_tool(name, arguments):
        # 调用工具的 handler
        # 转换结果为 MCP 格式

    return McpSdkServerConfig(...)
```

### 7. 错误处理 (`_errors.py`)

**错误层次结构**：

```python
ClaudeSDKError (基类)
├── CLIConnectionError        # 连接错误
│   └── CLINotFoundError      # CLI 未找到
├── ProcessError              # 进程错误
├── CLIJSONDecodeError        # JSON 解码错误
└── MessageParseError         # 消息解析错误
```

## 开源代码的职责

### 1. **API 封装**
- 提供 Pythonic 的 API (`query()`, `ClaudeSDKClient`)
- 类型安全（使用 dataclass 和 TypedDict）
- 异步支持（基于 anyio）

### 2. **协议桥接**
- 实现控制协议（双向通信）
- 管理请求/响应路由
- 处理 Hook 和权限回调

### 3. **MCP 集成**
- 支持外部 MCP 服务器（stdio, SSE, HTTP）
- 提供 SDK MCP 服务器（in-process）
- 桥接 JSONRPC 消息到 Python MCP SDK

### 4. **进程管理**
- 启动和管理闭源 CLI 子进程
- 处理 stdin/stdout 通信
- 管理进程生命周期

### 5. **配置管理**
- 解析和验证配置选项
- 转换 Python 配置为 CLI 参数
- 管理环境变量

## 闭源 CLI 的职责（推测）

基于开源代码的交互，闭源 CLI 负责：

### 1. **核心 Agent 循环**
- 实现思考-行动循环
- 管理多轮对话
- 处理工具调用链

### 2. **Claude API 交互**
- 实际的 API 调用
- 认证和授权
- 请求/响应处理
- 流式响应解析

### 3. **工具执行引擎**
- 内置工具实现（Read, Write, Edit, Bash, Glob, Grep 等）
- 工具权限验证
- 沙箱执行
- 工具结果处理

### 4. **上下文管理**
- 对话历史管理
- 自动压缩（compact）
- Token 预算控制
- 会话持久化

### 5. **MCP 客户端**
- MCP 协议实现
- 与外部 MCP 服务器通信
- 工具发现和调用

### 6. **文件系统操作**
- 文件 checkpointing
- 文件回滚
- 工作目录管理

### 7. **权限系统**
- 权限规则评估
- 交互式权限提示
- 权限持久化

## 通信协议

### JSON-RPC over stdin/stdout

**消息格式**：

```json
// 用户消息
{
  "type": "user",
  "message": {"role": "user", "content": "..."},
  "parent_tool_use_id": null,
  "session_id": "..."
}

// 助手消息
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "..."},
      {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    ]
  },
  "model": "claude-sonnet-4-5-20250929"
}

// 控制请求
{
  "type": "control_request",
  "request_id": "req_1_abc123",
  "request": {
    "subtype": "can_use_tool",
    "tool_name": "Bash",
    "input": {"command": "ls"},
    "permission_suggestions": [...]
  }
}

// 控制响应
{
  "type": "control_response",
  "response": {
    "subtype": "success",
    "request_id": "req_1_abc123",
    "response": {
      "behavior": "allow",
      "updatedInput": {...}
    }
  }
}
```

## 关键设计模式

### 1. **Transport 抽象**
- 分离通信机制和协议逻辑
- 支持自定义传输实现
- 便于测试和扩展

### 2. **控制协议**
- 双向通信（Python ↔ CLI）
- 请求/响应匹配（通过 request_id）
- 异步回调支持

### 3. **Hook 系统**
- 事件驱动架构
- 可组合的 Hook 匹配器
- 支持异步 Hook

### 4. **权限系统**
- 回调式权限验证
- 可更新权限规则
- 支持权限建议

### 5. **Stream 管理**
- 内存对象流（anyio）
- 消息队列
- 正确的流关闭处理

## 使用场景

### ClaudeSDKClient 适用场景：
- 聊天界面
- REPL 交互
- 需要根据响应发送后续消息
- 需要中断能力
- 长时间会话

### query() 适用场景：
- 一次性查询
- 批处理
- 代码生成/分析
- CI/CD 自动化
- 已知所有输入

## 限制和注意事项

1. **异步上下文限制**：
   - ClaudeSDKClient 不能跨异步运行时上下文
   - 必须在同一个 task group 中完成所有操作

2. **Python MCP SDK 限制**：
   - 缺少 Transport 抽象
   - 需要手动路由 JSONRPC 方法
   - 与 TypeScript SDK 不对称

3. **API 稳定性**：
   - Transport 是内部 API，可能变更
   - 控制协议可能扩展新的请求类型

4. **性能考虑**：
   - 子进程通信有开销
   - SDK MCP 服务器性能更好（in-process）
   - 大型消息可能受缓冲区限制

## 总结

Claude Agent SDK 的开源部分主要是：

1. **协议层**：实现与闭源 CLI 的双向通信协议
2. **封装层**：提供 Pythonic 的 API 和类型系统
3. **桥接层**：连接 Python 代码和闭源 Agent 引擎
4. **扩展层**：支持 Hook、权限回调、MCP 集成

真正的 AI agent 逻辑、Claude API 交互、工具执行引擎都在闭源的 CLI 可执行文件中。Python SDK 更像是一个"遥控器"，让你能够用 Python 控制和扩展闭源 agent 的行为。

这种设计的优势：
- ✅ 核心逻辑闭源保护
- ✅ API 层开源便于集成
- ✅ 支持自定义扩展（Hooks, MCP, 权限）
- ✅ 跨语言一致性（TypeScript/Python SDK 共享 CLI）

劣势：
- ❌ 无法修改核心 agent 逻辑
- ❌ 调试困难（CLI 部分黑盒）
- ❌ 依赖闭源二进制
- ❌ 平台限制（需要为每个平台编译 CLI）
