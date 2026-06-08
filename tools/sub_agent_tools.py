from typing import Any, Dict, Optional

from core.tool_registry import register_tool

_agent_ref: Optional[Any] = None


def set_parent_agent(agent: Any) -> None:
    global _agent_ref
    _agent_ref = agent


@register_tool(
    name="delegate_task",
    description=(
        "将任务委托给专门的子 Agent 执行。子 Agent 拥有独立的上下文和专用工具集，"
        "适合处理特定领域的任务，如文件分析、网络调研等。"
        "主 Agent 应在任务需要专业化处理时使用此工具。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "要委托给子 Agent 的具体任务描述，应尽量清晰完整",
            },
            "agent_type": {
                "type": "string",
                "description": (
                    "子 Agent 类型：file_analyst(文件分析专家，可读取、搜索、"
                    "统计文件)、web_researcher(网络调研专家，可搜索和抓取网页)、"
                    "general(通用助手，具备基础工具)"
                ),
            },
        },
        "required": ["task", "agent_type"],
    },
)
def delegate_task(task: str, agent_type: str) -> Dict:
    if _agent_ref is None:
        return {
            "success": False,
            "content": "",
            "error": "子 Agent 系统未初始化。",
        }

    return _agent_ref.delegate_to_sub_agent(task, agent_type)
