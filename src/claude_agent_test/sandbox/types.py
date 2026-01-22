"""
沙箱类型定义

定义工具调用和执行结果的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ToolType(Enum):
    """工具类型枚举"""
    
    # 文件操作
    READ = "Read"
    WRITE = "Write"
    EDIT = "Edit"
    
    # 命令执行
    BASH = "Bash"
    
    # 搜索操作
    GLOB = "Glob"
    GREP = "Grep"
    
    # 任务管理
    TASK = "Task"
    TASK_OUTPUT = "TaskOutput"
    
    # 其他
    WEB_FETCH = "WebFetch"
    WEB_SEARCH = "WebSearch"
    NOTEBOOK_EDIT = "NotebookEdit"
    TODO_WRITE = "TodoWrite"
    
    # 交互
    ASK_USER_QUESTION = "AskUserQuestion"
    
    # 高级
    SKILL = "Skill"
    SLASH_COMMAND = "SlashCommand"
    ENTER_PLAN_MODE = "EnterPlanMode"
    EXIT_PLAN_MODE = "ExitPlanMode"
    KILL_SHELL = "KillShell"


# 高危工具列表（需要沙箱执行）
HIGH_RISK_TOOLS = {
    ToolType.BASH,
    ToolType.WRITE,
    ToolType.EDIT,
    ToolType.TASK,
    ToolType.NOTEBOOK_EDIT,
}

# 文件操作工具列表
FILE_OPERATION_TOOLS = {
    ToolType.READ,
    ToolType.WRITE,
    ToolType.EDIT,
    ToolType.GLOB,
    ToolType.GREP,
}

# 只读工具列表（相对安全）
READ_ONLY_TOOLS = {
    ToolType.READ,
    ToolType.GLOB,
    ToolType.GREP,
}


@dataclass
class ToolInput:
    """工具输入"""
    
    tool_name: str
    arguments: dict[str, Any]
    tool_use_id: Optional[str] = None
    
    @property
    def tool_type(self) -> Optional[ToolType]:
        """获取工具类型枚举"""
        try:
            return ToolType(self.tool_name)
        except ValueError:
            return None
    
    @property
    def is_high_risk(self) -> bool:
        """是否为高危工具"""
        tool_type = self.tool_type
        return tool_type in HIGH_RISK_TOOLS if tool_type else True  # 未知工具视为高危


@dataclass
class ExecutionResult:
    """执行结果"""
    
    success: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    
    # 执行元数据
    execution_time_ms: int = 0
    sandbox_id: Optional[str] = None
    
    # 文件变更信息（用于文件操作）
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    
    # 审计信息
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_tool_result(self) -> dict[str, Any]:
        """转换为工具结果格式"""
        if self.success:
            return {
                "content": [
                    {"type": "text", "text": self.output}
                ]
            }
        else:
            return {
                "content": [
                    {"type": "text", "text": f"Error: {self.error or 'Unknown error'}"}
                ],
                "isError": True
            }


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    
    timestamp: datetime
    tool_name: str
    tool_input: dict[str, Any]
    result: ExecutionResult
    sandbox_id: Optional[str]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "success": self.result.success,
            "output": self.result.output[:1000] if self.result.output else None,  # 截断长输出
            "error": self.result.error,
            "exit_code": self.result.exit_code,
            "execution_time_ms": self.result.execution_time_ms,
            "sandbox_id": self.sandbox_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }
