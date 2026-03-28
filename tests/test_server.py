"""Integration tests for MCP server tools."""

import asyncio
import pytest

from evds_mcp.server import mcp


@pytest.fixture
def tool_names():
    """Get registered tool names."""
    comps = mcp._local_provider._components
    return [
        key.split(":")[1].split("@")[0]
        for key in comps.keys()
        if key.startswith("tool:")
    ]


def test_all_tools_registered(tool_names):
    """All 4 tools are registered."""
    expected = {"evds_ara", "evds_meta", "evds_cek", "evds_analiz"}
    assert expected == set(tool_names)


def test_tool_descriptions_not_empty(tool_names):
    """Every tool has a description."""
    tools = asyncio.run(mcp.list_tools())
    tool_map = {t.name: t for t in tools}
    for name in tool_names:
        tool = tool_map.get(name)
        assert tool is not None, f"Tool {name} not found"
        assert tool.description and len(tool.description) > 10, (
            f"Tool {name} has empty/short description"
        )
