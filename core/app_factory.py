import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from core.agent import Agent
from core.llm_client import LLMClient
from core.message_history import MessageHistory
from core.plugin_loader import load_plugins
from core.tool_registry import TOOL_REGISTRY
from gateway.session_manager import SessionManager
from memory.long_term_memory import LongTermMemory
from memory.session_memory import SessionMemory
from tools import register_builtin_tools
from tools import image_tools  # 导入图片工具
from tools import ppt_tools    # 导入PPT工具

def load_yaml_config(path: str) -> Dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def ensure_directories(config: Dict[str, Any]) -> None:
    paths = config["paths"]
    Path(paths["workspace_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["history_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["qq_history_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["memory_file"]).parent.mkdir(parents=True, exist_ok=True)
    Path(paths["memory_logs_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["tool_audit_log"]).parent.mkdir(parents=True, exist_ok=True)

    plugin_dir = config.get("plugins", {}).get("plugin_dir", "plugins")
    Path(plugin_dir).mkdir(parents=True, exist_ok=True)

def apply_environment(config: Dict[str, Any]) -> None:
    os.environ["MINI_OPENCLAW_WORKSPACE"] = str(
        Path(config["paths"]["workspace_dir"]).resolve()
    )
    os.environ["MINI_OPENCLAW_SECURITY_CONFIG"] = str(
        Path("config/security_config.yaml").resolve()
    )


def configure_tools(config: Dict[str, Any]) -> None:
    register_builtin_tools()

    plugins_config = config.get("plugins", {})
    if plugins_config.get("auto_load", True):
        load_plugins(plugins_config.get("plugin_dir", "plugins"))

    tools_config = load_yaml_config("config/tools_config.yaml")
    enabled_tools = tools_config.get("enabled_tools", [])
    TOOL_REGISTRY.enable_only(enabled_tools)


def build_agent(resume_session_id: str = "") -> Agent:
    load_dotenv()

    config = load_yaml_config("config/config.yaml")
    ensure_directories(config)
    apply_environment(config)
    configure_tools(config)

    long_term_memory = LongTermMemory(
        memory_file=config["paths"]["memory_file"],
        logs_dir=config["paths"]["memory_logs_dir"],
    )

    base_prompt = config["agent"]["system_prompt"]
    full_system_prompt = long_term_memory.build_system_prompt(base_prompt)

    message_history = MessageHistory(system_prompt=full_system_prompt)
    session_memory = SessionMemory(
        max_messages=config["memory"]["max_history_messages"]
    )
    session_manager = SessionManager(history_dir=config["paths"]["history_dir"])

    loaded_session_meta: Optional[Dict[str, Any]] = None

    if resume_session_id:
        old_session = session_manager.load_session(resume_session_id)
        if old_session and old_session.get("messages"):
            message_history.messages = old_session["messages"]
            session_manager.resume_from_session(old_session)
            loaded_session_meta = {
                "session_id": old_session.get("session_id"),
                "start_time": old_session.get("start_time"),
                "end_time": old_session.get("end_time"),
                "model": old_session.get("model"),
                "tool_calls_count": old_session.get("tool_calls_count", 0),
            }

    llm_client = LLMClient(config["llm"])

    agent = Agent(
        llm_client=llm_client,
        message_history=message_history,
        session_memory=session_memory,
        long_term_memory=long_term_memory,
        session_manager=session_manager,
        app_config=config["app"],
        paths_config=config["paths"],
        sub_agents_config=config.get("sub_agents"),
    )
    agent.loaded_session_meta = loaded_session_meta

    from tools.sub_agent_tools import set_parent_agent
    set_parent_agent(agent)

    return agent