"""Render a Claude Code session JSONL into readable markdown.

Strips system reminders, collapses tool calls/results, keeps the user-Claude
conversation flow + tool activity summary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _flatten_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("type")
                if t == "text":
                    out.append(block.get("text", ""))
                elif t == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input") or {}
                    desc = inp.get("description") or inp.get("command") or inp.get("file_path") or ""
                    out.append(f"\n> 🛠 **{name}** — {desc}")
                elif t == "tool_result":
                    raw = block.get("content")
                    text = _flatten_text(raw) if not isinstance(raw, str) else raw
                    snippet = (text or "").strip().splitlines()
                    if not snippet:
                        continue
                    head = "\n".join(snippet[:8])
                    more = f"\n…(+{len(snippet) - 8} lines)" if len(snippet) > 8 else ""
                    out.append(f"\n```\n{head}{more}\n```")
                elif t == "thinking":
                    pass  # skip
        return "\n".join(out)
    return str(content)


def render(jsonl_path: Path, out_path: Path) -> None:
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    out.append(f"# Session log\n\nSource: `{jsonl_path.name}`\n")
    last_role = None
    for raw in lines:
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
        text = _flatten_text(msg.get("content"))
        if not text or not text.strip():
            continue
        # Drop system reminder content
        cleaned = []
        skip_block = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("<system-reminder>"):
                skip_block = True
                continue
            if "</system-reminder>" in stripped:
                skip_block = False
                continue
            if skip_block:
                continue
            cleaned.append(line)
        text = "\n".join(cleaned).strip()
        if not text:
            continue
        if role != last_role:
            out.append(f"\n## {role.upper()}\n")
            last_role = role
        out.append(text)
        out.append("")
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "session_2026-05-01_lom-channel.jsonl"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".md")
    render(src, dst)
