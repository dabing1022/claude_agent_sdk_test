"""快速测试：只测试 CLI 启动时间"""

import time
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=" * 70)
print("Claude Agent SDK 快速测试")
print("=" * 70)

# 检查环境
print("\n1. 环境检查：")
print(f"   • Python 版本: {os.sys.version.split()[0]}")
print(f"   • 工作目录: {os.getcwd()}")

api_key = os.getenv("ANTHROPIC_API_KEY")
base_url = os.getenv("ANTHROPIC_BASE_URL")
print(f"   • API Key: {'已设置' if api_key else '未设置'}")
print(f"   • Base URL: {base_url or '默认'}")

# 检查 CLI 二进制
print("\n2. CLI 二进制检查：")
cli_path = Path(".venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude")
if cli_path.exists():
    size_mb = cli_path.stat().st_size / (1024 * 1024)
    print(f"   ✓ CLI 找到: {size_mb:.1f} MB")
else:
    print(f"   ✗ CLI 未找到")
    exit(1)

# 测试导入时间
print("\n3. 导入测试：")
start = time.time()
try:
    from claude_agent_sdk import query, ClaudeAgentOptions
    import_time = time.time() - start
    print(f"   ✓ 导入成功: {import_time:.2f}s")
except Exception as e:
    print(f"   ✗ 导入失败: {e}")
    exit(1)

# 测试 CLI 启动（不实际调用 API）
print("\n4. CLI 启动测试（这会比较慢）：")
print("   提示: 首次启动 CLI 需要 5-10 秒，这是正常的...")

start = time.time()
try:
    import subprocess

    # 只测试 CLI 能否启动和返回版本信息
    result = subprocess.run(
        [str(cli_path), "--version"],
        capture_output=True,
        text=True,
        timeout=30
    )

    startup_time = time.time() - start

    if result.returncode == 0:
        print(f"   ✓ CLI 启动成功: {startup_time:.2f}s")
        print(f"   版本信息: {result.stdout.strip()}")
    else:
        print(f"   ⚠ CLI 返回错误码: {result.returncode}")
        print(f"   启动耗时: {startup_time:.2f}s")
        if result.stderr:
            print(f"   错误信息: {result.stderr[:200]}")

except subprocess.TimeoutExpired:
    print(f"   ✗ CLI 启动超时 (>30s)")
except Exception as e:
    print(f"   ✗ CLI 启动失败: {e}")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)

print("\n📊 性能总结：")
print(f"   • 导入耗时: {import_time:.2f}s")
if 'startup_time' in locals():
    print(f"   • CLI 启动: {startup_time:.2f}s")

    if startup_time > 10:
        print("\n⚠️  分析：CLI 启动较慢 (>10s)")
        print("   原因：174MB 二进制文件加载时间")
        print("   建议：这是正常现象，使用 ClaudeSDKClient 复用连接")
    elif startup_time > 5:
        print("\nℹ️  分析：CLI 启动时间适中 (5-10s)")
        print("   这是正常范围，后续查询会更快")
    else:
        print("\n✓ 分析：CLI 启动快速 (<5s)")

print("\n💡 优化建议：")
print("   1. 使用 ClaudeSDKClient 复用连接（避免重复启动）")
print("   2. 使用带进度提示的示例（让用户知道程序在运行）")
print("   3. 查看 docs/PERFORMANCE_OPTIMIZATION.md 了解更多")

print("=" * 70)
