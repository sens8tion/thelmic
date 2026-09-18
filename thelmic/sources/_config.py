"""Where thelmic keeps its source state - and where credentials do NOT come from.

Credentials (``FREESOUND_API_KEY``, ``FREESOUND_OAUTH_TOKEN``) live in 1Password and are declared
in ``<repo>/secrets.toml``. Run anything that needs them under opsec, which injects them into the
environment and scrubs them from the output::

    opsec run -- python -m thelmic.sources search freesound "ragga shout"

This module used to read ``KEY=value`` lines out of ``<repo>/.thelmic/.env`` and
``~/.thelmic/.env``: credentials in plaintext, against how secrets work on this machine. It no
longer reads them, and warns if either file is still there, so a stale copy gets noticed and
removed rather than silently shadowing the vault.
"""

from __future__ import annotations

import warnings
from pathlib import Path

_PLAINTEXT = (".thelmic", ".env")


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists():
            return parent
    return p.parent


def config_dir() -> Path:
    return _repo_root() / ".thelmic"


def _warn_plaintext() -> None:
    for base in (_repo_root(), Path.home()):
        path = base.joinpath(*_PLAINTEXT)
        if path.is_file():
            warnings.warn(
                f"{path} is no longer read: thelmic's credentials come from opsec "
                "(secrets.toml; run with `opsec run -- ...`). Once `opsec check` shows them "
                "present, delete that file.",
                stacklevel=3,
            )


_warn_plaintext()
