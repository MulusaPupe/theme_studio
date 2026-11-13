"""Block markup, written the way the block editor writes it.

The editor re-serialises every block when it opens a page and compares the result with what
is stored, so comment attributes and wrapper markup must match its own output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def encode_attrs(attrs: dict[str, Any]) -> str:
    """JSON for a block comment, with the same escapes as the editor's own serialiser."""
    text = json.dumps(attrs, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("--", "\\u002d\\u002d").replace("<", "\\u003c").replace(">", "\\u003e")
        .replace("&", "\\u0026").replace('\\"', "\\u0022")
    )


def comment_name(name: str) -> str:
    return name[len("core/"):] if name.startswith("core/") else name


@dataclass
class Block:
    """``before`` and ``after`` are the block's own markup, around ``inner`` blocks."""

    name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    before: str = ""
    inner: list["Block"] = field(default_factory=list)
    after: str = ""
    separator: str = "\n"

    @property
    def self_closing(self) -> bool:
        return not (self.before or self.after or self.inner)

    def serialize(self) -> str:
        label = comment_name(self.name)
        attrs = f" {encode_attrs(self.attrs)}" if self.attrs else ""
        if self.self_closing:
            return f"<!-- wp:{label}{attrs} /-->"
        body = self.separator.join(block.serialize() for block in self.inner)
        return f"<!-- wp:{label}{attrs} -->\n{self.before}{body}{self.after}\n<!-- /wp:{label} -->"


def serialize_all(blocks: list[Block]) -> str:
    return "\n\n".join(block.serialize() for block in blocks)


def classes(*names: str) -> str:
    return " ".join(name for name in names if name)
