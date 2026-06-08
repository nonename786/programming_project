import subprocess
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.tool_registry import register_tool

_scheduled_tasks: Dict[str, Any] = {}


class _ScheduledTask:
    def __init__(
        self, task_id: str, command: str, delay: float, description: str
    ) -> None:
        self.task_id = task_id
        self.command = command
        self.delay = delay
        self.description = description
        self.status = "pending"
        self.result = ""
        self.created_at = datetime.now()
        self.scheduled_for = self.created_at + timedelta(seconds=delay)
        self.timer: threading.Timer | None = None

    def execute(self) -> None:
        self.status = "running"
        try:
            proc = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.result = proc.stdout or proc.stderr or "(无输出)"
            self.status = "completed"
        except subprocess.TimeoutExpired:
            self.result = "命令执行超时（120秒）"
            self.status = "failed"
        except Exception as exc:
            self.result = f"{type(exc).__name__}: {exc}"
            self.status = "failed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "command": self.command,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "scheduled_for": self.scheduled_for.strftime("%Y-%m-%d %H:%M:%S"),
            "result": self.result if self.status in ("completed", "failed") else "",
        }


def _run_task(task_id: str) -> None:
    task = _scheduled_tasks.get(task_id)
    if task:
        task.execute()


@register_tool(
    name="schedule_task",
    description="安排一个定时任务，在指定秒数后执行 shell 命令。适合延迟执行脚本、定时检查等场景。",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "delay_seconds": {
                "type": "number",
                "description": "延迟执行的秒数",
            },
            "description": {
                "type": "string",
                "description": "任务描述（可选）",
            },
        },
        "required": ["command", "delay_seconds"],
    },
)
def schedule_task(
    command: str, delay_seconds: float, description: str = ""
) -> Dict:
    if delay_seconds < 1:
        return {
            "success": False,
            "content": "",
            "error": "延迟时间不能小于 1 秒。",
        }
    if delay_seconds > 86400:
        return {
            "success": False,
            "content": "",
            "error": "延迟时间不能超过 86400 秒（24小时）。",
        }

    task_id = uuid.uuid4().hex[:8]
    task = _ScheduledTask(task_id, command, delay_seconds, description)
    _scheduled_tasks[task_id] = task

    timer = threading.Timer(delay_seconds, _run_task, args=[task_id])
    timer.daemon = True
    task.timer = timer
    timer.start()

    return {
        "success": True,
        "content": (
            f"任务已安排，ID: {task_id}\n"
            f"命令: {command}\n"
            f"将在 {delay_seconds} 秒后执行\n"
            f"预计执行时间: {task.scheduled_for.strftime('%H:%M:%S')}"
        ),
        "error": None,
    }


@register_tool(
    name="list_scheduled_tasks",
    description="列出所有已安排的定时任务及其执行状态。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_scheduled_tasks() -> Dict:
    if not _scheduled_tasks:
        return {"success": True, "content": "当前没有已安排的任务。", "error": None}

    lines: List[str] = []
    for task in _scheduled_tasks.values():
        info = task.to_dict()
        line = (
            f"[{info['task_id']}] {info['status']} | "
            f"{info['description'] or info['command']} | "
            f"计划: {info['scheduled_for']}"
        )
        if info["result"]:
            line += f"\n  结果: {info['result'][:200]}"
        lines.append(line)

    return {
        "success": True,
        "content": "\n".join(lines),
        "error": None,
    }


@register_tool(
    name="cancel_scheduled_task",
    description="取消一个尚未执行的定时任务。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "要取消的任务 ID",
            },
        },
        "required": ["task_id"],
    },
)
def cancel_scheduled_task(task_id: str) -> Dict:
    task = _scheduled_tasks.get(task_id)
    if task is None:
        return {
            "success": False,
            "content": "",
            "error": f"任务 {task_id} 不存在。",
        }
    if task.status != "pending":
        return {
            "success": False,
            "content": "",
            "error": f"任务 {task_id} 状态为 {task.status}，无法取消。",
        }

    if task.timer:
        task.timer.cancel()
    task.status = "cancelled"

    return {
        "success": True,
        "content": f"任务 {task_id} 已取消。",
        "error": None,
    }
