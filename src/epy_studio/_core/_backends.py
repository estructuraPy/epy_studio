"""Whether ePy Docs is on this machine, and how to say so.

The requirement is that a document can be exported through ePy Docs
**when it is installed**. Inside a frozen bundle that cannot be answered
by importing, and the reason is not the exclusion list:

* PyInstaller's onedir closes ``sys.path`` to the bundle, so a package
  installed in the user's own Python is invisible to the frozen
  applications no matter what the spec says. Measured: the installed
  ``_internal/`` carries epy_reports and epy_slides and no epy_docs, so
  every "export via ePy Docs" entry in every shipped application has
  been permanently disabled.
* Bundling it instead would not fix that. ePy Docs shells out to the
  ``quarto`` executable and to a TeX distribution, and neither is a
  Python module PyInstaller can collect -- the menu would enable itself
  and the export would die in a worker thread.
* And it must not be bundled anyway: it is a commercial package while
  this installer is a free per-user download under MIT.

So the question is about the MACHINE, not about ``sys.path``, and the
answer is a subprocess. Studio finds an interpreter that has ePy Docs,
asks it, and hands the answer to the applications it launches through
the environment -- a hint they are free to ignore, never a dependency.

Three states, three different things for a person to do, and today the
middle one is invisible until a render dies in a worker thread:

    not found          install it (commercial add-on)
    found, no Quarto   install Quarto; PDF export through it will fail
    found and complete nothing to do

**Validated by a real import in a subprocess, never by find_spec.** Any
bare directory named ``epy_docs`` on the path satisfies find_spec as a
namespace package and imports to an empty module -- the caller then
reaches for ``DocumentWriter`` and gets an AttributeError instead of the
honest "not installed".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from epy_export import ENV_DOCS_PYTHON

from . import _i18n

__all__ = ["Backend", "detect_docs", "handoff_env"]

ENV_PYTHON = ENV_DOCS_PYTHON
"""Where an interpreter carrying ePy Docs was found, for the children.

Imported rather than spelled again. Studio publishes this variable
and the applications read it through ``epy_export``, and neither
package depends on the other -- so a rename spelled twice would
leave one side listening for a name the other stopped setting, and
the only symptom would be a menu entry quietly greying out.
"""

ENV_VERSION = "EPY_DOCS_VERSION"
"""Its version, so a child need not pay for a second subprocess."""

_PROBE = (
    "import epy_docs, shutil, sys;"
    "print(getattr(epy_docs, '__version__', '?'));"
    "print(bool(getattr(epy_docs, 'DocumentWriter', None)));"
    "print(shutil.which('quarto') or '')"
)


@dataclass(frozen=True)
class Backend:
    """What was found, and what a person should do about it.

    Attributes:
        python: The interpreter that carries it, when one was found.
        version: Its reported version.
        quarto: Path to the ``quarto`` executable it can reach.
    """

    python: Path | None = None
    version: str = ""
    quarto: str = ""

    def describe(self) -> str:
        """Return the status line for this backend, translated.

        Built when it is READ rather than when the backend is detected:
        a sentence baked in English at detection time cannot follow a
        language the user changes afterwards.

        Returns:
            One line naming the state and, where it matters, what to do
            about it.
        """
        if self.python is None:
            return _i18n.tr("ePy Docs not installed — commercial add-on")
        if self.quarto:
            return _i18n.tr("ePy Docs {version} (Quarto found)").format(
                version=self.version
            )
        return _i18n.tr(
            "ePy Docs {version} found, but Quarto is not installed — "
            "PDF export through it will fail"
        ).format(version=self.version)

    @property
    def present(self) -> bool:
        """Whether an interpreter carrying a usable ePy Docs was found."""
        return self.python is not None

    @property
    def complete(self) -> bool:
        """Whether it can actually produce a PDF.

        Separate from :attr:`present` on purpose: ePy Docs without
        Quarto imports fine and fails at render time, which is the state
        nobody can see today.
        """
        return self.present and bool(self.quarto)


def _candidates() -> list[Path]:
    """Return interpreters worth asking, best first."""
    found: list[Path] = []
    named = os.environ.get(ENV_PYTHON, "")
    if named:
        found.append(Path(named))
    # The convention every sibling follows for a per-user install.
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        found.append(Path(local) / "Programs" / "epy_docs" / "python.exe")
    # Whatever is on PATH, and this interpreter itself when not frozen.
    for name in ("python", "py"):
        which = shutil.which(name)
        if which:
            found.append(Path(which))
    if not getattr(sys, "frozen", False):
        found.append(Path(sys.executable))
    seen: set[str] = set()
    unique: list[Path] = []
    for item in found:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def detect_docs(*, timeout: float = 20.0) -> Backend:
    """Find an interpreter that can actually run ePy Docs.

    Args:
        timeout: How long to give each candidate. A wrong interpreter
            that hangs must not hang the selector.

    Returns:
        What was found. An absent backend is a normal answer, not an
        error: the applications work without it.
    """
    for python in _candidates():
        if not python.is_file():
            continue
        try:
            result = subprocess.run(
                [str(python), "-c", _PROBE],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        lines = result.stdout.splitlines()
        if len(lines) < 3 or lines[1].strip() != "True":
            # It imported but has no DocumentWriter -- the namespace
            # package case. Not a backend.
            continue
        version, quarto = lines[0].strip(), lines[2].strip()
        return Backend(python=python, version=version, quarto=quarto)
    return Backend()


def handoff_env(backend: Backend, *, offer: bool = True) -> dict[str, str]:
    """Return the environment additions for a launched application.

    A HINT, never a dependency. An application launched from the Start
    menu, from Explorer or from a checkout sees none of this and behaves
    identically minus the shortcut -- which is what keeps Studio out of
    its dependency graph.

    Args:
        backend: What :func:`detect_docs` found.
        offer: Whether the user wants ePy Docs offered at all. Off, the
            applications behave exactly as they do when it is not
            installed: the hint is what makes the entry reachable, so
            withholding it withdraws the offer without pretending the
            machine lacks the package.

    Returns:
        Variables to add, empty when nothing was found or nothing is
        offered.
    """
    if backend.python is None or not offer:
        return {}
    return {
        ENV_PYTHON: str(backend.python),
        ENV_VERSION: backend.version,
    }
