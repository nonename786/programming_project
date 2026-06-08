# tests\test_memory.py
import shutil
import tempfile
import unittest
from pathlib import Path

from memory.long_term_memory import LongTermMemory
from memory.session_memory import SessionMemory


class TestMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.memory_file = str(Path(self.temp_dir) / "MEMORY.md")
        self.logs_dir = str(Path(self.temp_dir) / "logs")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_long_term_memory_append_and_load(self):
        memory = LongTermMemory(self.memory_file, self.logs_dir)
        memory.append_memory("用户偏好：喜欢中文回答")
        text = memory.load_memory_text()
        self.assertIn("喜欢中文回答", text)

    def test_build_system_prompt(self):
        memory = LongTermMemory(self.memory_file, self.logs_dir)
        prompt = memory.build_system_prompt("你是一个助手")
        self.assertIn("你是一个助手", prompt)
        self.assertIn("长期记忆", prompt)

    def test_session_memory_trim(self):
        session_memory = SessionMemory(max_messages=4)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ]
        trimmed = session_memory.trim_messages(messages)
        self.assertEqual(len(trimmed), 4)
        self.assertEqual(trimmed[0]["role"], "system")


if __name__ == "__main__":
    unittest.main()