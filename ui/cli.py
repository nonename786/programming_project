def print_welcome() -> None:
    print("=" * 60)
    print("Mini-OpenClaw CLI")
    print("输入自然语言开始对话；输入 /help 查看命令。")
    print("=" * 60)


def print_welcome() -> None:
    print("=" * 60)
    print("Mini-OpenClaw CLI")
    print("输入自然语言开始对话；输入 /help 查看命令。")
    print("=" * 60)


def print_help() -> None:
    print(
        """
可用命令：
  /help            查看帮助
  /history         查看当前会话轮数
  /clear           清空当前会话
  /save            立即保存当前会话
  /remember 内容    写入长期记忆 MEMORY.md
  /list-sessions   查看历史会话
  /exit            保存并退出程序

启动方式补充：
  python main.py
  python main.py --resume latest
  python main.py --resume 你的session_id
  python main.py --web
  python main.py --qq
        """.strip()
    )


