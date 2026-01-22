"""
沙箱基类

定义沙箱执行器的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .config import SandboxConfig
from .types import ExecutionResult, ToolInput


class BaseSandbox(ABC):
    """沙箱执行器基类"""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self._sandbox_id: Optional[str] = None
        self._is_connected: bool = False
    
    @property
    def sandbox_id(self) -> Optional[str]:
        """获取沙箱 ID"""
        return self._sandbox_id
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected
    
    @abstractmethod
    async def connect(self) -> None:
        """
        连接到沙箱
        
        创建或连接到沙箱实例。
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        断开沙箱连接
        
        清理资源并关闭沙箱。
        """
        pass
    
    @abstractmethod
    async def execute_bash(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """
        执行 Bash 命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒），None 使用默认值
        
        Returns:
            ExecutionResult: 执行结果
        """
        pass
    
    @abstractmethod
    async def read_file(self, path: str) -> ExecutionResult:
        """
        读取文件
        
        Args:
            path: 文件路径
        
        Returns:
            ExecutionResult: 包含文件内容的执行结果
        """
        pass
    
    @abstractmethod
    async def write_file(self, path: str, content: str) -> ExecutionResult:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
        
        Returns:
            ExecutionResult: 执行结果
        """
        pass
    
    @abstractmethod
    async def list_files(self, path: str, pattern: Optional[str] = None) -> ExecutionResult:
        """
        列出文件
        
        Args:
            path: 目录路径
            pattern: 可选的 glob 模式
        
        Returns:
            ExecutionResult: 包含文件列表的执行结果
        """
        pass
    
    @abstractmethod
    async def search_files(
        self, 
        pattern: str, 
        path: str = ".", 
        file_pattern: Optional[str] = None
    ) -> ExecutionResult:
        """
        搜索文件内容
        
        Args:
            pattern: 搜索模式（正则表达式）
            path: 搜索路径
            file_pattern: 文件名模式
        
        Returns:
            ExecutionResult: 包含搜索结果的执行结果
        """
        pass
    
    async def execute_tool(self, tool_input: ToolInput) -> ExecutionResult:
        """
        执行工具
        
        根据工具类型调用对应的执行方法。
        
        Args:
            tool_input: 工具输入
        
        Returns:
            ExecutionResult: 执行结果
        """
        tool_name = tool_input.tool_name
        args = tool_input.arguments
        
        if tool_name == "Bash":
            command = args.get("command", "")
            timeout = args.get("timeout")
            return await self.execute_bash(command, timeout)
        
        elif tool_name == "Read":
            path = args.get("path", args.get("file_path", ""))
            return await self.read_file(path)
        
        elif tool_name == "Write":
            path = args.get("path", args.get("file_path", ""))
            content = args.get("content", args.get("file_content", ""))
            return await self.write_file(path, content)
        
        elif tool_name == "Glob":
            path = args.get("path", ".")
            pattern = args.get("pattern")
            return await self.list_files(path, pattern)
        
        elif tool_name == "Grep":
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            file_pattern = args.get("include")
            return await self.search_files(pattern, path, file_pattern)
        
        elif tool_name == "Edit":
            # Edit 工具通常需要更复杂的处理
            return await self._handle_edit(args)
        
        else:
            return ExecutionResult(
                success=False,
                error=f"不支持的工具类型: {tool_name}"
            )
    
    async def _handle_edit(self, args: dict[str, Any]) -> ExecutionResult:
        """
        处理 Edit 工具
        
        Edit 工具通常涉及读取、修改、写入的组合操作。
        """
        path = args.get("path", args.get("file_path", ""))
        
        # 读取原文件
        read_result = await self.read_file(path)
        if not read_result.success:
            # 如果文件不存在，可能是新建文件
            original_content = ""
        else:
            original_content = read_result.output
        
        # 应用编辑
        old_text = args.get("old_string", args.get("old_text", ""))
        new_text = args.get("new_string", args.get("new_text", ""))
        
        if old_text:
            # 替换模式
            if old_text not in original_content:
                return ExecutionResult(
                    success=False,
                    error=f"在文件中找不到要替换的文本: {old_text[:100]}..."
                )
            new_content = original_content.replace(old_text, new_text, 1)
        else:
            # 新建或完全覆盖
            new_content = new_text
        
        # 写入文件
        return await self.write_file(path, new_content)
    
    async def __aenter__(self) -> "BaseSandbox":
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()
