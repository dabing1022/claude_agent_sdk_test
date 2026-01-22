"""
工具代理模块

实现工具调用的拦截和沙箱转发。
"""

import logging
import re
import time
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

from .config import SandboxConfig, SecurityConfig
from .types import AuditLogEntry, ExecutionResult, ToolInput, ToolType, HIGH_RISK_TOOLS

logger = logging.getLogger(__name__)


class SecurityValidator:
    """安全验证器"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self._blacklist_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.command_blacklist
        ]
    
    def validate_tool(self, tool_input: ToolInput) -> tuple[bool, Optional[str]]:
        """
        验证工具调用是否允许
        
        Returns:
            (是否允许, 拒绝原因)
        """
        tool_name = tool_input.tool_name
        
        # 检查工具黑名单
        if tool_name in self.config.blocked_tools:
            return False, f"工具 {tool_name} 在黑名单中"
        
        # 检查工具白名单
        if self.config.allowed_tools and tool_name not in self.config.allowed_tools:
            return False, f"工具 {tool_name} 不在白名单中"
        
        # 对 Bash 命令进行额外验证
        if tool_name == "Bash":
            command = tool_input.arguments.get("command", "")
            is_valid, reason = self._validate_bash_command(command)
            if not is_valid:
                return False, reason
        
        return True, None
    
    def _validate_bash_command(self, command: str) -> tuple[bool, Optional[str]]:
        """验证 Bash 命令"""
        # 检查命令黑名单
        for pattern in self._blacklist_patterns:
            if pattern.search(command):
                return False, f"命令匹配黑名单模式: {pattern.pattern}"
        
        # 检查命令白名单
        if self.config.command_whitelist:
            allowed = False
            for allowed_cmd in self.config.command_whitelist:
                if command.startswith(allowed_cmd) or allowed_cmd in command:
                    allowed = True
                    break
            if not allowed:
                return False, "命令不在白名单中"
        
        # 检查是否包含危险操作
        dangerous_patterns = [
            (r"sudo\s+", "不允许 sudo 命令"),
            (r"su\s+-", "不允许切换用户"),
            (r">\s*/etc/", "不允许写入系统配置"),
            (r"nc\s+-l", "不允许开启网络监听"),
        ]
        
        if not self.config.allow_root:
            for pattern, reason in dangerous_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return False, reason
        
        return True, None


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._logs: list[AuditLogEntry] = []
    
    def log(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: ExecutionResult,
        sandbox_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """记录审计日志"""
        if not self.enabled:
            return
        
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            tool_name=tool_name,
            tool_input=tool_input,
            result=result,
            sandbox_id=sandbox_id,
            user_id=user_id,
            session_id=session_id,
        )
        
        self._logs.append(entry)
        
        # 同时输出到日志
        log_level = logging.INFO if result.success else logging.WARNING
        logger.log(
            log_level,
            f"[Audit] Tool: {tool_name}, Success: {result.success}, "
            f"Time: {result.execution_time_ms}ms, Sandbox: {sandbox_id}"
        )
    
    def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tool_name: Optional[str] = None,
    ) -> list[AuditLogEntry]:
        """获取审计日志"""
        logs = self._logs
        
        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]
        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]
        if tool_name:
            logs = [log for log in logs if log.tool_name == tool_name]
        
        return logs
    
    def export_logs(self) -> list[dict[str, Any]]:
        """导出审计日志"""
        return [log.to_dict() for log in self._logs]


class ToolProxy:
    """
    工具代理
    
    拦截工具调用并转发到沙箱执行。
    """
    
    def __init__(
        self,
        config: SandboxConfig,
        sandbox_factory: Callable[[], Coroutine[Any, Any, Any]],
    ):
        """
        初始化工具代理
        
        Args:
            config: 沙箱配置
            sandbox_factory: 创建沙箱实例的工厂函数
        """
        self.config = config
        self._sandbox_factory = sandbox_factory
        self._sandbox = None
        self._security_validator = SecurityValidator(config.security)
        self._audit_logger = AuditLogger(config.security.enable_audit_log)
        self._user_id: Optional[str] = None
        self._session_id: Optional[str] = None
    
    def set_context(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """设置上下文信息"""
        self._user_id = user_id
        self._session_id = session_id
    
    async def get_sandbox(self) -> Any:
        """获取或创建沙箱实例"""
        if self._sandbox is None:
            self._sandbox = await self._sandbox_factory()
            await self._sandbox.connect()
        return self._sandbox
    
    async def close(self) -> None:
        """关闭沙箱"""
        if self._sandbox is not None:
            await self._sandbox.disconnect()
            self._sandbox = None
    
    def should_sandbox(self, tool_name: str) -> bool:
        """判断工具是否需要沙箱执行"""
        try:
            tool_type = ToolType(tool_name)
            return tool_type in HIGH_RISK_TOOLS
        except ValueError:
            # 未知工具默认需要沙箱
            return True
    
    async def execute(self, tool_input: ToolInput) -> ExecutionResult:
        """
        执行工具
        
        Args:
            tool_input: 工具输入
        
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        
        # 安全验证
        is_valid, reason = self._security_validator.validate_tool(tool_input)
        if not is_valid:
            result = ExecutionResult(
                success=False,
                error=f"安全验证失败: {reason}",
                exit_code=-1,
            )
            self._audit_logger.log(
                tool_input.tool_name,
                tool_input.arguments,
                result,
                user_id=self._user_id,
                session_id=self._session_id,
            )
            return result
        
        try:
            # 获取沙箱并执行
            sandbox = await self.get_sandbox()
            result = await sandbox.execute_tool(tool_input)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            result.sandbox_id = sandbox.sandbox_id
            
        except Exception as e:
            logger.exception(f"工具执行失败: {tool_input.tool_name}")
            result = ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        
        # 记录审计日志
        self._audit_logger.log(
            tool_input.tool_name,
            tool_input.arguments,
            result,
            sandbox_id=result.sandbox_id,
            user_id=self._user_id,
            session_id=self._session_id,
        )
        
        return result
    
    def get_audit_logs(self) -> list[dict[str, Any]]:
        """获取审计日志"""
        return self._audit_logger.export_logs()


# 权限回调创建函数
def create_sandbox_tool_callback(
    tool_proxy: ToolProxy,
) -> Callable[[str, dict, Any], Coroutine[Any, Any, Any]]:
    """
    创建用于 Claude Agent SDK 的工具权限回调
    
    此回调函数会拦截工具调用并转发到沙箱执行。
    
    Args:
        tool_proxy: 工具代理实例
    
    Returns:
        可用于 ClaudeAgentOptions.can_use_tool 的回调函数
    
    Usage:
        ```python
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_test.sandbox import ToolProxy, create_sandbox_tool_callback
        
        tool_proxy = ToolProxy(config, sandbox_factory)
        callback = create_sandbox_tool_callback(tool_proxy)
        
        options = ClaudeAgentOptions(
            can_use_tool=callback,
        )
        
        async for message in query(prompt="...", options=options):
            ...
        ```
    """
    
    async def can_use_tool(
        tool_name: str,
        input_args: dict,
        context: Any,  # ToolPermissionContext
    ) -> Any:
        """
        工具权限回调
        
        对于需要沙箱执行的工具：
        1. 在沙箱中执行工具
        2. 返回执行结果作为更新后的输入
        
        对于不需要沙箱的工具：
        1. 直接允许执行
        """
        # 尝试导入 SDK 类型
        try:
            from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
        except ImportError:
            # 如果导入失败，使用字典格式（兼容旧版本）
            PermissionResultAllow = None
            PermissionResultDeny = None
        
        logger.info(f"can_use_tool 被调用: tool_name={tool_name}, input_args={input_args}")
        
        # 检查是否需要沙箱执行
        if not tool_proxy.should_sandbox(tool_name):
            # 允许直接执行
            logger.info(f"工具 {tool_name} 不需要沙箱，直接允许")
            if PermissionResultAllow:
                return PermissionResultAllow(behavior="allow")
            return {"behavior": "allow"}
        
        # 在沙箱中执行
        tool_input = ToolInput(
            tool_name=tool_name,
            arguments=input_args,
        )
        
        logger.info(f"在沙箱中执行工具: {tool_name}")
        result = await tool_proxy.execute(tool_input)
        logger.info(f"沙箱执行结果: success={result.success}, output={result.output}, error={result.error}")
        
        if result.success:
            # 返回允许，并提供执行结果
            # 注意：这里我们通过 updated_input 传递沙箱执行结果
            # SDK 会使用这个结果而不是实际执行工具
            updated_input = {
                **input_args,
                "_sandbox_result": result.output,
                "_sandbox_executed": True,
            }
            if PermissionResultAllow:
                return PermissionResultAllow(behavior="allow", updated_input=updated_input)
            return {
                "behavior": "allow",
                "updated_input": updated_input,
            }
        else:
            # 执行失败，拒绝工具调用
            error_msg = f"沙箱执行失败: {result.error}"
            if PermissionResultDeny:
                return PermissionResultDeny(behavior="deny", message=error_msg, interrupt=False)
            return {
                "behavior": "deny",
                "message": error_msg,
            }
    
    return can_use_tool
