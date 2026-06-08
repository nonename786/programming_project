import tempfile
import unittest
import zipfile
from pathlib import Path

from core.attachments import (
    FILE_PART_TYPE,
    IMAGE_PART_TYPE,
    SOURCE_CAMERA,
    TEXT_PART_TYPE,
    build_visible_message,
    message_contains_images,
    prepare_messages_for_model,
)


class TestAttachments(unittest.TestCase):
    def test_build_visible_message_marks_camera_image_as_photo(self):
        content = [
            {"type": TEXT_PART_TYPE, "text": "请看这张图"},
            {
                "type": IMAGE_PART_TYPE,
                "name": "photo.jpg",
                "mime_type": "image/jpeg",
                "size": 123,
                "relative_path": "demo/photo.jpg",
                "source": SOURCE_CAMERA,
            },
        ]

        visible = build_visible_message(content)
        self.assertEqual(visible["text"], "请看这张图")
        self.assertEqual(visible["attachments"][0]["kind_label"], "照片")

    def test_prepare_messages_for_model_inlines_text_files_and_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_file = root / "note.txt"
            image_file = root / "image.png"
            text_file.write_text("hello attachment", encoding="utf-8")
            image_file.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": TEXT_PART_TYPE, "text": "请一起看附件"},
                        {
                            "type": FILE_PART_TYPE,
                            "name": "note.txt",
                            "path": str(text_file),
                            "mime_type": "text/plain",
                            "size": text_file.stat().st_size,
                            "relative_path": "demo/note.txt",
                        },
                        {
                            "type": IMAGE_PART_TYPE,
                            "name": "image.png",
                            "path": str(image_file),
                            "mime_type": "image/png",
                            "size": image_file.stat().st_size,
                            "relative_path": "demo/image.png",
                        },
                    ],
                }
            ]

            prepared = prepare_messages_for_model(messages)
            parts = prepared[0]["content"]

            self.assertEqual(parts[0]["type"], "text")
            self.assertIn("hello attachment", parts[1]["text"])
            self.assertEqual(parts[2]["type"], "image_url")
            self.assertTrue(parts[2]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_prepare_messages_for_model_falls_back_when_images_not_allowed(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": TEXT_PART_TYPE, "text": "分析一下"},
                    {
                        "type": IMAGE_PART_TYPE,
                        "name": "image.png",
                        "path": "missing.png",
                        "mime_type": "image/png",
                        "size": 12,
                    },
                ],
            }
        ]

        prepared = prepare_messages_for_model(messages, allow_image_inputs=False)
        self.assertEqual(prepared[0]["content"][1]["type"], "text")
        self.assertIn("当前模型不支持直接识图", prepared[0]["content"][1]["text"])

    def test_docx_file_is_extracted_as_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docx_file = root / "demo.docx"
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p></w:body></w:document>"
            )
            with zipfile.ZipFile(docx_file, "w") as archive:
                archive.writestr("word/document.xml", xml)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": TEXT_PART_TYPE, "text": "读一下"},
                        {
                            "type": FILE_PART_TYPE,
                            "name": "demo.docx",
                            "path": str(docx_file),
                            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "size": docx_file.stat().st_size,
                        },
                    ],
                }
            ]

            prepared = prepare_messages_for_model(messages)
            self.assertIn("Hello DOCX", prepared[0]["content"][1]["text"])

    def test_message_contains_images_detects_image_parts(self):
        messages = [
            {"role": "user", "content": [{"type": IMAGE_PART_TYPE, "name": "a.png"}]}
        ]
        self.assertTrue(message_contains_images(messages))


if __name__ == "__main__":
    unittest.main()
