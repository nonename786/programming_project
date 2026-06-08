import argparse
import asyncio

from core.app_factory import build_agent, load_yaml_config
from core.message_history import MessageHistory
from gateway.input_handler import parse_user_input
from gateway.output_handler import OutputHandler
from gateway.qq_bot import QQBotRunner
from ui.cli import print_help, print_welcome
from ui.web_panel import create_web_app
from utils.logger import get_logger, setup_logger

logger = get_logger("Main")


def _run_streaming(agent: "Agent", user_input: str) -> None:
    OH = OutputHandler
    token_started = False
    for event in agent.handle_user_message_stream(user_input):
        etype = event["type"]
        if etype == "token":
            if not token_started:
                print(f"{OH.GREEN}✅ AI:{OH.RESET} ", end="", flush=True)
                token_started = True
            print(event["content"], end="", flush=True)
        elif etype == "thought_done":
            if token_started:
                print()
                token_started = False
            OH.thought(event["content"])
        elif etype == "action":
            if token_started:
                print()
                token_started = False
            OH.action(event["tool"], event["args"])
        elif etype == "observation":
            OH.observation(event["content"])
        elif etype == "answer_done":
            if not token_started:
                print(f"{OH.GREEN}✅ AI:{OH.RESET} {event['content']}")
            else:
                print()
        elif etype == "error":
            if token_started:
                print()
                token_started = False
            OH.error(event["content"])


def run_cli(resume_session_id: str = "") -> None:
    config = load_yaml_config("config/config.yaml")
    agent = build_agent(resume_session_id=resume_session_id)

    print_welcome()
    print(
        f"当前模型提供商: {agent.llm_client.get_provider_name()} | "
        f"当前模型: {agent.llm_client.get_model_name()}"
    )

    if resume_session_id:
        if agent.loaded_session_meta:
            print(
                "已恢复会话："
                f"{agent.loaded_session_meta['session_id']} | "
                f"start={agent.loaded_session_meta['start_time']} | "
                f"tool_calls={agent.loaded_session_meta['tool_calls_count']}"
            )
        else:
            print(f"未找到可恢复会话：{resume_session_id}，已启动新会话。")

    while True:
        user_input = input("\n你：").strip()
        parsed = parse_user_input(user_input)

        if parsed["type"] == "empty":
            continue

        if parsed["type"] == "command":
            cmd = parsed["value"]

            if cmd == "exit":
                save_path = agent.session_manager.save_session(
                    model_name=agent.llm_client.model,
                    messages=agent.message_history.get_messages(),
                )
                print(f"\n会话已保存：{save_path}")
                break

            if cmd == "save":
                save_path = agent.session_manager.save_session(
                    model_name=agent.llm_client.model,
                    messages=agent.message_history.get_messages(),
                )
                print(f"当前会话已保存：{save_path}")
                continue

            if cmd == "clear":
                base_prompt = config["agent"]["system_prompt"]
                memory_text = agent.long_term_memory.build_system_prompt(base_prompt)
                agent.message_history = MessageHistory(system_prompt=memory_text)
                print("当前会话已清空。")
                continue

            if cmd == "history":
                turns = agent.message_history.get_turn_count()
                print(f"当前会话轮数：{turns}")
                continue

            if cmd == "remember":
                content = parsed.get("content", "").strip()
                if not content:
                    print("记忆内容不能为空。")
                else:
                    agent.long_term_memory.append_memory(content)
                    print(f"已写入长期记忆：{content}")
                continue

            if cmd == "list-sessions":
                sessions = agent.session_manager.list_sessions(limit=30)
                if not sessions:
                    print("暂无历史会话。")
                else:
                    for item in sessions:
                        resumed_from = item.get("resumed_from_session_id") or "-"
                        print(
                            f"session_id={item['session_id']} | "
                            f"model={item['model']} | "
                            f"start={item['start_time']} | "
                            f"tool_calls={item['tool_calls_count']} | "
                            f"resumed_from={resumed_from}"
                        )
                continue

            if cmd == "help":
                print_help()
                continue

        _run_streaming(agent, parsed["value"])


def run_web(resume_session_id: str, host: str, port: int, debug: bool) -> None:
    app = create_web_app(resume_session_id=resume_session_id)
    print(f"Web Panel 启动中：http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


async def qq_terminal_loop(runner: QQBotRunner) -> None:
    help_text = """
QQ 模式终端命令：
  /help                      查看帮助
  /status                    查看 QQ 当前状态
  /sessions                  查看当前 QQ 会话列表
  /ask <问题>                用 QQ-terminal 会话向 AI 提问
  /send <QQ号> <消息>        主动发送私聊消息
  /sendg <群号> <消息>       主动发送群消息
  /quit                      退出 QQ 模式
""".strip()

    print(help_text)
    print("💬 QQ 自动回复已启动，现在可以在终端输入命令。\n")

    while True:
        try:
            user_input = await asyncio.to_thread(input, "QQ> ")
            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input in ("/quit", "/exit", "/q"):
                logger.info("👋 收到退出指令")
                break

            if user_input in ("/help", "/h", "/?"):
                print(help_text)
                continue

            if user_input == "/status":
                print("\n📊 当前状态：")
                print(runner.get_status_text())
                print()
                continue

            if user_input == "/sessions":
                sessions = runner.list_session_ids()
                if not sessions:
                    print("（当前暂无 QQ 会话）")
                else:
                    print("当前 QQ 会话：")
                    for sid in sessions:
                        print(f"  - {sid}")
                continue

            if user_input.startswith("/ask "):
                question = user_input[5:].strip()
                if not question:
                    print("⚠️ 请输入问题内容")
                    continue
                print("\n🤔 AI思考中...\n")
                answer = runner.ask_terminal(question)
                print(f"🤖 AI回复：\n{'-' * 50}")
                print(answer)
                print("-" * 50)
                continue

            if user_input.startswith("/send "):
                parts = user_input.split(" ", 2)
                if len(parts) < 3:
                    print("⚠️ 格式错误，用法：/send <QQ号> <消息>")
                    continue

                target_qq = parts[1].strip()
                message = parts[2].strip()

                if not target_qq or not message:
                    print("⚠️ QQ号和消息内容都不能为空")
                    continue

                await runner.send_private_message(target_qq, message)
                print("✅ 私聊消息发送成功")
                continue

            if user_input.startswith("/sendg "):
                parts = user_input.split(" ", 2)
                if len(parts) < 3:
                    print("⚠️ 格式错误，用法：/sendg <群号> <消息>")
                    continue

                target_group = parts[1].strip()
                message = parts[2].strip()

                if not target_group or not message:
                    print("⚠️ 群号和消息内容都不能为空")
                    continue

                await runner.send_group_message(target_group, message)
                print("✅ 群消息发送成功")
                continue

            print("⚠️ 未知命令，输入 /help 查看帮助")

        except KeyboardInterrupt:
            print()
            logger.info("👋 用户中断，准备退出")
            break
        except Exception as exc:
            logger.error(f"❌ QQ 终端处理异常: {exc}")


async def run_qq() -> None:
    config = load_yaml_config("config/config.yaml")
    qq_enabled = bool(config.get("qq", {}).get("enabled", False))
    if not qq_enabled:
        raise RuntimeError("qq.enabled=false，未开启 QQ 模式。请先修改 config/config.yaml。")

    app_config = config.get("app", {})
    log_level = app_config.get("log_level", "INFO")
    log_file = app_config.get("log_file", "logs/qq_mode.log")
    setup_logger(log_level=log_level, log_file=log_file)

    runner = QQBotRunner(config_path="config/config.yaml")
    logger.info("🚀 QQ Bot 启动中...")

    await runner.start()
    try:
        await qq_terminal_loop(runner)
    finally:
        await runner.close()
        logger.info("👋 QQ Bot 已退出")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini-OpenClaw")
    parser.add_argument(
        "--resume",
        type=str,
        default="",
        help="通过 session_id 恢复历史会话，或传 latest 恢复最近一次会话",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="以 Flask Web Panel 模式启动",
    )
    parser.add_argument(
        "--qq",
        action="store_true",
        help="以 QQ OneBot 模式启动",
    )
    parser.add_argument("--host", type=str, default="", help="Web 模式 host")
    parser.add_argument("--port", type=int, default=0, help="Web 模式 port")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Web 模式调试开关",
    )
    args = parser.parse_args()

    config = load_yaml_config("config/config.yaml")

    if args.qq:
        asyncio.run(run_qq())
        return

    if args.web:
        host = args.host or config.get("web", {}).get("host", "127.0.0.1")
        port = args.port or int(config.get("web", {}).get("port", 7860))
        debug = args.debug or bool(config.get("web", {}).get("debug", False))
        run_web(
            resume_session_id=args.resume,
            host=host,
            port=port,
            debug=debug,
        )
        return

    run_cli(resume_session_id=args.resume)


if __name__ == "__main__":
    main()