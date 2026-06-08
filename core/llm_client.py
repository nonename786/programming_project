import os
from typing import Any, Dict, List, Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from core.attachments import message_contains_images, prepare_messages_for_model


class LLMClient:
    PROVIDER_CONFIG = {
        "qwen": {
            "api_key_env": "DASHSCOPE_API_KEY",
            "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "display_name": "Qwen",
        },
        "gemini": {
            "api_key_env": "GEMINI_API_KEY",
            "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "display_name": "Gemini",
        },
        "deepseek":{
          "api_key_env": "DEEPSEEK_API_KEY",
          "default_base_url": "https://api.deepseek.com",
          "display_name": "Deepseek",
        },

    }

    def __init__(self, llm_config: Dict[str, Any]) -> None:
        self.provider = llm_config["provider"]
        self.model = llm_config["model"]
        self.vision_fallback_model = llm_config.get("vision_fallback_model", "")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)

        if self.provider not in self.PROVIDER_CONFIG:
            raise ValueError(
                f"不支持的 provider: {self.provider}，当前仅支持 qwen / gemini/deepseek。"
            )

        provider_info = self.PROVIDER_CONFIG[self.provider]
        self.display_name = provider_info["display_name"]
        self.base_url = llm_config.get("base_url") or provider_info["default_base_url"]
        self.api_key = os.getenv(provider_info["api_key_env"], "")

        if not self.api_key:
            raise ValueError(
                f"未读取到 API Key，请检查环境变量 {provider_info['api_key_env']}。"
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _extract_detail(self, exc: Exception) -> str:
        detail = getattr(exc, "message", None)
        if detail:
            return str(detail)

        body = getattr(exc, "body", None)
        if body:
            return str(body)

        return str(exc)

    def _friendly_error(self, exc: Exception) -> str:
        provider = self.display_name
        detail = self._extract_detail(exc)

        if isinstance(exc, AuthenticationError):
            if self.provider == "gemini":
                return (
                    f"{provider} 认证失败：请检查 GEMINI_API_KEY 是否正确，"
                    f"并确认 provider/base_url/model 配置匹配。原始信息：{detail}"
                )
            return f"{provider} 认证失败：请检查 API Key 是否正确。原始信息：{detail}"

        if isinstance(exc, RateLimitError):
            return (
                f"{provider} 请求频率过高或额度不足，请稍后重试，"
                f"或检查账号配额。原始信息：{detail}"
            )

        if isinstance(exc, BadRequestError):
            if self.provider == "gemini":
                return (
                    f"{provider} 请求参数无效：请重点检查 model、messages、tools "
                    f"以及是否使用了兼容接口支持的参数。原始信息：{detail}"
                )
            return f"{provider} 请求参数无效。原始信息：{detail}"

        if isinstance(exc, APITimeoutError):
            return f"{provider} 请求超时，请稍后重试。原始信息：{detail}"

        if isinstance(exc, APIConnectionError):
            return f"{provider} 网络连接失败，请检查网络环境。原始信息：{detail}"

        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", "unknown")
            return (
                f"{provider} 接口返回异常状态码 {status_code}。"
                f"原始信息：{detail}"
            )

        return f"{provider} 调用失败：{detail}"

    def create_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True,
    ):
        contains_images = message_contains_images(messages)
        request_model = self._resolve_request_model(contains_images=contains_images)

        kwargs: Dict[str, Any] = {
            "model": request_model,
            "messages": prepare_messages_for_model(
                messages,
                allow_image_inputs=self._model_supports_vision(request_model),
            ),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            return self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(self._friendly_error(exc)) from exc

    def get_provider_name(self) -> str:
        return self.provider

    def get_model_name(self) -> str:
        return self.model

    def _resolve_request_model(self, contains_images: bool) -> str:
        if not contains_images:
            return self.model

        if self._model_supports_vision(self.model):
            return self.model

        fallback = self.vision_fallback_model or self._default_vision_fallback_model()
        return fallback or self.model

    def _default_vision_fallback_model(self) -> str:
        if self.provider == "qwen":
            return "qwen3.6-plus"
        return ""

    def _model_supports_vision(self, model_name: str) -> bool:
        normalized = str(model_name or "").strip().lower()
        if not normalized:
            return False

        if self.provider == "qwen":
            return normalized.startswith(
                ("qwen3.6-", "qwen3.5-", "qwen3-vl-", "qwen-vl-")
            )

        if self.provider == "gemini":
            return "gemini" in normalized

        return False
