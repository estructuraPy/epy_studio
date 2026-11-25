"""``python -m epy_studio``: the module runs the launcher's main().

Nothing imported this module before -- it carried 0% coverage. A plain
import only reaches the `if __name__ == "__main__":` line itself (the
condition is False for an import), never its body, so the module is run
under its own name via ``runpy`` to reach the line that actually exits.
"""

from __future__ import annotations

import runpy

import pytest

from epy_studio import launcher


def test_running_the_module_calls_main_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher, "main", lambda: 3)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("epy_studio.__main__", run_name="__main__")
    assert excinfo.value.code == 3
