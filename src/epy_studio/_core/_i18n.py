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
    "Columns": "Columnas",
    "Theme": "Tema",
    "looking for ePy Docs…": "buscando ePy Docs…",
    "Offer ePy Docs as a renderer":
        "Ofrecer ePy Docs como motor de composicion",
    "Adds ePy Docs to the export choices of the applications "
    "launched from here. Each one keeps its own renderer as the "
    "default.":
        "Agrega ePy Docs a las opciones de exportacion de las "
        "aplicaciones que se abren desde aqui. Cada una conserva "
        "su propio motor como predeterminado.",
    "Not installed — re-run the installer to add it.":
        "No instalado — vuelva a ejecutar el instalador para agregarlo.",
    "(not installed)": "(no instalado)",
    "Install...": "Instalar...",
    "Locate...": "Ubicar...",
    "Locate {app}": "Ubicar {app}",
    "Get it from its own project:": "Obténgalo de su propio proyecto:",
    "Point Studio at an executable already on disk.":
        "Indique a Studio un ejecutable que ya esté en disco.",
    "No download page is declared for this application.":
        "No hay página de descarga declarada para esta aplicación.",
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
    # --- the ePy Blender launcher --------------------------------------
    "ePy Blender": "ePy Blender",
    "Open Blender with the ePy Suite addon loaded.":
        "Abrir Blender con el addon de ePy Suite cargado.",
    "Not available: install epy_blender, or set "
    "EPY_BLENDER_LAUNCH to the launcher command.":
        "No disponible: instale epy_blender o defina EPY_BLENDER_LAUNCH "
        "con el comando del lanzador.",
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
    "Sales outreach — contact registry, client research and "
    "service-presentation letters":
        "Prospección comercial — registro de contactos, investigación del "
        "cliente y cartas de presentación de servicios",
    "Virtual structures laboratory — parametric experiments, exports "
    "interactive pages, animations and .kepy cases":
        "Laboratorio virtual de estructuras — experimentos paramétricos, "
        "exporta páginas interactivas, animaciones y casos .kepy",
    # --- adopted applications (ArtCraft Crafting Apps) ----------------
    #
    # Same one-sentence shape as the family's own apps: what the tool
    # is, the formats at its edges, and -- because these are foreign
    # programs the bundle offers rather than ones this repository
    # builds -- the upstream project that actually made it. The ePy
    # name is the display; the ArtCraft name in the sentence is the
    # attribution the MIT/Apache-2.0 licence asks for.
    "2D drafting and CAD — reads and writes DXF (R12–2018) and DWG; "
    "the drafting engine is ArtCraft's CADCraft (MIT/Apache-2.0)":
        "Dibujo 2D y CAD — lee y escribe DXF (R12–2018) y DWG; el motor "
        "de dibujo es CADCraft de ArtCraft (MIT/Apache-2.0)",
    "Raster image editor — layers, selections, PSD/PSB; the engine is "
    "ArtCraft's PhotoCraft (MIT/Apache-2.0)":
        "Editor de imágenes de mapa de bits — capas, selecciones, "
        "PSD/PSB; el motor es PhotoCraft de ArtCraft (MIT/Apache-2.0)",
    "RAW photo catalog and develop — DNG/CR2/ARW/NEF and more; the "
    "engine is ArtCraft's LightCraft (MIT/Apache-2.0)":
        "Catálogo y revelado de fotos RAW — DNG/CR2/ARW/NEF y más; el "
        "motor es LightCraft de ArtCraft (MIT/Apache-2.0)",
    "Video editor — H.264/HEVC/ProRes/AV1, MP4/MOV/WebM; the engine is "
    "ArtCraft's FilmCraft (MIT/Apache-2.0)":
        "Editor de video — H.264/HEVC/ProRes/AV1, MP4/MOV/WebM; el motor "
        "es FilmCraft de ArtCraft (MIT/Apache-2.0)",
    "Vector graphics — SVG/PDF/EPS export and DXF read; the engine is "
    "ArtCraft's VectorCraft (MIT/Apache-2.0)":
        "Gráficos vectoriales — exporta SVG/PDF/EPS y lee DXF; el motor "
        "es VectorCraft de ArtCraft (MIT/Apache-2.0)",
    "PDF authoring and batch — combine, split, extract, edit; the "
    "engine is ArtCraft's PDFCraft (MIT/Apache-2.0)":
        "Autoría y lote de PDF — combinar, dividir, extraer, editar; el "
        "motor es PDFCraft de ArtCraft (MIT/Apache-2.0)",
    "Presentations — opens and saves .pptx, exports PDF; the engine is "
    "ArtCraft's DeckCraft (MIT/Apache-2.0)":
        "Presentaciones — abre y guarda .pptx, exporta PDF; el motor es "
        "DeckCraft de ArtCraft (MIT/Apache-2.0)",
    "Spreadsheets — native .xlsx, formulas, CSV/TSV; the engine is "
    "ArtCraft's GridCraft (MIT/Apache-2.0)":
        "Hojas de cálculo — .xlsx nativo, fórmulas, CSV/TSV; el motor es "
        "GridCraft de ArtCraft (MIT/Apache-2.0)",
    "Audio production — WAV/FLAC/AIFF, mixing and bounce; the engine is "
    "ArtCraft's SoundCraft (MIT/Apache-2.0)":
        "Producción de audio — WAV/FLAC/AIFF, mezcla y bounce; el motor "
        "es SoundCraft de ArtCraft (MIT/Apache-2.0)",
    "Word processor — .docx/.odt/.rtf/.md, exports PDF; the engine is "
    "ArtCraft's WordCraft (MIT/Apache-2.0)":
        "Procesador de texto — .docx/.odt/.rtf/.md, exporta PDF; el "
        "motor es WordCraft de ArtCraft (MIT/Apache-2.0)",
    "Page layout and composition — IDML import/export; the engine is "
    "ArtCraft's DesignCraft (MIT/Apache-2.0)":
        "Maquetación y composición de páginas — importa/exporta IDML; "
        "el motor es DesignCraft de ArtCraft (MIT/Apache-2.0)",
    "Motion graphics and VFX — Lottie, H.264/ProRes; the engine is "
    "ArtCraft's EffectCraft (MIT/Apache-2.0)":
        "Gráficos en movimiento y VFX — Lottie, H.264/ProRes; el motor "
        "es EffectCraft de ArtCraft (MIT/Apache-2.0)",
    "Not installed — it ships on its own; install it and this row "
    "becomes available.":
        "No instalado — se distribuye por separado; instálelo y esta fila "
        "queda disponible.",
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
