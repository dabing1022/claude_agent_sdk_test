"""
安全策略模块

提供完整的安全验证和审计功能。
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .config import SecurityConfig
from .types import ExecutionResult, ToolInput, ToolType

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityViolation:
    """安全违规记录"""
    timestamp: datetime
    violation_type: str
    description: str
    tool_name: str
    tool_input: Dict[str, Any]
    risk_level: RiskLevel
    blocked: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "violation_type": self.violation_type,
            "description": self.description,
            "tool_name": self.tool_name,
            "risk_level": self.risk_level.value,
            "blocked": self.blocked,
        }


class CommandAnalyzer:
    """命令分析器"""
    
    # 危险命令模式
    DANGEROUS_PATTERNS = {
        # 文件系统破坏
        "filesystem_destruction": [
            (r"rm\s+-rf\s+/(?!\S)", "删除根目录", RiskLevel.CRITICAL),
            (r"rm\s+-rf\s+/\*", "删除根目录所有文件", RiskLevel.CRITICAL),
            (r"rm\s+-rf\s+~", "删除用户主目录", RiskLevel.HIGH),
            (r"mkfs\.\w+", "格式化文件系统", RiskLevel.CRITICAL),
            (r"dd\s+if=/dev/(zero|random)\s+of=/dev/[sh]d", "覆盖磁盘", RiskLevel.CRITICAL),
        ],
        
        # 系统破坏
        "system_destruction": [
            (r":(){ :|:& };:", "Fork 炸弹", RiskLevel.CRITICAL),
            (r">\s*/dev/[sh]d[a-z]", "覆盖磁盘设备", RiskLevel.CRITICAL),
            (r"chmod\s+-R\s+777\s+/", "危险权限修改", RiskLevel.HIGH),
            (r"chmod\s+777\s+/etc", "修改系统配置权限", RiskLevel.HIGH),
        ],
        
        # 权限提升
        "privilege_escalation": [
            (r"\bsudo\b", "使用 sudo", RiskLevel.HIGH),
            (r"\bsu\s+-", "切换用户", RiskLevel.HIGH),
            (r"chmod\s+[+]?[ugo]*s", "设置 SUID/SGID", RiskLevel.HIGH),
        ],
        
        # 远程代码执行
        "remote_code_execution": [
            (r"curl.*\|\s*(ba)?sh", "远程脚本执行 (curl)", RiskLevel.CRITICAL),
            (r"wget.*\|\s*(ba)?sh", "远程脚本执行 (wget)", RiskLevel.CRITICAL),
            (r"curl.*-o\s*/tmp.*&&.*sh", "下载并执行", RiskLevel.HIGH),
            (r"python\s+-c\s+['\"]import\s+urllib", "Python 远程下载", RiskLevel.MEDIUM),
        ],
        
        # 网络攻击
        "network_attacks": [
            (r"nc\s+-l", "开启网络监听", RiskLevel.HIGH),
            (r"nmap\s+", "网络扫描", RiskLevel.MEDIUM),
            (r"tcpdump\s+", "网络抓包", RiskLevel.MEDIUM),
        ],
        
        # 信息泄露
        "information_disclosure": [
            (r"cat\s+/etc/passwd", "读取用户列表", RiskLevel.LOW),
            (r"cat\s+/etc/shadow", "读取密码文件", RiskLevel.HIGH),
            (r"cat\s+~/.ssh/", "读取 SSH 密钥", RiskLevel.HIGH),
            (r"cat\s+.*\.env", "读取环境变量文件", RiskLevel.MEDIUM),
            (r"printenv|env\s*$", "打印环境变量", RiskLevel.LOW),
        ],
        
        # 资源耗尽
        "resource_exhaustion": [
            (r"while\s+true.*do", "无限循环", RiskLevel.MEDIUM),
            (r"for\s*\(\s*;\s*;\s*\)", "无限循环", RiskLevel.MEDIUM),
            (r"dd\s+if=/dev/zero\s+of=", "磁盘填充", RiskLevel.HIGH),
            (r"yes\s+", "无限输出", RiskLevel.MEDIUM),
        ],
    }
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self._compiled_blacklist = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.command_blacklist
        ]
        self._compiled_dangerous = {}
        for category, patterns in self.DANGEROUS_PATTERNS.items():
            self._compiled_dangerous[category] = [
                (re.compile(pattern, re.IGNORECASE), desc, risk)
                for pattern, desc, risk in patterns
            ]
    
    def analyze(self, command: str) -> List[SecurityViolation]:
        """
        分析命令的安全风险
        
        Returns:
            发现的安全违规列表
        """
        violations = []
        
        # 检查用户定义的黑名单
        for pattern in self._compiled_blacklist:
            if pattern.search(command):
                violations.append(SecurityViolation(
                    timestamp=datetime.now(),
                    violation_type="blacklist_match",
                    description=f"命令匹配黑名单模式: {pattern.pattern}",
                    tool_name="Bash",
                    tool_input={"command": command},
                    risk_level=RiskLevel.HIGH,
                ))
        
        # 检查危险模式
        for category, patterns in self._compiled_dangerous.items():
            for pattern, description, risk_level in patterns:
                if pattern.search(command):
                    violations.append(SecurityViolation(
                        timestamp=datetime.now(),
                        violation_type=category,
                        description=description,
                        tool_name="Bash",
                        tool_input={"command": command},
                        risk_level=risk_level,
                    ))
        
        # 检查命令白名单
        if self.config.command_whitelist:
            is_allowed = False
            for allowed_cmd in self.config.command_whitelist:
                if command.strip().startswith(allowed_cmd):
                    is_allowed = True
                    break
            
            if not is_allowed:
                violations.append(SecurityViolation(
                    timestamp=datetime.now(),
                    violation_type="whitelist_violation",
                    description="命令不在白名单中",
                    tool_name="Bash",
                    tool_input={"command": command},
                    risk_level=RiskLevel.MEDIUM,
                ))
        
        return violations
    
    def is_safe(self, command: str) -> tuple[bool, Optional[str]]:
        """
        判断命令是否安全
        
        Returns:
            (是否安全, 不安全原因)
        """
        violations = self.analyze(command)
        
        # 过滤掉低风险的违规（可以记录但不阻止）
        blocking_violations = [
            v for v in violations
            if v.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
        
        if blocking_violations:
            reasons = [f"{v.description} ({v.risk_level.value})" for v in blocking_violations]
            return False, "; ".join(reasons)
        
        return True, None


class FilePathValidator:
    """文件路径验证器"""
    
    # 敏感路径
    SENSITIVE_PATHS = {
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/root",
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
        "~/.config",
    }
    
    # 禁止写入的路径
    READONLY_PATHS = {
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/lib",
        "/lib64",
        "/boot",
        "/sys",
        "/proc",
        "/dev",
    }
    
    def __init__(self, working_directory: str = "/workspace"):
        self.working_directory = working_directory
    
    def validate_read(self, path: str) -> tuple[bool, Optional[str]]:
        """验证读取路径"""
        normalized = self._normalize_path(path)
        
        for sensitive in self.SENSITIVE_PATHS:
            if normalized.startswith(sensitive) or sensitive in normalized:
                return False, f"禁止读取敏感路径: {sensitive}"
        
        return True, None
    
    def validate_write(self, path: str) -> tuple[bool, Optional[str]]:
        """验证写入路径"""
        normalized = self._normalize_path(path)
        
        # 检查只读路径
        for readonly in self.READONLY_PATHS:
            if normalized.startswith(readonly):
                return False, f"禁止写入系统路径: {readonly}"
        
        # 检查敏感路径
        for sensitive in self.SENSITIVE_PATHS:
            if normalized.startswith(sensitive) or sensitive in normalized:
                return False, f"禁止写入敏感路径: {sensitive}"
        
        return True, None
    
    def _normalize_path(self, path: str) -> str:
        """规范化路径"""
        import os
        
        # 展开 ~ 
        if path.startswith("~"):
            path = os.path.expanduser(path)
        
        # 处理相对路径
        if not path.startswith("/"):
            path = f"{self.working_directory}/{path}"
        
        # 规范化
        path = os.path.normpath(path)
        
        return path


class RateLimiter:
    """速率限制器"""
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def check(self, key: str = "default") -> tuple[bool, Optional[str]]:
        """
        检查是否超过速率限制
        
        Returns:
            (是否允许, 拒绝原因)
        """
        now = time.time()
        
        if key not in self._requests:
            self._requests[key] = []
        
        # 清理过期记录
        self._requests[key] = [
            t for t in self._requests[key]
            if now - t < self.window_seconds
        ]
        
        # 检查速率
        if len(self._requests[key]) >= self.max_requests:
            return False, f"超过速率限制: {self.max_requests} 次/{self.window_seconds} 秒"
        
        # 记录请求
        self._requests[key].append(now)
        return True, None


class SecurityManager:
    """
    安全管理器
    
    整合所有安全功能的统一入口。
    """
    
    def __init__(
        self,
        config: SecurityConfig,
        working_directory: str = "/home/user/workspace",
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
    ):
        self.config = config
        self.command_analyzer = CommandAnalyzer(config)
        self.path_validator = FilePathValidator(working_directory)
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        
        self._violations: List[SecurityViolation] = []
    
    def validate_tool_call(
        self,
        tool_input: ToolInput,
        user_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        验证工具调用
        
        Returns:
            (是否允许, 拒绝原因)
        """
        tool_name = tool_input.tool_name
        args = tool_input.arguments
        
        # 速率限制检查
        rate_key = user_id or "default"
        is_allowed, reason = self.rate_limiter.check(rate_key)
        if not is_allowed:
            self._record_violation(
                "rate_limit",
                reason,
                tool_input,
                RiskLevel.MEDIUM,
            )
            return False, reason
        
        # 工具黑名单检查
        if tool_name in self.config.blocked_tools:
            reason = f"工具 {tool_name} 在黑名单中"
            self._record_violation(
                "tool_blocked",
                reason,
                tool_input,
                RiskLevel.HIGH,
            )
            return False, reason
        
        # 工具白名单检查
        if self.config.allowed_tools and tool_name not in self.config.allowed_tools:
            reason = f"工具 {tool_name} 不在白名单中"
            self._record_violation(
                "tool_not_allowed",
                reason,
                tool_input,
                RiskLevel.MEDIUM,
            )
            return False, reason
        
        # 根据工具类型进行特定验证
        if tool_name == "Bash":
            command = args.get("command", "")
            is_safe, reason = self.command_analyzer.is_safe(command)
            if not is_safe:
                self._record_violation(
                    "unsafe_command",
                    reason,
                    tool_input,
                    RiskLevel.HIGH,
                )
                return False, reason
        
        elif tool_name == "Read":
            path = args.get("path", args.get("file_path", ""))
            is_valid, reason = self.path_validator.validate_read(path)
            if not is_valid:
                self._record_violation(
                    "invalid_read_path",
                    reason,
                    tool_input,
                    RiskLevel.MEDIUM,
                )
                return False, reason
        
        elif tool_name in ("Write", "Edit"):
            path = args.get("path", args.get("file_path", ""))
            is_valid, reason = self.path_validator.validate_write(path)
            if not is_valid:
                self._record_violation(
                    "invalid_write_path",
                    reason,
                    tool_input,
                    RiskLevel.HIGH,
                )
                return False, reason
        
        return True, None
    
    def _record_violation(
        self,
        violation_type: str,
        description: str,
        tool_input: ToolInput,
        risk_level: RiskLevel,
    ) -> None:
        """记录安全违规"""
        violation = SecurityViolation(
            timestamp=datetime.now(),
            violation_type=violation_type,
            description=description,
            tool_name=tool_input.tool_name,
            tool_input=tool_input.arguments,
            risk_level=risk_level,
        )
        
        self._violations.append(violation)
        
        # 记录到日志
        logger.warning(
            f"[Security] Violation: {violation_type} - {description} "
            f"(Tool: {tool_input.tool_name}, Risk: {risk_level.value})"
        )
    
    def get_violations(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        risk_level: Optional[RiskLevel] = None,
    ) -> List[SecurityViolation]:
        """获取安全违规记录"""
        violations = self._violations
        
        if start_time:
            violations = [v for v in violations if v.timestamp >= start_time]
        if end_time:
            violations = [v for v in violations if v.timestamp <= end_time]
        if risk_level:
            violations = [v for v in violations if v.risk_level == risk_level]
        
        return violations
    
    def export_violations(self) -> List[Dict[str, Any]]:
        """导出安全违规记录"""
        return [v.to_dict() for v in self._violations]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取安全统计"""
        total = len(self._violations)
        by_level = {}
        by_type = {}
        
        for v in self._violations:
            by_level[v.risk_level.value] = by_level.get(v.risk_level.value, 0) + 1
            by_type[v.violation_type] = by_type.get(v.violation_type, 0) + 1
        
        return {
            "total_violations": total,
            "by_risk_level": by_level,
            "by_violation_type": by_type,
        }
