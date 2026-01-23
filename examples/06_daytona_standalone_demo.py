#!/usr/bin/env python3
"""
Daytona SDK 独立演示

直接使用 Daytona SDK 创建沙箱并执行代码。
这是一个独立的演示文件，不依赖项目中的其他模块。

运行前准备:
1. 安装 daytona-sdk: pip install daytona-sdk
2. 设置环境变量: export DAYTONA_API_KEY="your-api-key"

运行方式:
    python examples/06_daytona_standalone_demo.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv(override=True)

async def demo_sync_usage():
    """同步用法演示（使用同步 API）"""
    print("\n" + "=" * 60)
    print("📦 Daytona SDK 同步用法演示")
    print("=" * 60)
    
    from daytona import Daytona
    
    # 初始化 Daytona 客户端（自动使用环境变量）
    daytona = Daytona()
    
    # 创建沙箱
    print("\n🔄 正在创建沙箱...")
    sandbox = daytona.create()
    print(f"✅ 沙箱已创建: {sandbox.id}")
    
    try:
        # 1. 执行简单命令
        print("\n📌 1. 执行 Shell 命令")
        response = sandbox.process.exec("echo 'Hello from Daytona!'")
        print(f"   输出: {response.result}")
        
        # 2. 执行 Python 代码
        print("\n📌 2. 执行 Python 代码")
        code = '''
def greet(name):
    return f"Hello, {name}!"

result = greet("Daytona")
print(result)
'''
        response = sandbox.process.code_run(code)
        print(f"   输出: {response.result}")
        
        # 3. 带环境变量执行
        print("\n📌 3. 带环境变量执行")
        response = sandbox.process.exec(
            "echo $MY_SECRET",
            env={"MY_SECRET": "secret-value-123"}
        )
        print(f"   输出: {response.result}")
        
        # 4. 文件操作
        print("\n📌 4. 文件操作")
        
        # 创建目录
        sandbox.fs.create_folder("demo", "755")
        
        # 上传文件
        content = b"Hello, this is a test file!"
        sandbox.fs.upload_file(content, "demo/test.txt")
        print("   文件已上传: demo/test.txt")
        
        # 读取文件
        downloaded = sandbox.fs.download_file("demo/test.txt")
        print(f"   文件内容: {downloaded.decode('utf-8')}")
        
        # 列出文件
        files = sandbox.fs.list_files("demo")
        print(f"   目录内容: {files}")
        
        # 5. 数学计算示例
        print("\n📌 5. 数学计算")
        math_code = '''
import math

# 计算圆的面积
radius = 5
area = math.pi * radius ** 2
print(f"半径为 {radius} 的圆面积: {area:.4f}")

# 计算阶乘
n = 10
factorial = math.factorial(n)
print(f"{n}! = {factorial}")

# 计算平方根
numbers = [2, 3, 5, 7, 11]
for num in numbers:
    print(f"√{num} = {math.sqrt(num):.4f}")
'''
        response = sandbox.process.code_run(math_code)
        print(f"   输出:\n{response.result}")
        
    finally:
        # 删除沙箱
        print("\n🗑️ 正在删除沙箱...")
        daytona.delete(sandbox)
        print("✅ 沙箱已删除")


async def demo_async_usage():
    """异步用法演示"""
    print("\n" + "=" * 60)
    print("⚡ Daytona SDK 异步用法演示")
    print("=" * 60)
    
    from daytona import AsyncDaytona
    
    # 使用异步上下文管理器
    async with AsyncDaytona() as daytona:
        # 创建沙箱
        print("\n🔄 正在创建沙箱...")
        sandbox = await daytona.create()
        print(f"✅ 沙箱已创建: {sandbox.id}")
        
        try:
            # 1. 执行命令
            print("\n📌 1. 异步执行命令")
            response = await sandbox.process.exec("uname -a")
            print(f"   系统信息: {response.result}")
            
            # 2. 执行 Python 代码
            print("\n📌 2. 异步执行 Python 代码")
            code = '''
# 异步演示代码
import json

data = {
    "message": "Hello from async Daytona!",
    "numbers": [1, 2, 3, 4, 5],
    "nested": {"key": "value"}
}

print(json.dumps(data, indent=2))
'''
            response = await sandbox.process.code_run(code)
            print(f"   输出:\n{response.result}")
            
            # 3. 并发执行多个命令
            print("\n📌 3. 并发执行命令")
            import time
            start = time.time()
            
            # 创建多个并发任务
            tasks = [
                sandbox.process.exec("sleep 0.5 && echo 'Task 1 done'"),
                sandbox.process.exec("sleep 0.3 && echo 'Task 2 done'"),
                sandbox.process.exec("sleep 0.4 && echo 'Task 3 done'"),
            ]
            
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start
            
            print(f"   并发执行 3 个任务，总耗时: {elapsed:.2f}秒")
            for i, r in enumerate(results, 1):
                print(f"   任务 {i}: {r.result.strip()}")
            
        finally:
            # 删除沙箱
            print("\n🗑️ 正在删除沙箱...")
            await daytona.delete(sandbox)
            print("✅ 沙箱已删除")


async def demo_session_usage():
    """会话用法演示（保持状态）"""
    print("\n" + "=" * 60)
    print("🔗 Daytona SDK 会话用法演示")
    print("=" * 60)
    
    from daytona import Daytona, SessionExecuteRequest
    
    daytona = Daytona()
    sandbox = daytona.create()
    
    try:
        print(f"\n✅ 沙箱已创建: {sandbox.id}")
        
        # 创建会话
        session_id = "my-session"
        sandbox.process.create_session(session_id)
        print(f"\n📌 会话已创建: {session_id}")
        
        # 在会话中设置环境变量
        print("\n📌 1. 设置环境变量")
        cmd1 = sandbox.process.execute_session_command(
            session_id,
            SessionExecuteRequest(command="export MY_VAR='Hello from session'")
        )
        print(f"   退出码: {cmd1.exit_code}")
        
        # 在同一会话中读取环境变量
        print("\n📌 2. 读取环境变量（同一会话）")
        cmd2 = sandbox.process.execute_session_command(
            session_id,
            SessionExecuteRequest(command="echo $MY_VAR")
        )
        print(f"   输出: {cmd2.output}")
        
        # 在会话中创建文件
        print("\n📌 3. 创建文件")
        cmd3 = sandbox.process.execute_session_command(
            session_id,
            SessionExecuteRequest(command="echo 'Session data' > session_file.txt")
        )
        
        # 读取文件
        print("\n📌 4. 读取文件")
        cmd4 = sandbox.process.execute_session_command(
            session_id,
            SessionExecuteRequest(command="cat session_file.txt")
        )
        print(f"   文件内容: {cmd4.output}")
        
        # 获取会话命令日志
        print("\n📌 5. 获取命令日志")
        logs = sandbox.process.get_session_command_logs(session_id, cmd4.cmd_id)
        print(f"   stdout: {logs.stdout}")
        print(f"   stderr: {logs.stderr}")
        
    finally:
        daytona.delete(sandbox)
        print("\n✅ 沙箱已删除")


async def demo_advanced_features():
    """高级功能演示"""
    print("\n" + "=" * 60)
    print("🚀 Daytona SDK 高级功能演示")
    print("=" * 60)
    
    from daytona import Daytona
    
    daytona = Daytona()
    sandbox = daytona.create()
    
    try:
        print(f"\n✅ 沙箱已创建: {sandbox.id}")
        
        # 1. 复杂的 Python 代码执行
        print("\n📌 1. 数据处理示例")
        data_code = '''
# 模拟数据分析
class DataAnalyzer:
    def __init__(self, data):
        self.data = data
    
    def mean(self):
        return sum(self.data) / len(self.data)
    
    def variance(self):
        mean = self.mean()
        return sum((x - mean) ** 2 for x in self.data) / len(self.data)
    
    def std_dev(self):
        return self.variance() ** 0.5
    
    def summary(self):
        return {
            "count": len(self.data),
            "sum": sum(self.data),
            "mean": self.mean(),
            "min": min(self.data),
            "max": max(self.data),
            "variance": self.variance(),
            "std_dev": self.std_dev(),
        }

# 分析数据
data = [23, 45, 67, 12, 89, 34, 56, 78, 90, 11, 33, 55, 77, 99, 22]
analyzer = DataAnalyzer(data)

print("数据分析结果:")
for key, value in analyzer.summary().items():
    if isinstance(value, float):
        print(f"  {key}: {value:.4f}")
    else:
        print(f"  {key}: {value}")
'''
        response = sandbox.process.code_run(data_code)
        print(f"   输出:\n{response.result}")
        
        # 2. 文件搜索和替换
        print("\n📌 2. 文件搜索和替换")
        
        # 创建测试文件
        test_content = b"Hello World! This is a test. Hello again!"
        sandbox.fs.upload_file(test_content, "test_replace.txt")
        
        # 搜索内容
        matches = sandbox.fs.find_files(".", "Hello")
        print(f"   搜索 'Hello' 的结果: {matches}")
        
        # 替换内容
        sandbox.fs.replace_in_files(["test_replace.txt"], "Hello", "Hi")
        
        # 读取替换后的内容
        new_content = sandbox.fs.download_file("test_replace.txt")
        print(f"   替换后内容: {new_content.decode('utf-8')}")
        
        # 3. 获取文件信息
        print("\n📌 3. 获取文件信息")
        file_info = sandbox.fs.get_file_info("test_replace.txt")
        print(f"   文件信息: {file_info}")
        
        # 4. 错误处理
        print("\n📌 4. 错误处理演示")
        
        # 执行会失败的命令
        response = sandbox.process.exec("ls /nonexistent")
        print(f"   退出码: {response.exit_code}")
        print(f"   结果: {response.result}")
        
        # 执行有错误的代码
        bad_code = '''
# 这会产生运行时错误
x = 1 / 0
'''
        response = sandbox.process.code_run(bad_code)
        print(f"   错误代码退出码: {response.exit_code}")
        print(f"   错误信息: {response.result[:100]}...")
        
    finally:
        daytona.delete(sandbox)
        print("\n✅ 沙箱已删除")


async def main():
    """主函数"""
    print("=" * 60)
    print("🌟 Daytona SDK 完整演示")
    print("=" * 60)
    
    # 检查 API Key
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        print("\n⚠️  错误: DAYTONA_API_KEY 环境变量未设置")
        print("\n请按以下步骤操作:")
        print("1. 访问 https://www.daytona.io/ 注册账户")
        print("2. 获取 API Key")
        print("3. 设置环境变量:")
        print("   export DAYTONA_API_KEY='your-api-key'")
        print("\n4. 重新运行此脚本")
        return
    
    print(f"\n✅ API Key 已配置: {api_key[:8]}...")
    
    try:
        # 检查 SDK 是否安装
        try:
            import daytona
            print(f"✅ Daytona SDK 版本: {daytona.__version__ if hasattr(daytona, '__version__') else 'unknown'}")
        except ImportError:
            print("\n❌ Daytona SDK 未安装")
            print("   请运行: pip install daytona-sdk")
            return
        
        # 运行演示
        # 注意：同步演示使用 asyncio.to_thread 包装
        print("\n" + "-" * 60)
        print("选择要运行的演示:")
        print("1. 同步用法演示")
        print("2. 异步用法演示")
        print("3. 会话用法演示")
        print("4. 高级功能演示")
        print("5. 运行所有演示")
        print("-" * 60)
        
        choice = input("\n请输入选项 (1-5，默认 5): ").strip() or "5"
        
        if choice == "1":
            await asyncio.to_thread(lambda: asyncio.run(demo_sync_usage()))
        elif choice == "2":
            await demo_async_usage()
        elif choice == "3":
            await asyncio.to_thread(lambda: asyncio.run(demo_session_usage()))
        elif choice == "4":
            await asyncio.to_thread(lambda: asyncio.run(demo_advanced_features()))
        else:
            # 运行所有演示
            await asyncio.to_thread(lambda: asyncio.run(demo_sync_usage()))
            await demo_async_usage()
            await asyncio.to_thread(lambda: asyncio.run(demo_session_usage()))
            await asyncio.to_thread(lambda: asyncio.run(demo_advanced_features()))
        
        print("\n" + "=" * 60)
        print("✅ 演示完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 对于同步演示，我们直接运行
    # 对于需要选择的情况，使用 asyncio.run
    asyncio.run(main())
