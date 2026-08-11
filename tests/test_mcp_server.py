from __future__ import annotations

import asyncio

from scimath_mcp.server import mcp


def test_mcp_catalog_is_compact_and_annotated() -> None:
    async def check() -> None:
        tools = await mcp.list_tools()
        names = {tool.name for tool in tools}
        assert names == {
            "calculate",
            "calculus",
            "convert_units",
            "linear_algebra",
            "physical_constant",
            "propagate_uncertainty",
            "solve",
            "statistics",
        }
        for tool in tools:
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.destructive_hint is False
            assert tool.output_schema is not None

    asyncio.run(check())


def test_mcp_direct_tool_call_has_structured_output() -> None:
    async def check() -> None:
        response = await mcp.call_tool(
            "calculate",
            {
                "expression": "sqrt(2)",
                "precision": 40,
                "angle_unit": "radians",
            },
        )
        assert response.is_error is False
        assert response.structured_content is not None
        assert response.structured_content["exact"] == "sqrt(2)"
        assert response.structured_content["approximate"].startswith("1.41421356237")

    asyncio.run(check())


def test_server_instructions_force_tool_use_policy() -> None:
    assert mcp.instructions is not None
    assert "Do not perform arithmetic mentally" in mcp.instructions
    assert len(mcp.instructions) < 1_000
