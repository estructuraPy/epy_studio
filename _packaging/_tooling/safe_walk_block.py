"""The ONE tree walk the suite's audits use, and the only place it is edited.

WHY IT EXISTS
-------------
``Path.rglob`` and ``Path.glob`` cannot survive an entry they are not allowed to
enumerate. On 2026-09-06 ``epy_concrete/housekeeper.py --strict`` could not
report a single finding, because ``epy_concrete/rubrics`` is a Windows directory
junction whose target no longer exists: ``sorted(lib_root.rglob("*"))`` raised
``FileNotFoundError [WinError 3]`` before the loop body ran once, and the
audit's own ``try/except OSError`` around ``path.read_text(...)`` never saw it,
because the traversal dies while the generator is being exhausted, not while a
file is being read.

The same housekeeper walks the same tree without trouble a few functions
earlier, using ``os.walk``: its generator wraps each directory's ``scandir`` in
its own error handling and simply skips what it cannot enumerate, unless an
``onerror`` callback asks otherwise. That difference is the whole bug. A gate
that dies on a broken link reports nothing about the 1,200 files it could have
read, which is strictly worse than reporting the link.

WHAT IT GUARANTEES
------------------
* Every readable file under ``root`` matching the pattern is yielded, in sorted
  order, exactly as ``rglob`` yielded them.
* An entry that cannot be enumerated (a dangling junction or symlink, a
  permission-denied directory, a path that vanished mid-walk) is SKIPPED and
  RECORDED, never raised and never silently forgotten: ``walk_problems`` returns
  what was skipped so an audit can say so instead of pretending the tree was
  whole.

WHAT IT IS NOT
--------------
Not a filter: it does not know about ``_archive`` or ``__pycache__``. Each audit
keeps its own skip list, because each one skips different things for different
reasons.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

__all__ = ["safe_rglob", "walk_problems"]

#: Entries the last walk could not enumerate, as ``{path: reason}``. Module
#: state on purpose: every audit in a housekeeper run shares one walk report,
#: and the run prints it once rather than each audit inventing its own.
_PROBLEMS: dict[str, str] = {}


def walk_problems() -> dict[str, str]:
    """Paths the walks could not enumerate since the last reset, with the reason.

    Returns a copy, so a caller printing the report cannot mutate it.
    """
    return dict(_PROBLEMS)


def _reset_problems() -> None:
    """Forget the recorded problems (used by the tests; a run accumulates)."""
    _PROBLEMS.clear()


def safe_rglob(root: Path, pattern: str = "*") -> list[Path]:
    """Every path under ``root`` matching ``pattern``, sorted, skipping the unwalkable.

    Drop-in for ``sorted(root.rglob(pattern))`` with one difference that is the
    entire point: an entry that raises ``OSError`` while being enumerated is
    skipped and recorded in :func:`walk_problems` instead of aborting the walk.

    ``pattern`` is matched against the entry NAME with :mod:`fnmatch`, which is
    what the callers use it for (``"*"``, ``"*.md"``, ``"V_*.md"``). A pattern
    with a path separator is refused rather than silently matching nothing:
    ``rglob("a/b.md")`` and this function would disagree, and a walk that
    quietly returns an empty list is how an audit reports a clean tree it never
    read.

    Args:
        root: Directory to walk. A ``root`` that is not a directory yields ``[]``
            and is recorded, for the same reason.
        pattern: ``fnmatch`` pattern for the entry name.

    Returns:
        list[Path]: Matching paths, sorted, as absolute or as given.

    """
    if "/" in pattern or "\\" in pattern:
        raise ValueError(
            f"safe_rglob matches a NAME pattern with fnmatch, got {pattern!r}, which "
            "contains a path separator. Walk with '*' and filter the parts yourself; a "
            "pattern this function cannot honour must not return an empty list."
        )
    root = Path(root)
    if not root.is_dir():
        _PROBLEMS[str(root)] = "not a directory"
        return []

    found: list[Path] = []

    def _onerror(exc: OSError) -> None:
        """Record what could not be enumerated instead of stopping the walk."""
        _PROBLEMS[str(getattr(exc, "filename", "") or root)] = (
            f"{type(exc).__name__}: {exc.strerror or exc}"
        )

    for dirpath, dirnames, filenames in os.walk(root, onerror=_onerror, followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames):
            entry = base / name
            # A junction whose target is gone answers lexists() but not exists();
            # os.walk descends into it and only then fails, so it is pruned here
            # and recorded once with the reason a reader can act on.
            if not entry.exists():
                _PROBLEMS[str(entry)] = "dangling link or junction (target does not exist)"
                dirnames.remove(name)
                continue
            if fnmatch.fnmatch(name, pattern):
                found.append(entry)
        for name in filenames:
            if fnmatch.fnmatch(name, pattern):
                found.append(base / name)
    return sorted(found)
