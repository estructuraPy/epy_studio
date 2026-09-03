r"""Read a module's string constants out of a PyInstaller executable.

Why this exists: a fix that is in git is not a fix the user has. The
window's PDF export was repaired at 14:00 and the installed bundle still
raised `TypeError` at 19:00, because nobody had rebuilt it. Driving the
installed window to prove the fix shipped failed twice on this machine
(Qt exposes no menu bar to UI Automation; `SendKeys` never reached the
app), so the check that finally worked read the shipped BYTES instead:
open the PYZ archive PyInstaller appends to the executable, pull one
module's code object out of it, and look for a literal that only exists
because of the fix.

That check lived in a scratch folder the owner deleted the same day. It
belongs here, in the repository whose build it guards, as a gate that
runs on every build rather than a ritual someone has to remember.

The archive layout, for the reader who has to touch this:

* A CArchive cookie ``MEI\\x0c\\x0b\\x0a\\x0b\\x0e`` sits near the end of the
  exe, followed by ``!8sIIii64s``: magic, package length, TOC offset, TOC
  length, Python version, and the Python DLL name.
* The TOC is a sequence of entries ``!i`` (entry length) then ``!iiiBc``
  (offset, compressed length, uncompressed length, flag, type code), then
  the name padded with NUL.
* The entry typed ``z`` is the PYZ: ``b"PYZ\\0"``, a version, a ``!i``
  offset to a marshalled table, and zlib-compressed marshalled code
  objects. PyInstaller 6 marshals the table as a LIST of
  ``(name, (is_package, offset, length))``; older versions used a dict.

None of this is public API. It is pinned by the tests beside it, and if
PyInstaller changes the layout the failure is loud: no cookie, no PYZ
entry, or a module not in the table -- never a silent pass.
"""

from __future__ import annotations

import marshal
import struct
import zlib
from pathlib import Path
from types import CodeType

_COOKIE = b"MEI\x0c\x0b\x0a\x0b\x0e"
_COOKIE_FMT = "!8sIIii64s"
_TOC_ENTRY_FMT = "!iiiBc"


class BundleProbeError(RuntimeError):
    """The executable is not a PyInstaller bundle this probe can read."""


TocEntry = tuple[str, int, int, int, int, bytes]


def _toc(data: bytes) -> tuple[list[TocEntry], int]:
    """Return the CArchive table of contents and the archive's start offset.

    Args:
        data: The whole executable.

    Returns:
        The entries as ``(name, offset, compressed, uncompressed, flag,
        type)`` and the byte offset the entry offsets are relative to.

    Raises:
        BundleProbeError: When the cookie is absent -- not a bundle.
    """
    pos = data.rfind(_COOKIE)
    if pos < 0:
        raise BundleProbeError("no PyInstaller cookie: not a bundle")
    cookie_len = struct.calcsize(_COOKIE_FMT)
    _magic, pkg_len, toc_off, toc_len, _pyver, _pylib = struct.unpack(
        _COOKIE_FMT, data[pos : pos + cookie_len]
    )
    start = pos + cookie_len - pkg_len
    raw = data[start + toc_off : start + toc_off + toc_len]

    entries: list[tuple[str, int, int, int, int, bytes]] = []
    at = 0
    head = struct.calcsize(_TOC_ENTRY_FMT)
    while at < len(raw):
        (size,) = struct.unpack("!i", raw[at : at + 4])
        fields = struct.unpack(_TOC_ENTRY_FMT, raw[at + 4 : at + 4 + head])
        name = raw[at + 4 + head : at + size].rstrip(bytes([0]))
        entries.append((name.decode("utf-8"), *fields))
        at += size
    return entries, start


def _pyz_blob(data: bytes) -> bytes:
    """Return the PYZ archive bytes from a bundle's TOC.

    Raises:
        BundleProbeError: When the TOC carries no PYZ entry.
    """
    entries, start = _toc(data)
    for name, off, comp_len, _raw_len, _flag, typ in entries:
        if typ == b"z" or name.upper().startswith("PYZ"):
            return data[start + off : start + off + comp_len]
    raise BundleProbeError("no PYZ entry in the archive TOC")


def module_code(exe: Path, dotted: str) -> CodeType:
    """Return the code object of one module inside a bundled executable.

    Args:
        exe: The PyInstaller executable.
        dotted: The module's dotted name, e.g. ``epy_reports._ui.tab``.

    Returns:
        The module's code object, as the bundle would execute it.

    Raises:
        BundleProbeError: When the exe is not a bundle, has no PYZ, or the
            module is not in it -- each named, none silent.
    """
    pyz = _pyz_blob(exe.read_bytes())
    if pyz[:4] != b"PYZ\0":
        raise BundleProbeError(f"unexpected PYZ magic {pyz[:4]!r}")
    (toc_pos,) = struct.unpack("!i", pyz[8:12])
    table = marshal.loads(pyz[toc_pos:])
    if isinstance(table, list):
        # PyInstaller 6 marshals a list of pairs; older versions a dict.
        table = dict(table)
    if dotted not in table:
        near = sorted(
            str(k) for k in table if str(k).startswith(dotted.split(".")[0])
        )[:6]
        raise BundleProbeError(
            f"{dotted} is not in the PYZ of {exe.name}; nearby: {near}"
        )
    _is_pkg, off, length = table[dotted]
    return marshal.loads(zlib.decompress(pyz[off : off + length]))


def strings_of(code: CodeType) -> set[str]:
    """Return every string reachable from a code object.

    Descends into nested code objects AND into tuple constants. Keyword
    argument names are not plain string constants in 3.10 bytecode -- a
    call packs them into a tuple -- so a walker that yields only ``str``
    reports ``creator``/``producer`` as absent from a module that passes
    them. The first version of this probe did exactly that and declared
    the fix missing from a bundle that carried it.
    """
    found: set[str] = set()
    seen: set[int] = set()

    def walk(obj: CodeType) -> None:
        if id(obj) in seen:
            return
        seen.add(id(obj))
        for const in obj.co_consts:
            if isinstance(const, str):
                found.add(const)
            elif isinstance(const, tuple):
                found.update(item for item in const if isinstance(item, str))
            elif isinstance(const, CodeType):
                walk(const)
        found.update(obj.co_names)

    walk(code)
    return found


def carries(exe: Path, dotted: str, literal: str) -> bool:
    """Report whether the bundled module contains ``literal`` anywhere.

    Args:
        exe: The PyInstaller executable.
        dotted: The module to open inside it.
        literal: The substring that only exists because of a given fix.

    Returns:
        ``True`` when some string reachable from the module contains it.
    """
    return any(literal in s for s in strings_of(module_code(exe, dotted)))
