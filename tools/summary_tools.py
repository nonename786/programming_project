# tools\summary_tools.py
from typing import Dict

from core.tool_registry import register_tool


@register_tool(
    name="simple_text_summary",
    description="对较长文本做一个非常基础的本地摘要（非 LLM 摘要）。",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "需要摘要的文本"},
            "max_length": {"type": "integer", "description": "摘要最大长度，默认 120"},
        },
        "required": ["text"],
    },
)
def simple_text_summary(text: str, max_length: int = 120) -> Dict:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        summary = cleaned
    else:
        summary = cleaned[:max_length].rstrip() + "..."
    return {"success": True, "content": summary, "error": None}