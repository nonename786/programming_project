import os
import time


class OutputHandler:
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"

    @classmethod
    def thought(cls, content: str) -> None:
        if content.strip():
            print(f"{cls.BLUE}💭 Thought:{cls.RESET} {content}")

    @classmethod
    def action(cls, tool_name: str, arguments: dict) -> None:
        print(f"{cls.YELLOW}🔧 Action:{cls.RESET} {tool_name}({arguments})")

    @classmethod
    def observation(cls, content: str) -> None:
        print(f"{cls.CYAN}👁️ Observation:{cls.RESET} {content}")

    @classmethod
    def final_answer(cls, content: str) -> None:
        print(f"{cls.GREEN}✅ Final Answer:{cls.RESET} {content}")

    @classmethod
    def final_answer_stream(cls, content: str) -> None:
        try:
            delay = float(os.getenv("MINI_OPENCLAW_STREAM_DELAY", "0.01"))
        except ValueError:
            delay = 0.01

        print(f"{cls.GREEN}✅ Final Answer:{cls.RESET} ", end="", flush=True)
        for ch in content:
            print(ch, end="", flush=True)
            if delay > 0:
                time.sleep(delay)
        print()

    @classmethod
    def error(cls, content: str) -> None:
        print(f"{cls.RED}❌ Error:{cls.RESET} {content}")

    MAGENTA = "\033[95m"

    @classmethod
    def sub_agent_start(cls, name: str, task: str) -> None:
        print(f"{cls.MAGENTA}🤖 SubAgent [{name}] 启动:{cls.RESET} {task}")

    @classmethod
    def sub_agent_thought(cls, name: str, content: str) -> None:
        if content.strip():
            print(f"{cls.MAGENTA}  💭 [{name}] Thought:{cls.RESET} {content}")

    @classmethod
    def sub_agent_action(cls, name: str, tool_name: str, arguments: dict) -> None:
        print(f"{cls.MAGENTA}  🔧 [{name}] Action:{cls.RESET} {tool_name}({arguments})")

    @classmethod
    def sub_agent_observation(cls, name: str, content: str) -> None:
        print(f"{cls.MAGENTA}  👁️ [{name}] Observation:{cls.RESET} {content}")

    @classmethod
    def sub_agent_end(cls, name: str, content: str) -> None:
        print(f"{cls.MAGENTA}🤖 SubAgent [{name}] 完成:{cls.RESET} {content}")

    @classmethod
    def sub_agent_error(cls, name: str, content: str) -> None:
        print(f"{cls.RED}🤖 SubAgent [{name}] 出错:{cls.RESET} {content}")