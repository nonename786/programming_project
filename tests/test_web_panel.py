import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui.web_panel import create_web_app


class FakeLLMClient:
    model = "fake-model"

    def get_provider_name(self):
        return "fake"

    def get_model_name(self):
        return self.model


class FakeMessageHistory:
    def __init__(self):
        self.messages = [{"role": "system", "content": "system"}]

    def get_messages(self):
        return self.messages


class FakeSessionManager:
    def __init__(self):
        self.session_id = "session123"

    def list_sessions(self, limit=30):
        return []

    def save_session(self, model_name, messages):
        return "history/sessions/demo.json"


class FakeLongTermMemory:
    def build_system_prompt(self, prompt):
        return prompt


class FakeAgent:
    def __init__(self):
        self.llm_client = FakeLLMClient()
        self.message_history = FakeMessageHistory()
        self.session_manager = FakeSessionManager()
        self.long_term_memory = FakeLongTermMemory()
        self.loaded_session_meta = None
        self.received = None

    def handle_user_message(self, user_input):
        self.received = user_input
        self.message_history.messages.append({"role": "user", "content": user_input})
        self.message_history.messages.append({"role": "assistant", "content": "ok"})
        return "ok"


class TestWebPanel(unittest.TestCase):
    def test_chat_route_accepts_file_and_camera_photo(self):
        fake_agent = FakeAgent()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            fake_config = {
                "agent": {"system_prompt": "你是测试助手"},
                "paths": {
                    "workspace_dir": str(temp_root / "workspace"),
                    "history_dir": str(temp_root / "history"),
                    "qq_history_dir": str(temp_root / "qq_history"),
                    "memory_file": str(temp_root / "memory" / "MEMORY.md"),
                    "memory_logs_dir": str(temp_root / "memory_logs"),
                    "tool_audit_log": str(temp_root / "logs" / "audit.log"),
                },
                "web": {
                    "secret_key": "test-secret",
                    "max_upload_bytes": 2 * 1024 * 1024,
                },
            }

            def fake_load_yaml_config(_path):
                return fake_config

            with patch("ui.web_panel.build_agent", return_value=fake_agent), patch(
                "ui.web_panel.load_yaml_config",
                side_effect=fake_load_yaml_config,
            ):
                app = create_web_app()
                client = app.test_client()

                response = client.post(
                    "/chat",
                    data={
                        "prompt": "请分析附件",
                        "attachments": (io.BytesIO(b"hello text file"), "note.txt"),
                        "camera_photos": (
                            io.BytesIO(b"\xff\xd8\xff\xe0fakejpeg"),
                            "photo.jpg",
                        ),
                    },
                    content_type="multipart/form-data",
                )

            self.assertEqual(response.status_code, 302)
            self.assertIsInstance(fake_agent.received, list)
            self.assertEqual(fake_agent.received[0]["text"], "请分析附件")
            self.assertEqual(fake_agent.received[1]["type"], "input_file")
            self.assertEqual(fake_agent.received[1]["source"], "upload")
            self.assertEqual(fake_agent.received[2]["type"], "input_image")
            self.assertEqual(fake_agent.received[2]["source"], "camera")

            upload_dir = temp_root / "workspace" / "uploads" / "session123"
            saved_files = list(upload_dir.glob("*"))
            self.assertEqual(len(saved_files), 2)


if __name__ == "__main__":
    unittest.main()
