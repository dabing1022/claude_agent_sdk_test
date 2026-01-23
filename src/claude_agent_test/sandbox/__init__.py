"""
沙箱执行服务模块

提供将 Claude Agent SDK 工具执行隔离到沙箱环境的能力。
支持多种沙箱后端：E2B、Daytona、Docker 等。
"""

from .config import (
    SandboxConfig,
    SandboxType,
    ResourceLimits,
    NetworkConfig,
    SecurityConfig,
    SANDBOX_PRESETS,
)
from .types import (
    ToolType,
    ToolInput,
    ExecutionResult,
    AuditLogEntry,
    HIGH_RISK_TOOLS,
    FILE_OPERATION_TOOLS,
    READ_ONLY_TOOLS,
)
from .executor import SandboxExecutor, SandboxPool
from .tool_proxy import ToolProxy, create_sandbox_tool_callback
from .e2b_sandbox import E2BSandbox, create_e2b_sandbox
from .daytona_sandbox import DaytonaSandbox, create_daytona_sandbox
from .security import (
    SecurityManager,
    CommandAnalyzer,
    FilePathValidator,
    RateLimiter,
    RiskLevel,
    SecurityViolation,
)

__all__ = [
    # 配置
    "SandboxConfig",
    "SandboxType",
    "ResourceLimits",
    "NetworkConfig",
    "SecurityConfig",
    "SANDBOX_PRESETS",
    # 类型
    "ToolType",
    "ToolInput",
    "ExecutionResult",
    "AuditLogEntry",
    "HIGH_RISK_TOOLS",
    "FILE_OPERATION_TOOLS",
    "READ_ONLY_TOOLS",
    # 执行器
    "SandboxExecutor",
    "SandboxPool",
    # 工具代理
    "ToolProxy",
    "create_sandbox_tool_callback",
    # E2B 沙箱
    "E2BSandbox",
    "create_e2b_sandbox",
    # Daytona 沙箱
    "DaytonaSandbox",
    "create_daytona_sandbox",
    # 安全
    "SecurityManager",
    "CommandAnalyzer",
    "FilePathValidator",
    "RateLimiter",
    "RiskLevel",
    "SecurityViolation",
]
