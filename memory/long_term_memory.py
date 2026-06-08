# memory\long_term_memory.py
from datetime import datetime
from pathlib import Path


class LongTermMemory:
    def __init__(self, memory_file: str, logs_dir: str) -> None:
        self.memory_file = Path(memory_file)
        self.logs_dir = Path(logs_dir)

        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self.memory_file.write_text("# MEMORY\n\n", encoding="utf-8")

    def load_memory_text(self) -> str:
        return self.memory_file.read_text(encoding="utf-8")

    def append_memory(self, content: str) -> None:
        with self.memory_file.open("a", encoding="utf-8") as f:
            f.write(f"- {content.strip()}\n")

    def build_system_prompt(self, base_prompt: str) -> str:
        memory_text = self.load_memory_text().strip()
        return f"{base_prompt}\n\n以下是长期记忆，请在后续对话中参考：\n{memory_text}"

    def append_daily_log(self, content: str) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.md"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(content + "\n")