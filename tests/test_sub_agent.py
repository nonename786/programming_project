import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.agent import Agent
from core.message_history import MessageHistory
from core.sub_agent import SubAgent
from core.tool_registry import TOOL_REGISTRY
from gateway.session_manager import SessionManager
from memory.long_term_memory import LongTermMemory
from memory.session_memory import SessionMemory
from tools import register_builtin_tools
from tools.sub_agent_tools import set_parent_agent


class FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, tool_id: str, name: str, arguments: str):
        self.id = tool_id
        self.type = "function"
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content: str = "", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class SubAgentFakeLLM:
    """直接返回文本答案的 Fake LLM，用于测试子 Agent。"""

    def __init__(self, answer: str = "子Agent分析完成。"):
        self.model = "fake-model"
        self.answer = answer

    def create_chat_completion(self, messages, tools=None, stream=False):
        return FakeResponse(FakeMessage(self.answer, []))


class SubAgentToolCallFakeLLM:
    """先调用一次工具，再返回文本答案的 Fake LLM。"""

    def __init__(self):
        self.model = "fake-model"
        self.calls = 0

    def create_chat_completion(self, messages, tools=None, stream=False):
        self.calls += 1
        if self.calls == 1:
            tool_calls = [
                FakeToolCall("sub_call_1", "get_current_time", json.dumps({}))
            ]
            return FakeResponse(FakeMessage("让我查一下时间。", tool_calls))
        return FakeResponse(FakeMessage("子Agent已获取到时间信息。", []))


class SubAgentErrorFakeLLM:
    """模拟 LLM 调用失败的情况。"""

    def __init__(self):
        self.model = "fake-model"

    def create_chat_completion(self, messages, tools=None, stream=False):
        raise RuntimeError("模拟API错误")


class TestSubAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        register_builtin_tools()
        TOOL_REGISTRY.enable_only(["get_current_time", "calculate", "delegate_task"])

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sub_agent_direct_answer(self):
        sub_agent = SubAgent(
            name="test_agent",
            llm_client=SubAgentFakeLLM("这是测试结果。"),
            system_prompt="你是测试子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=3,
        )
        result = sub_agent.run("请分析一下")
        self.assertEqual(result, "这是测试结果。")

    def test_sub_agent_with_tool_call(self):
        sub_agent = SubAgent(
            name="test_agent",
            llm_client=SubAgentToolCallFakeLLM(),
            system_prompt="你是测试子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=5,
        )
        result = sub_agent.run("现在几点")
        self.assertIn("子Agent已获取到时间信息", result)

    def test_sub_agent_disallowed_tool(self):
        class DisallowedToolFakeLLM:
            model = "fake-model"
            calls = 0

            def create_chat_completion(self, messages, tools=None, stream=False):
                self.calls += 1
                if self.calls == 1:
                    tool_calls = [
                        FakeToolCall("call_1", "run_shell_command", json.dumps({"command": "ls"}))
                    ]
                    return FakeResponse(FakeMessage("尝试执行命令。", tool_calls))
                return FakeResponse(FakeMessage("工具不可用，任务结束。", []))

        sub_agent = SubAgent(
            name="restricted",
            llm_client=DisallowedToolFakeLLM(),
            system_prompt="你是受限子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=5,
        )
        result = sub_agent.run("执行命令")
        self.assertIn("任务结束", result)

    def test_sub_agent_max_iterations(self):
        class AlwaysToolCallFakeLLM:
            model = "fake-model"

            def create_chat_completion(self, messages, tools=None, stream=False):
                tool_calls = [
                    FakeToolCall("call_loop", "get_current_time", json.dumps({}))
                ]
                return FakeResponse(FakeMessage("继续调用。", tool_calls))

        sub_agent = SubAgent(
            name="looper",
            llm_client=AlwaysToolCallFakeLLM(),
            system_prompt="你是测试子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=2,
        )
        result = sub_agent.run("无限循环测试")
        self.assertIn("最大推理轮数", result)

    def test_sub_agent_llm_error(self):
        sub_agent = SubAgent(
            name="error_agent",
            llm_client=SubAgentErrorFakeLLM(),
            system_prompt="你是测试子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=3,
        )
        result = sub_agent.run("触发错误")
        self.assertIn("执行出错", result)
        self.assertIn("模拟API错误", result)

    def test_sub_agent_audit_log(self):
        audit_log = str(Path(self.temp_dir) / "sub_audit.log")
        sub_agent = SubAgent(
            name="audit_test",
            llm_client=SubAgentToolCallFakeLLM(),
            system_prompt="你是测试子Agent。",
            allowed_tool_names=["get_current_time"],
            max_iterations=5,
            tool_audit_log=audit_log,
        )
        sub_agent.run("测试审计日志")
        self.assertTrue(Path(audit_log).exists())
        log_content = Path(audit_log).read_text(encoding="utf-8")
        self.assertIn("get_current_time", log_content)


class TestDelegateTask(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        register_builtin_tools()
        TOOL_REGISTRY.enable_only(["get_current_time", "delegate_task"])

        self.long_term_memory = LongTermMemory(
            memory_file=str(Path(self.temp_dir) / "MEMORY.md"),
            logs_dir=str(Path(self.temp_dir) / "logs"),
        )

    def tearDown(self) -> None:
        set_parent_agent(None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delegate_unknown_type(self):
        agent = Agent(
            llm_client=SubAgentFakeLLM(),
            message_history=MessageHistory("测试"),
            session_memory=SessionMemory(max_messages=20),
            long_term_memory=self.long_term_memory,
            session_manager=SessionManager(
                history_dir=str(Path(self.temp_dir) / "sessions")
            ),
            app_config={"max_iterations": 5, "stream_output": False},
            paths_config={"tool_audit_log": str(Path(self.temp_dir) / "audit.log")},
            sub_agents_config={
                "max_iterations": 3,
                "types": {
                    "file_analyst": {
                        "system_prompt": "你是文件分析子Agent。",
                        "allowed_tools": ["read_file"],
                    },
                },
            },
        )
        set_parent_agent(agent)

        result = agent.delegate_to_sub_agent("测试", "nonexistent")
        self.assertFalse(result["success"])
        self.assertIn("未知的子 Agent 类型", result["error"])

    def test_delegate_file_analyst(self):
        agent = Agent(
            llm_client=SubAgentFakeLLM("文件分析完成。"),
            message_history=MessageHistory("测试"),
            session_memory=SessionMemory(max_messages=20),
            long_term_memory=self.long_term_memory,
            session_manager=SessionManager(
                history_dir=str(Path(self.temp_dir) / "sessions")
            ),
            app_config={"max_iterations": 5, "stream_output": False},
            paths_config={"tool_audit_log": str(Path(self.temp_dir) / "audit.log")},
            sub_agents_config={
                "max_iterations": 3,
                "types": {
                    "file_analyst": {
                        "system_prompt": "你是文件分析子Agent。",
                        "allowed_tools": ["read_file", "list_directory"],
                    },
                },
            },
        )
        set_parent_agent(agent)

        result = agent.delegate_to_sub_agent("分析workspace中的文件", "file_analyst")
        self.assertTrue(result["success"])
        self.assertIn("文件分析完成", result["content"])

    def test_delegate_no_agent_ref(self):
        set_parent_agent(None)
        from tools.sub_agent_tools import delegate_task

        result = delegate_task(task="测试任务", agent_type="general")
        self.assertFalse(result["success"])
        self.assertIn("未初始化", result["error"])


if __name__ == "__main__":
    unittest.main()
