# Claude Agent SDK 性能优化指南

## 问题：启动慢 / 卡顿

### 原因分析

Claude Agent SDK 在首次运行时会出现明显的延迟，主要原因：

1. **闭源 CLI 启动慢**
   - `_bundled/claude` 二进制文件约 174MB
   - 需要加载到内存并初始化
   - 首次启动通常需要 3-10 秒

2. **双向通信建立**
   - SDK 需要通过 stdin/stdout 与 CLI 建立双向通信
   - 初始化握手协议需要时间

3. **API 调用延迟**
   - 实际的 Claude API 调用需要网络请求
   - DeepSeek API 可能有额外延迟

## 性能优化建议

### 1. 使用带进度提示的代码

**原因**：让用户知道程序在运行，而不是卡住

**示例**：
```python
import time

async def main():
    start = time.time()
    print(f"[{time.time()-start:.1f}s] 正在初始化...")

    async for message in query(prompt="...", options=options):
        print(f"[{time.time()-start:.1f}s] 收到消息")
        # 处理消息
```

**提供的工具**：
- `examples/01_basic_usage_verbose.py` - 带详细进度提示的示例
- `tools/performance_diagnostics.py` - 性能诊断工具

### 2. 使用 ClaudeSDKClient 复用连接

**原因**：避免每次查询都重新启动 CLI

**对比**：

❌ **慢速方式**（每次都启动 CLI）：
```python
# 每次查询都启动新的 CLI 进程
async for msg in query(prompt="问题1", options=options):
    pass  # 耗时 5-10s

async for msg in query(prompt="问题2", options=options):
    pass  # 又耗时 5-10s
```

✅ **快速方式**（复用连接）：
```python
async with ClaudeSDKClient(options) as client:
    # 只启动一次 CLI（5-10s）

    await client.query("问题1")
    async for msg in client.receive_response():
        pass  # 快速，只有 API 调用延迟

    await client.query("问题2")
    async for msg in client.receive_response():
        pass  # 快速，只有 API 调用延迟
```

### 3. 调整超时和缓冲区设置

**默认值可能太保守**：

```python
import os

# 增加流关闭超时（默认 60 秒）
os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] = "120000"  # 120 秒

options = ClaudeAgentOptions(
    max_buffer_size=1024*1024,  # 1MB 缓冲区
    # ...
)
```

### 4. 使用更简洁的 system prompt

**原因**：减少 token 使用，加快响应

❌ **冗长**：
```python
system_prompt="你是一个非常有帮助的 AI 助手，专注于提供准确、详细、有深度的回答..."
```

✅ **简洁**：
```python
system_prompt="你是一个助手。"
```

### 5. 限制 max_turns 和 max_budget

**原因**：防止无限循环，加快失败响应

```python
options = ClaudeAgentOptions(
    max_turns=5,              # 最多 5 轮对话
    max_budget_usd=0.10,      # 最多花费 $0.10
    # ...
)
```

### 6. 并行处理多个查询

**场景**：需要问多个独立的问题

```python
import asyncio

async def ask_question(prompt: str):
    async for msg in query(prompt=prompt, options=options):
        # 处理响应
        pass

# 并行运行多个查询
await asyncio.gather(
    ask_question("问题1"),
    ask_question("问题2"),
    ask_question("问题3"),
)
```

### 7. 使用本地缓存（适用于重复查询）

**自己实现简单缓存**：

```python
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(".cache/claude_responses")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_cache_key(prompt: str, options: dict) -> str:
    """生成缓存键"""
    content = f"{prompt}:{json.dumps(options, sort_keys=True)}"
    return hashlib.md5(content.encode()).hexdigest()

async def cached_query(prompt: str, options: ClaudeAgentOptions):
    """带缓存的查询"""
    cache_key = get_cache_key(prompt, {})
    cache_file = CACHE_DIR / f"{cache_key}.json"

    # 检查缓存
    if cache_file.exists():
        print("使用缓存结果")
        with open(cache_file) as f:
            return json.load(f)

    # 实际查询
    result = []
    async for msg in query(prompt=prompt, options=options):
        result.append(msg)

    # 保存缓存
    with open(cache_file, 'w') as f:
        json.dump(result, f)

    return result
```

## 使用建议

### 场景 1：单次查询

**适合**: 一次性问题，如 CLI 工具

**推荐方式**: `query()`

```python
async for message in query(prompt="...", options=options):
    # 处理消息
```

### 场景 2：多轮对话

**适合**: 聊天应用、REPL

**推荐方式**: `ClaudeSDKClient`

```python
async with ClaudeSDKClient(options) as client:
    while True:
        user_input = input("You: ")
        await client.query(user_input)
        async for msg in client.receive_response():
            # 处理消息
```

### 场景 3：批量处理

**适合**: 处理多个独立任务

**推荐方式**: 并行 `query()`

```python
tasks = [query(prompt=p, options=options) for p in prompts]
await asyncio.gather(*tasks)
```

## 性能基准

### 正常耗时参考

基于 174MB CLI 二进制和网络 API：

| 阶段 | 预期耗时 | 说明 |
|------|---------|------|
| CLI 启动 | 3-10 秒 | 首次启动，加载二进制 |
| 初始化握手 | 0.5-2 秒 | 建立双向通信 |
| API 调用 | 1-5 秒 | 取决于网络和模型 |
| **总计（首次）** | **5-17 秒** | 正常范围 |
| **后续查询** | **1-5 秒** | 只有 API 延迟 |

### 异常情况

如果超过以下时间，可能存在问题：

- CLI 启动 > 20 秒：检查系统资源、磁盘速度
- API 调用 > 30 秒：检查网络连接、API 配额
- 完全卡住不动：检查 API Key、防火墙设置

## 诊断工具使用

### 1. 运行性能诊断

```bash
python tools/performance_diagnostics.py
```

输出示例：
```
[  0.00s] 开始
[  0.01s] 检查环境变量
[  0.02s] 检查 CLI 二进制
[  0.03s] 创建配置
[  0.04s] 开始查询（启动 CLI 子进程）
[  5.23s] 收到第一条消息 (SystemMessage)
[  6.45s] 助手回复 (包含 1 个文本块)
[  6.50s] 收到结果消息
[  6.51s] 查询完成

瓶颈分析:
CLI 启动耗时: 5.19s
  ℹ️  CLI 启动时间适中（2-5秒）
```

### 2. 运行带进度的示例

```bash
python examples/01_basic_usage_verbose.py
```

## 常见问题

### Q: 为什么第一次运行这么慢？

A: 这是正常现象。闭源 CLI 需要加载 174MB 的二进制文件。后续查询会快很多。

### Q: 能否预热 CLI 避免延迟？

A: 可以。使用 `ClaudeSDKClient` 并保持连接：

```python
# 启动时预热
client = ClaudeSDKClient(options)
await client.connect()

# 后续使用都很快
await client.query("...")
```

### Q: 使用 DeepSeek API 会更慢吗？

A: 可能。DeepSeek 的 Anthropic 兼容 API 可能有额外的转换开销。建议使用官方 Anthropic API 以获得最佳性能。

### Q: 可以禁用某些功能加快速度吗？

A: 部分可以：

```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",  # 跳过权限检查
    max_turns=3,                          # 限制最大轮次
    disallowed_tools=["Bash", "WebFetch"], # 禁用某些工具
)
```

## 总结

**关键要点**：

1. ✅ **首次启动慢是正常的**（5-10 秒）
2. ✅ **使用进度提示**避免用户以为卡住
3. ✅ **复用连接**（ClaudeSDKClient）处理多个查询
4. ✅ **使用诊断工具**定位具体瓶颈
5. ❌ **不要**每次查询都创建新的 query
6. ❌ **不要**使用过于复杂的 system prompt

**下一步**：

运行性能诊断工具了解你的系统具体情况：

```bash
python tools/performance_diagnostics.py
```
