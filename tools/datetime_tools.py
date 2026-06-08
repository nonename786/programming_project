# tools\datetime_tools.py
from datetime import datetime
from typing import Dict

from core.tool_registry import register_tool


@register_tool(
    name="get_current_time",
    description="获取当前系统时间和日期。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def get_current_time() -> Dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "success": True,
        "content": now,
        "error": None,
    }