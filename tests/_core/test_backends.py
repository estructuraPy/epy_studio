"""Finding ePy Docs on the machine, and handing it over as a hint."""

from __future__ import annotations

import subprocess
from pathlib import Path

from epy_studio._core import _backends


def test_nothing_found_is_a_normal_answer() -> None:
    absent = _backends.Backend()
    assert not absent.present
    assert not absent.complete
    assert "not installed" in absent.describe()


def test_found_without_quarto_is_its_own_state() -> None:
    # The state nobody can see today: ePy Docs imports fine and the
    # render dies later in a worker thread. Present and complete are
    # separate questions because they need separate actions.
    half = _backends.Backend(
        python=Path("py.exe"), version="1.4.2", quarto=""
    )
    assert "Quarto" in half.describe()
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


def test_the_handoff_is_withheld_when_the_reader_declines_it() -> None:
    # The choice the owner asked for: offer it, or do not. Withheld, the
    # applications behave exactly as they do on a machine without the
    # package -- because the hint is what makes the entry reachable at
    # all inside a frozen bundle.
    found = _backends.Backend(python=Path("C:/py/python.exe"), version="1.4")
    assert _backends.handoff_env(found, offer=False) == {}
    assert _backends.handoff_env(found, offer=True) != {}
    # And declining does not conjure a backend that is not there.
    assert _backends.handoff_env(_backends.Backend(), offer=True) == {}


def test_the_variable_name_has_one_home() -> None:
    # Studio publishes it, the applications read it through epy_export,
    # and neither package depends on the other. Spelled twice, a rename
    # would leave one side listening for a name the other stopped
    # setting, and the only symptom would be a menu entry going grey.
    #
    # Checked against the SOURCE, not by comparing the two values:
    # Python interns a short string literal, so the same name spelled
    # twice is the same object and an identity check cannot tell the
    # two apart. Measured -- that version of this test passed with the
    # literal restored.
    import inspect

    import epy_export

    assert _backends.ENV_PYTHON == epy_export.ENV_DOCS_PYTHON
    source = inspect.getsource(_backends)
    assert '"EPY_DOCS_PYTHON"' not in source
    assert "ENV_DOCS_PYTHON" in source


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
    assert "1.4.2" in found.describe()


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
