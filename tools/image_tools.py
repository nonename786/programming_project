# tools/image_tools.py
import os
from pathlib import Path
from typing import Dict
from datetime import datetime

from core.tool_registry import register_tool

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _get_image_path() -> Path:
    """获取图片存储目录"""
    workspace = Path(os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")).resolve()
    image_dir = workspace / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    return image_dir


@register_tool(
    name="generate_image",
    description="生成图片，支持纯色背景、文字图片、简单图表、动物图片等。",
    parameters={
        "type": "object",
        "properties": {
            "image_type": {
                "type": "string",
                "enum": ["text", "color_bg", "simple_chart"],
                "description": "图片类型：text(文字图片)、color_bg(纯色背景)、simple_chart(简单柱状图)"
            },
            "width": {"type": "integer", "description": "图片宽度(像素)，默认800"},
            "height": {"type": "integer", "description": "图片高度(像素)，默认600"},
            "text": {"type": "string", "description": "文字内容(text类型必需)"},
            "bg_color": {"type": "string", "description": "背景颜色，RGB格式如'255,255,255'或颜色名如'white'"},
            "text_color": {"type": "string", "description": "文字颜色，默认'black'"},
            "title": {"type": "string", "description": "图片标题"},
            "data": {"type": "string", "description": "数据，JSON格式如'{\"A\": 10, \"B\": 20}'(simple_chart类型)"},
        },
        "required": ["image_type"],
    },
)
def generate_image(
        image_type: str,
        width: int = 800,
        height: int = 600,
        text: str = "",
        bg_color: str = "white",
        text_color: str = "black",
        title: str = "",
        data: str = "",
) -> Dict:
    """生成图片"""

    if not PIL_AVAILABLE:
        return {
            "success": False,
            "content": "",
            "error": "PIL库未安装，请运行: pip install Pillow"
        }

    try:
        image_dir = _get_image_path()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if image_type == "text":
            if not text.strip():
                return {"success": False, "content": "", "error": "text类型必须提供text参数"}

            img = Image.new("RGB", (width, height), bg_color)
            draw = ImageDraw.Draw(img)

            # 尝试使用系统字体，如果失败则使用默认字体
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
            except:
                font = ImageFont.load_default()

            # 计算文字位置（居中）
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2

            draw.text((x, y), text, fill=text_color, font=font)

            filename = f"text_{timestamp}.png"
            filepath = image_dir / filename
            img.save(filepath)

            return {
                "success": True,
                "content": f"✅ 文字图片已生成: {filename}\n📁 路径: {filepath}",
                "error": None
            }

        elif image_type == "color_bg":
            img = Image.new("RGB", (width, height), bg_color)
            filename = f"color_{timestamp}.png"
            filepath = image_dir / filename
            img.save(filepath)

            return {
                "success": True,
                "content": f"✅ 纯色背景图片已生成: {filename}\n📁 路径: {filepath}",
                "error": None
            }

        elif image_type == "simple_chart":
            if not data.strip():
                return {"success": False, "content": "", "error": "simple_chart类型必须提供data参数"}

            import json
            try:
                chart_data = json.loads(data)
            except json.JSONDecodeError:
                return {"success": False, "content": "", "error": f"data格式错误，应为JSON: {data}"}

            # 创建简单柱状图
            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)

            # 绘制标题
            if title:
                try:
                    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
                except:
                    font_title = ImageFont.load_default()
                draw.text((20, 20), title, fill="black", font=font_title)

            # 绘制柱状图
            items = list(chart_data.items())
            if not items:
                return {"success": False, "content": "", "error": "data不能为空"}

            max_value = max(chart_data.values())
            bar_width = (width - 100) // len(items)
            bar_height_scale = (height - 150) / max_value if max_value > 0 else 1

            for idx, (label, value) in enumerate(items):
                x1 = 50 + idx * bar_width + 10
                y1 = height - 50 - int(value * bar_height_scale)
                x2 = x1 + bar_width - 20
                y2 = height - 50

                draw.rectangle([x1, y1, x2, y2], fill="steelblue", outline="black")
                draw.text((x1 + 5, y2 + 5), f"{label}\n{value}", fill="black")

            filename = f"chart_{timestamp}.png"
            filepath = image_dir / filename
            img.save(filepath)

            return {
                "success": True,
                "content": f"✅ 柱状图已生成: {filename}\n📁 路径: {filepath}",
                "error": None
            }

        else:
            return {"success": False, "content": "", "error": f"不支持的image_type: {image_type}"}

    except Exception as e:
        return {"success": False, "content": "", "error": f"生成图片失败: {str(e)}"}