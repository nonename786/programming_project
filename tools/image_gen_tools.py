import os
import uuid
from pathlib import Path
from typing import Dict

import requests
from openai import OpenAI

from core.tool_registry import register_tool


def _get_gen_dir() -> Path:
    workspace = os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")
    gen_dir = Path(workspace).resolve() / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    return gen_dir


@register_tool(
    name="generate_image",
    description=(
        "使用 AI 模型（通义万相）根据文字描述生成图片。"
        "生成的图片会保存到 workspace/generated/ 目录。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图片描述，尽量详细（如：一只橘色小猫坐在窗台上，阳光照进来）",
            },
            "size": {
                "type": "string",
                "enum": ["1024*1024", "720*1280", "1280*720"],
                "description": "图片尺寸：1024*1024(方形)、720*1280(竖版)、1280*720(横版)",
            },
        },
        "required": ["prompt"],
    },
)
def generate_image(prompt: str, size: str = "1024*1024") -> Dict:
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "content": "",
            "error": "未配置 DASHSCOPE_API_KEY，无法生成图片。",
        }

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    try:
        result = client.images.generate(
            model="wanx2.1-t2i-turbo",
            prompt=prompt,
            n=1,
            size=size,
        )
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"图片生成失败: {exc}",
        }

    image_url = result.data[0].url
    if not image_url:
        return {
            "success": False,
            "content": "",
            "error": "模型未返回图片 URL。",
        }

    gen_dir = _get_gen_dir()
    filename = f"{uuid.uuid4().hex[:8]}.png"
    filepath = gen_dir / filename

    try:
        resp = requests.get(image_url, timeout=60)
        resp.raise_for_status()
        filepath.write_bytes(resp.content)
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"图片下载保存失败: {exc}",
        }

    return {
        "success": True,
        "content": f"图片已生成并保存到: generated/{filename}",
        "error": None,
        "image_path": f"generated/{filename}",
    }


@register_tool(
    name="generate_file",
    description=(
        "使用 AI 模型生成文件内容（如代码、配置、文档等），并保存到 workspace 中。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "要生成的文件名（如 hello.py, config.yaml）",
            },
            "content": {
                "type": "string",
                "description": "文件内容",
            },
        },
        "required": ["filename", "content"],
    },
)
def generate_file(filename: str, content: str) -> Dict:
    gen_dir = _get_gen_dir()
    safe_name = "".join(
        c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename
    )
    filepath = gen_dir / safe_name

    try:
        filepath.write_text(content, encoding="utf-8")
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"文件保存失败: {exc}",
        }

    return {
        "success": True,
        "content": f"文件已生成并保存到: generated/{safe_name}",
        "error": None,
        "file_path": f"generated/{safe_name}",
    }
