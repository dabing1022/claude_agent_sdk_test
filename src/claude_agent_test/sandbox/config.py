"""
沙箱配置模块

定义沙箱的配置选项和类型。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SandboxType(Enum):
    """沙箱类型枚举"""
    
    E2B = "e2b"
    DAYTONA = "daytona"
    DOCKER = "docker"
    LOCAL = "local"  # 本地执行（不推荐用于生产）


@dataclass
class ResourceLimits:
    """资源限制配置"""
    
    # CPU 核心数
    cpu_cores: int = 2
    # 内存大小 (MB)
    memory_mb: int = 512
    # 磁盘大小 (MB)
    disk_mb: int = 1024
    # 执行超时时间 (秒)
    timeout_seconds: int = 60
    # 最大进程数
    max_processes: int = 50


@dataclass
class NetworkConfig:
    """网络配置"""
    
    # 是否允许网络访问
    enabled: bool = False
    # 允许访问的域名白名单
    allowed_domains: list[str] = field(default_factory=list)
    # 是否允许访问外部 API
    allow_external_api: bool = False


@dataclass
class SecurityConfig:
    """安全配置"""
    
    # 允许执行的工具列表（空表示全部允许）
    allowed_tools: list[str] = field(default_factory=list)
    # 禁止执行的工具列表
    blocked_tools: list[str] = field(default_factory=list)
    # 命令黑名单（正则表达式）
    command_blacklist: list[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/",  # 防止删除根目录
        r":(){ :|:& };:",  # Fork 炸弹
        r"dd\s+if=/dev/zero",  # 磁盘填充
        r"mkfs\.",  # 格式化命令
        r"chmod\s+-R\s+777\s+/",  # 危险权限修改
        r"curl.*\|\s*(ba)?sh",  # 远程脚本执行
        r"wget.*\|\s*(ba)?sh",
    ])
    # 命令白名单（如果设置，只允许白名单中的命令）
    command_whitelist: Optional[list[str]] = None
    # 是否启用审计日志
    enable_audit_log: bool = True
    # 是否允许 root 执行
    allow_root: bool = False


@dataclass
class SandboxConfig:
    """沙箱总配置"""
    
    # 沙箱类型
    sandbox_type: SandboxType = SandboxType.E2B
    
    # E2B 特定配置
    e2b_api_key: Optional[str] = None
    e2b_template: str = "base"  # 使用的模板
    
    # Daytona 特定配置
    daytona_api_key: Optional[str] = None
    daytona_base_url: Optional[str] = None
    
    # 资源限制
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    
    # 网络配置
    network: NetworkConfig = field(default_factory=NetworkConfig)
    
    # 安全配置
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # 沙箱会话配置
    session_timeout_minutes: int = 60  # 会话超时
    auto_cleanup: bool = True  # 执行完成后自动清理
    persist_files: bool = False  # 是否持久化文件
    
    # 工作目录
    working_directory: str = "/workspace"
    
    # 调试模式
    debug: bool = False
    
    def validate(self) -> list[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        if self.sandbox_type == SandboxType.E2B and not self.e2b_api_key:
            errors.append("E2B 沙箱需要配置 e2b_api_key")
        
        if self.sandbox_type == SandboxType.DAYTONA:
            if not self.daytona_api_key:
                errors.append("Daytona 沙箱需要配置 daytona_api_key")
            if not self.daytona_base_url:
                errors.append("Daytona 沙箱需要配置 daytona_base_url")
        
        if self.resource_limits.timeout_seconds < 1:
            errors.append("超时时间必须大于 0 秒")
        
        if self.resource_limits.memory_mb < 128:
            errors.append("内存限制不能小于 128MB")
        
        return errors


# 预定义配置模板
SANDBOX_PRESETS = {
    "minimal": SandboxConfig(
        resource_limits=ResourceLimits(
            cpu_cores=1,
            memory_mb=256,
            timeout_seconds=30,
        ),
        network=NetworkConfig(enabled=False),
    ),
    "standard": SandboxConfig(
        resource_limits=ResourceLimits(
            cpu_cores=2,
            memory_mb=512,
            timeout_seconds=60,
        ),
        network=NetworkConfig(enabled=False),
    ),
    "development": SandboxConfig(
        resource_limits=ResourceLimits(
            cpu_cores=4,
            memory_mb=2048,
            timeout_seconds=300,
        ),
        network=NetworkConfig(
            enabled=True,
            allowed_domains=["pypi.org", "npmjs.com", "github.com"],
        ),
        debug=True,
    ),
}
