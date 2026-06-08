import unittest

from core.llm_client import LLMClient


class TestLLMClient(unittest.TestCase):
    def test_qwen_text_model_uses_vision_fallback_for_image_requests(self):
        client = object.__new__(LLMClient)
        client.provider = "qwen"
        client.model = "qwen-plus"
        client.vision_fallback_model = "qwen3.6-plus"

        self.assertEqual(client._resolve_request_model(contains_images=True), "qwen3.6-plus")
        self.assertFalse(client._model_supports_vision("qwen-plus"))
        self.assertTrue(client._model_supports_vision("qwen3.6-plus"))

    def test_non_image_requests_keep_primary_model(self):
        client = object.__new__(LLMClient)
        client.provider = "qwen"
        client.model = "qwen-plus"
        client.vision_fallback_model = "qwen3.6-plus"

        self.assertEqual(client._resolve_request_model(contains_images=False), "qwen-plus")


if __name__ == "__main__":
    unittest.main()
