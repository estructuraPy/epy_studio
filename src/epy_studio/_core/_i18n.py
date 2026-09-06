"""Lightweight in-app internationalization (English / Spanish).

The same shape the four applications already use: English is the source
language AND the lookup key, so a string with no translation renders as
itself rather than as a missing-key marker. Spanish is neutral and
professional -- no regional voseo.

Kept here rather than imported from a sibling on purpose. The selector
launches the applications as separate processes and never imports them;
reaching into one of them for a translation table would make Studio
depend on an application it is meant to merely start, and a partial
install -- exactly what this window is built to survive -- would then
take the launcher down with it.
"""

from __future__ import annotations

__all__ = ["LANGUAGES", "current_language", "set_language", "tr"]

LANGUAGES: dict[str, str] = {"en": "English", "es": "Español"}

_lang = "en"

# English -> Spanish. Neutral / professional Spanish.
_ES: dict[str, str] = {
    "ePy Studio": "ePy Studio",
    "Choose the editor for your document:":
        "Elija el editor para su documento:",
    "Open <b>{names}</b> with:": "Abrir <b>{names}</b> con:",
    "Open": "Abrir",
    "User manual": "Manual de usuario",
    "Language": "Idioma",
    "Not installed — re-run the installer to add it.":
        "No instalado — vuelva a ejecutar el instalador para agregarlo.",
    "(not installed)": "(no instalado)",
    "ePy Studio is not set up to open your documents. Add it to "
    "the list of applications that handle Markdown files?\n\n"
    "This only adds it to “Open with”. Windows still asks you to "
    "confirm a default in Settings.":
        "ePy Studio no está configurado para abrir sus documentos. "
        "¿Desea agregarlo a la lista de aplicaciones que manejan "
        "archivos Markdown?\n\nEsto solo lo agrega a «Abrir con». "
        "Windows le pedirá confirmar el valor predeterminado en "
        "Configuración.",
    "Export backends: built-in": "Motores de exportación: integrados",
    # --- what each application is for ---------------------------------
    #
    # One sentence per application, and they answer the SAME questions in
    # the same order: what kind of document, what the editor gives you,
    # and what comes out. Before this they did not: ePy Reports claimed
    # "live preview" while ePy Slides and ePy Papers said nothing about
    # it -- and all three have it (measured: 15, 16 and 9 files reaching
    # the preview widget). A reader comparing the three would have
    # concluded the other two lacked it.
    #
    # ePy Draft is the one that genuinely differs: it has no live
    # preview because it is a batch tool, and saying so is the point of
    # having a sentence at all.
    "Technical reports — live preview, exports to PDF, Word and HTML":
        "Informes técnicos — vista previa en vivo, exporta a PDF, Word y HTML",
    "Presentation decks — live preview, exports to PDF, PowerPoint and HTML":
        "Presentaciones — vista previa en vivo, exporta a PDF, "
        "PowerPoint y HTML",
    "Academic manuscripts — live preview, journal profiles, exports to "
    "PDF and Word":
        "Manuscritos académicos — vista previa en vivo, perfiles de revista, "
        "exporta a PDF y Word",
    "Batch drafting over your reference library — no preview, renders "
    "through the other three":
        "Redacción por lotes sobre su biblioteca de referencias — sin vista "
        "previa, renderiza con los otros tres",
    "Service offers — fee quotation for structural-engineering work":
        "Ofertas de servicios — cotización de honorarios para trabajos "
        "de ingeniería estructural",
    # --- the export backend strip -------------------------------------
    "ePy Docs not installed — commercial add-on":
        "ePy Docs no instalado — complemento comercial",
    "ePy Docs {version} (Quarto found)":
        "ePy Docs {version} (Quarto encontrado)",
    "ePy Docs {version} found, but Quarto is not installed — PDF export "
    "through it will fail":
        "ePy Docs {version} encontrado, pero Quarto no está instalado — la "
        "exportación a PDF por ese medio va a fallar",
}


def tr(text: str) -> str:
    """Return ``text`` in the current language.

    Args:
        text: The English source string, which is also the key.

    Returns:
        Its translation, or the text itself. English is the identity,
        and an untranslated string renders as written rather than as a
        marker -- a missing entry is a small blemish, a marker in the
        interface is a bug report from a user.
    """
    if _lang == "en":
        return text
    return _ES.get(text, text)


def set_language(lang: str) -> None:
    """Switch the active language.

    Args:
        lang: A code from :data:`LANGUAGES`. Anything else is ignored,
            because a typo in a stored setting must not leave the
            interface in a language that does not exist.
    """
    global _lang
    if lang in LANGUAGES:
        _lang = lang


def current_language() -> str:
    """Return the active language code."""
    return _lang
