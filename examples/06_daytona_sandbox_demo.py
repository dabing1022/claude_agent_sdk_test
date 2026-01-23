#!/usr/bin/env python3
"""
Daytona Sandbox 演示

展示如何使用 Daytona SDK 创建安全的代码执行沙箱环境。

运行前准备:
1. 安装 daytona-sdk: pip install daytona-sdk
2. 设置环境变量: export DAYTONA_API_KEY="your-api-key"
3. (可选) 设置 API URL: export DAYTONA_API_URL="https://your-api.com"

运行方式:
    python examples/06_daytona_sandbox_demo.py
"""

import asyncio
import logging
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv

from claude_agent_test.sandbox.config import SandboxConfig, SandboxType
from claude_agent_test.sandbox.daytona_sandbox import DaytonaSandbox, create_daytona_sandbox

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

async def demo_basic_usage():
    """基础用法演示"""
    print("\n" + "=" * 60)
    print("📦 Daytona Sandbox 基础用法演示")
    print("=" * 60)
    
    # 创建配置
    # Daytona 沙箱有默认工作目录，不需要手动指定
    config = SandboxConfig(
        sandbox_type=SandboxType.DAYTONA,
        debug=False,
    )
    
    # 使用上下文管理器自动管理沙箱生命周期
    async with DaytonaSandbox(config) as sandbox:
        print(f"\n✅ 沙箱已创建: {sandbox.sandbox_id}")
        
        # 1. 执行简单命令
        print("\n📌 1. 执行简单命令")
        result = await sandbox.execute_bash("echo 'Hello from Daytona!'")
        print(f"   输出: {result.output.strip()}")
        print(f"   耗时: {result.execution_time_ms}ms")
        
        # 2. 查看系统信息
        print("\n📌 2. 查看系统信息")
        result = await sandbox.execute_bash("uname -a")
        print(f"   系统: {result.output.strip()}")
        
        # 3. 检查 Python 版本
        print("\n📌 3. 检查 Python 版本")
        result = await sandbox.execute_bash("python3 --version")
        print(f"   Python: {result.output.strip()}")
        
        # 4. 获取沙箱信息
        print("\n📌 4. 沙箱信息")
        info = await sandbox.get_sandbox_info()
        for key, value in info.items():
            print(f"   {key}: {value}")


async def demo_code_execution():
    """代码执行演示"""
    print("\n" + "=" * 60)
    print("🐍 Daytona Sandbox 代码执行演示")
    print("=" * 60)
    
    config = SandboxConfig(sandbox_type=SandboxType.DAYTONA)
    
    async with DaytonaSandbox(config) as sandbox:
        # 1. 执行 Python 代码
        print("\n📌 1. 执行 Python 代码")
        code = '''
def fibonacci(n):
    """计算斐波那契数列"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# 计算前 10 个斐波那契数
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
'''
        result = await sandbox.execute_code(code)
        print(f"   输出:\n{result.output}")
        print(f"   耗时: {result.execution_time_ms}ms")
        
        # 2. 带环境变量的代码执行
        print("\n📌 2. 带环境变量的代码执行")
        code_with_env = '''
import os
api_key = os.environ.get('MY_API_KEY', 'not set')
debug_mode = os.environ.get('DEBUG', 'false')
print(f"API Key: {api_key}")
print(f"Debug Mode: {debug_mode}")
'''
        result = await sandbox.execute_code(
            code_with_env,
            env={"MY_API_KEY": "secret-123", "DEBUG": "true"}
        )
        print(f"   输出:\n{result.output}")
        
        # 3. 数据处理示例
        print("\n📌 3. 数据处理示例")
        data_code = '''
# 简单的数据处理
data = [
    {"name": "Alice", "score": 85},
    {"name": "Bob", "score": 92},
    {"name": "Charlie", "score": 78},
    {"name": "Diana", "score": 96},
]

# 计算平均分
avg_score = sum(d["score"] for d in data) / len(data)
print(f"平均分: {avg_score:.2f}")

# 找出最高分
top_student = max(data, key=lambda x: x["score"])
print(f"最高分: {top_student['name']} ({top_student['score']}分)")

# 排序
sorted_data = sorted(data, key=lambda x: x["score"], reverse=True)
print("\\n排名:")
for i, d in enumerate(sorted_data, 1):
    print(f"  {i}. {d['name']}: {d['score']}分")
'''
        result = await sandbox.execute_code(data_code)
        print(f"   输出:\n{result.output}")


async def demo_file_operations():
    """文件操作演示（使用 shell 命令）"""
    print("\n" + "=" * 60)
    print("📁 Daytona Sandbox 文件操作演示")
    print("=" * 60)
    
    config = SandboxConfig(sandbox_type=SandboxType.DAYTONA)
    
    async with DaytonaSandbox(config) as sandbox:
        # 1. 使用 shell 命令创建文件
        print("\n📌 1. 创建 Python 脚本")
        create_script = '''cat > hello.py << 'EOF'
#!/usr/bin/env python3
"""示例 Python 脚本"""

def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("Daytona"))
    print(greet("World"))
EOF'''
        result = await sandbox.execute_bash(create_script)
        print(f"   文件创建完成")
        
        # 2. 读取文件
        print("\n📌 2. 读取文件内容")
        result = await sandbox.execute_bash("cat hello.py")
        print(f"   文件内容:\n{result.output}")
        
        # 3. 执行脚本
        print("\n📌 3. 执行脚本")
        result = await sandbox.execute_bash("python3 hello.py")
        print(f"   输出: {result.output}")
        
        # 4. 列出文件
        print("\n📌 4. 列出文件")
        result = await sandbox.execute_bash("ls -la")
        print(f"   文件列表:\n{result.output}")
        
        # 5. 创建项目结构
        print("\n📌 5. 创建项目结构")
        await sandbox.execute_bash("mkdir -p myproject/src myproject/tests")
        
        # 写入主模块
        create_main = '''cat > myproject/src/math_utils.py << 'EOF'
"""主模块"""

def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
EOF'''
        await sandbox.execute_bash(create_main)
        
        # 写入测试文件
        create_test = '''cat > myproject/tests/test_math.py << 'EOF'
"""测试模块"""
import sys
sys.path.insert(0, '../src')
from math_utils import add, multiply

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    print("add 测试通过!")

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-2, 3) == -6
    print("multiply 测试通过!")

if __name__ == "__main__":
    test_add()
    test_multiply()
    print("所有测试通过!")
EOF'''
        await sandbox.execute_bash(create_test)
        print("   项目结构创建完成")
        
        # 运行测试
        print("\n📌 6. 运行测试")
        result = await sandbox.execute_bash("cd myproject/tests && python3 test_math.py")
        print(f"   测试结果:\n{result.output}")
        
        # 显示项目结构
        print("\n📌 7. 项目结构")
        result = await sandbox.execute_bash("find myproject -type f")
        print(f"   结构:\n{result.output}")


async def demo_advanced_usage():
    """高级用法演示"""
    print("\n" + "=" * 60)
    print("🚀 Daytona Sandbox 高级用法演示")
    print("=" * 60)
    
    # Daytona 沙箱使用默认工作目录
    config = SandboxConfig(sandbox_type=SandboxType.DAYTONA)
    
    async with DaytonaSandbox(config) as sandbox:
        # 1. 安装 Python 包并使用
        print("\n📌 1. 安装并使用 Python 包")
        
        # 安装 requests（如果可用）
        install_result = await sandbox.execute_bash("pip install requests --quiet 2>/dev/null || echo 'pip not available'")
        
        # 使用标准库演示
        http_code = '''
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

# 使用标准库获取 JSON 数据
try:
    # 使用 httpbin 测试 API
    url = "https://httpbin.org/json"
    req = Request(url, headers={"User-Agent": "Daytona-Sandbox"})
    with urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode())
        print("API 响应:")
        print(json.dumps(data, indent=2))
except URLError as e:
    print(f"网络请求失败: {e}")
except Exception as e:
    print(f"发生错误: {e}")
'''
        result = await sandbox.execute_code(http_code)
        print(f"   输出:\n{result.output}")
        
        # 2. 并发执行多个命令
        print("\n📌 2. 并发执行命令")
        
        commands = [
            "echo 'Task 1' && sleep 0.5 && echo 'Task 1 完成'",
            "echo 'Task 2' && sleep 0.3 && echo 'Task 2 完成'",
            "echo 'Task 3' && sleep 0.4 && echo 'Task 3 完成'",
        ]
        
        import time
        start = time.time()
        
        # 并发执行
        tasks = [sandbox.execute_bash(cmd) for cmd in commands]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        print(f"   并发执行 {len(commands)} 个任务，总耗时: {elapsed:.2f}秒")
        for i, r in enumerate(results, 1):
            print(f"   任务 {i}: {r.output.strip()}")
        
        # 3. 错误处理演示
        print("\n📌 3. 错误处理演示")
        
        # 执行会失败的命令
        result = await sandbox.execute_bash("ls /nonexistent_directory")
        print(f"   成功: {result.success}")
        print(f"   退出码: {result.exit_code}")
        print(f"   错误: {result.error}")
        
        # 执行有语法错误的代码
        bad_code = '''
def broken_function(
    print("missing closing parenthesis"
'''
        result = await sandbox.execute_code(bad_code)
        print(f"\n   语法错误代码执行:")
        print(f"   成功: {result.success}")
        print(f"   错误: {result.error[:100]}..." if result.error and len(result.error) > 100 else f"   错误: {result.error}")


async def demo_quick_start():
    """快速开始演示 - 使用便捷函数"""
    print("\n" + "=" * 60)
    print("⚡ Daytona Sandbox 快速开始")
    print("=" * 60)
    
    # 使用便捷函数创建沙箱
    sandbox = await create_daytona_sandbox()
    
    try:
        print(f"\n✅ 沙箱已创建: {sandbox.sandbox_id}")
        
        # 执行一些操作
        result = await sandbox.execute_bash("echo 'Quick start demo!'")
        print(f"   输出: {result.output.strip()}")
        
        result = await sandbox.execute_code("print('Hello from Python!')")
        print(f"   代码输出: {result.output.strip()}")
        
    finally:
        # 手动断开连接
        await sandbox.disconnect()
        print("\n✅ 沙箱已关闭")


async def main():
    """主函数"""
    print("=" * 60)
    print("🌟 Daytona Sandbox 演示程序")
    print("=" * 60)
    
    # 检查 API Key
    if not os.environ.get("DAYTONA_API_KEY"):
        print("\n⚠️  警告: DAYTONA_API_KEY 环境变量未设置")
        print("   请设置环境变量后再运行:")
        print("   export DAYTONA_API_KEY='your-api-key'")
        print("\n   或者使用模拟模式运行演示...")
        
        # 显示如何获取 API Key
        print("\n📖 获取 Daytona API Key:")
        print("   1. 访问 https://www.daytona.io/")
        print("   2. 注册/登录账户")
        print("   3. 在控制台获取 API Key")
        return
    
    try:
        # 运行各个演示
        await demo_basic_usage()
        await demo_code_execution()
        await demo_file_operations()
        await demo_advanced_usage()
        await demo_quick_start()
        
        print("\n" + "=" * 60)
        print("✅ 所有演示完成!")
        print("=" * 60)
        
    except ImportError as e:
        print(f"\n❌ 导入错误: {e}")
        print("   请确保已安装 daytona-sdk:")
        print("   pip install daytona-sdk")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        logger.exception("演示过程中发生错误")


if __name__ == "__main__":
    asyncio.run(main())
