"""The ``subtitle.*`` MCP tool group, shared with NulEdit.

NulEdit's MCP server re-exports these so "caption this clip" works from the same
agent path. Kept as a data surface at scaffold stage.
"""
from __future__ import annotations

TOOL_SURFACE: dict[str, str] = {
    "subtitle.transcribe": "Extract audio and transcribe a clip to word-level timestamps.",
    "subtitle.generate_karaoke": "Generate styled ASS karaoke from word timings (sweep preset).",
    "subtitle.apply": "Apply ASS to a Kdenlive subtitle track (Path A) or burn it in (Path B).",
}


def main() -> None:
    """Console entry point (``nulcaption-mcp``)."""
    raise SystemExit(
        "nulcaption MCP server is a scaffold (Phase 4). Tool surface in "
        "nulcaption.mcp.tools.TOOL_SURFACE."
    )


if __name__ == "__main__":
    main()
