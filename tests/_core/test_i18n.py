"""Every user-facing string reaches Spanish, and the four sentences match.

Two properties, and both were reported by somebody reading the window
rather than the code:

* ePy Reports claimed "live preview" while ePy Slides and ePy Papers
  said nothing about it -- and all three have it. A reader comparing the
  three concluded the other two lacked it.
* Nothing in the selector was translated, while the four applications it
  launches all are.
"""

from __future__ import annotations

from epy_studio._core import _catalog, _i18n


def test_english_is_the_identity() -> None:
    _i18n.set_language("en")
    assert _i18n.tr("Open") == "Open"
    assert _i18n.tr("a string nobody translated") == (
        "a string nobody translated"
    )


def test_every_description_has_spanish() -> None:
    # The catalog holds English keys; a missing entry renders as English
    # inside an otherwise Spanish window, which looks like a bug and is
    # invisible to anyone testing in English.
    missing = [
        app.app_id
        for app in _catalog.apps()
        if app.description not in _i18n._ES
    ]
    assert missing == [], f"no Spanish for: {missing}"


def test_the_descriptions_answer_the_same_questions() -> None:
    # Each says what kind of document, then what the editor gives you,
    # then what comes out -- separated by an em dash. Three of the four
    # editors have a live preview and now all three say so; ePy Draft is
    # the one that genuinely differs and says THAT.
    for app in _catalog.apps():
        assert "—" in app.description, f"{app.app_id}: no clause separator"
        if app.optional:
            # The quotation tool is not an editor a reader compares on
            # preview; its description says what it is FOR, and the
            # thread that builds it owns the wording.
            continue
        assert "preview" in app.description.lower(), (
            f"{app.app_id}: says nothing about preview, which is the "
            f"difference a reader is comparing"
        )


def test_the_three_editors_claim_the_preview_they_have() -> None:
    by_id = {app.app_id: app.description for app in _catalog.apps()}
    for app_id in ("epy_reports", "epy_slides", "epy_papers"):
        assert "live preview" in by_id[app_id]
    # The control: asserting "preview" everywhere would pass with Draft
    # claiming one it does not have.
    assert "no preview" in by_id["epy_draft"]


def test_spanish_is_neutral() -> None:
    # The user's Spanish is neutral and professional. Voseo forms slipped
    # into the first draft of this table and are what this catches.
    voseo = ("Elegí ", "volvé ", "tenés", "podés", "hacé ", " tu ", " vos ")
    offenders = [
        text
        for text in _i18n._ES.values()
        if any(form in text for form in voseo)
    ]
    assert offenders == [], f"regional forms: {offenders}"


def test_switching_language_changes_what_a_reader_sees() -> None:
    _i18n.set_language("es")
    try:
        assert _i18n.tr("Open") == "Abrir"
        assert _i18n.tr("User manual") == "Manual de usuario"
    finally:
        _i18n.set_language("en")


def test_an_unknown_language_is_ignored() -> None:
    # A typo in a stored setting must not leave the interface in a
    # language that does not exist.
    _i18n.set_language("es")
    _i18n.set_language("klingon")
    assert _i18n.current_language() == "es"
    _i18n.set_language("en")
