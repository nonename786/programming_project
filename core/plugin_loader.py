import importlib.util
import sys
from pathlib import Path
from typing import List


def load_plugins(plugin_dir: str) -> List[str]:
    plugin_path = Path(plugin_dir)
    if not plugin_path.exists():
        return []

    loaded_modules: List[str] = []

    for file in sorted(plugin_path.glob("*.py")):
        if file.name.startswith("_") or file.name == "__init__.py":
            continue

        module_name = f"plugins.{file.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, file)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded_modules.append(module_name)
        except Exception as exc:
            print(f"插件加载失败：{file.name} -> {exc}")

    return loaded_modules