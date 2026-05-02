"""Render a Claude Code session JSONL into a clean dialogue-only markdown.

Strips: tool calls, tool results, thinking blocks, system reminders.
Keeps: user prose, assistant prose. The conversation, nothing else.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SYSREM_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def _text_only(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(block.get("text", ""))
        return "\n".join(out)
    return ""


def _clean(text: str) -> str:
    # Drop full <system-reminder>...</system-reminder> blocks (single or multi-line)
    text = SYSREM_RE.sub("", text)
    # Drop user-prompt-submit-hook fragments that some shells inject
    text = re.sub(r"<user-prompt-submit-hook>.*?</user-prompt-submit-hook>", "", text, flags=re.DOTALL)
    # Drop tool result tags if any leaked through
    text = re.sub(r"<tool_use_error>.*?</tool_use_error>", "", text, flags=re.DOTALL)
    return text.strip()


def render(jsonl_path: Path, out_path: Path) -> None:
    out: list[str] = []
    out.append("# Conversation\n")
    last_role = None
    for raw in jsonl_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        msg = rec.get("message")
        if not msg:
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _clean(_text_only(msg.get("content")))
        if not text:
            continue
        if role != last_role:
            out.append(f"\n## {role.capitalize()}\n")
            last_role = role
        out.append(text)
        out.append("")
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "session_2026-05-01_lom-channel.jsonl"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + "_dialogue.md")
    render(src, dst)
