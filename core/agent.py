import json
from typing import Any, Dict, Generator, List, Optional

from core.attachments import describe_message_content
from core.llm_client import LLMClient
from core.message_history import MessageHistory
from core.tool_registry import TOOL_REGISTRY, append_tool_audit_log
from gateway.output_handler import OutputHandler
from gateway.session_manager import SessionManager
from memory.long_term_memory import LongTermMemory
from memory.session_memory import SessionMemory


class Agent:
    def __init__(
        self,
        llm_client: LLMClient,
        message_history: MessageHistory,
        session_memory: SessionMemory,
        long_term_memory: LongTermMemory,
        session_manager: SessionManager,
        app_config: Dict[str, Any],
        paths_config: Dict[str, Any],
        allowed_tool_names: Optional[List[str]] = None,
        sub_agents_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.llm_client = llm_client
        self.message_history = message_history
        self.session_memory = session_memory
        self.long_term_memory = long_term_memory
        self.session_manager = session_manager
        self.max_iterations = int(app_config.get("max_iterations", 10))
        self.stream_output = bool(app_config.get("stream_output", False))
        self.tool_audit_log = paths_config["tool_audit_log"]
        self.loaded_session_meta: Optional[Dict[str, Any]] = None
        self.allowed_tool_names = allowed_tool_names
        self.sub_agents_config = sub_agents_config or {}

    def set_allowed_tools(self, allowed_tool_names: Optional[List[str]]) -> None:
        self.allowed_tool_names = allowed_tool_names

    def get_current_tool_names(self) -> List[str]:
        return [tool.name for tool in TOOL_REGISTRY.list_tools(self.allowed_tool_names)]

    def _normalize_tool_result(self, result: Dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _is_tool_allowed(self, tool_name: str) -> bool:
        if self.allowed_tool_names is None:
            return True
        return tool_name in set(self.allowed_tool_names)

    def handle_user_message(self, user_input: Any) -> str:
        self.message_history.add_user(user_input)
        final_answer = ""
        user_input_text = describe_message_content(user_input)

        for _ in range(self.max_iterations):
            messages = self.session_memory.trim_messages(
                self.message_history.get_messages()
            )

            try:
                response = self.llm_client.create_chat_completion(
                    messages=messages,
                    tools=TOOL_REGISTRY.get_openai_tool_schemas(
                        allowed_names=self.allowed_tool_names
                    ),
                    stream=False,
                )
            except Exception as exc:
                error_message = str(exc)
                self.message_history.add_assistant(content=error_message, tool_calls=None)
                self.long_term_memory.append_daily_log(
                    f"## User\n{user_input_text}\n\n## Assistant Error\n{error_message}\n"
                )
                OutputHandler.error(error_message)
                return error_message

            choice = response.choices[0]
            assistant_message = choice.message

            thought_text = assistant_message.content or ""
            if thought_text.strip():
                OutputHandler.thought(thought_text)

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

                self.message_history.add_assistant(
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

                    OutputHandler.action(tool_name, tool_args)

                    if not self._is_tool_allowed(tool_name):
                        result = {
                            "success": False,
                            "content": "",
                            "error": f"工具 {tool_name} 在当前入口未被允许使用。",
                        }
                    else:
                        result = TOOL_REGISTRY.call_tool(tool_name, tool_args)

                    append_tool_audit_log(
                        self.tool_audit_log,
                        tool_name,
                        tool_args,
                        result,
                    )
                    self.session_manager.add_tool_record(tool_name, tool_args, result)

                    observation_text = self._normalize_tool_result(result)
                    OutputHandler.observation(observation_text)

                    self.message_history.add_tool(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        content=observation_text,
                    )

                continue

            final_answer = thought_text.strip() or "模型返回了空内容。"
            self.message_history.add_assistant(content=final_answer, tool_calls=None)

            self.long_term_memory.append_daily_log(
                f"## User\n{user_input_text}\n\n## Assistant\n{final_answer}\n"
            )

            if self.stream_output:
                OutputHandler.final_answer_stream(final_answer)
            else:
                OutputHandler.final_answer(final_answer)

            return final_answer

        final_answer = "已达到最大推理轮数，任务被安全终止。"
        self.message_history.add_assistant(content=final_answer)
        OutputHandler.error(final_answer)
        return final_answer

    def handle_user_message_stream(
        self, user_input: Any
    ) -> Generator[Dict[str, Any], None, None]:
        self.message_history.add_user(user_input)
        user_input_text = describe_message_content(user_input)

        for _ in range(self.max_iterations):
            messages = self.session_memory.trim_messages(
                self.message_history.get_messages()
            )

            tools_schemas = TOOL_REGISTRY.get_openai_tool_schemas(
                allowed_names=self.allowed_tool_names
            )

            try:
                response = self.llm_client.create_chat_completion(
                    messages=messages,
                    tools=tools_schemas,
                    stream=True,
                )
            except Exception as exc:
                error_message = str(exc)
                self.message_history.add_assistant(
                    content=error_message, tool_calls=None
                )
                yield {"type": "error", "content": error_message}
                return

            content_parts: List[str] = []
            tool_calls_buf: List[Dict[str, Any]] = []

            try:
                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if hasattr(delta, "content") and delta.content:
                        content_parts.append(delta.content)
                        yield {"type": "token", "content": delta.content}

                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            while len(tool_calls_buf) <= idx:
                                tool_calls_buf.append(
                                    {"id": "", "name": "", "arguments": ""}
                                )
                            if tc_delta.id:
                                tool_calls_buf[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_buf[idx]["name"] = (
                                        tc_delta.function.name
                                    )
                                if tc_delta.function.arguments:
                                    tool_calls_buf[idx]["arguments"] += (
                                        tc_delta.function.arguments
                                    )
            except Exception as exc:
                error_message = str(exc)
                self.message_history.add_assistant(
                    content=error_message, tool_calls=None
                )
                yield {"type": "error", "content": error_message}
                return

            full_content = "".join(content_parts)
            has_tool_calls = bool(
                tool_calls_buf and tool_calls_buf[0].get("name")
            )

            if has_tool_calls:
                if full_content.strip():
                    yield {"type": "thought_done", "content": full_content}

                serialized_tool_calls = []
                for tc in tool_calls_buf:
                    serialized_tool_calls.append(
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                    )

                self.message_history.add_assistant(
                    content=full_content,
                    tool_calls=serialized_tool_calls,
                )

                for tc in tool_calls_buf:
                    tool_name = tc["name"]
                    raw_args = tc["arguments"] or "{}"
                    try:
                        tool_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {
                        "type": "action",
                        "tool": tool_name,
                        "args": tool_args,
                    }

                    if not self._is_tool_allowed(tool_name):
                        result = {
                            "success": False,
                            "content": "",
                            "error": (
                                f"工具 {tool_name} 在当前入口未被允许使用。"
                            ),
                        }
                    else:
                        result = TOOL_REGISTRY.call_tool(tool_name, tool_args)

                    append_tool_audit_log(
                        self.tool_audit_log, tool_name, tool_args, result
                    )
                    self.session_manager.add_tool_record(
                        tool_name, tool_args, result
                    )

                    observation_text = self._normalize_tool_result(result)
                    yield {"type": "observation", "content": observation_text}

                    self.message_history.add_tool(
                        tool_call_id=tc["id"],
                        name=tool_name,
                        content=observation_text,
                    )

                continue

            final_answer = full_content.strip() or "模型返回了空内容。"
            self.message_history.add_assistant(
                content=final_answer, tool_calls=None
            )
            self.long_term_memory.append_daily_log(
                f"## User\n{user_input_text}\n\n## Assistant\n{final_answer}\n"
            )
            yield {"type": "answer_done", "content": final_answer}
            return

        timeout_msg = "已达到最大推理轮数，任务被安全终止。"
        self.message_history.add_assistant(content=timeout_msg)
        yield {"type": "error", "content": timeout_msg}

    def delegate_to_sub_agent(self, task: str, agent_type: str) -> Dict[str, Any]:
        from core.sub_agent import SubAgent

        available_types = self.sub_agents_config.get("types", {})
        type_config = available_types.get(agent_type)
        if type_config is None:
            valid = ", ".join(available_types.keys()) or "无"
            return {
                "success": False,
                "content": "",
                "error": f"未知的子 Agent 类型：{agent_type}，可选类型：{valid}",
            }

        sub_agent = SubAgent(
            name=agent_type,
            llm_client=self.llm_client,
            system_prompt=type_config["system_prompt"],
            allowed_tool_names=type_config["allowed_tools"],
            max_iterations=self.sub_agents_config.get("max_iterations", 5),
            tool_audit_log=self.tool_audit_log,
        )

        result_text = sub_agent.run(task)
        return {
            "success": True,
            "content": result_text,
            "error": None,
        }
