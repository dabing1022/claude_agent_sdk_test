"""
E2B 沙箱实现

使用 E2B 云服务提供安全的代码执行环境。
"""

import asyncio
import logging
import os
import time
from typing import Any, Optional

from .base import BaseSandbox
from .config import SandboxConfig
from .types import ExecutionResult

logger = logging.getLogger(__name__)


class E2BSandbox(BaseSandbox):
    """
    E2B 沙箱实现
    
    使用 E2B 的 Firecracker microVM 提供强隔离的代码执行环境。
    
    需要安装: pip install e2b
    需要配置: E2B_API_KEY 环境变量或通过 config 传入
    """
    
    def __init__(self, config: SandboxConfig):
        super().__init__(config)
        self._sandbox: Any = None  # E2B Sandbox 实例
        self._api_key = config.e2b_api_key or os.environ.get("E2B_API_KEY")
        
        if not self._api_key:
            raise ValueError(
                "E2B API Key 未配置。请设置 E2B_API_KEY 环境变量或在配置中提供 e2b_api_key"
            )
    
    async def connect(self) -> None:
        """连接到 E2B 沙箱"""
        if self._is_connected:
            return
        
        try:
            # 动态导入 E2B SDK（避免未安装时报错）
            from e2b import AsyncSandbox
            
            logger.info(f"正在创建 E2B 沙箱 (模板: {self.config.e2b_template})...")
            
            # 创建沙箱
            self._sandbox = await AsyncSandbox.create(
                template=self.config.e2b_template,
                api_key=self._api_key,
                timeout=self.config.session_timeout_minutes * 60,
            )
            
            self._sandbox_id = self._sandbox.sandbox_id
            self._is_connected = True
            
            logger.info(f"E2B 沙箱创建成功: {self._sandbox_id}")
            
            # 设置工作目录
            if self.config.working_directory != "/":
                await self._sandbox.commands.run(f"mkdir -p {self.config.working_directory}")
            
        except ImportError:
            raise ImportError(
                "E2B SDK 未安装。请运行: pip install e2b"
            )
        except Exception as e:
            logger.error(f"创建 E2B 沙箱失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开 E2B 沙箱连接"""
        if not self._is_connected or self._sandbox is None:
            logger.warning("E2B 沙箱未连接或已关闭")
            return
        
        try:
            logger.info(f"正在关闭 E2B 沙箱: {self._sandbox_id}")
            await self._sandbox.kill()
            logger.info("E2B 沙箱已关闭")
        except Exception as e:
            logger.warning(f"关闭 E2B 沙箱时出错: {e}")
        finally:
            self._sandbox = None
            self._sandbox_id = None
            self._is_connected = False
    
    async def execute_bash(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """执行 Bash 命令"""
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        timeout = timeout or self.config.resource_limits.timeout_seconds
        
        try:
            logger.debug(f"执行命令: {command}")
            
            # 在工作目录中执行命令
            full_command = f"cd {self.config.working_directory} && {command}"
            
            result = await asyncio.wait_for(
                self._sandbox.commands.run(full_command),
                timeout=timeout,
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                success=result.exit_code == 0,
                output=result.stdout or "",
                error=result.stderr if result.exit_code != 0 else None,
                exit_code=result.exit_code,
                execution_time_ms=execution_time,
                sandbox_id=self._sandbox_id,
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error=f"命令执行超时 ({timeout}秒)",
                exit_code=-1,
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
        except Exception as e:
            logger.exception(f"执行命令失败: {command}")
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
    
    async def read_file(self, path: str) -> ExecutionResult:
        """读取文件"""
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        
        try:
            # 处理相对路径
            if not path.startswith("/"):
                path = f"{self.config.working_directory}/{path}"
            
            logger.debug(f"读取文件: {path}")
            
            content = await self._sandbox.files.read(path)
            
            return ExecutionResult(
                success=True,
                output=content,
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
            
        except Exception as e:
            logger.debug(f"读取文件失败: {path}, 错误: {e}")
            return ExecutionResult(
                success=False,
                error=f"读取文件失败: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
    
    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入文件"""
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        
        try:
            # 处理相对路径
            if not path.startswith("/"):
                path = f"{self.config.working_directory}/{path}"
            
            logger.debug(f"写入文件: {path}")
            
            # 确保目录存在
            dir_path = "/".join(path.split("/")[:-1])
            if dir_path:
                await self._sandbox.commands.run(f"mkdir -p {dir_path}")
            
            await self._sandbox.files.write(path, content)
            
            return ExecutionResult(
                success=True,
                output=f"文件已写入: {path}",
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
                files_created=[path] if not await self._file_exists(path) else [],
                files_modified=[path],
            )
            
        except Exception as e:
            logger.exception(f"写入文件失败: {path}")
            return ExecutionResult(
                success=False,
                error=f"写入文件失败: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
    
    async def list_files(self, path: str, pattern: Optional[str] = None) -> ExecutionResult:
        """列出文件"""
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        
        try:
            # 处理相对路径
            if not path.startswith("/"):
                path = f"{self.config.working_directory}/{path}"
            
            # 构建命令
            if pattern:
                # 使用 glob 模式
                command = f"find {path} -name '{pattern}' -type f 2>/dev/null"
            else:
                command = f"ls -la {path} 2>/dev/null"
            
            result = await self._sandbox.commands.run(command)
            
            return ExecutionResult(
                success=result.exit_code == 0,
                output=result.stdout or "",
                error=result.stderr if result.exit_code != 0 else None,
                exit_code=result.exit_code,
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
            
        except Exception as e:
            logger.exception(f"列出文件失败: {path}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
    
    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
    ) -> ExecutionResult:
        """搜索文件内容"""
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        
        try:
            # 处理相对路径
            if not path.startswith("/"):
                path = f"{self.config.working_directory}/{path}"
            
            # 构建 grep 命令
            cmd_parts = ["grep", "-r", "-n"]
            
            if file_pattern:
                cmd_parts.extend(["--include", f"'{file_pattern}'"])
            
            cmd_parts.append(f"'{pattern}'")
            cmd_parts.append(path)
            cmd_parts.append("2>/dev/null")
            
            command = " ".join(cmd_parts)
            result = await self._sandbox.commands.run(command)
            
            # grep 返回码 1 表示没找到，不算错误
            success = result.exit_code in (0, 1)
            
            return ExecutionResult(
                success=success,
                output=result.stdout or "未找到匹配内容",
                error=result.stderr if not success else None,
                exit_code=result.exit_code,
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
            
        except Exception as e:
            logger.exception(f"搜索文件失败: {pattern}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
            )
    
    async def _file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        try:
            result = await self._sandbox.commands.run(f"test -f {path}")
            return result.exit_code == 0
        except Exception:
            return False
    
    async def get_sandbox_info(self) -> dict:
        """获取沙箱信息"""
        if not self._is_connected:
            return {"error": "沙箱未连接"}
        
        return {
            "sandbox_id": self._sandbox_id,
            "template": self.config.e2b_template,
            "working_directory": self.config.working_directory,
            "is_connected": self._is_connected,
        }


# 便捷工厂函数
async def create_e2b_sandbox(config: Optional[SandboxConfig] = None) -> E2BSandbox:
    """
    创建 E2B 沙箱实例
    
    Args:
        config: 沙箱配置，如果为 None 则使用默认配置
    
    Returns:
        已连接的 E2B 沙箱实例
    """
    if config is None:
        config = SandboxConfig()
    
    sandbox = E2BSandbox(config)
    await sandbox.connect()
    return sandbox
