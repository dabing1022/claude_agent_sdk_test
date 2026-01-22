"""
沙箱执行器

统一管理沙箱的生命周期和工具执行。
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from .base import BaseSandbox
from .config import SandboxConfig, SandboxType
from .e2b_sandbox import E2BSandbox
from .tool_proxy import ToolProxy
from .types import ExecutionResult, ToolInput

logger = logging.getLogger(__name__)


class SandboxPool:
    """
    沙箱池
    
    管理多个沙箱实例，支持复用和自动清理。
    """
    
    def __init__(
        self,
        config: SandboxConfig,
        max_size: int = 5,
        idle_timeout: int = 300,  # 空闲超时（秒）
    ):
        self.config = config
        self.max_size = max_size
        self.idle_timeout = idle_timeout
        
        self._available: asyncio.Queue[BaseSandbox] = asyncio.Queue()
        self._in_use: set[BaseSandbox] = set()
        self._total_created: int = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> BaseSandbox:
        """获取一个沙箱实例"""
        async with self._lock:
            # 尝试从可用池中获取
            try:
                sandbox = self._available.get_nowait()
                if sandbox.is_connected:
                    self._in_use.add(sandbox)
                    logger.debug(f"复用沙箱: {sandbox.sandbox_id}")
                    return sandbox
            except asyncio.QueueEmpty:
                pass
            
            # 创建新沙箱
            if self._total_created < self.max_size:
                sandbox = await self._create_sandbox()
                self._in_use.add(sandbox)
                self._total_created += 1
                logger.debug(f"创建新沙箱: {sandbox.sandbox_id}")
                return sandbox
            
            # 等待可用沙箱
            logger.debug("等待可用沙箱...")
            sandbox = await self._available.get()
            self._in_use.add(sandbox)
            return sandbox
    
    async def release(self, sandbox: BaseSandbox) -> None:
        """释放沙箱回池中"""
        async with self._lock:
            if sandbox in self._in_use:
                self._in_use.remove(sandbox)
            
            if sandbox.is_connected and self.config.auto_cleanup is False:
                # 放回可用池
                await self._available.put(sandbox)
                logger.debug(f"沙箱归还池中: {sandbox.sandbox_id}")
            else:
                # 关闭沙箱
                await sandbox.disconnect()
                self._total_created -= 1
                logger.debug(f"沙箱已关闭: {sandbox.sandbox_id}")
    
    async def _create_sandbox(self) -> BaseSandbox:
        """根据配置创建沙箱"""
        if self.config.sandbox_type == SandboxType.E2B:
            sandbox = E2BSandbox(self.config)
        else:
            raise ValueError(f"不支持的沙箱类型: {self.config.sandbox_type}")
        
        await sandbox.connect()
        return sandbox
    
    async def close_all(self) -> None:
        """关闭所有沙箱"""
        logger.info("正在关闭所有沙箱...")
        
        # 关闭使用中的沙箱
        for sandbox in list(self._in_use):
            await sandbox.disconnect()
        self._in_use.clear()
        
        # 关闭可用池中的沙箱
        while not self._available.empty():
            sandbox = await self._available.get()
            await sandbox.disconnect()
        
        self._total_created = 0
        logger.info("所有沙箱已关闭")
    
    @property
    def stats(self) -> Dict[str, int]:
        """获取池状态"""
        return {
            "total_created": self._total_created,
            "in_use": len(self._in_use),
            "available": self._available.qsize(),
            "max_size": self.max_size,
        }


class SandboxExecutor:
    """
    沙箱执行器
    
    提供统一的工具执行接口，管理沙箱生命周期。
    
    Usage:
        ```python
        config = SandboxConfig(
            sandbox_type=SandboxType.E2B,
            e2b_api_key="your-api-key",
        )
        
        async with SandboxExecutor(config) as executor:
            result = await executor.execute_bash("echo 'Hello, World!'")
            print(result.output)
        ```
    """
    
    def __init__(
        self,
        config: SandboxConfig,
        use_pool: bool = False,
        pool_size: int = 5,
    ):
        """
        初始化沙箱执行器

        Args:
            config: 沙箱配置
            use_pool: 是否使用沙箱池（多沙箱复用）
            pool_size: 沙箱池大小
        """
        self.config = config
        self._use_pool = use_pool
        self._pool_size = pool_size
        
        self._pool: Optional[SandboxPool] = None
        self._sandbox: Optional[BaseSandbox] = None
        self._tool_proxy: Optional[ToolProxy] = None
    
    async def __aenter__(self) -> "SandboxExecutor":
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.stop()
    
    async def start(self) -> None:
        """启动执行器"""
        logger.info("启动沙箱执行器...")
        
        # 验证配置
        errors = self.config.validate()
        if errors:
            raise ValueError(f"配置错误: {', '.join(errors)}")
        
        if self._use_pool:
            self._pool = SandboxPool(self.config, max_size=self._pool_size)
        else:
            self._sandbox = await self._create_sandbox()
        
        # 创建工具代理
        self._tool_proxy = ToolProxy(
            config=self.config,
            sandbox_factory=self._get_sandbox,
        )
        
        logger.info("沙箱执行器已启动")
    
    async def stop(self) -> None:
        """停止执行器"""
        logger.info("停止沙箱执行器...")
        
        if self._tool_proxy:
            await self._tool_proxy.close()
        
        if self._pool:
            await self._pool.close_all()
        
        if self._sandbox:
            await self._sandbox.disconnect()
        
        logger.info("沙箱执行器已停止")
    
    async def _create_sandbox(self) -> BaseSandbox:
        """创建沙箱实例"""
        if self.config.sandbox_type == SandboxType.E2B:
            sandbox = E2BSandbox(self.config)
        else:
            raise ValueError(f"不支持的沙箱类型: {self.config.sandbox_type}")
        
        await sandbox.connect()
        return sandbox
    
    async def _get_sandbox(self) -> BaseSandbox:
        """获取沙箱实例"""
        if self._pool:
            return await self._pool.acquire()
        
        if self._sandbox is None:
            self._sandbox = await self._create_sandbox()
        
        return self._sandbox
    
    @asynccontextmanager
    async def sandbox_session(self) -> AsyncGenerator[BaseSandbox, None]:
        """
        获取沙箱会话
        
        使用上下文管理器自动管理沙箱生命周期。
        """
        sandbox = await self._get_sandbox()
        try:
            yield sandbox
        finally:
            if self._pool:
                await self._pool.release(sandbox)
    
    # 便捷执行方法
    
    async def execute_tool(self, tool_input: ToolInput) -> ExecutionResult:
        """执行工具"""
        if self._tool_proxy is None:
            raise RuntimeError("执行器未启动，请先调用 start()")
        return await self._tool_proxy.execute(tool_input)
    
    async def execute_bash(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """执行 Bash 命令"""
        return await self.execute_tool(ToolInput(
            tool_name="Bash",
            arguments={"command": command, "timeout": timeout},
        ))
    
    async def read_file(self, path: str) -> ExecutionResult:
        """读取文件"""
        return await self.execute_tool(ToolInput(
            tool_name="Read",
            arguments={"path": path},
        ))
    
    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """写入文件"""
        return await self.execute_tool(ToolInput(
            tool_name="Write",
            arguments={"path": path, "content": content},
        ))
    
    async def list_files(self, path: str = ".", pattern: Optional[str] = None) -> ExecutionResult:
        """列出文件"""
        return await self.execute_tool(ToolInput(
            tool_name="Glob",
            arguments={"path": path, "pattern": pattern},
        ))
    
    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        include: Optional[str] = None,
    ) -> ExecutionResult:
        """搜索文件"""
        return await self.execute_tool(ToolInput(
            tool_name="Grep",
            arguments={"pattern": pattern, "path": path, "include": include},
        ))
    
    def get_tool_callback(self) -> Any:
        """
        获取 Claude Agent SDK 的工具权限回调
        
        Returns:
            可用于 ClaudeAgentOptions.can_use_tool 的回调函数
        """
        from .tool_proxy import create_sandbox_tool_callback
        
        if self._tool_proxy is None:
            raise RuntimeError("执行器未启动，请先调用 start()")
        
        return create_sandbox_tool_callback(self._tool_proxy)
    
    def get_audit_logs(self) -> list[dict]:
        """获取审计日志"""
        if self._tool_proxy is None:
            return []
        return self._tool_proxy.get_audit_logs()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取执行器状态"""
        result = {
            "sandbox_type": self.config.sandbox_type.value,
            "use_pool": self._use_pool,
        }
        
        if self._pool:
            result["pool"] = self._pool.stats
        
        if self._sandbox:
            result["sandbox_id"] = self._sandbox.sandbox_id
            result["is_connected"] = self._sandbox.is_connected
        
        return result
