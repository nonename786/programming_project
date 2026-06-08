# tests\test_tools.py
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.file_tools import create_directory, list_directory, read_file, write_file
from tools.calculator_tools import calculate
from tools.todo_tools import manage_todo


class TestTools(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MINI_OPENCLAW_WORKSPACE"] = self.temp_dir
        os.environ["MINI_OPENCLAW_SECURITY_CONFIG"] = str(
            Path("config/security_config.yaml").resolve()
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_file(self):
        result1 = write_file("notes/a.txt", "hello world", "overwrite")
        self.assertTrue(result1["success"])

        result2 = read_file("notes/a.txt")
        self.assertTrue(result2["success"])
        self.assertEqual(result2["content"], "hello world")

    def test_create_and_list_directory(self):
        result1 = create_directory("demo")
        self.assertTrue(result1["success"])

        result2 = write_file("demo/x.txt", "abc", "overwrite")
        self.assertTrue(result2["success"])

        result3 = list_directory("demo")
        self.assertTrue(result3["success"])
        self.assertIn("x.txt", result3["content"])

    def test_calculate(self):
        result = calculate("2*(3+4)")
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "14")

    def test_todo_manager(self):
        add_result = manage_todo("add", title="写作业")
        self.assertTrue(add_result["success"])

        list_result = manage_todo("list")
        self.assertTrue(list_result["success"])
        self.assertIn("写作业", list_result["content"])


if __name__ == "__main__":
    unittest.main()