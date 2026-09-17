"""Shared fixtures.

The active language is process-global: a test that switches it leaves it
switched for every test after, and the failure lands on whichever test
happens to run next and assert an English string. Measured -- the
selector's Spanish test took down a backend test three files away.
"""

from __future__ import annotations

import pytest

# Before any test module imports Qt. In a conda environment PySide6 does
# not load until the system ICU is pinned ahead of it, and the failure is
# a DLL error that `importorskip` turns into a silent skip -- a whole file
# of assertions that never ran. Studio is a launcher and never needs the
# pin at run time (the frozen bundle carries no conda ICU), so it lives
# here rather than in the package.
try:
    from epy_export import pin_system_icu

    pin_system_icu()
except ImportError:  # pragma: no cover - epy_export is optional here
    pass

from epy_studio._core import _i18n  # noqa: E402 - must follow the ICU pin


@pytest.fixture(autouse=True)
def _english_by_default():
    """Run every test in English and restore it afterwards."""
    previous = _i18n.current_language()
    _i18n.set_language("en")
    yield
    _i18n.set_language(previous)


@pytest.fixture(autouse=True, scope="session")
def _never_open_a_browser():
    """No test may open a browser tab, whatever it passes for display.

    Plotly's ``fig.show()`` outside a notebook does not draw anything locally:
    it starts an ephemeral HTTP server on 127.0.0.1, points the default
    browser at it, and blocks until that one request arrives. A test run that
    opens tabs is a test run nobody can leave unattended.

    Installed in EVERY repo rather than only where a scan found display calls.
    Going by scan is what let the tabs come back twice: a regex missed six
    repos because it could not cross a line end, and the AST scan that
    replaced it still only sees a display keyword passed as a literal ``True``
    -- one passed positionally, through a variable or from a parametrize list
    is invisible to both. The fixture is inert where nothing displays, so
    predicting which repos need it buys nothing and costs a recurrence.

    The branch under test still executes and still counts as covered; it just
    cannot reach a browser. This is the half the housekeeper's Rule 14 audits
    cannot see -- they read library ``src/``, and this lives in ``tests/``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        yield
        return

    original = go.Figure.show
    go.Figure.show = lambda self, *args, **kwargs: None
    try:
        yield
    finally:
        go.Figure.show = original
