"""Finding ePy Docs on the machine, and handing it over as a hint."""

from __future__ import annotations

import subprocess
from pathlib import Path

from epy_studio._core import _backends


def test_nothing_found_is_a_normal_answer() -> None:
    absent = _backends.Backend()
    assert not absent.present
    assert not absent.complete
    assert "not installed" in absent.detail


def test_found_without_quarto_is_its_own_state() -> None:
    # The state nobody can see today: ePy Docs imports fine and the
    # render dies later in a worker thread. Present and complete are
    # separate questions because they need separate actions.
    half = _backends.Backend(
        python=Path("py.exe"), version="1.4.2", quarto="",
        detail="ePy Docs 1.4.2 found, but Quarto is not installed",
    )
    assert half.present
    assert not half.complete


def test_the_handoff_is_empty_when_nothing_was_found() -> None:
    # Absent must always be valid. An application launched from the
    # Start menu, from Explorer or from a checkout sees no hint and has
    # to behave identically -- that is what keeps Studio out of its
    # dependency graph.
    assert _backends.handoff_env(_backends.Backend()) == {}


def test_the_handoff_names_the_interpreter_and_the_version() -> None:
    found = _backends.Backend(python=Path("C:/py/python.exe"), version="1.4")
    handed = _backends.handoff_env(found)
    assert handed[_backends.ENV_PYTHON] == "C:\\py\\python.exe".replace(
        "\\", "/"
    ) or handed[_backends.ENV_PYTHON].endswith("python.exe")
    assert handed[_backends.ENV_VERSION] == "1.4"


def test_an_interpreter_without_documentwriter_is_not_a_backend(
    monkeypatch, tmp_path
) -> None:
    # The namespace-package case, stated as a test because find_spec
    # cannot tell it apart: any bare directory named epy_docs on the
    # path imports to an empty module, and the caller then reaches for
    # DocumentWriter and gets an AttributeError instead of the honest
    # "not installed". The probe asks for the attribute, so an empty
    # module answers False and is skipped.
    fake = tmp_path / "python.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(_backends, "_candidates", lambda: [fake])

    def _answer(*_a, **_k):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1.4.2\nFalse\n\n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _answer)
    assert not _backends.detect_docs().present


def test_a_complete_interpreter_is_reported_with_quarto(
    monkeypatch, tmp_path
) -> None:
    # The control. Without it, rejecting everything satisfies the test
    # above and the detection never finds anything.
    fake = tmp_path / "python.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(_backends, "_candidates", lambda: [fake])

    def _answer(*_a, **_k):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="1.4.2\nTrue\nC:/quarto/quarto.exe\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _answer)
    found = _backends.detect_docs()
    assert found.present and found.complete
    assert found.version == "1.4.2"
    assert "1.4.2" in found.detail


def test_a_hanging_interpreter_does_not_hang_the_selector(
    monkeypatch, tmp_path
) -> None:
    fake = tmp_path / "python.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(_backends, "_candidates", lambda: [fake])

    def _hang(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    monkeypatch.setattr(subprocess, "run", _hang)
    assert not _backends.detect_docs().present
