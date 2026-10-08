"""工具调用参数校验 —— 堵 AIOS Tool Manager 无校验的洞。

    python -m unittest tests.test_validate -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.validate import ValidationError, validate_args  # noqa: E402


class TestValidateArgs(unittest.TestCase):
    SCHEMA = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path"],
    }

    def test_missing_required(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {})

    def test_wrong_type(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {"path": 123})

    def test_bool_not_int(self):
        with self.assertRaises(ValidationError):
            validate_args(
                {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]},
                {"n": True},
            )

    def test_enum(self):
        s = {
            "type": "object",
            "properties": {"m": {"type": "string", "enum": ["a", "b"]}},
            "required": ["m"],
        }
        with self.assertRaises(ValidationError):
            validate_args(s, {"m": "c"})

    def test_path_traversal_blocked(self):
        with self.assertRaises(ValidationError):
            validate_args(self.SCHEMA, {"path": "../etc/passwd"})

    def test_ok(self):
        validate_args(self.SCHEMA, {"path": "/main/x"})


if __name__ == "__main__":
    unittest.main()
