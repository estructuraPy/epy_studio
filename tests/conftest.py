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
