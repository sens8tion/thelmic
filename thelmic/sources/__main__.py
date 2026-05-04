"""CLI: python -m thelmic.sources <query> [--limit N] [--source NAME] [--fetch]"""

from __future__ import annotations

import argparse
import sys

from . import find, fetch, list_sources


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser("thelmic.sources")
    p.add_argument("query", nargs="?")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--source", action="append", help="restrict to source(s)")
    p.add_argument("--fetch", action="store_true", help="download all hits")
    p.add_argument("--list-sources", action="store_true")
    args = p.parse_args(argv)

    if args.list_sources or not args.query:
        for name in list_sources():
            print(name)
        return 0

    hits = find(args.query, limit=args.limit, sources=args.source)
    for h in hits:
        print(f"[{h.source:<16}] {h.id:<24} {h.title[:60]:<60} {h.license or ''}")
        if args.fetch:
            try:
                path = fetch(h)
                print(f"    -> {path}")
            except Exception as e:
                print(f"    !! {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
