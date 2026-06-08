import json
from typing import Any, Dict, List

from core.llm_client import LLMClient
from core.message_history import MessageHistory
from core.tool_registry import TOOL_REGISTRY, append_tool_audit_log
from gateway.output_handler import OutputHandler


class SubAgent:
    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        system_prompt: str,
        allowed_tool_names: List[str],
        max_iterations: int = 5,
        tool_audit_log: str = "",
    ) -> None:
        self.name = name
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.allowed_tool_names = allowed_tool_names
        self.max_iterations = max_iterations
        self.tool_audit_log = tool_audit_log

    def run(self, task: str) -> str:
        OutputHandler.sub_agent_start(self.name, task)

        message_history = MessageHistory(system_prompt=self.system_prompt)
        message_history.add_user(task)

        for _ in range(self.max_iterations):
            messages = message_history.get_messages()

            try:
                response = self.llm_client.create_chat_completion(
                    messages=messages,
                    tools=TOOL_REGISTRY.get_openai_tool_schemas(
                        allowed_names=self.allowed_tool_names
                    ),
                    stream=False,
                )
            except Exception as exc:
                error_msg = str(exc)
                OutputHandler.sub_agent_error(self.name, error_msg)
                return f"[子Agent {self.name} 执行出错] {error_msg}"

            choice = response.choices[0]
            assistant_message = choice.message

            thought_text = assistant_message.content or ""
            if thought_text.strip():
                OutputHandler.sub_agent_thought(self.name, thought_text)

            tool_calls = assistant_message.tool_calls or []
            if tool_calls:
                serialized_tool_calls = []
                for tool_call in tool_calls:
                    serialized_tool_calls.append(
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    )

                message_history.add_assistant(
                    content=thought_text,
                    tool_calls=serialized_tool_calls,
                )

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    raw_args = tool_call.function.arguments or "{}"

                    try:
                        tool_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                    OutputHandler.sub_agent_action(self.name, tool_name, tool_args)

                    if tool_name not in set(self.allowed_tool_names):
                        result = {
                            "success": False,
                            "content": "",
                            "error": f"工具 {tool_name} 未被允许在子Agent {self.name} 中使用。",
                        }
                    else:
                        result = TOOL_REGISTRY.call_tool(tool_name, tool_args)

                    if self.tool_audit_log:
                        append_tool_audit_log(
                            self.tool_audit_log, tool_name, tool_args, result
                        )

                    observation_text = json.dumps(
                        result, ensure_ascii=False, indent=2
                    )
                    OutputHandler.sub_agent_observation(self.name, observation_text)

                    message_history.add_tool(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        content=observation_text,
                    )

                continue

            final_answer = thought_text.strip() or "子Agent 返回了空内容。"
            OutputHandler.sub_agent_end(self.name, final_answer)
            return final_answer

        timeout_msg = (
            f"子Agent {self.name} 已达到最大推理轮数 ({self.max_iterations})，任务被终止。"
        )
        OutputHandler.sub_agent_error(self.name, timeout_msg)
        return timeout_msg
