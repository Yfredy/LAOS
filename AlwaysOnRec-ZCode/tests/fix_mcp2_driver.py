#!/usr/bin/env python3
"""测试夹具：最小 MCP server（elicit/echo 工具）。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer

drv = MCPServer("fix", version="0.1.0")


@drv.tool("echo", "回显", {"type": "object",
          "properties": {"text": {"type": "string"}}, "required": ["text"]})
def echo(text: str) -> str:
    return f"ECHO: {text}"


@drv.tool("elicit_gate", "先 elicit 再放行",
          {"type": "object", "properties": {"text": {"type": "string"}},
           "required": ["text"]})
def elicit_gate(text: str) -> str:
    drv.elicit(f"allow {text}?")
    return f"GATED: {text}"


@drv.tool("slow", "睡 N 秒", {"type": "object",
          "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]})
def slow(seconds: float) -> str:
    time.sleep(float(seconds))
    return "SLOW-OK"


if __name__ == "__main__":
    drv.serve_forever()
