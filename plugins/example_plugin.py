from typing import Dict

from core.tool_registry import register_tool


@register_tool(
    name="count_words",
    description="统计一段文本的字符数和词数。",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "需要统计的文本内容",
            }
        },
        "required": ["text"],
    },
)
def count_words(text: str) -> Dict:
    normalized = " ".join(text.split())
    word_count = len(normalized.split()) if normalized else 0
    char_count = len(text)

    return {
        "success": True,
        "content": f"字符数: {char_count}\n词数: {word_count}",
        "error": None,
    }