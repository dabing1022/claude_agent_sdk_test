"""
示例 5: 沙箱 API 服务器

演示如何创建一个安全的 API 服务器，将 Claude Agent SDK 的工具执行隔离到沙箱中。

这是一个简单的 FastAPI 示例，展示了如何在生产环境中部署沙箱执行服务。

需要安装:
    pip install fastapi uvicorn e2b

运行:
    python examples/05_sandbox_api_server.py

或使用 uvicorn:
    uvicorn examples.05_sandbox_api_server:app --host 0.0.0.0 --port 8000
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    from claude_agent_test.sandbox import (
        SandboxConfig,
        SandboxExecutor,
        SandboxType,
    )
    from claude_agent_test.sandbox.config import NetworkConfig, ResourceLimits, SecurityConfig
    from claude_agent_test.sandbox.types import ToolInput
except ImportError:
    print("请安装 FastAPI: pip install fastapi uvicorn")
    exit(1)

# ============================================
# 请求/响应模型
# ============================================

class ExecuteRequest(BaseModel):
    """执行请求"""
    tool_name: str
    arguments: dict[str, Any]
    session_id: Optional[str] = None


class ExecuteResponse(BaseModel):
    """执行响应"""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    execution_time_ms: int = 0
    sandbox_id: Optional[str] = None


class BashRequest(BaseModel):
    """Bash 命令请求"""
    command: str
    timeout: Optional[int] = None
    session_id: Optional[str] = None


class FileRequest(BaseModel):
    """文件操作请求"""
    path: str
    content: Optional[str] = None  # 写入时使用
    session_id: Optional[str] = None


class SearchRequest(BaseModel):
    """搜索请求"""
    pattern: str
    path: str = "."
    include: Optional[str] = None
    session_id: Optional[str] = None


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    sandbox_id: Optional[str]
    created_at: str
    is_active: bool


# ============================================
# 会话管理
# ============================================

class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self._sessions: dict[str, SandboxExecutor] = {}
        self._session_info: dict[str, dict[str, Any]] = {}
    
    async def create_session(self, config: SandboxConfig) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        
        executor = SandboxExecutor(config)
        await executor.start()
        
        self._sessions[session_id] = executor
        self._session_info[session_id] = {
            "created_at": asyncio.get_event_loop().time(),
            "is_active": True,
        }
        
        return session_id
    
    async def get_executor(self, session_id: str) -> SandboxExecutor:
        """获取会话执行器"""
        if session_id not in self._sessions:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        return self._sessions[session_id]
    
    async def close_session(self, session_id: str) -> None:
        """关闭会话"""
        if session_id in self._sessions:
            executor = self._sessions[session_id]
            await executor.stop()
            del self._sessions[session_id]
            if session_id in self._session_info:
                del self._session_info[session_id]
    
    async def close_all(self) -> None:
        """关闭所有会话"""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)
    
    def list_sessions(self) -> list[SessionInfo]:
        """列出所有会话"""
        result = []
        for session_id, info in self._session_info.items():
            executor = self._sessions.get(session_id)
            result.append(SessionInfo(
                session_id=session_id,
                sandbox_id=executor._sandbox.sandbox_id if executor and executor._sandbox else None,
                created_at=str(info["created_at"]),
                is_active=info["is_active"],
            ))
        return result


# ============================================
# 全局状态
# ============================================

session_manager = SessionManager()
default_executor: Optional[SandboxExecutor] = None


def get_sandbox_config() -> SandboxConfig:
    """获取沙箱配置"""
    return SandboxConfig(
        sandbox_type=SandboxType.E2B,
        e2b_api_key=os.environ.get("E2B_API_KEY"),
        resource_limits=ResourceLimits(
            cpu_cores=2,
            memory_mb=512,
            timeout_seconds=60,
            max_processes=50,
        ),
        network=NetworkConfig(
            enabled=False,  # 禁用网络访问以提高安全性
        ),
        security=SecurityConfig(
            command_blacklist=[
                r"rm\s+-rf\s+/",
                r":(){ :|:& };:",
                r"dd\s+if=/dev/zero",
                r"mkfs\.",
                r"chmod\s+-R\s+777\s+/",
                r"curl.*\|\s*(ba)?sh",
                r"wget.*\|\s*(ba)?sh",
                r"sudo",
            ],
            enable_audit_log=True,
            allow_root=False,
        ),
        working_directory="/home/user/workspace",
        debug=os.environ.get("DEBUG", "").lower() == "true",
    )


# ============================================
# FastAPI 应用
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global default_executor
    
    # 启动
    print("启动沙箱 API 服务器...")
    
    # 检查 E2B API Key
    if not os.environ.get("E2B_API_KEY"):
        print("警告: 未设置 E2B_API_KEY，沙箱功能将不可用")
    else:
        try:
            config = get_sandbox_config()
            default_executor = SandboxExecutor(config)
            await default_executor.start()
            print("默认沙箱执行器已启动")
        except Exception as e:
            print(f"启动默认沙箱执行器失败: {e}")
    
    yield
    
    # 关闭
    print("关闭沙箱 API 服务器...")
    
    if default_executor:
        await default_executor.stop()
    
    await session_manager.close_all()
    print("所有沙箱已关闭")


app = FastAPI(
    title="Claude Agent SDK 沙箱 API",
    description="安全执行 Claude Agent SDK 工具的 API 服务",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================
# API 端点
# ============================================

@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "Claude Agent SDK 沙箱 API",
        "version": "1.0.0",
        "status": "running",
        "default_sandbox_ready": default_executor is not None,
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "sandbox_ready": default_executor is not None and default_executor._sandbox is not None,
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_tool(request: ExecuteRequest):
    """
    执行工具
    
    支持所有 Claude Agent SDK 工具的安全执行。
    """
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    tool_input = ToolInput(
        tool_name=request.tool_name,
        arguments=request.arguments,
    )
    
    result = await default_executor.execute_tool(tool_input)
    
    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time_ms=result.execution_time_ms,
        sandbox_id=result.sandbox_id,
    )


@app.post("/bash", response_model=ExecuteResponse)
async def execute_bash(request: BashRequest):
    """执行 Bash 命令"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    result = await default_executor.execute_bash(
        request.command,
        timeout=request.timeout,
    )
    
    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time_ms=result.execution_time_ms,
        sandbox_id=result.sandbox_id,
    )


@app.post("/file/read", response_model=ExecuteResponse)
async def read_file(request: FileRequest):
    """读取文件"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    result = await default_executor.read_file(request.path)
    
    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time_ms=result.execution_time_ms,
        sandbox_id=result.sandbox_id,
    )


@app.post("/file/write", response_model=ExecuteResponse)
async def write_file(request: FileRequest):
    """写入文件"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    if request.content is None:
        raise HTTPException(status_code=400, detail="缺少 content 参数")
    
    result = await default_executor.write_file(request.path, request.content)
    
    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time_ms=result.execution_time_ms,
        sandbox_id=result.sandbox_id,
    )


@app.post("/search", response_model=ExecuteResponse)
async def search_files(request: SearchRequest):
    """搜索文件"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    result = await default_executor.search_files(
        request.pattern,
        request.path,
        request.include,
    )
    
    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time_ms=result.execution_time_ms,
        sandbox_id=result.sandbox_id,
    )


@app.get("/audit-logs")
async def get_audit_logs():
    """获取审计日志"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    return {
        "logs": default_executor.get_audit_logs(),
    }


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    if not default_executor:
        raise HTTPException(status_code=503, detail="沙箱服务未就绪")
    
    return {
        "executor": default_executor.stats,
        "sessions": len(session_manager._sessions),
    }


# ============================================
# 会话管理端点
# ============================================

@app.post("/sessions")
async def create_session():
    """创建新会话"""
    config = get_sandbox_config()
    session_id = await session_manager.create_session(config)
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """列出所有会话"""
    return {"sessions": session_manager.list_sessions()}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    await session_manager.close_session(session_id)
    return {"message": f"会话 {session_id} 已关闭"}


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"启动沙箱 API 服务器: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)
