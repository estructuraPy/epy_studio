"""Shared fixtures.

The active language is process-global: a test that switches it leaves it
switched for every test after, and the failure lands on whichever test
happens to run next and assert an English string. Measured -- the
selector's Spanish test took down a backend test three files away.
"""

from __future__ import annotations

import pytest

from epy_studio._core import _i18n


@pytest.fixture(autouse=True)
def _english_by_default():
    """Run every test in English and restore it afterwards."""
    previous = _i18n.current_language()
    _i18n.set_language("en")
    yield
    _i18n.set_language(previous)
