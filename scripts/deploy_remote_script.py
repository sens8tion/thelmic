"""Deploy the ThelmicLive remote script into every Ableton install found.

Ableton updates replace the Resources tree, which takes third-party remote
scripts with it, and a major version bump lands in a new directory entirely.
Re-running this after an update puts the script back wherever Live now lives.

    python scripts/deploy_remote_script.py            # deploy
    python scripts/deploy_remote_script.py --check    # report only
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parent.parent / "thelmic" / "live_remote_script"
SEARCH_ROOTS = [
    Path(r"C:\ProgramData\Ableton"),
    Path.home() / "Documents" / "Ableton" / "User Library" / "Remote Scripts",
]
PACKAGE = "ThelmicLive"
FILES = ("__init__.py", "_upstream.py")


def find_targets() -> list[Path]:
    """Every 'MIDI Remote Scripts' directory belonging to an Ableton install."""
    out = []
    root = SEARCH_ROOTS[0]
    if root.is_dir():
        for install in sorted(root.iterdir()):
            d = install / "Resources" / "MIDI Remote Scripts"
            if d.is_dir():
                out.append(d)
    user = SEARCH_ROOTS[1]
    if user.is_dir():
        out.append(user)
    return out


def main() -> int:
    check_only = "--check" in sys.argv
    targets = find_targets()
    if not targets:
        print("no Ableton install found - is Live installed?")
        return 1

    missing_src = [f for f in FILES if not (REPO_SRC / f).is_file()]
    if missing_src:
        print(f"missing in repo: {missing_src}")
        return 1

    rc = 0
    for base in targets:
        dest = base / PACKAGE
        installed = dest.is_dir()
        same = installed and all(
            (dest / f).is_file() and filecmp.cmp(REPO_SRC / f, dest / f, shallow=False)
            for f in FILES
        )
        state = "up to date" if same else ("DRIFTED" if installed else "ABSENT")
        print(f"{base}\n    {PACKAGE}: {state}")

        if check_only:
            if not same:
                rc = 1
            continue
        if same:
            continue

        dest.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            shutil.copy2(REPO_SRC / f, dest / f)
        # bytecode from the previous version would shadow the new source
        pyc = dest / "__pycache__"
        if pyc.is_dir():
            shutil.rmtree(pyc)
        print(f"    deployed {len(FILES)} files, cleared __pycache__")

    if not check_only:
        print("\nRestart Live for the remote script to reload.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
