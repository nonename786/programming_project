# tests\test_agent.py
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.agent import Agent
from core.message_history import MessageHistory
from core.tool_registry import TOOL_REGISTRY
from gateway.session_manager import SessionManager
from memory.long_term_memory import LongTermMemory
from memory.session_memory import SessionMemory
from tools import register_builtin_tools


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


class FakeStreamDelta:
    def __init__(self, content: str):
        self.content = content


class FakeStreamChoice:
    def __init__(self, delta):
        self.delta = delta


class FakeStreamChunk:
    def __init__(self, content: str):
        self.choices = [FakeStreamChoice(FakeStreamDelta(content))]


class FakeLLMClient:
    def __init__(self):
        self.model = "fake-model"
        self.calls = 0

    def create_chat_completion(self, messages, tools=None, stream=False):
        self.calls += 1
        if self.calls == 1:
            tool_calls = [
                FakeToolCall("call_1", "get_current_time", json.dumps({}))
            ]
            return FakeResponse(FakeMessage("我先获取当前时间。", tool_calls))
        return FakeResponse(FakeMessage("现在已经获取到时间了。", []))

    def create_streaming_text_completion(self, messages):
        yield FakeStreamChunk("流式")
        yield FakeStreamChunk("回答")


class TestAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

        register_builtin_tools()
        TOOL_REGISTRY.enable_only(["get_current_time"])

        self.long_term_memory = LongTermMemory(
            memory_file=str(Path(self.temp_dir) / "MEMORY.md"),
            logs_dir=str(Path(self.temp_dir) / "logs"),
        )
        self.message_history = MessageHistory("你是一个测试助手")
        self.session_memory = SessionMemory(max_messages=20)
        self.session_manager = SessionManager(
            history_dir=str(Path(self.temp_dir) / "sessions")
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_agent_tool_call_flow(self):
        agent = Agent(
            llm_client=FakeLLMClient(),
            message_history=self.message_history,
            session_memory=self.session_memory,
            long_term_memory=self.long_term_memory,
            session_manager=self.session_manager,
            app_config={"max_iterations": 5, "stream_output": False},
            paths_config={"tool_audit_log": str(Path(self.temp_dir) / "audit.log")},
        )

        result = agent.handle_user_message("现在几点")
        self.assertIn("现在已经获取到时间了", result)

    def test_agent_stream_final_answer(self):
        class StreamOnlyFakeLLM(FakeLLMClient):
            def create_chat_completion(self, messages, tools=None, stream=False):
                return FakeResponse(FakeMessage("这是最终答案", []))

        agent = Agent(
            llm_client=StreamOnlyFakeLLM(),
            message_history=MessageHistory("你是一个测试助手"),
            session_memory=SessionMemory(max_messages=20),
            long_term_memory=self.long_term_memory,
            session_manager=self.session_manager,
            app_config={"max_iterations": 5, "stream_output": True},
            paths_config={"tool_audit_log": str(Path(self.temp_dir) / "audit.log")},
        )

        result = agent.handle_user_message("你好")
        self.assertEqual(result, "这是最终答案")


if __name__ == "__main__":
    unittest.main()
