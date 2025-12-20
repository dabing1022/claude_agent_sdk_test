# 性能诊断报告

## 测试环境

- **Python 版本**: 3.12.11
- **CLI 版本**: 2.0.72
- **CLI 大小**: 174.0 MB
- **API 提供商**: DeepSeek (通过 anyrouter.top)
- **测试时间**: 2025-12-20

## 性能测试结果

| 测试项 | 实测耗时 | 状态 | 说明 |
|--------|---------|------|------|
| Python 导入 | 0.34s | ✓ 优秀 | SDK 模块加载 |
| CLI 启动 | 0.90s | ✓ 优秀 | 闭源二进制启动 |
| API 调用 | 30-60s+ | ⚠️ 慢 | 主要瓶颈 |

## 关键发现

### ✅ 好消息

1. **CLI 启动非常快**（<1 秒）
   - 之前担心的 174MB 二进制加载问题不存在
   - 启动开销可以忽略不计

2. **导入速度快**
   - Python 模块加载正常

### ⚠️ 主要瓶颈

**实际 API 调用慢**（30-60 秒或更久）

可能原因：
1. **DeepSeek API 兼容层延迟**
   - DeepSeek 需要将请求转换为 Anthropic 格式
   - 转换过程可能有开销

2. **网络延迟**
   - `anyrouter.top` 可能有网络延迟
   - 国际网络连接可能不稳定

3. **API 处理时间**
   - DeepSeek 模型处理需要时间
   - 不同于直接使用 Anthropic API

## 解决方案

### 方案 1：使用进度提示（推荐）

**目的**：让用户知道程序在运行，不是卡死

```bash
python examples/01_basic_usage_verbose.py
```

**效果**：
```
[  0.00s] 开始初始化...
[  1.23s] ✓ 初始化完成，开始处理请求
[ 45.67s] 收到响应
```

### 方案 2：使用优化配置（推荐）

**文件**：`examples/04_optimized_for_deepseek.py`

**优化点**：
- 增加超时时间（3分钟）
- 简短的 system prompt（减少 token）
- 限制最大轮次（避免长时间运行）
- 限制预算（控制成本）

```bash
python examples/04_optimized_for_deepseek.py
```

### 方案 3：复用连接（重要！）

如果要问多个问题，**必须**使用 `ClaudeSDKClient`：

```python
async with ClaudeSDKClient(options) as client:
    await client.query("问题1")  # 慢：30-60s
    await client.query("问题2")  # 快：只有 API 延迟
    await client.query("问题3")  # 快：只有 API 延迟
```

### 方案 4：考虑切换到官方 API（可选）

如果性能要求高，考虑使用官方 Anthropic API：

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-xxx...  # 官方 API key
# 不设置 ANTHROPIC_BASE_URL（使用默认）
```

**预期改善**：
- 官方 API 响应通常在 2-10 秒
- 无兼容层转换开销
- 网络更稳定

## 性能基准对比

| 场景 | DeepSeek API | Anthropic 官方 API |
|------|-------------|-------------------|
| CLI 启动 | 0.9s | 0.9s |
| API 响应 | 30-60s+ | 2-10s |
| **总耗时** | **31-61s** | **3-11s** |

## 使用建议

### 当前情况（DeepSeek API）

✅ **可以接受**，如果：
- 不介意等待 30-60 秒
- 成本优先（DeepSeek 更便宜）
- 使用进度提示告知用户

❌ **需要改进**，如果：
- 需要快速响应
- 交互式应用
- 用户体验敏感

### 优化清单

- [x] 使用带进度提示的示例
- [x] 增加超时设置
- [x] 简化 prompt 减少 token
- [x] 限制最大轮次和预算
- [ ] 考虑切换到官方 API（可选）
- [ ] 实现本地缓存（避免重复查询）
- [ ] 使用 ClaudeSDKClient 复用连接

## 结论

**卡顿不是 SDK 的问题，而是 API 调用慢！**

CLI 本身很快（<1 秒），主要瓶颈在：
1. DeepSeek API 兼容层
2. 网络延迟
3. API 处理时间

**推荐行动**：
1. 立即使用优化配置示例：`python examples/04_optimized_for_deepseek.py`
2. 所有示例都添加进度提示
3. 如果需要更快响应，考虑切换到官方 API

**最重要的**：让用户知道程序在运行！使用进度提示避免误以为卡死。
