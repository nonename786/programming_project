import json
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolMeta:
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Dict[str, Any]]
    enabled: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolMeta] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable[..., Dict[str, Any]],
    ) -> None:
        self._tools[name] = ToolMeta(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
            enabled=True,
        )

    def get_tool(self, name: str) -> Optional[ToolMeta]:
        return self._tools.get(name)

    def list_tools(self, allowed_names: Optional[List[str]] = None) -> List[ToolMeta]:
        tools = [tool for tool in self._tools.values() if tool.enabled]
        if allowed_names is None:
            return tools

        allowed_set = set(allowed_names)
        return [tool for tool in tools if tool.name in allowed_set]

    def enable_only(self, enabled_names: List[str]) -> None:
        enabled_set = set(enabled_names)
        for tool_name, tool_meta in self._tools.items():
            tool_meta.enabled = tool_name in enabled_set

    def get_openai_tool_schemas(
        self,
        allowed_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        for tool in self.list_tools(allowed_names=allowed_names):
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return schemas

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if tool is None or not tool.enabled:
            return {
                "success": False,
                "content": "",
                "error": f"工具 {name} 不存在或未启用。",
            }

        try:
            result = tool.func(**arguments)
            if not isinstance(result, dict):
                return {
                    "success": True,
                    "content": str(result),
                    "error": None,
                }
            result.setdefault("success", True)
            result.setdefault("content", "")
            result.setdefault("error", None)
            return result
        except Exception as exc:
            return {
                "success": False,
                "content": "",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }


TOOL_REGISTRY = ToolRegistry()


def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    def decorator(func: Callable[..., Dict[str, Any]]):
        TOOL_REGISTRY.register(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
        )
        return func

    return decorator


def append_tool_audit_log(
    log_path: str,
    tool_name: str,
    arguments: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")