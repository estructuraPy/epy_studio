"""The shared tree walk survives what ``Path.rglob`` cannot.

Mirrors safe_walk_block.py.

The bug this measures is real and dated: on 2026-09-06 the whole
``epy_concrete/housekeeper.py --strict`` run reported nothing at all, because
``epy_concrete/rubrics`` is a directory junction whose target was gone and
``sorted(lib_root.rglob("*"))`` raised before the loop body ran once. Every
test here builds a broken link for real rather than mocking one, because the
failure is the operating system's, not Python's.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_BLOCK = Path(__file__).resolve().parent / "safe_walk_block.py"
_spec = importlib.util.spec_from_file_location("_safe_walk_block_under_test", _BLOCK)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
safe_rglob, walk_problems = _mod.safe_rglob, _mod.walk_problems


@pytest.fixture(autouse=True)
def _clean_problem_log():
    _mod._reset_problems()
    yield
    _mod._reset_problems()


def _tree(root: Path) -> Path:
    (root / "docs").mkdir()
    (root / "docs" / "manual.md").write_text("m", encoding="utf-8")
    (root / "docs" / "V_WIND.md").write_text("v", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "mod.py").write_text("x", encoding="utf-8")
    (root / "top.md").write_text("t", encoding="utf-8")
    return root


def _break_link(root: Path, name: str = "rubrics") -> Path:
    """A directory link whose target does not exist, as the junction was.

    On Windows a JUNCTION is used, not a symlink: creating a symlink needs
    Developer Mode or an elevated shell, so a symlink-based fixture SKIPS on an
    ordinary machine, and a test that skips measures nothing. A junction is
    also the real case -- ``epy_concrete/rubrics`` is one.
    """
    link = root / name
    target = root / "gone"
    target.mkdir()
    if os.name == "nt":
        rc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True)
        if rc.returncode != 0:  # pragma: no cover - environment without mklink
            pytest.skip(f"mklink unavailable: {rc.stderr.strip()}")
    else:
        link.symlink_to(target, target_is_directory=True)
    target.rmdir()
    return link


class TestItWalksTheSameTree:
    def test_every_file_rglob_would_find(self, tmp_path):
        _tree(tmp_path)
        assert safe_rglob(tmp_path) == sorted(tmp_path.rglob("*"))

    def test_a_name_pattern_filters_like_rglob(self, tmp_path):
        _tree(tmp_path)
        assert safe_rglob(tmp_path, "*.md") == sorted(tmp_path.rglob("*.md"))
        assert [p.name for p in safe_rglob(tmp_path, "V_*.md")] == ["V_WIND.md"]

    def test_it_returns_directories_too(self, tmp_path):
        _tree(tmp_path)
        names = {p.name for p in safe_rglob(tmp_path)}
        assert {"docs", "src", "manual.md", "mod.py"} <= names

    def test_an_empty_tree_is_an_empty_list(self, tmp_path):
        assert safe_rglob(tmp_path) == []


class TestItSurvivesWhatRglobCannot:
    def test_rglob_itself_still_dies_on_the_broken_link(self, tmp_path):
        """The measurement can fail: this pins the behaviour being worked around."""
        _tree(tmp_path)
        _break_link(tmp_path)
        if os.name != "nt":
            pytest.skip("only Windows raises here; POSIX rglob yields the dangling link")
        with pytest.raises(OSError):
            sorted(tmp_path.rglob("*"))

    def test_the_safe_walk_returns_the_whole_tree_anyway(self, tmp_path):
        _tree(tmp_path)
        _break_link(tmp_path)
        names = {p.name for p in safe_rglob(tmp_path)}
        assert {"manual.md", "V_WIND.md", "mod.py", "top.md"} <= names

    def test_the_skipped_entry_is_recorded_not_forgotten(self, tmp_path):
        _tree(tmp_path)
        link = _break_link(tmp_path)
        safe_rglob(tmp_path)
        problems = walk_problems()
        assert str(link) in problems
        assert "dangling" in problems[str(link)]

    def test_the_broken_link_is_not_reported_as_a_file(self, tmp_path):
        _tree(tmp_path)
        link = _break_link(tmp_path)
        assert link not in safe_rglob(tmp_path)

    def test_the_report_is_a_copy(self, tmp_path):
        _tree(tmp_path)
        _break_link(tmp_path)
        safe_rglob(tmp_path)
        walk_problems().clear()
        assert walk_problems(), "clearing the returned dict must not clear the log"


class TestItRefusesRatherThanReturningNothing:
    @pytest.mark.parametrize("pattern", ["docs/*.md", "a\\b.md", "**/V_*.md"])
    def test_a_path_pattern_is_refused_by_name(self, tmp_path, pattern):
        """rglob('**/V_*.md') and an fnmatch of the same string disagree; a walk
        that silently returns [] is how an audit reports a tree it never read."""
        with pytest.raises(ValueError, match="path separator"):
            safe_rglob(tmp_path, pattern)

    def test_a_root_that_is_not_a_directory_is_recorded(self, tmp_path):
        f = tmp_path / "top.md"
        f.write_text("t", encoding="utf-8")
        assert safe_rglob(f) == []
        assert walk_problems()[str(f)] == "not a directory"

    def test_a_root_that_does_not_exist_is_recorded(self, tmp_path):
        missing = tmp_path / "nope"
        assert safe_rglob(missing) == []
        assert str(missing) in walk_problems()


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows construct")
class TestTheRealJunctionCase:
    def test_a_junction_is_not_a_symlink_to_os_path(self, tmp_path):
        """``epy_concrete/rubrics`` is a junction: ``lexists`` is True,
        ``exists`` is False and ``islink`` is False, which is why an
        ``islink()`` guard would have walked straight into it."""
        link = _break_link(tmp_path)
        assert os.path.lexists(link) and not os.path.exists(link)
        assert not os.path.islink(link), "a junction is not a symlink to os.path"
