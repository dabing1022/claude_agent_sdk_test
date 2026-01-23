"""
Daytona 沙箱实现

使用 Daytona SDK 提供安全的代码执行环境。
Daytona 提供快速的沙箱创建、隔离运行时和程序化控制。
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


def _get_output_from_response(result: Any, debug: bool = False) -> str:
    """从 ExecuteResponse 中提取输出"""
    output_parts = []
    
    if debug:
        # 调试：打印所有属性
        logger.info(f"Response type: {type(result)}")
        logger.info(f"Response attributes: {dir(result)}")
        for attr in ['result', 'output', 'stdout', 'stderr', 'artifacts', 'exit_code']:
            if hasattr(result, attr):
                val = getattr(result, attr)
                logger.info(f"  {attr}: {repr(val)[:200]}")
    
    # 尝试 result 字段
    if hasattr(result, 'result') and result.result:
        output_parts.append(str(result.result))
    
    # 尝试 artifacts.stdout
    if hasattr(result, 'artifacts') and result.artifacts:
        if debug:
            logger.info(f"Artifacts type: {type(result.artifacts)}")
            logger.info(f"Artifacts attributes: {dir(result.artifacts)}")
        if hasattr(result.artifacts, 'stdout') and result.artifacts.stdout:
            stdout = str(result.artifacts.stdout)
            if stdout not in output_parts:
                output_parts.append(stdout)
        # 也检查 stderr（用于错误信息）
        if hasattr(result.artifacts, 'stderr') and result.artifacts.stderr:
            stderr = str(result.artifacts.stderr)
            if stderr not in output_parts:
                output_parts.append(stderr)
    
    # 尝试 output 字段（SessionExecuteResponse 使用）
    if hasattr(result, 'output') and result.output:
        output = str(result.output)
        if output not in output_parts:
            output_parts.append(output)
    
    # 尝试 stdout 字段（直接在 result 上）
    if hasattr(result, 'stdout') and result.stdout:
        stdout = str(result.stdout)
        if stdout not in output_parts:
            output_parts.append(stdout)
    
    return "\n".join(output_parts) if output_parts else ""


class DaytonaSandbox(BaseSandbox):
    """
    Daytona 沙箱实现
    
    使用 Daytona 提供安全、弹性的 AI 代码执行基础设施。
    
    需要安装: pip install daytona-sdk
    需要配置: DAYTONA_API_KEY 环境变量或通过 config 传入
    
    特性:
    - 快速沙箱创建（毫秒级）
    - 隔离的运行时环境
    - 支持多种编程语言
    - 文件系统操作
    - 持久化会话支持
    """
    
    def __init__(self, config: SandboxConfig):
        super().__init__(config)
        self._daytona: Any = None  # AsyncDaytona 客户端
        self._sandbox: Any = None  # Sandbox 实例
        self._api_key = config.daytona_api_key or os.environ.get("DAYTONA_API_KEY")
        self._api_url = config.daytona_base_url or os.environ.get("DAYTONA_API_URL")
        
        if not self._api_key:
            raise ValueError(
                "Daytona API Key 未配置。请设置 DAYTONA_API_KEY 环境变量或在配置中提供 daytona_api_key"
            )
    
    async def connect(self) -> None:
        """连接到 Daytona 沙箱"""
        if self._is_connected:
            return
        
        try:
            # 动态导入 Daytona SDK（避免未安装时报错）
            from daytona import AsyncDaytona, DaytonaConfig
            
            logger.info("正在创建 Daytona 沙箱...")
            
            # 创建配置
            daytona_config = DaytonaConfig(
                api_key=self._api_key,
            )
            if self._api_url:
                daytona_config.api_url = self._api_url
            
            # 创建 Daytona 客户端
            self._daytona = AsyncDaytona(daytona_config)
            
            # 创建沙箱
            self._sandbox = await self._daytona.create()
            
            self._sandbox_id = self._sandbox.id
            self._is_connected = True
            
            logger.info(f"Daytona 沙箱创建成功: {self._sandbox_id}")
            
            # Daytona 沙箱有默认工作目录（通常是 /home/daytona 或 Dockerfile 中的 WORKDIR）
            # 不需要手动创建工作目录，SDK 会自动处理相对路径
            
        except ImportError:
            raise ImportError(
                "Daytona SDK 未安装。请运行: pip install daytona-sdk"
            )
        except Exception as e:
            logger.error(f"创建 Daytona 沙箱失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开 Daytona 沙箱连接"""
        if not self._is_connected:
            logger.warning("Daytona 沙箱未连接或已关闭")
            return
        
        try:
            logger.info(f"正在关闭 Daytona 沙箱: {self._sandbox_id}")
            
            if self._sandbox and self._daytona:
                await self._daytona.delete(self._sandbox)
            
            if self._daytona:
                await self._daytona.close()
            
            logger.info("Daytona 沙箱已关闭")
        except Exception as e:
            logger.warning(f"关闭 Daytona 沙箱时出错: {e}")
        finally:
            self._sandbox = None
            self._daytona = None
            self._sandbox_id = None
            self._is_connected = False
    
    def _normalize_path(self, path: str) -> str:
        """
        规范化路径
        
        Daytona SDK 支持相对路径，会自动相对于沙箱工作目录解析。
        绝对路径（以 / 开头）会直接使用。
        """
        # 移除开头的 ./ 
        if path.startswith("./"):
            path = path[2:]
        # 如果是 . 则返回空字符串（表示当前目录）
        if path == ".":
            return ""
        return path
    
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
            
            # 执行命令（不指定 cwd，让命令自己处理目录）
            # Daytona 沙箱默认工作目录已经是合适的
            result = await asyncio.wait_for(
                self._sandbox.process.exec(command, timeout=timeout),
                timeout=timeout + 5,  # 额外 5 秒用于网络延迟
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            # 启用调试模式查看返回结构
            output = _get_output_from_response(result, debug=self.config.debug)
            
            return ExecutionResult(
                success=result.exit_code == 0,
                output=output,
                error=output if result.exit_code != 0 else None,
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
    
    async def execute_code(
        self, 
        code: str, 
        language: str = "python",
        env: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        执行代码片段
        
        Args:
            code: 要执行的代码
            language: 编程语言（目前主要支持 python）
            env: 环境变量（注意：通过在代码前设置环境变量实现）
        
        Returns:
            ExecutionResult: 执行结果
        """
        if not self._is_connected:
            return ExecutionResult(
                success=False,
                error="沙箱未连接",
            )
        
        start_time = time.time()
        
        try:
            logger.debug(f"执行 {language} 代码")
            
            # 如果有环境变量，在代码前添加设置环境变量的代码
            if env:
                env_setup = "\n".join([
                    "import os",
                    *[f"os.environ['{k}'] = '{v}'" for k, v in env.items()],
                    "",  # 空行分隔
                ])
                code = env_setup + code
            
            result = await self._sandbox.process.code_run(code)
            
            execution_time = int((time.time() - start_time) * 1000)
            output = _get_output_from_response(result)
            
            return ExecutionResult(
                success=result.exit_code == 0,
                output=output,
                error=output if result.exit_code != 0 else None,
                exit_code=result.exit_code,
                execution_time_ms=execution_time,
                sandbox_id=self._sandbox_id,
            )
            
        except Exception as e:
            logger.exception("执行代码失败")
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
            # 规范化路径（Daytona SDK 支持相对路径）
            remote_path = self._normalize_path(path)
            
            logger.debug(f"读取文件: {remote_path}")
            
            # 使用 fs.download_file 读取文件内容
            content = await self._sandbox.fs.download_file(remote_path)
            
            # 如果返回的是 bytes，转换为字符串
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            
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
            # 规范化路径
            remote_path = self._normalize_path(path)
            
            logger.debug(f"写入文件: {remote_path}")
            
            # 确保目录存在（使用 shell 命令）
            dir_path = "/".join(remote_path.split("/")[:-1])
            if dir_path:
                await self._sandbox.process.exec(f"mkdir -p {dir_path}")
            
            # 写入文件（需要转换为 bytes）
            content_bytes = content.encode("utf-8") if isinstance(content, str) else content
            await self._sandbox.fs.upload_file(content_bytes, remote_path)
            
            return ExecutionResult(
                success=True,
                output=f"文件已写入: {remote_path}",
                execution_time_ms=int((time.time() - start_time) * 1000),
                sandbox_id=self._sandbox_id,
                files_modified=[remote_path],
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
            # 规范化路径（. 变为空字符串表示当前目录）
            remote_path = self._normalize_path(path)
            # 如果是空字符串，使用 "." 表示当前目录
            if not remote_path:
                remote_path = "."
            
            logger.debug(f"列出文件: {remote_path}")
            
            if pattern:
                # 使用搜索功能
                files = await self._sandbox.fs.search_files(remote_path, pattern)
                output = "\n".join(str(f) for f in files) if files else "未找到匹配文件"
            else:
                # 列出目录内容
                files = await self._sandbox.fs.list_files(remote_path)
                # 格式化输出
                if files:
                    output_lines = []
                    for f in files:
                        # 尝试获取文件名
                        if hasattr(f, 'name'):
                            name = f.name
                            is_dir = getattr(f, 'is_dir', False)
                            size = getattr(f, 'size', 0)
                            output_lines.append(f"{'[DIR]' if is_dir else '[FILE]'} {name} ({size} bytes)")
                        elif hasattr(f, 'path'):
                            output_lines.append(f.path)
                        else:
                            output_lines.append(str(f))
                    output = "\n".join(output_lines)
                else:
                    output = "目录为空"
            
            return ExecutionResult(
                success=True,
                output=output,
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
            # 规范化路径
            remote_path = self._normalize_path(path)
            if not remote_path:
                remote_path = "."
            
            logger.debug(f"搜索文件内容: {pattern} in {remote_path}")
            
            # 使用 fs.find_files 搜索内容
            matches = await self._sandbox.fs.find_files(remote_path, pattern)
            
            if matches:
                output = "\n".join(str(m) for m in matches)
            else:
                output = "未找到匹配内容"
            
            return ExecutionResult(
                success=True,
                output=output,
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
    
    async def get_sandbox_info(self) -> dict:
        """获取沙箱信息"""
        if not self._is_connected:
            return {"error": "沙箱未连接"}
        
        return {
            "sandbox_id": self._sandbox_id,
            "working_directory": self.config.working_directory,
            "is_connected": self._is_connected,
            "provider": "daytona",
        }


# 便捷工厂函数
async def create_daytona_sandbox(config: Optional[SandboxConfig] = None) -> DaytonaSandbox:
    """
    创建 Daytona 沙箱实例
    
    Args:
        config: 沙箱配置，如果为 None 则使用默认配置
    
    Returns:
        已连接的 Daytona 沙箱实例
    """
    from .config import SandboxType
    
    if config is None:
        config = SandboxConfig(sandbox_type=SandboxType.DAYTONA)
    
    sandbox = DaytonaSandbox(config)
    await sandbox.connect()
    return sandbox
