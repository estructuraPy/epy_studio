"""Canonical i18n-coverage test, synced into every application repo.

The applications translate their interface through a ``_ES`` dictionary
keyed by the ENGLISH string, and ``tr()`` returns its argument unchanged
when the key is missing. That fallback is the problem this guards: a
string nobody translated looks exactly like a string that needs no
translation, and the only way to find one is for a Spanish-speaking
reader to open the menu it hides in. Fifty-two of them were found that
way on 2026-09-04, in three applications that had shipped for months.

ONE rule, because the applications reach the reader two ways and both
end at the same dictionary: a widget held on the window is built with
its ENGLISH text and retranslated by ``_capture_i18n``, while a status
message or a dialog built fresh calls ``tr()`` itself. Wrapping a
captured widget would store Spanish as its key and break the next
language change. So what the gate demands is not a ``tr()`` at the call
site -- it is that **every user-visible literal is a key in ``_ES``**,
however it gets there. An f-string can never be a key, so one in a
visible position fails on sight; the family's idiom is
``tr("...{x}").format(x=...)``, where the key carries the field.

Not covered, and said out loud rather than left to be discovered:
literals held in a module constant and passed by name, strings built
inside ``_core``, and text that lives in ``.epyson`` data.

SYNCED from _packaging/_tooling/i18n_coverage_block.py -- edit it THERE
and re-copy. A local edit here is overwritten by the next sync.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
PACKAGE = next(
    p for p in SRC.iterdir() if p.is_dir() and p.name.startswith("epy_")
)

#: Call name -> the argument positions a reader actually sees.
VISIBLE: dict[str, tuple[int, ...]] = {
    "QAction": (0,),
    "QLabel": (0,),
    "QPushButton": (0,),
    "QCheckBox": (0,),
    "QGroupBox": (0,),
    "addMenu": (0,),
    "setText": (0,),
    "setTitle": (0,),
    "setToolTip": (0,),
    "setStatusTip": (0,),
    "setPlaceholderText": (0,),
    "setWindowTitle": (0,),
    "setLabelText": (0,),
    "showMessage": (0,),
    "addTab": (1,),
    "setTabText": (1,),
    "critical": (1, 2),
    "warning": (1, 2),
    "information": (1, 2),
    "question": (1, 2),
}

#: Literal -> why it is not translated. Reviewed with the gate itself.
ALLOWED: dict[str, str] = {
    "<b>Ing. Angel Navarro-Mora M.Sc.</b>": "a person's name",
    '<a href="mailto:ahnavarro@anmingenieria.com">'
    "ahnavarro@anmingenieria.com</a>": "an address",
    '<a href="https://www.linkedin.com/in/ahnavarro">'
    "linkedin.com/in/ahnavarro</a>": "a link",
    '<a href="https://www.anmingenieria.com/">ANM Ingeniería</a>'
    " / estructuraPy © 2026, Costa Rica": "a company name and a notice",
    "def f(x): return x": "a code sample, rendered as code",
    "PDF": "a format name, the same in both languages",
    "HTML": "a format name, the same in both languages",
    "DOCX": "a format name, the same in both languages",
    "LaTeX": "a format name, the same in both languages",
    "PowerPoint": "a product name",
    "ePy Studio": "a product name",
    "<b>epy_reports</b> &nbsp; v": "a product name and a version",
    "<b>epy_slides</b> &nbsp; v": "a product name and a version",
    "<b>epy_papers</b> &nbsp; v": "a product name and a version",
}

_FSTRING = "an f-string in a visible position; use tr('...{x}')"

_FILE_FILTER = re.compile(
    r"^[^()]+ \(\*\.[A-Za-z0-9]+( \*\.[A-Za-z0-9]+)*\)$"
)


def _is_prose(text: str) -> bool:
    """Whether a literal is text a reader reads, rather than a token."""
    if text in ALLOWED or not text.strip():
        return False
    if not re.search(r"[A-Za-z]{3,}", text):
        return False
    if _FILE_FILTER.match(text):
        return False
    if text.startswith(("epy_", "http://", "https://", ".", "/")):
        return False
    return " " in text or text[0].isupper()


def _ui_files() -> list[Path]:
    files = [PACKAGE / "app.py", PACKAGE / "launcher.py"]
    files += sorted((PACKAGE / "_ui").glob("*.py"))
    return [f for f in files if f.is_file()]


def _i18n_source() -> str:
    for candidate in (
        PACKAGE / "_core" / "_i18n" / "__init__.py",
        PACKAGE / "_core" / "_i18n.py",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise AssertionError(f"no _i18n module under {PACKAGE}")


def _es_keys() -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(ast.parse(_i18n_source())):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
    return keys


def _called(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def _translated_literals(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _called(node) == "tr"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


def _bare_visible(tree: ast.AST) -> list[tuple[int, str]]:
    bare: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        positions = VISIBLE.get(_called(node))
        if positions is None:
            continue
        for index in positions:
            if index >= len(node.args):
                continue
            arg = node.args[index]
            if isinstance(arg, ast.JoinedStr):
                # Only the LITERAL parts decide. `f"{app} - {title}"`
                # composes two already-translated pieces and carries no
                # sentence of its own; `f"Not a file: {path}"` does, and
                # that sentence can never be a key.
                literal = "".join(
                    part.value
                    for part in arg.values
                    if isinstance(part, ast.Constant)
                    and isinstance(part.value, str)
                )
                if _is_prose(literal):
                    bare.append((arg.lineno, _FSTRING))
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _is_prose(arg.value):
                    bare.append((arg.lineno, arg.value))
    return bare


def test_every_visible_literal_has_a_spanish_entry() -> None:
    # The one rule. A literal that is not a key reads English whatever
    # language the reader chose, and nothing reports it -- tr() returns
    # its argument unchanged, so the code looks finished either way.
    keys = _es_keys()
    offenders: list[str] = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for line, text in _bare_visible(tree):
            if text not in keys:
                offenders.append(f"{path.name}:{line}  {text!r}")
    assert not offenders, "visible text with no Spanish entry: " + "; ".join(
        offenders
    )


def test_every_translated_literal_has_a_spanish_entry() -> None:
    # The other direction: a tr() whose literal is not a key is the same
    # bug wearing a disguise, and it is the one a reviewer cannot see,
    # because the call site looks exactly right.
    keys = _es_keys()
    missing: list[str] = []
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for literal in sorted(_translated_literals(tree)):
            if literal not in keys:
                missing.append(f"{path.name}: {literal!r}")
    assert not missing, "tr() with no _ES entry: " + "; ".join(missing)


def test_the_scan_reaches_the_calls_it_is_meant_to_guard() -> None:
    # The control. A walker that found nothing -- a wrong root, a changed
    # call shape -- would pass both tests above over any amount of
    # untranslated text.
    seen = 0
    for path in _ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        seen += len(_translated_literals(tree))
    assert seen >= 10, f"only {seen} translated literal(s) seen"


def test_the_prose_filter_can_tell_text_from_a_token() -> None:
    # The second control: the filter is what decides whether anything is
    # checked at all, so it is asserted directly.
    assert _is_prose("Browse themes…")
    assert _is_prose("Export DOCX failed")
    assert not _is_prose("")
    assert not _is_prose("…")
    assert not _is_prose("epy_reports")
    assert not _is_prose("Markdown (*.md *.markdown)")
    assert not _is_prose("PDF")
