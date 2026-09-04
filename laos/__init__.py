"""Linux AgentOS —— 架在 Linux kernel 之上的 Agent 操作系统薄内核。

    Linux kernel   : 调度 / 内存 / namespace / cgroup / seccomp（强制层）
    laosd          : Agent 进程表 / 能力表 / MCP 驱动路由 / 审计（语义层）
    MCP Server     : 设备驱动，把资源封装成 syscall
    Agent          : 进程，唯一副作用出口是 syscall

零第三方依赖，Python 3.10+ 可直接运行。
"""

from .agent import Agent, AgentResult
from .brain import Brain, OpenAIChatBrain, ScriptedBrain, make_brain
from .branch import BranchContext, BranchTable
from .context import ContextManager
from .kernel import AgentKernel, CapabilitySet, PCB
from .mcp import MCPClient, MCPServer, ToolSpec

__version__ = "0.1.0"

__all__ = [
    "AgentKernel",
    "Agent",
    "AgentResult",
    "PCB",
    "CapabilitySet",
    "ContextManager",
    "BranchTable",
    "BranchContext",
    "MCPServer",
    "MCPClient",
    "ToolSpec",
    "Brain",
    "ScriptedBrain",
    "OpenAIChatBrain",
    "make_brain",
]
