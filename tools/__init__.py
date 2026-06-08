from tools import file_tools  # noqa: F401
from tools import shell_tools  # noqa: F401
from tools import search_tools  # noqa: F401
from tools import calculator_tools  # noqa: F401
from tools import datetime_tools  # noqa: F401
from tools import summary_tools  # noqa: F401
from tools import todo_tools  # noqa: F401
from tools import web_tools  # noqa: F401
from tools import local_file_tools  # noqa: F401
from tools import powershell_tools  # noqa: F401
from tools import sub_agent_tools  # noqa: F401
from tools import scheduler_tools  # noqa: F401
from tools import image_gen_tools  # noqa: F401

def register_builtin_tools() -> None:
    """
    导入模块即完成注册，这个函数只是提供一个显式调用入口。
    """
    return