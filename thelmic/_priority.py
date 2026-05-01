"""Lower the current process's priority so Live's UI thread stays responsive.

Called from LiveChannel.start() when enabled. Best-effort: failures log a
warning and proceed. Idempotent.
"""

from __future__ import annotations

import logging
import os
import sys

LOG = logging.getLogger("thelmic._priority")

_applied = False


def lower_process_priority() -> bool:
    """Drop priority of the current process to BELOW_NORMAL (Win) or nice +10 (Unix).

    Returns True if a priority change was applied (or already applied), False if
    the platform path failed silently. Never raises — caller can ignore result.
    """
    global _applied
    if _applied:
        return True

    if sys.platform.startswith("win"):
        ok = _lower_windows()
    else:
        ok = _lower_unix()
    _applied = ok
    return ok


def _lower_windows() -> bool:
    # Try psutil first (cleanest API), fall back to ctypes SetPriorityClass.
    try:
        import psutil  # type: ignore

        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        LOG.info("Lowered process priority to BELOW_NORMAL via psutil.")
        return True
    except Exception as e:
        LOG.debug("psutil priority drop failed: %s — trying ctypes", e)

    try:
        import ctypes

        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        rc = ctypes.windll.kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
        if rc:
            LOG.info("Lowered process priority to BELOW_NORMAL via ctypes.")
            return True
        LOG.warning("SetPriorityClass returned 0; priority unchanged.")
        return False
    except Exception as e:
        LOG.warning("ctypes priority drop failed: %s", e)
        return False


def _lower_unix() -> bool:
    try:
        os.nice(10)
        LOG.info("Lowered process nice by +10.")
        return True
    except Exception as e:
        LOG.warning("os.nice failed: %s", e)
        return False
