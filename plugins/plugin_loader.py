import importlib.util
import sys
from pathlib import Path
from typing import List


class PluginLoader:
    def __init__(self, plugins_dir: str = "plugins") -> None:
        self.plugins_dir = Path(plugins_dir)

    def load_all(self) -> List[str]:
        """
        扫描 plugins/ 目录下所有 .py 文件（排除 __init__.py），
        动态 import 并调用其 register() 函数完成工具注册。
        返回成功加载的插件文件名列表。
        """
        loaded: List[str] = []
        if not self.plugins_dir.exists():
            return loaded

        for plugin_file in sorted(self.plugins_dir.glob("*.py")):
            if plugin_file.name.startswith("_"):
                continue
            module_name = f"plugins.{plugin_file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, plugin_file
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                if hasattr(module, "register") and callable(module.register):
                    module.register()
                    loaded.append(plugin_file.name)
            except Exception as exc:
                print(f"[PluginLoader] 加载插件 {plugin_file.name} 失败：{exc}")

        return loaded